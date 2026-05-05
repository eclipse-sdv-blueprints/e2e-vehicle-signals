---
sidebar_position: 2
title: Architecture
---

# Architecture

The E2E Demo Blueprint spans multiple physical devices connected over Wi-Fi and CAN bus. This page describes the full component architecture and how each piece interacts.

## High-Level Architecture

```mermaid
graph TB
    subgraph Driver Inputs
        JOY[Joystick ECU<br/>Arduino Uno R4 WiFi]
        RFID[Door RFID ECU<br/>Arduino + RC522]
    end

    subgraph AnkaiosWL["Raspberry Pi 5 - Ankaios Workloads"]
        MOSQ[Mosquitto MQTT Broker<br/>:1883]
        BRIDGE[MQTT-to-gRPC Bridge]
        KDB[Kuksa Databroker 0.6.0<br/>:55555]
        CAN_PROV[Kuksa CAN Provider<br/>dbc2val + val2dbc]
        SOCK["SocketCAN - can0"]
    end

    subgraph FMStack["Raspberry Pi 5 - Fleet Management Stack"]
        FWD[FMS Forwarder]
        ZENOH[Zenoh Router]
        CONS[FMS Consumer]
        INFLUX[(InfluxDB 2.7)]
        FMS_SRV["FMS Server - rFMS API<br/>:8081"]
        ANALYTICS[Fleet Analysis Backend<br/>Jakarta EE :8082]
        GRAFANA[Grafana<br/>:3000]
    end

    subgraph CANBus1["CAN Bus - 500 kbit/s"]
        LED_ECU[MCU1 LED Control<br/>Arduino Uno + MCP2515<br/>WS2812 8-LED Strip]
    end

    subgraph ThreadX["Optional - ThreadX SOME/IP"]
        AZ1[MXChip AZ3166 #1<br/>MQTT Sub + SOME/IP Pub]
        AZ2[MXChip AZ3166 #2<br/>SOME/IP Peer]
    end

    JOY -->|Wi-Fi / MQTT JSON| MOSQ
    RFID -->|Wi-Fi / MQTT JSON| MOSQ
    MOSQ --> BRIDGE
    BRIDGE -->|gRPC Val/Set| KDB
    KDB -->|target subscription| CAN_PROV
    CAN_PROV --> SOCK
    SOCK -->|CAN ID 0x120<br/>BlinkerCommand| LED_ECU
    LED_ECU -->|CAN ID 0x121<br/>BlinkerStatus| SOCK
    SOCK --> CAN_PROV
    CAN_PROV -->|current values| KDB

    KDB --> FWD
    FWD -->|uProtocol| ZENOH
    ZENOH --> CONS
    CONS --> INFLUX
    FMS_SRV --> INFLUX
    ANALYTICS --> INFLUX
    GRAFANA --> INFLUX

    MOSQ -->|subscribe| AZ1
    AZ1 -->|SOME/IP over Wi-Fi| AZ2
    AZ2 -->|SOME/IP over Wi-Fi| AZ1
```

## Component Descriptions

### Raspberry Pi 5 — Signal Workloads (Eclipse Ankaios)

All in-vehicle signal workloads are managed as Podman containers by **Eclipse Ankaios 0.7.0**. The Ankaios manifest (`vehicle-signals.yaml`) defines the following workloads:

| Workload | Container Image | Purpose |
| --- | --- | --- |
| `mosquitto-broker` | `eclipse-mosquitto:latest` | MQTT broker for driver-input ECUs |
| `grpc-mqtt-bridge` | `grpc-mqtt-bridge:main` | Translates MQTT JSON payloads to Kuksa gRPC `Val/Set` updates |
| `kuksa-databroker` | `kuksa-databroker:0.6.0` | Central VSS signal store |
| `kuksa-can-provider` | `can-provider:0.4.4` | Bidirectional CAN ↔ VSS mapping via DBC files |
| `pi5-demo-website` | `pi5-demo-website:latest` | Live architecture / signal-flow dashboard at `:8090` |

All workloads run with `--net=host` so they share the host network namespace and can reach each other at `localhost`.

### Raspberry Pi 5 — Fleet Management Stack (Docker Compose)

The Fleet Management Blueprint services run via Docker Compose alongside the Ankaios workloads:

| Service | Purpose |
| --- | --- |
| `fms-forwarder` | Reads VSS signals from Kuksa Databroker and forwards them via uProtocol |
| `fms-zenoh-router` | Zenoh transport layer |
| `fms-consumer` | Receives telemetry and writes to InfluxDB |
| `fms-server` | rFMS HTTP API at `:8081` |
| `fleet-analysis-backend` | Jakarta EE analytics API at `:8082` |
| `influxdb` | Time-series database |
| `grafana` | Dashboards at `:3000` |
| `csv-provider` | Optional simulated vehicle data source |

### Arduino Joystick ECU

An Arduino Uno R4 WiFi reads an analog joystick (left/right + button press) and publishes VSS-aligned JSON on MQTT topic `InVehicleTopics`. The payload directly maps to:

- `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` (boolean)
- `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` (boolean)
- `Vehicle.Body.Lights.Brake.IsActive` (string: `INACTIVE` / `ACTIVE` / `ADAPTIVE`)

→ **[Full device guide: Joystick Input ECU](./device-joystick-ecu)**

### Arduino RFID Door ECU

An Arduino with an RC522 RFID reader publishes the scanned card UID as:

- `Vehicle.Driver.Identifier.Subject` (string)

→ **[Full device guide: RFID Door ECU](./device-rfid-ecu)**

### MCU1 LED Control ECU

An Arduino Uno with an MCP2515 CAN transceiver listens for `BlinkerCommand` frames on CAN ID `0x120` and drives a WS2812 8-LED strip:

| LEDs (0-based) | Function |
| --- | --- |
| 0–1 | Left indicator |
| 3–4 | Brake light |
| 6–7 | Right indicator |

The MCU sends `BlinkerStatus` frames on CAN ID `0x121` back to the Raspberry Pi.

→ **[Full device guide: LED Control ECU](./device-led-ecu)**

### ThreadX SOME/IP Extension (Optional)

Two MXChip AZ3166 boards form a SOME/IP peer pair:

- **Device 1** subscribes to MQTT blinker topics, maps the payload to SOME/IP events, and forwards button A/B state.
- **Device 2** receives SOME/IP events and updates its LED/OLED display, also sending its own button state back.

→ **[Full device guide: ThreadX SOME/IP ECU](./device-threadx-ecu)**

## Network Topology

```mermaid
graph LR
    subgraph WiFi["WiFi Network - 192.168.88.x"]
        PI5[Raspberry Pi 5<br/>192.168.88.100]
        JOY[Joystick ECU]
        RFID[RFID ECU]
        AZ1[AZ3166 #1]
        AZ2[AZ3166 #2]
    end
    subgraph CANBus["CAN Bus - 500 kbit/s"]
        PI5 ---|RS485 CAN Hat| CAN0[can0]
        CAN0 --- MCU1[MCU1 LED Control<br/>MCP2515]
    end
```

All Wi-Fi devices connect to the same network. The Raspberry Pi 5 bridges Wi-Fi (MQTT) and CAN (SocketCAN) traffic. The CAN bus operates at **500 kbit/s** with an 8 MHz oscillator on the MCP2515 module.
