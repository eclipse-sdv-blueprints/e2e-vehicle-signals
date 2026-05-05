# MCU1 LED Control (Arduino Uno + MCP2515)

This device drives an 8‑LED strip over CAN and reports its current light status to the Raspberry Pi 5 running the Kuksa CAN Provider.

## Hardware

- Arduino Uno R4 WiFi
- MCP2515 CAN module (8 MHz crystal)
- WS2812 LED strip (8 LEDs)

### Arduino Libs
- [FastLED](https://github.com/FastLED/FastLED)
- [107-Arduino-MCP2515](https://github.com/107-systems/107-Arduino-MCP2515)


### LED allocation

| LEDs (1‑based) | LEDs (0‑based) | Function |
| --- | --- | --- |
| 1‑2 | 0‑1 | Left indicator |
| 4‑5 | 3‑4 | Brake light |
| 7‑8 | 6‑7 | Right indicator |

## CAN payload

The Arduino expects a single‑byte payload where each bit (or bit pair) represents a VSS signal. The same encoding is used when publishing status back to the Raspberry Pi 5.

| Bit(s) | VSS signal |
| --- | --- |
| 0 | `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` |
| 1 | `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` |
| 2–3 | `Vehicle.Body.Lights.Brake.IsActive` (0=INACTIVE, 1=ACTIVE, 2=ADAPTIVE) |

### CAN IDs

- **0x120**: Command from Raspberry Pi → Arduino (set blinker + brake state).
- **0x121**: Status from Arduino → Raspberry Pi (current state).

## Notes

- CAN bitrate is **500 kbit/s** and MCP2515 clock is **8 MHz**.
- Left/right indicators blink at 1 Hz (500 ms toggle).

## Arduino sketch

The sketch lives under `mcu1-led-control-can/mcu1-led-control-can.ino`.
