# VSS ↔ CAN Mapping (MotorBike Blinker)

This demo uses VSS boolean signals for turn indicators and the brake light. The CAN payload is a single byte that encodes each signal as a bit.

## CAN encoding

| CAN ID | Direction | Byte | Bit | VSS signal | Description |
| --- | --- | --- | --- | --- | --- |
| 0x120 | Raspberry Pi → Arduino | 0 | 0 | `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` | Command left indicator state |
| 0x120 | Raspberry Pi → Arduino | 0 | 1 | `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` | Command right indicator state |
| 0x120 | Raspberry Pi → Arduino | 0 | 2 | `Vehicle.Body.Lights.Brake.IsActive` | Command brake light state |
| 0x121 | Arduino → Raspberry Pi | 0 | 0 | `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` | Current left indicator state |
| 0x121 | Arduino → Raspberry Pi | 0 | 1 | `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` | Current right indicator state |
| 0x121 | Arduino → Raspberry Pi | 0 | 2 | `Vehicle.Body.Lights.Brake.IsActive` | Current brake light state |

## Notes

- CAN bitrate is **500 kbit/s**.
- The Kuksa CAN Provider should map these VSS paths to the above CAN IDs and bit positions.
