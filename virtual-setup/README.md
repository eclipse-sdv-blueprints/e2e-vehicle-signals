<!--
/********************************************************************************
* Copyright (c) 2026 Contributors to the Eclipse Foundation
*
* See the NOTICE file(s) distributed with this work for additional
* information regarding copyright ownership.
*
* This program and the accompanying materials are made available under the
* terms of the Apache License 2.0 which is available at
* https://www.apache.org/licenses/LICENSE-2.0
*
* SPDX-License-Identifier: Apache-2.0
********************************************************************************/
-->

# Virtual Setup

Fully virtualized E2E Vehicle Signals blueprint — runs on any Linux host with Docker without physical hardware.

## What this folder contains

```
virtual-setup/
├── virtual-e2e-compose.yaml     ← virtual services (joins Fleet Management networks)
├── start-virtual-setup.sh       ← starts Fleet Management + virtual services
├── stop-virtual-setup.sh        ← stops both stacks
├── docker-compose.yaml          ← all-in-one compose variant
├── config/
│   ├── mosquitto.conf           ← MQTT broker config (adapted from ankaios/vehicle-signals.yaml)
│   ├── grpc-mqtt.yaml           ← bridge config (service names instead of localhost)
│   ├── grpc-livi.yaml           ← LIVI bridge config (optional; no LIVI needed)
│   └── site-config.json         ← website config (service names, CAN disabled)
├── virtual-indicator-ui/        ← NEW container replacing three physical ECUs
│   ├── Dockerfile
│   ├── api_server.py            ← POST /api/indicator + GET /api/sse/signals
│   ├── index.html               ← two-panel UI (input + actor)
│   ├── styles.css
│   ├── app.js
│   └── requirements.txt
└── tosca/
    ├── TOSCA-Metadata/TOSCA.meta
    ├── Definitions/
    │   ├── service-template.yaml
    │   ├── node-types.yaml
    │   └── relationship-types.yaml
    └── Scripts/
        ├── deploy-compose.sh    ← TOSCA lifecycle: configure
        └── teardown.sh          ← TOSCA lifecycle: delete
```

## Reused components (not copied, referenced by path)

| Component | Source path | How referenced |
|-|-|-|
| gRPC-MQTT bridge image | `devices/raspberry-pi5/grpc-mqtt-bridge/` | `ghcr.io/…/grpc-mqtt-bridge:main` |
| Kuksa-LIVI bridge image (optional) | `devices/raspberry-pi5/grpc-to-LIVI-telemetry-bridge/` | `ghcr.io/…/kuksa-livi-bridge:main` (disabled by default in `virtual-e2e-compose.yaml`) |
| Pi5 Demo Website | `devices/raspberry-pi5/website/` | `build: context: ../devices/raspberry-pi5/website` |
| grpc-mqtt signal mappings | `devices/raspberry-pi5/ankaios/grpc-mqtt.yaml` | adapted → `config/grpc-mqtt.yaml` (broker/target changed to service names) |
| grpc-livi mappings (optional) | `devices/raspberry-pi5/ankaios/grpc-livi.yaml` | adapted → `config/grpc-livi.yaml` (minimal blinker subset; only needed when enabling LIVI bridge) |
| Fleet Management stack | `external/fleet-management/` | Started via `start-virtual-setup.sh` using `fms-blueprint-compose.yaml` + `fms-blueprint-compose-zenoh.yaml` |

## Quick start

```bash
cd virtual-setup

# Start Fleet Management + virtual services
bash ./start-virtual-setup.sh

# Optional: enable debug logs for virtual-indicator-ui
LOG_LEVEL=DEBUG bash ./start-virtual-setup.sh

# Indicator Input + Actor UI
open http://localhost:8091

# Pi5 Demo Website (architecture / signal-flow dashboard)
open http://localhost:8090

# Logs
docker compose -f virtual-e2e-compose.yaml logs -f

# Stop everything
bash ./stop-virtual-setup.sh
```

### Signal flow (no hardware required)

```
Browser button click
  └─► POST /api/indicator (virtual-indicator-ui :8091)
        └─► MQTT publish → mosquitto :1883
              └─► grpc-mqtt-bridge → databroker :55556 (Val/Set gRPC)
                    └─► databroker → SSE poll (virtual-indicator-ui /api/sse/signals)
                          └─► Actor LED panel updates in browser
```

Inside the Docker `fms-vehicle` network, services must use `databroker:55556`.
By default, host access is mapped to `localhost:55555`.

The startup script prints **internal Docker Compose service ports**. If your compose
overrides remap ports, published host ports may differ.

## Virtual Indicator UI

Open **http://localhost:8091** to get:

| Panel | Replaces | Actions |
|-|-|-|
| **Indicator Input** | Arduino joystick ECU | ◄ Left / Right ► / ■ Off toggle buttons |
| **Driver ID** | Arduino RFID door ECU | Text field + Identify button |
| **Indicator Actor** | WS2812 8-LED ECU | Animated 8-LED strip — amber blink (indicator), red (brake) |

The input panel publishes VSS JSON to `InVehicleTopics` MQTT with the exact same schema the physical joystick ECU uses. `grpc-mqtt-bridge` requires no changes.

The actor panel subscribes to Kuksa Databroker via Server-Sent Events (`GET /api/sse/signals`) and updates the LED state every 200 ms.

The backend SSE stream emits **incremental updates** (changed paths only). The UI
maintains a local cache of the latest values per tracked path so partial events do
not clear indicator state.

The backend is aligned with the Kuksa Databroker `0.6.x` setup used in this
virtual stack.

The Kuksa LIVI bridge is optional in this virtual setup and is disabled by default (commented out in `virtual-e2e-compose.yaml`).

## Fleet Management

The startup script first starts Fleet Management, then starts the virtual services compose which attaches to the external Fleet networks (`fleet-management_fms-backend`, `fleet-management_fms-vehicle`):

```bash
open http://localhost:3000   # Grafana
open http://localhost:8081   # FMS rFMS API
open http://localhost:8082   # Fleet analytics backend
```

`fms-forwarder` only forwards telemetry from the FMS Kuksa Databroker into Zenoh. The service that writes those samples into InfluxDB is `fms-consumer`, which now uses the same token and startup wiring as the upstream Fleet Management compose files.

## Eclipse Winery / TOSCA

The `tosca/` folder contains the complete TOSCA 1.3 service topology.

```bash
# Run Eclipse Winery
docker run -d --name winery -p 8080:8080 opentosca/winery:latest

# Open topology modeller
open http://localhost:8080/winery
# Import: tosca/Definitions/node-types.yaml and relationship-types.yaml
# Then open: tosca/Definitions/service-template.yaml
```

Deploy via TOSCA lifecycle scripts:

```bash
# configure (build + docker compose up)
bash tosca/Scripts/deploy-compose.sh

# delete (docker compose down)
bash tosca/Scripts/teardown.sh
```

## Config differences from physical setup

| Config file | Physical original | Virtual change |
|-|-|-|
| `config/grpc-mqtt.yaml` | `devices/raspberry-pi5/ankaios/grpc-mqtt.yaml` | `mqtt.broker` and `grpc.target` use Docker service names |
| `config/grpc-livi.yaml` | `devices/raspberry-pi5/ankaios/grpc-livi.yaml` | `kuksa.target` uses service name; LIVI URL = `host.docker.internal:4000` |
| `config/site-config.json` | `devices/raspberry-pi5/website/site-config.json.example` | Service names for MQTT/Kuksa; `can_observer` disabled |
| `config/mosquitto.conf` | Inline in `vehicle-signals.yaml` configs section | Extracted as a file |
