---
sidebar_position: 9
title: "Device: LED Control ECU"
---

# MCU1 LED Control ECU (Arduino Uno + MCP2515)

This device drives an 8-LED strip over CAN and reports its current light status back to the Raspberry Pi 5 running the Kuksa CAN Provider.

## Hardware

| Component | Details |
| --- | --- |
| **Board** | Arduino Uno R4 WiFi |
| **CAN transceiver** | MCP2515 module (8 MHz crystal, TJA1050) |
| **LED output** | WS2812 LED strip (8 LEDs) |
| **Bus** | CAN at 500 kbit/s |

See the [Hardware BOM](./hardware) for sourcing details and wiring instructions.

## Responsibilities

- Receive `BlinkerCommand` CAN frames from the Raspberry Pi 5
- Drive the WS2812 LED strip to show turn-indicator and brake-light states
- Send `BlinkerStatus` CAN frames reporting the current state back to the Pi

## Arduino Libraries

- [FastLED](https://github.com/FastLED/FastLED) — WS2812 LED control
- [107-Arduino-MCP2515](https://github.com/107-systems/107-Arduino-MCP2515) — MCP2515 CAN controller driver

## LED Allocation

| LEDs (1-based) | LEDs (0-based) | Function |
| --- | --- | --- |
| 1-2 | 0-1 | Left indicator |
| 4-5 | 3-4 | Brake light |
| 7-8 | 6-7 | Right indicator |

## CAN Protocol

### Payload Encoding

The Arduino expects a single-byte payload where each bit (or bit pair) represents a VSS signal. The same encoding is used when publishing status back to the Raspberry Pi.

| Bit(s) | VSS Signal |
| --- | --- |
| 0 | `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` |
| 1 | `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` |
| 2-3 | `Vehicle.Body.Lights.Brake.IsActive` (0=INACTIVE, 1=ACTIVE, 2=ADAPTIVE) |

### CAN IDs

| CAN ID | Name | Direction | Description |
| --- | --- | --- | --- |
| `0x120` (288) | `BlinkerCommand` | Raspberry Pi → Arduino | Set blinker and brake state |
| `0x121` (289) | `BlinkerStatus` | Arduino → Raspberry Pi | Report current state |

See [VSS / CAN Signal Mapping](./signal-mapping) for the full DBC definition and value transforms.

## LED Blinking Behavior

| Signal State | LED Behavior |
| --- | --- |
| Left indicator ON | LEDs 0-1 blink at 1 Hz (500 ms on/off) |
| Right indicator ON | LEDs 6-7 blink at 1 Hz (500 ms on/off) |
| Brake ACTIVE | LEDs 3-4 solid on |
| All OFF | All LEDs off |

## Wiring

### MCP2515 to Arduino

| MCP2515 Pin | Arduino Pin |
| --- | --- |
| VCC | 5 V |
| GND | GND |
| CS | D10 (SPI SS) |
| SO | D12 (SPI MISO) |
| SI | D11 (SPI MOSI) |
| SCK | D13 (SPI SCK) |
| INT | D2 |

The WS2812 LED strip data line connects to a digital output pin (see sketch for the exact pin).

### CAN Bus Connection

Connect **CAN_H** and **CAN_L** between the MCP2515 module and the Waveshare RS485 CAN Hat on the Raspberry Pi 5. Use twisted-pair wiring and add 120 Ω termination resistors at each end of the bus.

## Configuration

- **CAN bitrate**: 500 kbit/s
- **MCP2515 clock**: 8 MHz

No Wi-Fi or MQTT configuration is needed — this ECU communicates solely over CAN.

## Sketch Location

```
devices/mcu1-led-control-can/mcu1-led-control-can/mcu1-led-control-can.ino
```

Upload via the Arduino IDE (2.x) with the **Arduino UNO R4 WiFi** board selected.
