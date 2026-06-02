# MQTT-to-Kuksa gRPC Bridge

Subscribes to MQTT topics on a local broker (e.g. Mosquitto) and forwards
selected JSON payload fields into the
[Kuksa Databroker](https://github.com/eclipse-kuksa/kuksa-databroker) over gRPC.

Used in this blueprint to ingest signals published by the Arduino joystick /
RFID / brake ECUs (via the MCU1 CAN gateway and `grpc-mqtt` Hono bridge) into
VSS so they can be consumed by every downstream workload (LED control, LIVI
IVI, fleet analytics, …).

## Run locally

```bash
pip install -r requirements.txt
python bridge.py --config ../ankaios/grpc-mqtt.yaml
```

## Container

```bash
docker build -t kuksa-mqtt-bridge .
docker run --rm --net=host \
  -v $(pwd)/../ankaios/grpc-mqtt.yaml:/config/grpc-mqtt.yaml:ro \
  kuksa-mqtt-bridge --config /config/grpc-mqtt.yaml
```

The published image is available at
`ghcr.io/<owner>/e2e-vehicle-signals/kuksa-mqtt-bridge:main` (built by the
[`publish-grpc-mqtt-bridge`](../../../.github/workflows/publish-grpc-mqtt-bridge.yml)
workflow).

## Configuration

See [`devices/raspberry-pi5/ankaios/grpc-mqtt.yaml`](../ankaios/grpc-mqtt.yaml).

### Top-level keys

```yaml
mqtt:
  broker: "tcp://192.168.88.100:1883"
  clientId: "kuksa-mqtt-bridge"
  subscriptions:
    - topic: "InVehicleTopics"
      qos: 0
grpc:
  target: "192.168.88.100:55555"
mappings:
  - name: "joystick-vss-update"
    mqtt:
      topic: "InVehicleTopics"
      jsonPointer: "/"
    grpc:
      updates:
        - path: "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling"
          type: "bool"
          jsonPointer: "/Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling"
```

### `mqtt` section

| Key | Required | Description |
| --- | --- | --- |
| `broker` | yes | Broker URL, `tcp://host:port` or `mqtt://host:port` |
| `clientId` | no | MQTT client identifier (default: `kuksa-mqtt-bridge`) |
| `subscriptions[].topic` | yes | Topic filter to subscribe to |
| `subscriptions[].qos` | no | MQTT QoS level (default: `0`) |

### `grpc` section

| Key | Required | Description |
| --- | --- | --- |
| `target` | yes | Kuksa Databroker `host:port` (default: `localhost:55555`) |

### `mappings[]` entries

Each mapping connects one MQTT topic to one or more VSS datapoints.

| Key | Required | Description |
| --- | --- | --- |
| `name` | no | Human-readable mapping label (logging only) |
| `mqtt.topic` | yes | Exact topic this mapping reacts to |
| `mqtt.jsonPointer` | no | [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901) JSON pointer scoping the payload before per-update extraction (default: `/`) |
| `grpc.updates[].path` | yes | Fully qualified VSS path to write (e.g. `Vehicle.Speed`) |
| `grpc.updates[].jsonPointer` | yes | JSON pointer into the (scoped) payload picking the value |
| `grpc.updates[].type` | no | Target scalar type: `bool`, `int`, `float`, `string` |

For each incoming MQTT message:

1. The payload is parsed as JSON (non-JSON payloads are skipped).
2. For every matching mapping, the payload is reduced via `mqtt.jsonPointer`.
3. Each entry in `grpc.updates[]` extracts a value via its `jsonPointer`,
   coerces it to the requested `type`, and is written to its VSS `path`.
4. Writes are routed automatically:
   - **`ACTUATOR`** entries are written via `set_target_values`.
   - All other entry types (sensor, attribute) use `set_current_values`.

VSS metadata (data type, value restriction, entry type) is fetched lazily on
first use and cached, so string-typed booleans, enum-restricted strings, and
numeric arrays are coerced to the exact representation the databroker expects.

## Notes

- The bridge connects once at startup and then loops via
  `paho.mqtt.client.loop_forever()`; if the broker disappears, Paho's built-in
  reconnect logic handles it.
- The Kuksa client is created at startup — make sure `kuksa-databroker` is
  reachable on `grpc.target` before launching the bridge in standalone mode.
  Under Ankaios the workload dependency order takes care of this.
