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
"""Kuksa Databroker (gRPC) → LIVI Telemetry bridge.

Subscribes to a configurable set of VSS paths on the Kuksa Databroker and
pushes the values, after optional transformation, into a running LIVI head
unit via its Socket.IO ``telemetry:push`` event (ws://<livi-host>:4000).

The payload shape is defined by LIVI in
https://github.com/f-io/LIVI/blob/main/src/main/shared/types/Telemetry.ts
"""

import argparse
import logging
import threading
import time
from typing import Any, Dict, Optional

import socketio
import yaml
from kuksa_client.grpc import VSSClient

LOG = logging.getLogger("kuksa-livi-bridge")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kuksa gRPC to LIVI telemetry bridge")
    parser.add_argument("--config", required=True, help="Path to grpc-livi.yaml config file")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser.parse_args()


def _read_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


# ---------------------------------------------------------------------------
# Value transforms — VSS value → LIVI telemetry value
# ---------------------------------------------------------------------------

def _coerce_scalar(value: Any, target_type: Optional[str]) -> Any:
    if value is None or target_type is None:
        return value
    target_type = target_type.lower()
    if target_type == "bool":
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on", "active", "adaptive")
        return bool(value)
    if target_type in ("int", "integer"):
        return int(value)
    if target_type in ("float", "number"):
        return float(value)
    if target_type == "string":
        return str(value)
    return value


def _apply_scale_offset(value: Any, scale: Optional[float], offset: Optional[float]) -> Any:
    if value is None or (scale is None and offset is None):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    if scale is not None:
        numeric = numeric * float(scale)
    if offset is not None:
        numeric = numeric + float(offset)
    return numeric


def _apply_enum_map(value: Any, mapping: Optional[Dict[Any, Any]]) -> Any:
    """Map a VSS value to a LIVI enum value (e.g. ``True`` → ``"left"``)."""
    if value is None or not mapping:
        return value
    # YAML keys are strings; also support bool / numeric keys.
    if value in mapping:
        return mapping[value]
    return mapping.get(str(value), value)


def _transform(value: Any, mapping_cfg: Dict[str, Any]) -> Any:
    value = _apply_enum_map(value, mapping_cfg.get("enumMap"))
    value = _apply_scale_offset(value, mapping_cfg.get("scale"), mapping_cfg.get("offset"))
    value = _coerce_scalar(value, mapping_cfg.get("type"))
    return value


# ---------------------------------------------------------------------------
# LIVI Socket.IO client
# ---------------------------------------------------------------------------

class LiviClient:
    """Minimal wrapper around python-socketio for LIVI telemetry pushes."""

    def __init__(self, url: str, reconnect_delay: float = 2.0):
        self._url = url
        self._reconnect_delay = reconnect_delay
        self._sio = socketio.Client(reconnection=True, reconnection_delay=reconnect_delay)
        self._connected = threading.Event()

        @self._sio.event
        def connect() -> None:
            LOG.info("Connected to LIVI at %s", self._url)
            self._connected.set()

        @self._sio.event
        def disconnect() -> None:
            LOG.warning("Disconnected from LIVI")
            self._connected.clear()

    def connect_forever(self) -> None:
        while True:
            try:
                self._sio.connect(self._url, transports=["websocket"])
                return
            except Exception as exc:  # noqa: BLE001
                LOG.warning("LIVI connect failed (%s) — retrying in %.1fs", exc, self._reconnect_delay)
                time.sleep(self._reconnect_delay)

    def push(self, payload: Dict[str, Any]) -> None:
        if not payload:
            return
        if not self._connected.is_set():
            LOG.debug("Skipping push (not connected): %s", payload)
            return
        try:
            self._sio.emit("telemetry:push", payload)
            LOG.debug("Pushed telemetry: %s", payload)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Telemetry push failed: %s", exc)


