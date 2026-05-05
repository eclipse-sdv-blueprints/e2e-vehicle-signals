#!/usr/bin/env python3
# /********************************************************************************
# * Copyright (c) 2026 Contributors to the Eclipse Foundation
# *
# * See the NOTICE file(s) distributed with this work for additional
# * information regarding copyright ownership.
# *
# * This program and the accompanying materials are made available under the
# * terms of the Apache License 2.0 which is available at
# * https://www.apache.org/licenses/LICENSE-2.0
# *
# * SPDX-License-Identifier: Apache-2.0
# ********************************************************************************/
"""Lightweight status API + static host for the Raspberry Pi 5 demo website."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "site-config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "probe_timeout_seconds": 1.2,
    "status_cache_seconds": 5.0,
    "log_window_seconds": 45,
    "mqtt": {"host": "127.0.0.1", "port": 1883},
    "kuksa": {"host": "127.0.0.1", "port": 55555},
    "assume_traffic_when_logs_unavailable": True,
    "require_container_presence_for_active": False,
    "ankaios_assume_active_when_signal_workloads_up": True,
    "forced_inactive_connections": [],
    "ankaios_dashboard_url": "http://127.0.0.1:8084",
    "dozzle_url": "http://127.0.0.1:8080",
    "can_observer": {
        "enabled": True,
        "interface": "can0",
        "sample_timeout_seconds": 0.8,
        "min_poll_interval_seconds": 10.0,
    },
    "fleet": {
        "grafana_url": "http://127.0.0.1:3000",
        "fms_server_url": "http://127.0.0.1:8081",
    },
    "kuksa_observer": {
        "enabled": True,
        "paths": [
            "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling",
            "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling",
            "Vehicle.Body.Lights.Brake.IsActive",
            "Vehicle.Driver.Identifier.Subject",
        ],
        "command_paths": [
            "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling",
            "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling",
            "Vehicle.Body.Lights.Brake.IsActive",
            "Vehicle.Driver.Identifier.Subject",
        ],
        "feedback_paths": [
            "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling",
            "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling",
            "Vehicle.Body.Lights.Brake.IsActive",
        ],
        "token": "",
        "token_file": "",
        "tls": False,
        "root_ca": "",
        "tls_server_name": "",
    },
    "containers": {
        "mqtt_broker": ["mosquitto", "mqtt"],
        "mqtt_bridge": ["grpc-mqtt-bridge", "mqtt-bridge"],
        "kuksa_databroker": ["kuksa-databroker", "databroker"],
        "can_provider": ["kuksa-can-provider", "can-provider"],
        "ankaios": ["ank-server", "ank-agent", "ankaios"],
        "dozzle": ["dozzle"],
        "fms_forwarder": ["fms-forwarder"],
        "grafana": ["grafana"],
    },
}


class StatusError(Exception):
    """Internal helper exception for status probing."""


_KUKSA_OBSERVER_LOCK = threading.Lock()
_KUKSA_LAST_VALUES: dict[str, Any] = {}
_KUKSA_LAST_CHANGE_TS: float | None = None
_CAN_OBSERVER_LOCK = threading.Lock()
_CAN_OBSERVER_CACHE: dict[str, Any] = {}
_STATUS_CACHE_LOCK = threading.Lock()
_STATUS_CACHE_PAYLOAD: dict[str, Any] | None = None
_STATUS_CACHE_TS: float | None = None


def deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            parsed = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                cfg = deep_merge(cfg, parsed)
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def run_command(args: list[str], timeout_seconds: float = 4.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }


def probe_tcp(host: str, port: int, timeout_seconds: float) -> dict[str, Any]:
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout_seconds)
        sock.close()
        return {
            "active": True,
            "detail": f"TCP reachable at {host}:{port}",
        }
    except OSError as exc:
        return {
            "active": False,
            "detail": f"TCP unreachable at {host}:{port} ({exc})",
        }


def probe_http(url: str, timeout_seconds: float) -> dict[str, Any]:
    if not url:
        return {"active": False, "detail": "URL not configured", "status_code": None}

    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            code = getattr(response, "status", 200)
            return {
                "active": 200 <= code < 500,
                "status_code": code,
                "detail": f"HTTP {code}",
            }
    except HTTPError as exc:
        code = getattr(exc, "code", None)
        return {
            "active": code is not None and code < 500,
            "status_code": code,
            "detail": f"HTTP error {code}",
        }
    except URLError as exc:
        return {
            "active": False,
            "status_code": None,
            "detail": f"HTTP unreachable ({exc.reason})",
        }


def value_to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        return text if text else default
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        parts = [value_to_text(part, "").strip() for part in value]
        parts = [part for part in parts if part]
        if parts:
            return ",".join(parts)
        return default
    if isinstance(value, dict):
        try:
            return json.dumps(value, separators=(",", ":"))
        except (TypeError, ValueError):
            return default
    return str(value)


def ensure_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = value_to_text(item, "").strip()
        if text:
            out.append(text)
    return out


def normalize_probe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [normalize_probe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): normalize_probe_value(v) for k, v in value.items()}
    if hasattr(value, "value"):
        return normalize_probe_value(getattr(value, "value"))

    for attr in (
        "bool",
        "boolean",
        "string",
        "int8",
        "int16",
        "int32",
        "int64",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "float",
        "double",
    ):
        if hasattr(value, attr):
            attr_val = getattr(value, attr)
            if attr_val is not None:
                return normalize_probe_value(attr_val)
    return value_to_text(value, "")


def read_kuksa_values_via_client(
    host: str,
    port: int,
    timeout_seconds: float,
    observer_cfg: dict[str, Any],
) -> dict[str, Any]:
    if not bool(observer_cfg.get("enabled", True)):
        return {"available": False, "detail": "kuksa observer disabled", "values": {}}

    paths = ensure_string_list(observer_cfg.get("paths"))
    if not paths:
        return {"available": False, "detail": "no kuksa observer paths configured", "values": {}}

    try:
        from kuksa_client.grpc import VSSClient  # type: ignore[import]
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "detail": f"kuksa-client unavailable ({exc})", "values": {}}

    root_ca = value_to_text(observer_cfg.get("root_ca"), "").strip()
    tls = bool(observer_cfg.get("tls", False))
    tls_server_name = value_to_text(observer_cfg.get("tls_server_name"), "").strip()
    token = value_to_text(observer_cfg.get("token"), "").strip()
    token_file = value_to_text(observer_cfg.get("token_file"), "").strip()
    if not token and token_file:
        try:
            token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError:
            token = ""

    constructor_variants: list[dict[str, Any]] = [
        {
            "host": host,
            "port": port,
            "ensure_startup_connection": False,
            "timeout": timeout_seconds,
        },
        {
            "host": host,
            "port": port,
            "ensure_startup_connection": False,
        },
        {"host": host, "port": port},
        {},
    ]
    if tls and root_ca:
        for variant in constructor_variants[:3]:
            variant["root_certificates"] = Path(root_ca)
            if tls_server_name:
                variant["tls_server_name"] = tls_server_name

    client = None
    last_error = ""
    for kwargs in constructor_variants:
        try:
            if kwargs:
                client = VSSClient(**kwargs)
            else:
                client = VSSClient(host, port)
            break
        except TypeError as exc:
            last_error = str(exc)
            continue
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "detail": f"kuksa observer connect failed ({exc})", "values": {}}

    if client is None:
        return {
            "available": False,
            "detail": f"kuksa observer connect failed ({last_error or 'constructor mismatch'})",
            "values": {},
        }

    try:
        if token and hasattr(client, "authorize"):
            try:
                client.authorize(token=token)
            except TypeError:
                client.authorize(token)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "detail": f"kuksa authorize failed ({exc})", "values": {}}

    raw_values: Any = None
    if hasattr(client, "get_current_values"):
        call_variants = [
            lambda: client.get_current_values(paths),
            lambda: client.get_current_values(tuple(paths)),
            lambda: client.get_current_values(*paths),
        ]
    elif hasattr(client, "get"):
        call_variants = [
            lambda: client.get(paths),
            lambda: client.get(tuple(paths)),
            lambda: client.get(*paths),
        ]
    else:
        call_variants = []

    try:
        for caller in call_variants:
            try:
                raw_values = caller()
                break
            except TypeError:
                continue
        if raw_values is None:
            return {"available": False, "detail": "kuksa observer has no usable get method", "values": {}}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "detail": f"kuksa value read failed ({exc})", "values": {}}
    finally:
        try:
            if hasattr(client, "close"):
                client.close()
        except Exception:  # noqa: BLE001
            pass

    values: dict[str, Any] = {}
    if isinstance(raw_values, dict):
        for path in paths:
            if path in raw_values:
                values[path] = normalize_probe_value(raw_values[path])
    elif isinstance(raw_values, (list, tuple)):
        for item in raw_values:
            if not isinstance(item, dict):
                continue
            name = value_to_text(item.get("name") or item.get("path"), "").strip()
            if not name:
                continue
            if "value" in item:
                values[name] = normalize_probe_value(item.get("value"))
    else:
        return {"available": False, "detail": "kuksa observer returned unsupported payload", "values": {}}

    return {"available": True, "detail": "kuksa-client probe ok", "values": values}


def observe_kuksa_signal_activity(
    host: str,
    port: int,
    timeout_seconds: float,
    window_seconds: int,
    observer_cfg: dict[str, Any],
) -> dict[str, Any]:
    global _KUKSA_LAST_CHANGE_TS

    sample = read_kuksa_values_via_client(host, port, timeout_seconds, observer_cfg)
    if not sample.get("available"):
        return {
            "available": False,
            "detail": sample.get("detail", "unavailable"),
            "changed_paths": [],
            "recent_change": False,
            "values_count": 0,
        }

    values = sample.get("values")
    if not isinstance(values, dict):
        values = {}

    now_ts = datetime.now(timezone.utc).timestamp()
    changed_paths: list[str] = []
    with _KUKSA_OBSERVER_LOCK:
        for path, value in values.items():
            if _KUKSA_LAST_VALUES.get(path) != value:
                changed_paths.append(path)
            _KUKSA_LAST_VALUES[path] = value
        if changed_paths:
            _KUKSA_LAST_CHANGE_TS = now_ts
        recent_change = bool(
            _KUKSA_LAST_CHANGE_TS is not None and (now_ts - _KUKSA_LAST_CHANGE_TS) <= max(window_seconds, 5)
        )

    return {
        "available": True,
        "detail": sample.get("detail", "ok"),
        "changed_paths": changed_paths,
        "recent_change": recent_change,
        "values_count": len(values),
        "values": values,
    }


def sample_socketcan_activity(interface: str, sample_timeout_seconds: float) -> dict[str, Any]:
    candump_path = shutil.which("candump")
    checked_at = utc_now_iso()
    if not candump_path:
        return {
            "available": False,
            "active": False,
            "checked_at": checked_at,
            "interface": interface,
            "detail": "candump not found",
            "sample_window_seconds": sample_timeout_seconds,
            "frames_seen": 0,
        }

    try:
        completed = subprocess.run(
            [candump_path, "-n", "1", interface],
            capture_output=True,
            text=True,
            timeout=sample_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "available": True,
            "active": False,
            "checked_at": checked_at,
            "interface": interface,
            "detail": f"no CAN frames observed on {interface} in {sample_timeout_seconds:.1f}s",
            "sample_window_seconds": sample_timeout_seconds,
            "frames_seen": 0,
        }
    except OSError as exc:
        return {
            "available": False,
            "active": False,
            "checked_at": checked_at,
            "interface": interface,
            "detail": f"candump start failed ({exc})",
            "sample_window_seconds": sample_timeout_seconds,
            "frames_seen": 0,
        }

    combined = f"{completed.stdout}\n{completed.stderr}".strip()
    lines = [line for line in combined.splitlines() if line.strip()]
    if completed.returncode == 0:
        return {
            "available": True,
            "active": bool(lines),
            "checked_at": checked_at,
            "interface": interface,
            "detail": (
                f"observed {len(lines)} CAN frame(s) on {interface}"
                if lines
                else f"candump returned without CAN frames on {interface}"
            ),
            "sample_window_seconds": sample_timeout_seconds,
            "frames_seen": len(lines),
        }

    detail = value_to_text(combined, "") or f"candump exited with {completed.returncode}"
    return {
        "available": False,
        "active": False,
        "checked_at": checked_at,
        "interface": interface,
        "detail": f"candump failed on {interface} ({detail})",
        "sample_window_seconds": sample_timeout_seconds,
        "frames_seen": 0,
    }


def observe_socketcan_activity(observer_cfg: dict[str, Any]) -> dict[str, Any]:
    if not bool(observer_cfg.get("enabled", True)):
        return {
            "available": False,
            "active": False,
            "checked_at": None,
            "interface": value_to_text(observer_cfg.get("interface"), "can0"),
            "detail": "socketcan observer disabled",
            "sample_window_seconds": None,
            "frames_seen": 0,
            "cached": False,
        }

    interface = value_to_text(observer_cfg.get("interface"), "can0")
    try:
        sample_timeout_seconds = max(float(observer_cfg.get("sample_timeout_seconds", 0.8)), 0.1)
    except (TypeError, ValueError):
        sample_timeout_seconds = 0.8
    try:
        min_poll_interval_seconds = max(float(observer_cfg.get("min_poll_interval_seconds", 10.0)), 1.0)
    except (TypeError, ValueError):
        min_poll_interval_seconds = 10.0

    cache_key = f"{interface}|{sample_timeout_seconds:.3f}|{min_poll_interval_seconds:.3f}"
    now_monotonic = time.monotonic()

    with _CAN_OBSERVER_LOCK:
        cached = _CAN_OBSERVER_CACHE.get(cache_key)
        if isinstance(cached, dict):
            checked_at_monotonic = cached.get("checked_at_monotonic")
            sample = cached.get("sample")
            if (
                isinstance(checked_at_monotonic, (int, float))
                and isinstance(sample, dict)
                and (now_monotonic - checked_at_monotonic) < min_poll_interval_seconds
            ):
                cached_sample = dict(sample)
                cached_sample["cached"] = True
                return cached_sample

        sample = sample_socketcan_activity(interface, sample_timeout_seconds)
        sample["cached"] = False
        _CAN_OBSERVER_CACHE.clear()
        _CAN_OBSERVER_CACHE[cache_key] = {
            "checked_at_monotonic": now_monotonic,
            "sample": dict(sample),
        }
        return sample


def list_containers(runtime: str) -> list[dict[str, Any]]:
    if not shutil.which(runtime):
        return []

    result = run_command([runtime, "ps", "--format", "{{json .}}"])
    if not result["ok"]:
        return []

    containers: list[dict[str, Any]] = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue

        name = value_to_text(raw.get("Names") or raw.get("Name"), "unknown")
        image = value_to_text(raw.get("Image"), "unknown")
        container_id = value_to_text(raw.get("ID") or raw.get("Id"), "")
        state = value_to_text(raw.get("State"), "")
        status = value_to_text(raw.get("Status"), state or "unknown")

        containers.append(
            {
                "runtime": runtime,
                "id": container_id,
                "name": name,
                "image": image,
                "state": state or "running",
                "status": status,
            }
        )

    return containers


def find_matches(
    containers: list[dict[str, Any]],
    patterns: list[str],
) -> list[dict[str, Any]]:
    lowered = [p.lower() for p in patterns]
    matches: list[dict[str, Any]] = []
    for item in containers:
        haystack = f"{item['name']} {item['image']}".lower()
        if any(pattern in haystack for pattern in lowered):
            matches.append(item)
    return matches


def collect_recent_logs(
    container: dict[str, Any] | None,
    seconds_window: int,
) -> dict[str, Any]:
    if not container:
        return {"lines": None, "keyword_hits": None, "logs_available": False, "detail": "container not found"}

    runtime = value_to_text(container.get("runtime"), "")
    name = value_to_text(container.get("name"), "")
    if not runtime or not name:
        return {
            "lines": None,
            "keyword_hits": None,
            "logs_available": False,
            "detail": "container runtime/name unavailable",
        }

    result = run_command([runtime, "logs", "--since", f"{seconds_window}s", name], timeout_seconds=5)
    if not result["ok"]:
        return {
            "lines": None,
            "keyword_hits": None,
            "logs_available": False,
            "detail": f"{runtime} logs failed",
        }

    combined = f"{result['stdout']}\n{result['stderr']}".strip()
    if not combined:
        return {"lines": 0, "keyword_hits": 0, "logs_available": True, "detail": "no recent log lines"}

    lines = [entry for entry in combined.splitlines() if entry.strip()]
    keywords = (
        "mqtt",
        "topic",
        "set",
        "val",
        "vehicle.",
        "can",
        "signal",
        "update",
    )
    hits = sum(1 for line in lines if any(word in line.lower() for word in keywords))
    return {
        "lines": len(lines),
        "keyword_hits": hits,
        "logs_available": True,
        "detail": f"{len(lines)} lines in last {seconds_window}s",
    }


def activity_has_traffic(activity: dict[str, Any]) -> bool:
    lines = activity.get("lines")
    hits = activity.get("keyword_hits")
    return bool((isinstance(hits, int) and hits > 0) or (isinstance(lines, int) and lines > 0))


def activity_logs_unavailable(activity: dict[str, Any]) -> bool:
    logs_available = activity.get("logs_available")
    if logs_available is False:
        return True
    lines = activity.get("lines")
    if isinstance(lines, int) and lines == 0:
        return True
    detail = value_to_text(activity.get("detail"), "").lower()
    return "logs failed" in detail or "container not found" in detail or "unavailable" in detail


def try_query_ank_workloads() -> dict[str, Any]:
    if not shutil.which("ank"):
        return {
            "available": False,
            "workload_count": None,
            "detail": "ank CLI not found",
        }

    candidate_commands = [
        ["ank", "-k", "get", "workloads", "-o", "json"],
        ["ank", "-k", "get", "workload", "-o", "json"],
        ["ank", "get", "workloads", "-o", "json"],
        ["ank", "get", "workload", "-o", "json"],
    ]

    for cmd in candidate_commands:
        result = run_command(cmd, timeout_seconds=5)
        if not result["ok"]:
            continue
        payload = result["stdout"].strip()
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, list):
            count = len(parsed)
        elif isinstance(parsed, dict):
            workloads = parsed.get("workloads")
            if isinstance(workloads, list):
                count = len(workloads)
            elif isinstance(workloads, dict):
                count = len(workloads.keys())
            else:
                count = 1
        else:
            count = None

        return {
            "available": True,
            "workload_count": count,
            "detail": "queried via ank CLI",
        }

    return {
        "available": False,
        "workload_count": None,
        "detail": "ank CLI query failed",
    }


def build_status(config: dict[str, Any]) -> dict[str, Any]:
    timeout = float(config.get("probe_timeout_seconds", 1.2))
    window = int(config.get("log_window_seconds", 45))
    assume_traffic_when_logs_unavailable = bool(config.get("assume_traffic_when_logs_unavailable", True))
    require_container_presence_for_active = bool(
        config.get("require_container_presence_for_active", False)
    )
    ankaios_assume_active_when_signal_workloads_up = bool(
        config.get("ankaios_assume_active_when_signal_workloads_up", True)
    )
    observer_cfg = config.get("kuksa_observer", {})
    if not isinstance(observer_cfg, dict):
        observer_cfg = {}
    can_observer_cfg = config.get("can_observer", {})
    if not isinstance(can_observer_cfg, dict):
        can_observer_cfg = {}
    fleet_cfg = config.get("fleet", {})
    if not isinstance(fleet_cfg, dict):
        fleet_cfg = {}

    mqtt = probe_tcp(config["mqtt"]["host"], int(config["mqtt"]["port"]), timeout)
    kuksa = probe_tcp(config["kuksa"]["host"], int(config["kuksa"]["port"]), timeout)
    ank_dashboard = probe_http(config.get("ankaios_dashboard_url", ""), timeout)
    dozzle = probe_http(config.get("dozzle_url", ""), timeout)
    fleet_grafana = probe_http(value_to_text(fleet_cfg.get("grafana_url"), ""), timeout)
    fleet_server = probe_http(value_to_text(fleet_cfg.get("fms_server_url"), ""), timeout)
    kuksa_signal_observer = observe_kuksa_signal_activity(
        config["kuksa"]["host"],
        int(config["kuksa"]["port"]),
        timeout,
        window,
        observer_cfg,
    )
    can_bus_activity = observe_socketcan_activity(can_observer_cfg)

    containers = list_containers("podman") + list_containers("docker")
    container_patterns = config.get("containers", {})
    grouped: dict[str, list[dict[str, Any]]] = {}

    for key, patterns in container_patterns.items():
        if isinstance(patterns, list):
            grouped[key] = find_matches(containers, patterns)
        else:
            grouped[key] = []

    container_inventory_available = len(containers) > 0

    bridge_container = grouped.get("mqtt_bridge", [None])[0] if grouped.get("mqtt_bridge") else None
    databroker_container = (
        grouped.get("kuksa_databroker", [None])[0] if grouped.get("kuksa_databroker") else None
    )

    bridge_logs = collect_recent_logs(bridge_container, window)
    databroker_logs = collect_recent_logs(databroker_container, window)
    ank_cli = try_query_ank_workloads()

    mqtt_container_ok = bool(grouped.get("mqtt_bridge")) and bool(grouped.get("mqtt_broker"))
    can_container_ok = bool(grouped.get("can_provider"))

    if require_container_presence_for_active:
        mqtt_transfer_active = mqtt["active"] and mqtt_container_ok
        databroker_signals_active = kuksa["active"] and can_container_ok
    else:
        # In containerized website deployments runtime inventory may be unavailable.
        # Do not force container-presence gating in that case.
        if container_inventory_available:
            mqtt_transfer_active = mqtt["active"] and mqtt_container_ok
            databroker_signals_active = kuksa["active"] and can_container_ok
        else:
            mqtt_transfer_active = mqtt["active"] and (kuksa["active"] or bool(grouped.get("mqtt_bridge")))
            databroker_signals_active = kuksa["active"]

    fms_container_ok = bool(grouped.get("fms_forwarder")) and bool(grouped.get("grafana"))
    fms_endpoint_ok = bool(fleet_grafana.get("active")) or bool(fleet_server.get("active"))
    if require_container_presence_for_active:
        fms_active = fms_container_ok
    else:
        if container_inventory_available:
            fms_active = fms_container_ok or (fms_endpoint_ok and kuksa["active"])
        else:
            fms_active = fms_endpoint_ok and kuksa["active"]

    ankaios_active = bool(grouped.get("ankaios")) or bool(ank_dashboard["active"]) or bool(ank_cli["available"])
    if (
        not ankaios_active
        and not require_container_presence_for_active
        and ankaios_assume_active_when_signal_workloads_up
        and mqtt_transfer_active
        and databroker_signals_active
    ):
        ankaios_active = True

    dozzle_active = bool(grouped.get("dozzle")) or bool(dozzle["active"])

    bridge_traffic = activity_has_traffic(bridge_logs)
    databroker_traffic = activity_has_traffic(databroker_logs)
    bridge_logs_missing = activity_logs_unavailable(bridge_logs)
    databroker_logs_missing = activity_logs_unavailable(databroker_logs)
    observer_changed_paths = set(ensure_string_list(kuksa_signal_observer.get("changed_paths")))
    observer_available = bool(kuksa_signal_observer.get("available"))
    observer_recent = bool(kuksa_signal_observer.get("recent_change"))
    observer_values_count = kuksa_signal_observer.get("values_count")
    observer_has_values = isinstance(observer_values_count, int) and observer_values_count > 0
    can_bus_traffic = bool(can_bus_activity.get("active"))

    default_observer_paths = ensure_string_list(observer_cfg.get("paths"))
    command_paths = ensure_string_list(observer_cfg.get("command_paths")) or default_observer_paths
    feedback_paths = ensure_string_list(observer_cfg.get("feedback_paths")) or default_observer_paths
    command_paths_set = set(command_paths)
    feedback_paths_set = set(feedback_paths)

    command_traffic_from_observer = observer_available and (
        bool(observer_changed_paths.intersection(command_paths_set)) or observer_recent or observer_has_values
    )
    feedback_traffic_from_observer = observer_available and (
        bool(observer_changed_paths.intersection(feedback_paths_set)) or observer_recent or observer_has_values
    )
    databroker_traffic_from_observer = observer_available and (
        bool(observer_changed_paths) or observer_recent or observer_has_values
    )

    mqtt_transfer_traffic = command_traffic_from_observer or bridge_traffic or (
        assume_traffic_when_logs_unavailable and mqtt_transfer_active and bridge_logs_missing
    )
    databroker_signals_traffic = databroker_traffic_from_observer or databroker_traffic or bridge_traffic or (
        assume_traffic_when_logs_unavailable and databroker_signals_active and databroker_logs_missing
    )
    databroker_signals_traffic = databroker_signals_traffic or can_bus_traffic
    can_feedback_traffic = feedback_traffic_from_observer or databroker_traffic or can_bus_traffic or (
        assume_traffic_when_logs_unavailable and databroker_signals_active and databroker_logs_missing
    )
    forced_inactive_connections = set(ensure_string_list(config.get("forced_inactive_connections")))
    fms_forced_inactive = "fms_pipeline" in forced_inactive_connections
    ankaios_forced_inactive = "ankaios_workloads" in forced_inactive_connections

    if fms_forced_inactive:
        fms_active = False
    if ankaios_forced_inactive:
        ankaios_active = False

    ankaios_detail_parts: list[str] = []
    if ankaios_forced_inactive:
        ankaios_detail_parts.append("forced inactive by config")
    else:
        ankaios_group = grouped.get("ankaios", [])
        if ankaios_group:
            ankaios_detail_parts.append(f"{len(ankaios_group)} Ankaios container(s) detected")
        if bool(ank_dashboard.get("active")):
            ankaios_detail_parts.append(value_to_text(ank_dashboard.get("detail"), "dashboard reachable"))
        if bool(ank_cli.get("available")):
            ankaios_detail_parts.append("workloads queried via ank CLI")
        elif not ankaios_detail_parts:
            ankaios_detail_parts.append(value_to_text(ank_cli.get("detail"), "Ankaios not detected"))

    ankaios_detail = "; ".join(part for part in ankaios_detail_parts if part) or "Ankaios not detected"

    return {
        "timestamp": utc_now_iso(),
        "services": {
            "mqtt": mqtt,
            "kuksa": kuksa,
            "ankaios_dashboard": ank_dashboard,
            "dozzle": dozzle,
            "fleet_grafana": fleet_grafana,
            "fleet_server": fleet_server,
        },
        "dashboards": {
            "ankaios": {
                "url": config.get("ankaios_dashboard_url", ""),
                "reachable": bool(ank_dashboard.get("active")),
            },
            "dozzle": {
                "url": config.get("dozzle_url", ""),
                "reachable": bool(dozzle.get("active")),
            },
        },
        "containers": {
            "running_count": len(containers),
            "running": containers,
            "groups": {
                name: [item["name"] for item in entries]
                for name, entries in grouped.items()
            },
        },
        "activity": {
            "bridge": bridge_logs,
            "databroker": databroker_logs,
            "kuksa_observer": kuksa_signal_observer,
            "can_bus": can_bus_activity,
            "ank_cli": ank_cli,
            "observation_mode": {
                "container_inventory_available": container_inventory_available,
                "require_container_presence_for_active": require_container_presence_for_active,
            },
        },
        "connections": {
            "mqtt_transfer": {
                "active": mqtt_transfer_active,
                "traffic_detected": mqtt_transfer_traffic,
                "detail": "MQTT Broker -> Bridge -> Kuksa path",
            },
            "databroker_signals": {
                "active": databroker_signals_active,
                "traffic_detected": databroker_signals_traffic,
                "detail": (
                    f"Kuksa Databroker <-> CAN Provider; {value_to_text(can_bus_activity.get('detail'), '')}"
                    if value_to_text(can_bus_activity.get("detail"), "")
                    else "Kuksa Databroker <-> CAN Provider"
                ),
            },
            "can_feedback": {
                "active": databroker_signals_active,
                "traffic_detected": can_feedback_traffic,
                "detail": (
                    f"Blinker ECU status feedback to VSS; {value_to_text(can_bus_activity.get('detail'), '')}"
                    if value_to_text(can_bus_activity.get("detail"), "")
                    else "Blinker ECU status feedback to VSS"
                ),
            },
            "fms_pipeline": {
                "active": fms_active,
                "traffic_detected": fms_active,
                "detail": "Kuksa -> FMS Forwarder -> Grafana",
            },
            "ankaios_workloads": {
                "active": ankaios_active,
                "traffic_detected": ankaios_active,
                "detail": ankaios_detail,
            },
            "dozzle_monitoring": {
                "active": dozzle_active,
                "traffic_detected": dozzle_active,
                "detail": "Dozzle container monitor",
            },
        },
    }


def get_status(config: dict[str, Any], force_refresh: bool = False) -> dict[str, Any]:
    global _STATUS_CACHE_PAYLOAD, _STATUS_CACHE_TS

    try:
        cache_seconds = max(float(config.get("status_cache_seconds", 5.0)), 0.0)
    except (TypeError, ValueError):
        cache_seconds = 5.0

    if force_refresh or cache_seconds <= 0:
        payload = build_status(config)
        with _STATUS_CACHE_LOCK:
            _STATUS_CACHE_PAYLOAD = payload
            _STATUS_CACHE_TS = time.monotonic()
        return payload

    now_monotonic = time.monotonic()
    with _STATUS_CACHE_LOCK:
        if (
            _STATUS_CACHE_PAYLOAD is not None
            and isinstance(_STATUS_CACHE_TS, (int, float))
            and (now_monotonic - _STATUS_CACHE_TS) < cache_seconds
        ):
            return _STATUS_CACHE_PAYLOAD

    payload = build_status(config)
    with _STATUS_CACHE_LOCK:
        _STATUS_CACHE_PAYLOAD = payload
        _STATUS_CACHE_TS = now_monotonic
    return payload


class DemoHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[SimpleHTTPRequestHandler]):
        super().__init__(server_address, handler_class)
        self.config = load_config()


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def send_json(self, payload: dict[str, Any], status_code: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/status":
            query = parse_qs(parsed.query)
            force_refresh = value_to_text(query.get("fresh"), "").lower() in {"1", "true", "yes"}
            payload = get_status(self.server.config, force_refresh=force_refresh)  # type: ignore[attr-defined]
            self.send_json(payload)
            return

        if parsed.path == "/api/config":
            payload = self.server.config  # type: ignore[attr-defined]
            self.send_json(payload)
            return

        if parsed.path == "/api/health":
            self.send_json({"ok": True, "timestamp": utc_now_iso()})
            return

        if parsed.path in ("/", ""):
            self.path = "/index.html"

        super().do_GET()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry Pi5 demo website server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8090, help="Bind port (default: 8090)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = DemoHTTPServer((args.host, args.port), DemoHandler)

    print(f"Serving website from: {ROOT}")
    print(f"Open: http://{args.host}:{args.port}")
    print(f"API:  http://{args.host}:{args.port}/api/status")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
