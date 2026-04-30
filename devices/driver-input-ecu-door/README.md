# Driver Input ECU Door (Arduino + RC522 RFID)

This device scans RFID cards and publishes the detected identifier as a VSS signal.

## Responsibilities

- Read RFID UID from RC522 (MFRC522-compatible) module using local `RFID` library.
- Connect over Wi-Fi and publish to MQTT broker on Raspberry Pi 5.
- Publish VSS signal:
  - `Vehicle.Driver.Identifier.Subject` (string)

## MQTT publishing details

- Broker: `<pi5-ip>:1883` (default in sketch: `192.168.88.100:1883`)
- Topic: `InVehicleTopics`
- Payload example:

```json
{
  "Vehicle.Driver.Identifier.Subject": "A1B2C3D4"
}
```

The MQTT-to-gRPC bridge on the Pi 5 maps this payload to Kuksa Databroker `Val/Set`.

## Files

- Sketch: `devices/driver-input-ecu-door/driver-input-ecu-door.ino`
- RFID library: `devices/driver-input-ecu-door/libraries/RFID`
