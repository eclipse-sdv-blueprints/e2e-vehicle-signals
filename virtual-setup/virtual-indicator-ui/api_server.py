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
"""Virtual Indicator UI – backend server.

Serves static files (index.html, styles.css, app.js) and provides:

  POST /api/indicator    – validates VSS payload, publishes to Mosquitto MQTT
                           topic InVehicleTopics (same schema the physical
                           joystick ECU produces, so grpc-mqtt-bridge requires
                           no changes).
  GET  /api/sse/signals  – Server-Sent Events stream with live VSS values read
                           from Kuksa Databroker.  Powers the actor LED panel.
  GET  /api/state        – One-shot JSON snapshot of the last known VSS state.

Configuration is read from environment variables (set via docker-compose):
  MQTT_HOST, MQTT_PORT, KUKSA_HOST, KUKSA_PORT, MQTT_TOPIC, HTTP_HOST, HTTP_PORT
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt

LOG = logging.getLogger("virtual-indicator-ui")

# ── Configuration ─────────────────────────────────────────────────────────────
MQTT_HOST     = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT     = int(os.environ.get("MQTT_PORT", "1883"))
KUKSA_HOST    = os.environ.get("KUKSA_HOST", "127.0.0.1")
KUKSA_PORT    = int(os.environ.get("KUKSA_PORT", "55555"))
MQTT_TOPIC    = os.environ.get("MQTT_TOPIC", "InVehicleTopics")
HTTP_HOST     = os.environ.get("HTTP_HOST", "0.0.0.0")
HTTP_PORT     = int(os.environ.get("HTTP_PORT", "8091"))
LOG_LEVEL     = os.environ.get("LOG_LEVEL", "INFO").upper()

# VSS paths handled by this service
VSS_BOOL_PATHS: frozenset[str] = frozenset({
    "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling",
    "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling",
})
VSS_BRAKE_PATH = "Vehicle.Body.Lights.Brake.IsActive"
VSS_DRIVER_PATH = "Vehicle.Driver.Identifier.Subject"
BRAKE_VALID_VALUES: frozenset[str] = frozenset({"INACTIVE", "ACTIVE", "ADAPTIVE"})
DRIVER_ID_MAX_LEN = 64
VSS_ALL_PATHS: list[str] = sorted(
    VSS_BOOL_PATHS | {VSS_BRAKE_PATH, VSS_DRIVER_PATH}
)
# Paths written by the bridge via set_target_values (actuators, entry_type=ACTUATOR)
ACTUATOR_PATHS: list[str] = sorted(VSS_BOOL_PATHS | {VSS_BRAKE_PATH})
# Paths written by the bridge via set_current_values (sensors/attributes)
SENSOR_PATHS: list[str] = [VSS_DRIVER_PATH]

ROOT = Path(__file__).resolve().parent

# ── Shared state ──────────────────────────────────────────────────────────────
_vss_state: dict[str, Any] = {p: None for p in VSS_ALL_PATHS}
_vss_lock = threading.Lock()
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()

# ── MQTT ──────────────────────────────────────────────────────────────────────
_mqtt_client: mqtt.Client | None = None
_mqtt_lock = threading.Lock()


def _build_mqtt_client() -> mqtt.Client:
    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,  # paho-mqtt >= 2.0
            client_id="virtual-indicator-ui",
        )
    except AttributeError:
        client = mqtt.Client(client_id="virtual-indicator-ui")  # type: ignore[call-arg]

    def _on_connect(cl, _ud, _flags, rc, *_args):
        if rc == 0:
            LOG.info("MQTT connected to %s:%d", MQTT_HOST, MQTT_PORT)
        else:
            LOG.warning("MQTT connect returned rc=%s", rc)

    def _on_disconnect(cl, _ud, rc, *_args):
        LOG.warning("MQTT disconnected rc=%s", rc)

    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    return client


def _mqtt_worker() -> None:
    """Background thread: maintain persistent MQTT connection."""
    global _mqtt_client
    with _mqtt_lock:
        _mqtt_client = _build_mqtt_client()
    while True:
        try:
            _mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
            _mqtt_client.loop_forever()
        except Exception as exc:
            LOG.warning("MQTT connect error: %s – retry in 5 s", exc)
            time.sleep(5)


def _publish_vss(payload: dict) -> None:
    with _mqtt_lock:
        client = _mqtt_client
    if client is None:
        LOG.warning("MQTT client not ready; dropping publish")
        return
    try:
        client.publish(MQTT_TOPIC, json.dumps(payload), qos=0)
        LOG.debug("MQTT → %s: %s", MQTT_TOPIC, payload)
    except Exception as exc:
        LOG.warning("MQTT publish error: %s", exc)


# ── Kuksa poller ──────────────────────────────────────────────────────────────
def _actuator_feedback_worker() -> None:
    """Poll actuator target values and mirror them to current values.

    Equivalent to the Kuksa CAN provider feedback loop:
      bridge → set_target_values()  →  this worker detects change within 100 ms
      → set_current_values()        →  _sensor_watcher triggers SSE broadcast

    We use polling instead of subscribe_target_values() because Kuksa 0.6.0
    does not reliably push target-value change notifications to subscribers.
    """
    try:
        from kuksa_client.grpc import Datapoint, VSSClient  # noqa: PLC0415
    except ImportError:
        LOG.error("kuksa-client not installed – actor panel will show no live data")
        return

    last_vals: dict[str, Any] = {}

    while True:
        try:
            with VSSClient(
                KUKSA_HOST, KUKSA_PORT, ensure_startup_connection=False
            ) as client:
                LOG.info("Actuator feedback worker connected to %s:%d", KUKSA_HOST, KUKSA_PORT)
                while True:
                    try:
                        entries = client.get_target_values(ACTUATOR_PATHS)
                        LOG.debug("Actuator target poll returned %d entries", len(entries))
                        changed: dict[str, Any] = {}
                        for path, entry in entries.items():
                            v = _get_entry_value(entry)
                            if v is None:
                                LOG.debug(
                                    "Target value missing for %s (entry_type=%s)",
                                    path,
                                    type(entry).__name__ if entry is not None else "NoneType",
                                )
                                continue
                            if v is not None and last_vals.get(path) != v:
                                changed[path] = Datapoint(v)
                                LOG.debug(
                                    "Target change detected: %s %r -> %r",
                                    path,
                                    last_vals.get(path),
                                    v,
                                )
                                last_vals[path] = v
                        if changed:
                            client.set_current_values(changed)
                            LOG.debug("Feedback target\u2192current: %s", list(changed))
                    except Exception as exc:
                        LOG.debug("Actuator poll/feedback error: %s", exc)
                        break  # reconnect outer loop
                    time.sleep(0.1)
        except Exception as exc:
            LOG.warning("Actuator feedback worker lost: %s \u2013 retry in 3 s", exc)
        last_vals.clear()
        time.sleep(3)


def _sensor_watcher() -> None:
    """Subscribe to current-value changes for ALL tracked paths and push to SSE.

    Both actuator paths (after _actuator_feedback_worker writes current values)
    and sensor paths (Driver.Identifier.Subject, written by the bridge) trigger
    this subscription, keeping the actor panel up-to-date.
    """
    try:
        from kuksa_client.grpc import VSSClient  # noqa: PLC0415
    except ImportError:
        return

    while True:
        try:
            with VSSClient(
                KUKSA_HOST, KUKSA_PORT, ensure_startup_connection=False
            ) as client:
                LOG.info("Sensor watcher connected to %s:%d", KUKSA_HOST, KUKSA_PORT)
                for updates in client.subscribe_current_values(VSS_ALL_PATHS):
                    LOG.debug("Sensor watcher received %d updates", len(updates))
                    snapshot: dict[str, Any] = {}
                    for path, entry in updates.items():
                        v = _get_entry_value(entry)
                        if v is not None:
                            snapshot[path] = v
                    if snapshot:
                        with _vss_lock:
                            _vss_state.update(snapshot)
                        _broadcast_sse(snapshot)
        except Exception as exc:
            LOG.warning("Sensor watcher lost: %s \u2013 retry in 3 s", exc)
        time.sleep(3)


def _get_entry_value(entry: Any) -> Any:
    """Extract raw Python value from kuksa-client objects used in this setup.

    In the current Kuksa stack, get/subscribe calls may return either:
    - Datapoint objects where .value is already a Python primitive, or
    - Entry wrappers where .value points to a datapoint-like object.
    """
    if entry is None:
        LOG.debug("_get_entry_value: entry is None")
        return None
    val = getattr(entry, "value", None)
    if val is None:
        LOG.debug("_get_entry_value: entry.value missing on %s", type(entry).__name__)
        return None

    # Most commonly in this setup, val is already the primitive value.
    if isinstance(val, (bool, str, int, float)):
        return val

    # If val is a wrapper, unwrap one level.
    extracted = getattr(val, "value", None)
    if extracted is None:
        LOG.debug(
            "_get_entry_value: unsupported value container on %s (entry.value type=%s)",
            type(entry).__name__,
            type(val).__name__,
        )
        return None

    if isinstance(extracted, (bool, str, int, float)):
        return extracted

    LOG.debug(
        "_get_entry_value: unsupported nested value type on %s (nested type=%s)",
        type(entry).__name__,
        type(extracted).__name__,
    )
    return None


def _broadcast_sse(data: dict) -> None:
    with _sse_lock:
        dead: list[queue.Queue] = []
        for q in _sse_clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            try:
                _sse_clients.remove(q)
            except ValueError:
                pass


# ── HTTP handler ──────────────────────────────────────────────────────────────
class IndicatorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        LOG.debug(fmt, *args)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/indicator":
            self._handle_indicator_post()
        else:
            self._json(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/api/sse/signals":
            self._handle_sse()
        elif self.path == "/api/state":
            with _vss_lock:
                snap = dict(_vss_state)
            self._json(200, snap)
        else:
            super().do_GET()

    # ── POST /api/indicator ──────────────────────────────────────────────────
    def _handle_indicator_post(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 4096:
            self._json(413, {"error": "payload too large"})
            return
        raw = self.rfile.read(length)
        try:
            payload: dict = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._json(400, {"error": "invalid JSON"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "expected JSON object"})
            return

        validated: dict[str, Any] = {}
        errors: list[str] = []

        for key, val in payload.items():
            if key in VSS_BOOL_PATHS:
                if not isinstance(val, bool):
                    errors.append(f"{key}: expected bool, got {type(val).__name__}")
                else:
                    validated[key] = val
            elif key == VSS_BRAKE_PATH:
                if val not in BRAKE_VALID_VALUES:
                    errors.append(
                        f"{VSS_BRAKE_PATH}: must be one of {sorted(BRAKE_VALID_VALUES)}"
                    )
                else:
                    validated[key] = val
            elif key == VSS_DRIVER_PATH:
                if not isinstance(val, str) or len(val) > DRIVER_ID_MAX_LEN:
                    errors.append(
                        f"{VSS_DRIVER_PATH}: expected string ≤ {DRIVER_ID_MAX_LEN} chars"
                    )
                else:
                    validated[key] = val
            # Unknown keys are silently ignored (no MQTT forwarding)

        if errors:
            self._json(400, {"error": "validation failed", "details": errors})
            return
        if not validated:
            self._json(400, {"error": "no recognized VSS paths in payload"})
            return

        _publish_vss(validated)
        self._json(200, {"ok": True, "published": list(validated.keys())})

    # ── GET /api/sse/signals ─────────────────────────────────────────────────
    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

        client_q: queue.Queue = queue.Queue(maxsize=30)
        with _sse_lock:
            _sse_clients.append(client_q)

        # Emit current snapshot immediately so the page renders without waiting
        with _vss_lock:
            initial = dict(_vss_state)
        self._sse_event(initial)

        try:
            while True:
                try:
                    data = client_q.get(timeout=20)
                    self._sse_event(data)
                except queue.Empty:
                    # Keep-alive heartbeat
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sse_lock:
                try:
                    _sse_clients.remove(client_q)
                except ValueError:
                    pass

    def _sse_event(self, data: dict) -> None:
        line = f"data: {json.dumps(data)}\n\n".encode()
        self.wfile.write(line)
        self.wfile.flush()

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Virtual Indicator UI server")
    parser.add_argument("--host", default=HTTP_HOST)
    parser.add_argument("--port", type=int, default=HTTP_PORT)
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    threading.Thread(target=_mqtt_worker, daemon=True, name="mqtt-worker").start()
    # Actuator feedback loop: subscribes to target-value changes and writes them
    # back as current values (virtual CAN provider equivalent).
    threading.Thread(target=_actuator_feedback_worker, daemon=True, name="actuator-feedback").start()
    # Sensor watcher: subscribes to current-value changes for Driver.Identifier.Subject.
    threading.Thread(target=_sensor_watcher, daemon=True, name="sensor-watcher").start()

    LOG.info("Virtual Indicator UI  →  http://%s:%d", args.host, args.port)
    with ThreadingHTTPServer((args.host, args.port), IndicatorHandler) as server:
        server.serve_forever()
