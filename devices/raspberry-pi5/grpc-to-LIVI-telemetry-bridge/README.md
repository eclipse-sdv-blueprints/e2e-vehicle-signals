# Kuksa-to-LIVI Telemetry Bridge

Subscribes to VSS signals on the [Kuksa Databroker](https://github.com/eclipse-kuksa/kuksa-databroker) via gRPC and pushes them, after optional transformation, into a running [LIVI](https://github.com/f-io/LIVI) head unit using its Socket.IO `telemetry:push` event.

The LIVI telemetry payload contract is defined in [`src/main/shared/types/Telemetry.ts`](https://github.com/f-io/LIVI/blob/main/src/main/shared/types/Telemetry.ts).

## Run locally

```bash
pip install -r requirements.txt
python bridge.py --config ../ankaios/grpc-livi.yaml --log-level INFO
```

## Container

```bash
docker build -t kuksa-livi-bridge .
docker run --rm --net=host \
  -v $(pwd)/../ankaios/grpc-livi.yaml:/config/grpc-livi.yaml:ro \
  kuksa-livi-bridge --config /config/grpc-livi.yaml
```

The published image is available at `ghcr.io/<owner>/e2e-vehicle-signals/kuksa-livi-bridge:main` (built by the [`publish-kuksa-livi-bridge`](../../../.github/workflows/publish-kuksa-livi-bridge.yml) workflow).

## Configuration

See [`devices/raspberry-pi5/ankaios/grpc-livi.yaml`](../ankaios/grpc-livi.yaml). Each mapping entry has:

| Key | Required | Description |
| --- | --- | --- |
| `vssPath` | yes | Fully qualified VSS path to subscribe to (e.g. `Vehicle.Speed`) |
| `liviField` | yes | Dotted LIVI telemetry field (e.g. `speedKph`, `gps.lat`) |
| `type` | no | Target scalar type: `bool`, `int`, `float`, `string` |
| `scale` / `offset` | no | Linear transform applied before type coercion |
| `enumMap` | no | Map VSS values (bool/string/int) to LIVI values (e.g. `True → "left"`) |
| `sendNone` | no | If `true`, also forward `null` values (default: skip) |

Top-level keys:

```yaml
kuksa:
  target: "localhost:55555"
livi:
  url: "ws://192.168.88.110:4000"
push:
  intervalMs: 250          # batch + coalesce VSS updates
  sendInitialSnapshot: true
mappings:
  - vssPath: Vehicle.Speed
    liviField: speedKph
    type: float
```
