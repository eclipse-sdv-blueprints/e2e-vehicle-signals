# Driver Door ECU (SOME/IP Door Actuator + Servo)

This document describes the Arduino sketch in `devices/driver-door-ecu/driver-door-ecu.ino`.

## Purpose

The ECU connects to Wi-Fi, receives door targets as SOME/IP-over-UDP events,
moves a servo, and reports its resulting door state through a second event.
It does not connect to Mosquitto.

## SOME/IP UDP Contract

| Direction | Service ID | Event ID | UDP port | Payload |
| --- | --- | --- | --- | --- |
| Door ECU -> provider | `0x4301` | `0x8001` | Pi `30500` | `0` closed, `1` open |
| Provider -> Door ECU | `0x4301` | `0x8002` | Door ECU `30501` | `0` close, `1` open |

`kuksa-opensomeip-door-provider` maps these events to
`Vehicle.Cabin.Door.Row1.DriverSide.IsOpen`: target values become actuator
commands and ECU state events become current values.

## Servo Behavior

- Servo library: `Servo.h`
- Servo pin: `D9`
- Closed position: 0 degrees
- Open position: 180 degrees
- Motion: 10 degree steps every 50 ms

Use a dedicated 5V supply for the servo if needed and always connect its ground
to Arduino ground.

## Network Settings

Define Wi-Fi credentials in `arduino_secrets.h`:

```cpp
#define SECRET_SSID "your-ssid"
#define SECRET_PASS "your-password"
```

Set `SOMEIP_PROVIDER_IP` in `arduino_config.h` to the Raspberry Pi address.
The source-controlled default is `192.168.88.100`. Start the Ankaios door
provider workload before powering the ECU.

The legacy filename is retained for existing documentation links; the active
door actuator implementation uses SOME/IP, not MQTT.