# ---------------------------------------------------------------------------
# Payload merging — supports nested keys ("gps.lat" → {"gps": {"lat": ...}})
# ---------------------------------------------------------------------------

def _merge_field(payload: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cursor: Dict[str, Any] = payload
    for part in parts[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cursor[part] = existing
        cursor = existing
    cursor[parts[-1]] = value


# ---------------------------------------------------------------------------
# Main bridge loop
# ---------------------------------------------------------------------------

class Bridge:
    def __init__(self, config: Dict[str, Any]):
        kuksa_cfg = config.get("kuksa", {})
        livi_cfg = config.get("livi", {})
        push_cfg = config.get("push", {})

        target = kuksa_cfg.get("target", "localhost:55555")
        host, _, port = target.partition(":")
        self._kuksa_host = host or "localhost"
        self._kuksa_port = int(port or "55555")

        self._livi_url = livi_cfg.get("url", "ws://livi.local:4000")
        self._push_interval = float(push_cfg.get("intervalMs", 250)) / 1000.0
        self._send_initial_snapshot = bool(push_cfg.get("sendInitialSnapshot", True))

        self._mappings: Dict[str, Dict[str, Any]] = {}
        for mapping in config.get("mappings", []):
            vss_path = mapping.get("vssPath")
            livi_field = mapping.get("liviField")
            if not vss_path or not livi_field:
                LOG.warning("Skipping incomplete mapping: %s", mapping)
                continue
            self._mappings[vss_path] = mapping

        self._pending: Dict[str, Any] = {}
        self._pending_lock = threading.Lock()
        self._livi = LiviClient(self._livi_url)

    # -- mapping ---------------------------------------------------------

    def _handle_vss_update(self, vss_path: str, raw_value: Any) -> None:
        mapping_cfg = self._mappings.get(vss_path)
        if mapping_cfg is None:
            return
        livi_field = mapping_cfg["liviField"]
        try:
            transformed = _transform(raw_value, mapping_cfg)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Transform failed for %s=%r: %s", vss_path, raw_value, exc)
            return
        if transformed is None and not mapping_cfg.get("sendNone", False):
            return
        with self._pending_lock:
            _merge_field(self._pending, livi_field, transformed)
        LOG.debug("VSS %s=%r → LIVI %s=%r", vss_path, raw_value, livi_field, transformed)

    # -- push loop --------------------------------------------------------

    def _push_loop(self) -> None:
        while True:
            time.sleep(self._push_interval)
            with self._pending_lock:
                if not self._pending:
                    continue
                payload = self._pending
                self._pending = {}
            payload.setdefault("ts", int(time.time() * 1000))
            self._livi.push(payload)

    # -- run --------------------------------------------------------------

    def run(self) -> None:
        if not self._mappings:
            LOG.error("No mappings configured — nothing to bridge.")
            return

        # Connect to LIVI first (non-fatal if it isn't up yet — keeps retrying).
        threading.Thread(target=self._livi.connect_forever, daemon=True).start()
        threading.Thread(target=self._push_loop, daemon=True).start()

        paths = list(self._mappings.keys())
        LOG.info("Subscribing to %d VSS path(s) on %s:%d", len(paths), self._kuksa_host, self._kuksa_port)

        with VSSClient(self._kuksa_host, self._kuksa_port) as client:
            if self._send_initial_snapshot:
                try:
                    snapshot = client.get_current_values(paths)
                    for path, datapoint in snapshot.items():
                        if datapoint is not None:
                            self._handle_vss_update(path, datapoint.value)
                except Exception as exc:  # noqa: BLE001
                    LOG.warning("Initial snapshot failed: %s", exc)

            for updates in client.subscribe_current_values(paths):
                for path, datapoint in updates.items():
                    if datapoint is None:
                        continue
                    self._handle_vss_update(path, datapoint.value)


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = _read_config(args.config)
    Bridge(config).run()


if __name__ == "__main__":
    main()
