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

import argparse
import json
import sys
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
import yaml


def _parse_args():
    parser = argparse.ArgumentParser(description="MQTT to Kuksa gRPC bridge")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to grpc-mqtt.yaml config file",
    )
    return parser.parse_args()


def _read_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _parse_broker_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("mqtt", "tcp"):
        raise ValueError(f"Unsupported broker scheme: {parsed.scheme}")
    host = parsed.hostname or "localhost"
    port = parsed.port or 1883
    return host, port


def _json_pointer(value, pointer):
    if pointer in ("", "/"):
        return value
    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON pointer: {pointer}")
    current = value
    for raw_part in pointer.split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            index = int(part)
            current = current[index]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(pointer)
    return current


def _cast_value(value, value_type):
    if not value_type:
        return value
    value_type = value_type.lower()
    if value_type == "bool":
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "on"):
                return True
            if normalized in ("false", "0", "no", "off"):
                return False
        return bool(value)
    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "string":
        return str(value)
    return value


class KuksaWriter:
    def __init__(self, host, port):
        self._datapoint_class = None
        self._data_type_enum = None
        self._metadata_field_enum = None
        self._entry_type_enum = None
        self._value_types = {}
        self._value_restrictions = {}
        self._entry_types = {}
        self._logged_metadata_paths = set()
        self._set_current_values = None
        self._set_target_values = None
        self._client = self._build_client(host, port)
        self._connect()
        self._select_setters()

    def _build_client(self, host, port):
        try:
            from kuksa_client.grpc import (
                Datapoint,
                DataType,
                EntryType,
                MetadataField,
                VSSClient,
            )

            self._datapoint_class = Datapoint
            self._data_type_enum = DataType
            self._metadata_field_enum = MetadataField
            self._entry_type_enum = EntryType
            return VSSClient(host, port)
        except ImportError:
            from kuksa_client import KuksaClient

            return KuksaClient(host=host, port=port)

    def _connect(self):
        if hasattr(self._client, "connect"):
            self._client.connect()

    def _select_setters(self):
        if hasattr(self._client, "set_target_values"):
            self._set_target_values = self._client.set_target_values
        if hasattr(self._client, "set_current_values"):
            self._set_current_values = self._client.set_current_values
        if self._set_target_values is None and self._set_current_values is None:
            raise RuntimeError("Kuksa client has no supported set_* method")

    def write(self, updates):
        if not updates:
            return
        normalized = self._normalize_updates(updates)
        if self._set_target_values and self._set_current_values:
            target_updates = {}
            current_updates = {}
            for path, value in normalized.items():
                entry_type = self._entry_types.get(path)
                if self._entry_type_enum is not None and entry_type is not None:
                    if entry_type == self._entry_type_enum.ACTUATOR:
                        target_updates[path] = value
                    else:
                        current_updates[path] = value
                else:
                    target_updates[path] = value
            if current_updates:
                self._set_current_values(current_updates)
            if target_updates:
                self._set_target_values(target_updates)
        elif self._set_target_values:
            self._set_target_values(normalized)
        else:
            self._set_current_values(normalized)

    def _normalize_updates(self, updates):
        if self._datapoint_class is None:
            return updates
        self._refresh_metadata(updates.keys())
        normalized = {}
        for path, value in updates.items():
            if hasattr(value, "v1_to_message"):
                normalized[path] = value
            else:
                normalized[path] = self._datapoint_class(
                    value=self._coerce_datapoint_value(
                        value,
                        self._value_types.get(path),
                        self._value_restrictions.get(path),
                    )
                )
        return normalized

    def _refresh_metadata(self, paths):
        if self._data_type_enum is None:
            return
        if (
            self._metadata_field_enum is not None
            and hasattr(self._client, "get_metadata")
        ):
            missing_metadata = [
                path
                for path in paths
                if path not in self._entry_types
                or path not in self._value_types
                or path not in self._value_restrictions
            ]
            if missing_metadata:
                try:
                    metadata = self._client.get_metadata(
                        missing_metadata,
                        self._metadata_field_enum.ALL,
                    )
                except Exception:
                    metadata = {}
                for path, md in (metadata or {}).items():
                    self._entry_types[path] = md.entry_type if md is not None else None
                    self._value_types[path] = md.data_type if md is not None else None
                    self._value_restrictions[path] = (
                        md.value_restriction if md is not None else None
                    )
                for path in missing_metadata:
                    if path not in metadata:
                        self._entry_types.setdefault(path, None)
                        self._value_restrictions.setdefault(path, None)

        if hasattr(self._client, "get_value_types"):
            missing_types = [
                path
                for path in paths
                if path not in self._value_types or self._value_types[path] is None
            ]
            if missing_types:
                try:
                    resolved = self._client.get_value_types(missing_types)
                except Exception:
                    resolved = {}
                self._value_types.update(resolved or {})

        self._log_metadata(paths)

    def _log_metadata(self, paths):
        if not paths:
            return
        pending = [path for path in paths if path not in self._logged_metadata_paths]
        if not pending:
            return
        for path in pending:
            value_type = self._value_types.get(path)
            restriction = self._value_restrictions.get(path)
            entry_type = self._entry_types.get(path)
            restriction_desc = None
            if restriction is not None:
                restriction_desc = {
                    "min": restriction.min,
                    "max": restriction.max,
                    "allowed_values": restriction.allowed_values,
                }
            print(
                f"Kuksa metadata: {path} type={value_type} entry_type={entry_type} restriction={restriction_desc}",
                file=sys.stderr,
            )
        self._logged_metadata_paths.update(pending)

    def _coerce_datapoint_value(self, value, value_type, restriction):
        if value is None:
            return None
        if value_type is None or self._data_type_enum is None:
            return value
        data_type = value_type
        if data_type in (self._data_type_enum.STRING,):
            return self._coerce_string(value, restriction)
        if data_type in (self._data_type_enum.BOOLEAN,):
            return self._coerce_bool(value)
        if data_type in (
            self._data_type_enum.INT8,
            self._data_type_enum.INT16,
            self._data_type_enum.INT32,
            self._data_type_enum.INT64,
            self._data_type_enum.UINT8,
            self._data_type_enum.UINT16,
            self._data_type_enum.UINT32,
            self._data_type_enum.UINT64,
        ):
            return self._coerce_int(value)
        if data_type in (self._data_type_enum.FLOAT, self._data_type_enum.DOUBLE):
            return self._coerce_float(value)
        if data_type in (self._data_type_enum.STRING_ARRAY,):
            return self._coerce_array(
                value, lambda item: self._coerce_string(item, restriction)
            )
        if data_type in (self._data_type_enum.BOOLEAN_ARRAY,):
            return self._coerce_array(value, self._coerce_bool)
        if data_type in (
            self._data_type_enum.INT8_ARRAY,
            self._data_type_enum.INT16_ARRAY,
            self._data_type_enum.INT32_ARRAY,
            self._data_type_enum.INT64_ARRAY,
            self._data_type_enum.UINT8_ARRAY,
            self._data_type_enum.UINT16_ARRAY,
            self._data_type_enum.UINT32_ARRAY,
            self._data_type_enum.UINT64_ARRAY,
        ):
            return self._coerce_array(value, self._coerce_int)
        if data_type in (
            self._data_type_enum.FLOAT_ARRAY,
            self._data_type_enum.DOUBLE_ARRAY,
        ):
            return self._coerce_array(value, self._coerce_float)
        return value

    @staticmethod
    def _coerce_bool(value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "on"):
                return True
            if normalized in ("false", "0", "no", "off"):
                return False
        return bool(value)

    @staticmethod
    def _coerce_int(value):
        return int(value)

    @staticmethod
    def _coerce_float(value):
        return float(value)

    def _coerce_string(self, value, restriction):
        if isinstance(value, bool):
            return self._bool_string_from_restriction(value, restriction)
        return str(value)

    @staticmethod
    def _coerce_array(value, caster):
        if isinstance(value, (list, tuple)):
            return [caster(item) for item in value]
        return [caster(value)]

    @staticmethod
    def _bool_string_from_restriction(value, restriction):
        if restriction and restriction.allowed_values:
            allowed = [str(v).strip().lower() for v in restriction.allowed_values]
            if "true" in allowed and "false" in allowed:
                return "true" if value else "false"
            if "1" in allowed and "0" in allowed:
                return "1" if value else "0"
            if "on" in allowed and "off" in allowed:
                return "on" if value else "off"
            if "yes" in allowed and "no" in allowed:
                return "yes" if value else "no"
            if len(restriction.allowed_values) == 2:
                return (
                    str(restriction.allowed_values[1])
                    if value
                    else str(restriction.allowed_values[0])
                )
        return "true" if value else "false"


