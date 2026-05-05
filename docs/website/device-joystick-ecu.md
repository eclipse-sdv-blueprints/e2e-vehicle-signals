---
sidebar_position: 8
title: "Device: Joystick Input ECU"
---

# Joystick Input ECU (Arduino Uno R4 WiFi)

The Joystick ECU is the primary driver-input device. It reads an analog joystick and publishes VSS-aligned JSON to the Raspberry Pi 5 over Wi-Fi/MQTT.

## Hardware

| Component | Details |
| --- | --- |
| **Board** | Arduino Uno R4 WiFi |
| **Input** | Analog joystick module ([SunFounder docs](https://docs.sunfounder.com/projects/elite-explorer-kit/de/latest/basic_projects/20_basic_joystick.html)) |
| **Connectivity** | Wi-Fi (2.4 GHz) → MQTT |

The joystick is included in the [SunFounder Elite Explorer Kit](https://www.sunfounder.com/collections/kits-with-orignal-arduino-board/products/sunfounder-elite-explorer-kit-with-official-arduino-uno-r4-wifi) listed in the [Hardware BOM](./hardware).

## Responsibilities

- Read X/Y axis and button state from the analog joystick
- Map joystick positions to VSS blinker and brake signals
- Publish JSON payloads to the MQTT broker on the Raspberry Pi 5

## VSS Signals Published

| VSS Path | Data Type | Joystick Mapping |
| --- | --- | --- |
| `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` | boolean | Joystick left |
| `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` | boolean | Joystick right |
| `Vehicle.Body.Lights.Brake.IsActive` | string | Joystick button press (`ACTIVE` / `INACTIVE`) |

## MQTT Publishing Details

| Setting | Value |
| --- | --- |
| **Broker** | `<pi5-ip>:1883` (default: `192.168.88.100:1883`) |
| **Topic** | `InVehicleTopics` |

**Payload example:**

```json
{
  "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling": true,
  "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling": false,
  "Vehicle.Body.Lights.Brake.IsActive": "ACTIVE"
}
```

The [MQTT-to-gRPC Bridge](./communication-workflow#1-command-path--joystick-to-leds) on the Pi 5 maps this payload to Kuksa Databroker `Val/Set` updates.

## Configuration

### Wi-Fi and MQTT Broker

Edit the secrets file before uploading the sketch:

```
devices/driver-input-ecu-arduino/mcu2-joystick-input/arduino_secrets.h
```

Set `SECRET_SSID`, `SECRET_PASS`, and the broker IP to match your network.

### Arduino Libraries

The sketch uses the following libraries (included in the repository):

- **ArduinoMqttClient** — MQTT connectivity
- **zenoh-pico** — Optional Zenoh transport (experimental)

## Sketch Location

```
devices/driver-input-ecu-arduino/mcu2-joystick-input/mcu2-joystick-input.ino
```

Upload via the Arduino IDE (2.x) with the **Arduino UNO R4 WiFi** board selected.

## Signal Flow

```
Joystick analog input
  → Arduino reads X/Y/button
    → Maps to VSS JSON payload
      → Publishes to MQTT "InVehicleTopics"
        → Bridge converts to gRPC Val/Set
          → Kuksa Databroker stores target values
            → CAN Provider emits BlinkerCommand (0x120) on CAN bus
              → LED ECU drives WS2812 LEDs
```

See [Communication Workflow](./communication-workflow) for the full end-to-end signal path.
