# Driver Door ECU (MQTT Door Actuator + Servo)

This document describes the behavior and wiring of the Arduino sketch in:

- devices/driver-door-ecu/driver-door-ecu.ino

## Purpose

The ECU performs three functions:

1. Connects to WiFi.
2. Subscribes to door actuator commands over MQTT.
3. Moves a servo to open/close position and publishes the resulting door state.

## MQTT behavior

- Broker: `192.168.88.100`
- Port: `1883`
- Topic: `InVehicleTopics`
- Command key: `Vehicle.Cabin.Door.Row1.DriverSide.IsOpen`
- Payload examples:

```json
{"Vehicle.Cabin.Door.Row1.DriverSide.IsOpen":true}
```

```json
{"Vehicle.Cabin.Door.Row1.DriverSide.IsOpen":false}
```

The ECU subscribes to this key and interprets it as actuator target:

- `true`  -> open door (servo toward 180 degrees)
- `false` -> close door (servo toward 0 degrees)

When the actuator reaches an end position, the ECU publishes the current state
using the same VSS key.

## Servo behavior

- Servo library: `Servo.h`
- Servo pin: `D9`
- Motion profile:

1. Starts at 0 degrees.
2. Moves in 10 degree steps every 50 ms.
3. Stops at 180 degrees when target is open.
4. Stops at 0 degrees when target is closed.

This is implemented in a non-blocking way so WiFi/MQTT handling can continue while the servo is moving.

## Pin mapping used in sketch

### Servo

- Signal: `D9`
- Power: external 5V supply recommended for reliable operation
- Ground: must be shared with Arduino GND

## Required local secrets

Define WiFi credentials in `arduino_secrets.h`:

```cpp
#define SECRET_SSID "your-ssid"
#define SECRET_PASS "your-password"
```

## Notes

- Keep MQTT broker IP aligned with your Raspberry Pi setup.
- If the servo jitters or resets the board, use a dedicated 5V source for the servo and common ground with the Arduino.
- `devices/raspberry-pi5/grpc-mqtt-bridge` should be configured to:
  - publish this path from **target value** to MQTT
  - write the ECU-published MQTT value back to Kuksa as **current value**