def main():
    args = _parse_args()
    config = _read_config(args.config)

    mqtt_config = config.get("mqtt", {})
    grpc_config = config.get("grpc", {})
    mappings = config.get("mappings", [])

    broker_url = mqtt_config.get("broker", "tcp://localhost:1883")
    broker_host, broker_port = _parse_broker_url(broker_url)
    client_id = mqtt_config.get("clientId", "kuksa-mqtt-bridge")
    subscriptions = mqtt_config.get("subscriptions", [])

    grpc_target = grpc_config.get("target", "localhost:55555")
    if ":" in grpc_target:
        grpc_host, grpc_port = grpc_target.rsplit(":", 1)
    else:
        grpc_host, grpc_port = grpc_target, "55555"

    try:
        grpc_port = int(grpc_port)
    except ValueError as exc:
        raise ValueError(f"Invalid gRPC port: {grpc_port}") from exc

    kuksa_writer = KuksaWriter(grpc_host, grpc_port)

    def on_message(_client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            print("Skipping non-JSON MQTT payload", file=sys.stderr)
            return

        updates = {}
        for mapping in mappings:
            mqtt_mapping = mapping.get("mqtt", {})
            if mqtt_mapping.get("topic") != msg.topic:
                continue
            mqtt_pointer = mqtt_mapping.get("jsonPointer", "/")
            try:
                scoped_payload = _json_pointer(payload, mqtt_pointer)
            except (KeyError, ValueError, IndexError):
                continue
            grpc_mapping = mapping.get("grpc", {})
            for update in grpc_mapping.get("updates", []):
                pointer = update.get("jsonPointer", "/")
                try:
                    value = _json_pointer(scoped_payload, pointer)
                except (KeyError, ValueError, IndexError):
                    continue
                try:
                    value = _cast_value(value, update.get("type"))
                except (TypeError, ValueError):
                    continue
                updates[update.get("path")] = value

        try:
            kuksa_writer.write(updates)
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to write to Kuksa: {exc}", file=sys.stderr)

    client = mqtt.Client(client_id=client_id)
    client.on_message = on_message
    client.connect(broker_host, broker_port)

    for subscription in subscriptions:
        topic = subscription.get("topic")
        if not topic:
            continue
        qos = subscription.get("qos", 0)
        client.subscribe(topic, qos=qos)

    client.loop_forever()


if __name__ == "__main__":
    main()
