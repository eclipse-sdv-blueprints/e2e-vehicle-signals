---
sidebar_position: 5
title: VSS / CAN Signal Mapping
---

# VSS / CAN Signal Mapping

All signals in this demo are aligned to the [COVESA Vehicle Signal Specification (VSS)](https://covesa.github.io/vehicle_signal_specification/). This page documents how VSS signals map to CAN frames on the bus.

## VSS Signals Used

| VSS Path | Data Type | Description |
| --- | --- | --- |
| `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` | boolean | Left turn indicator state |
| `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` | boolean | Right turn indicator state |
| `Vehicle.Body.Lights.Brake.IsActive` | string (`INACTIVE` / `ACTIVE` / `ADAPTIVE`) | Brake light state |
| `Vehicle.Driver.Identifier.Subject` | string | Driver RFID card UID |

## CAN Frame Encoding

The blinker signals are encoded in a single-byte CAN payload. Each signal occupies one or two bits:

| CAN ID | Name | Direction | Byte | Bit(s) | VSS Signal | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `0x120` (288) | `BlinkerCommand` | Raspberry Pi → Arduino | 0 | 0 | `...Left.IsSignaling` | Command left indicator |
| `0x120` (288) | `BlinkerCommand` | Raspberry Pi → Arduino | 0 | 1 | `...Right.IsSignaling` | Command right indicator |
| `0x120` (288) | `BlinkerCommand` | Raspberry Pi → Arduino | 0 | 2–3 | `...Brake.IsActive` | Command brake light |
| `0x121` (289) | `BlinkerStatus` | Arduino → Raspberry Pi | 0 | 0 | `...Left.IsSignaling` | Current left indicator |
| `0x121` (289) | `BlinkerStatus` | Arduino → Raspberry Pi | 0 | 1 | `...Right.IsSignaling` | Current right indicator |
| `0x121` (289) | `BlinkerStatus` | Arduino → Raspberry Pi | 0 | 2–3 | `...Brake.IsActive` | Current brake light |

- **CAN bitrate**: 500 kbit/s
- **Byte order**: Little-endian (Intel)
- **Brake encoding**: 0 = `INACTIVE`, 1 = `ACTIVE`, 2 = `ADAPTIVE`

## DBC File

The CAN encoding is formally defined in `motorbike-blinker-command.dbc`:

```dbc
BO_ 288 BlinkerCommand: 1 RPI5
 SG_ DirectionIndicatorLeft  : 0|1@1+ (1,0) [0|1] ""  MCU1
 SG_ DirectionIndicatorRight : 1|1@1+ (1,0) [0|1] ""  MCU1
 SG_ BrakeIsActive           : 2|2@1+ (1,0) [0|3] ""  MCU1

BO_ 289 BlinkerStatus: 1 Vector__XXX
 SG_ DirectionIndicatorLeft  : 0|1@1+ (1,0) [0|1] "" Vector__XXX
 SG_ DirectionIndicatorRight : 1|1@1+ (1,0) [0|1] "" Vector__XXX
 SG_ BrakeIsActive           : 2|2@1+ (1,0) [0|3] "" Vector__XXX
```

## VSS-to-DBC Mapping (Kuksa CAN Provider)

The Kuksa CAN Provider uses a VSS overlay JSON file (`motorbike-blinker-vss.json`) to map between VSS paths and DBC signal names. Key mapping:

| VSS Path | DBC Signal | Mode |
| --- | --- | --- |
| `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` | `DirectionIndicatorLeft` | `dbc2vss` + `vss2dbc` |
| `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` | `DirectionIndicatorRight` | `dbc2vss` + `vss2dbc` |
| `Vehicle.Body.Lights.Brake.IsActive` | `BrakeIsActive` | `dbc2vss` + `vss2dbc` (with value transform) |

### Brake Value Transform

The brake signal requires a value transform between VSS string values and CAN integer values:

**dbc2vss** (CAN → VSS):

| CAN Value | VSS Value |
| --- | --- |
| 0 | `INACTIVE` |
| 1 | `ACTIVE` |
| 2 | `ADAPTIVE` |

**vss2dbc** (VSS → CAN):

| VSS Value | CAN Value |
| --- | --- |
| `INACTIVE` | 0 |
| `ACTIVE` | 1 |
| `ADAPTIVE` | 1 |

## MQTT Payload Format

The Arduino ECUs publish JSON on the MQTT topic `InVehicleTopics`. The keys are the full VSS paths:

**Joystick ECU payload:**

```json
{
  "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling": true,
  "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling": false,
  "Vehicle.Body.Lights.Brake.IsActive": "ACTIVE"
}
```

**RFID Door ECU payload:**

```json
{
  "Vehicle.Driver.Identifier.Subject": "A1B2C3D4"
}
```

The MQTT-to-gRPC bridge maps these keys to Kuksa Databroker `Val/Set` gRPC calls using JSON pointer extraction as configured in `grpc-mqtt.yaml`.

## Default Signal Values

The CAN provider uses default values for unmapped signals when operating in `val2dbc` mode:

```json
{
  "DirectionIndicatorLeft": 0,
  "DirectionIndicatorRight": 0,
  "BrakeIsActive": 0
}
```
