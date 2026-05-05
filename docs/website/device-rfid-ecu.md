---
sidebar_position: 10
title: "Device: RFID Door ECU"
---

# Driver Input ECU - Door (Arduino + RC522 RFID)

This device scans RFID cards and publishes the detected identifier as a VSS signal. It serves as a driver-identification input in the demo.

## Hardware

| Component | Details |
| --- | --- |
| **Board** | Arduino Uno R4 WiFi |
| **RFID reader** | RC522 (MFRC522-compatible), SPI-connected |
| **Connectivity** | Wi-Fi (2.4 GHz) → MQTT |

See the [Hardware BOM](./hardware) for the full parts list.

## Responsibilities

- Read RFID UID from the RC522 module using the local `RFID1` library
- Connect over Wi-Fi to the MQTT broker on the Raspberry Pi 5
- Publish the scanned card UID as a VSS signal

## VSS Signal Published

| VSS Path | Data Type | Description |
| --- | --- | --- |
| `Vehicle.Driver.Identifier.Subject` | string | Hex-encoded RFID card UID (e.g., `A1B2C3D4`) |

## MQTT Publishing Details

| Setting | Value |
| --- | --- |
| **Broker** | `<pi5-ip>:1883` (default: `192.168.88.100:1883`) |
| **Topic** | `InVehicleTopics` |

**Payload example:**

```json
{
  "Vehicle.Driver.Identifier.Subject": "A1B2C3D4"
}
```

The [MQTT-to-gRPC Bridge](./communication-workflow#2-driver-identity-path--rfid-to-vss) on the Pi 5 maps this payload to a Kuksa Databroker `Val/Set` call.

## Signal Flow

```
RFID card tap on RC522 reader
  → Arduino reads UID bytes
    → JSON payload published to MQTT "InVehicleTopics"
      → Bridge writes to Kuksa Databroker
        → FMS Forwarder maps to telemetry field "driver1Id"
          → Stored in InfluxDB
            → Visible in Grafana "Driver Identifier (RFID)" panel
```

See [Communication Workflow](./communication-workflow) for the full end-to-end description.

## Configuration

### Wi-Fi and MQTT Broker

Edit the secrets file before uploading the sketch:

```
devices/driver-input-ecu-door/arduino_secrets.h
```

Set `SECRET_SSID`, `SECRET_PASS`, and the broker IP to match your network.

## Sketch Location

```
devices/driver-input-ecu-door/driver-input-ecu-door.ino
```

Upload via the Arduino IDE (2.x) with the **Arduino UNO R4 WiFi** board selected.

## RFID Library

The sketch uses a local `RFID1` library bundled in the repository at:

```
devices/driver-input-ecu-door/libraries/RFID1
```

This library must be available in the Arduino IDE's library path when compiling.
