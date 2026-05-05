# eclipse-sdv-e2e-demo-blueprint

This repository prepares a Vehicle E/E Architecture demo that combines the **Fleet Management** use case from the Eclipse SDV Blueprints project with an in-vehicle **MotorBike Blinker** use case. The demo aligns all signal names to the COVESA Vehicle Signal Specification (VSS) and uses Kuksa Databroker 0.6.0 running as an Eclipse Ankaios 0.7.0 workload.

## Architecture overview

- **Raspberry Pi 5 (HPC / FleetDisplay)**
  - Ubuntu
  - Eclipse Ankaios 0.7.0 (Podman workloads)
  - Kuksa Databroker 0.6.0
  - Kuksa CAN Provider + SocketCAN
  - Fleet Management Blueprint services
- **Raspberry Pi 4 (HPC)**
  - Optional higher-level control (Eclipse S-CORE or equivalent)
- **MCU1 LED Control (Arduino Uno + MCP2515)**
  - Controls 8-LED strip for left/right indicators and brake light
  - Publishes current light status over CAN @ 500 kbit/s
- **Driver input ECUs**
  - Arduino + joystick (manual input)
  - Arduino + RFID RC522 (driver identifier input)
  - ThreadX board with buttons + OLED (status display)

## Device code folders

Each device has a dedicated folder under `devices/`:

- `devices/raspberry-pi4` - connectivity unit setup notes
- `devices/raspberry-pi5` - HCP/control node notes
- `devices/mcu1-led-control-can` - Arduino sketch for the LED strip
- `devices/backend-fleet-analysis-java` - Jakarta EE 21 backend for fleet analytics
- `devices/driver-input-ecu-arduino` - driver input ECU placeholder
- `devices/driver-input-ecu-door` - RFID reader input ECU
- `devices/driver-input-ecu-threadx` - ThreadX input ECU placeholder

## VSS signals used

The blinker demo uses the following VSS signals:

- `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling`
- `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling`
- `Vehicle.Body.Lights.Brake.IsActive`
- `Vehicle.Driver.Identifier.Subject`

The CAN encoding for these signals is documented in [`docs/vss-can-signals.md`](docs/vss-can-signals.md).

## Communication workflow (Raspberry Pi 5 signal stack)

Signal flow used by the Ankaios `vehicle-signals.yaml` workloads:

1. Driver input ECUs (joystick and RFID door reader) publish VSS-aligned JSON to MQTT topic `InVehicleTopics`.
2. `grpc-mqtt-bridge` converts MQTT payloads into Kuksa Databroker `Val/Set` gRPC updates.
3. Kuksa CAN Provider (`val2dbc`) emits CAN command frames (`BlinkerCommand`, CAN ID `288`) to the blinker ECU.
4. Blinker ECU sends status frames (`BlinkerStatus`, CAN ID `289`) back on the CAN bus.
5. Kuksa CAN Provider (`dbc2val`) writes those status values back into Kuksa Databroker for subscribers.

PlantUML source: [`devices/raspberry-pi5/communication-workflow.puml`](devices/raspberry-pi5/communication-workflow.puml)

## Quickstart (Fleet Management + Java analytics, Zenoh)

1. Initialize the Fleet Management submodule:

```bash
git submodule update --init --recursive
```

2. Start the Zenoh-based Fleet Management stack plus the Java analytics backend:

```bash
docker compose -f external/fleet-management/fms-blueprint-compose.yaml -f external/fleet-management/fms-blueprint-compose-zenoh.yaml up --detach
```

Maybe use this to init the network:
````
docker swarm init
````

The analytics service will be available at `http://127.0.0.1:8082/fleet-analysis/api`.

## References

- Fleet Management Blueprint: https://github.com/eclipse-sdv-blueprints/fleet-management
- Ankaios vehicle signals tutorial: https://eclipse-ankaios.github.io/ankaios/latest/usage/tutorial-vehicle-signals/
- Kuksa Databroker 0.6.0: https://github.com/eclipse-kuksa/kuksa-databroker/releases/tag/0.6.0
- Ankaios 0.7.0: https://github.com/eclipse-ankaios/ankaios/releases/tag/v0.7.0
- Kuksa CAN Provider: https://github.com/eclipse-kuksa/kuksa-can-provider
- MCP2515 Arduino library: https://github.com/107-systems/107-Arduino-MCP2515
