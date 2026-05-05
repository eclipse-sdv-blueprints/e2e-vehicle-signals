# Driver Input ECU (Arduino + Joystick)

This device is the manual blinker/brake input ECU.

## Responsibilities

- Capture joystick input from an analog joystick:
  - https://docs.sunfounder.com/projects/elite-explorer-kit/de/latest/basic_projects/20_basic_joystick.html
- Publish VSS-aligned JSON to MQTT topic `InVehicleTopics` on the Raspberry Pi 5 broker.
- Provide values for:
  - `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling`
  - `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling`
  - `Vehicle.Body.Lights.Brake.IsActive`

## MQTT publishing details

- Broker: `<pi5-ip>:1883` (default in sketch: `192.168.88.100:1883`)
- Topic: `InVehicleTopics`
- Payload example:

```json
{
  "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling": true,
  "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling": false,
  "Vehicle.Body.Lights.Brake.IsActive": "ACTIVE"
}
```

The MQTT-to-gRPC bridge on the Pi 5 maps this payload to Kuksa Databroker updates.
