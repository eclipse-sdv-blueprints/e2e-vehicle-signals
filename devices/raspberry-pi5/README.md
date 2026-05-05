# Raspberry Pi 5 (Connectivity Unit)

This node runs the Fleet Management Blueprint components plus the vehicle signal stack for the MotorBike blinker demo.

## Required components

- **Ubuntu 24.04** image for Raspberry Pi 5
- **Eclipse Ankaios 0.7.0** running workloads with Podman
- **Eclipse Kuksa Databroker 0.6.0** workload
- **Eclipse Mosquitto** MQTT broker workload
- **MQTT-to-gRPC bridge** workload (for Kuksa Databroker)
- **SocketCAN** interface (e.g., `can0` at 500 kbit/s)
- **Kuksa CAN Provider** to translate CAN → VSS
- **Fleet Management Blueprint** services (as defined in the upstream repository)
- **Fleet Analysis Backend** (Jakarta EE) container

## Raspberry Pi5 Setup / SW + HW
- for the 10" display connect the HDMI and USB for power supply
- flash SD-Card with Ubuntu 24.04.xx Desktop (https://www.raspberrypi.com/software/)
- modify config.txt: For the single CAN Hat add this line at the end of the file
````
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
````
- insert the SD Card in the RPi and boot it up.
- finish the config wizard and configure your WiFi
- Hint: Setup all WiFi devices in the SAME WiFi and ensure that the Router is performant enough and is very near! MQTT connection loss could be happening if not done so.
- install git and clone this repo:
  - ````sudo apt update ````
  - ````sudo apt install git ````
  - ````git clone https://github.com/chheis/eclipse-sdv-e2e-demo-blueprint --recurse-submodules````
  - ````cd eclipse-sdv-e2e-demo-blueprint/devices/raspberry-pi5/ ````
  - ````chmod +x setup.sh ````
  - Hint: if you miss --recurse-submodules in the begining use: ````git submodule init ```` and ````git pull --recurse-submodules````
- use the setup.sh
  1. ````export ANKAIOS_INSTALL_URL="https://github.com/eclipse-ankaios/ankaios/releases/latest/download/install.sh" ````
  2. ```` sudo -E ./setup.sh````
- or do those steps manual:
  1. disable the network energy saving mode ````/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf```` and set wifi.powersave to 2 (disabled) instead of 3 (enabled)
  2.  install can-utils ````sudo apt-get install can-utils````
  3.  install net-tools ````sudo apt install net-tools ````
  4.  install curl ````sudo apt-get install curl````
  5.  install vim ````sudo apt-get install vim````
  6.  install podman ````sudo apt-get install podman````
  7.  install Docker and Docker Compose ````sudo apt-get install docker.io docker-compose-v2```` and enable the service ````sudo systemctl enable --now docker````
  8.  podman login to ghcr.io (if private packages needed)
  8.  enable socketCAN with startup (use /etc/systemd/network/80-can.network)
    -  ````sudo vim /etc/systemd/network/80-can.network````
    -  ````sudo systemctl enable systemd-networkd````
    - ````sudo systemctl restart systemd-networkd````
  9. install eclipse ankaios (with script) ````curl -sfL https://github.com/eclipse-ankaios/ankaios/releases/latest/download/install.sh | bash - ````
  10. Copy needed files to /opt/kuksa/can-provider
      1. "can-provider-config.ini"
      2. "motorbike-blinker-vss.json"
      3. "motorbike-blinker-command.dbc"
      4. "motorbike-blinker-defaults.json"
- Maybe use this to init the network: ````docker swarm init ````  
- start the workload from eclipse-sdv-e2e-demo-blueprint root folder: ````sudo ./start-fleet-and-ankaios.sh```` 
- the startup script also starts **Dozzle** (default `http://<pi-ip>:8080`) for container log/health visibility
- the startup script builds the **Pi5 website container image** and the Ankaios manifest starts `pi5-demo-website` on `http://<pi-ip>:8090`
- for the website workload config, edit `devices/raspberry-pi5/website/site-config.json`; the startup script injects that JSON into the Ankaios website workload before applying the manifest
- the website workload now samples SocketCAN activity with `candump` on `can0`; the probe is throttled in the backend, and the website container runs privileged so it can access the CAN interface
- optional legacy host-process mode for website can be enabled with `WEBSITE_ENABLED=true`

Hint: First Run takes a long time as all images for fleet-management blueprint must be build locally!


## Signal mapping

Use the VSS mapping defined in [`docs/vss-can-signals.md`](../../docs/vss-can-signals.md) to wire the CAN provider to the Arduino blinker ECU.

## Ankaios workload (Mosquitto + MQTT bridge + Kuksa Databroker + CAN provider)

Use the example Ankaios manifest in `devices/raspberry-pi5/ankaios/vehicle-signals.yaml`. It defines the Mosquitto MQTT broker, MQTT-to-gRPC bridge, Kuksa Databroker, and the Kuksa CAN Provider containers as Podman workloads.

1. Copy `devices/raspberry-pi5/ankaios/vehicle-signals.yaml` into your Ankaios manifests directory.
2. Copy CAN provider files to `/opt/kuksa/can-provider/` on the Raspberry Pi 5:
   1. `devices/raspberry-pi5/ankaios/can-provider-config.ini` -> `/opt/kuksa/can-provider/can-provider-config.ini`
   2. `devices/raspberry-pi5/ankaios/motorbike-blinker-vss.json` -> `/opt/kuksa/can-provider/motorbike-blinker-vss.json`
   3. `devices/raspberry-pi5/ankaios/motorbike-blinker-command.dbc` -> `/opt/kuksa/can-provider/motorbike-blinker-command.dbc`
   4. `devices/raspberry-pi5/ankaios/motorbike-blinker-defaults.json` -> `/opt/kuksa/can-provider/motorbike-blinker-defaults.json`
3. Adjust `can-provider-config.ini` if needed:
   - `port` in `[can]` to your SocketCAN device (default: `can0`)
   - `ip` and `port` in `[general]` to your Kuksa Databroker endpoint
4. Build the MQTT-to-gRPC bridge image from `devices/raspberry-pi5/grpc-mqtt-bridge` and tag it as `grpc-mqtt-bridge:latest`.

The manifest uses host networking so the CAN provider can reach the databroker at `localhost:55555`, the MQTT bridge can reach Mosquitto at `localhost:1883`, and Mosquitto listens on `localhost:1883`. Point Arduino MQTT broker IPs to the Raspberry Pi 5 address (default in `mcu2-joystick-input.ino` and `driver-input-ecu-door.ino` is `192.168.88.100`).

## Ankaios dashboard workaround (CLI workload view)

If the Ankaios dashboard is unavailable, use the CLI helper script to retrieve workloads:

```bash
python3 devices/raspberry-pi5/ank-workloads-cli.py
```

JSON output for automation:

```bash
python3 devices/raspberry-pi5/ank-workloads-cli.py --json
```

The script automatically tries multiple `ank` command variants (with and without `-k`) and prints the first successful result.

## Build the MQTT bridge image

Build locally on the Raspberry Pi 5 (Podman):

```bash
podman build -t grpc-mqtt-bridge:latest devices/raspberry-pi5/grpc-mqtt-bridge
```

Build locally on a dev machine (Docker):

```bash
docker build -t grpc-mqtt-bridge:latest devices/raspberry-pi5/grpc-mqtt-bridge
```

The GitHub Actions workflow publishes the image to `ghcr.io/<owner>/<repo>/grpc-mqtt-bridge` on pushes to `main` and version tags.

## MQTT to Kuksa mappings

The joystick ECU and RFID door ECU publish JSON payloads on `InVehicleTopics`.

Example joystick payload:

```json
{
  "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling": true,
  "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling": false,
  "Vehicle.Body.Lights.Brake.IsActive": "ACTIVE"
}
```

Test publish with mosquitto_pub:

```bash
mosquitto_pub -h localhost -p 1883 -t InVehicleTopics -q 0 -m '{"Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling":true,"Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling":false,"Vehicle.Body.Lights.Brake.IsActive":"INACTIVE"}'
```

Example RFID payload:

```json
{
  "Vehicle.Driver.Identifier.Subject": "A1B2C3D4"
}
```

The sample bridge config (`devices/raspberry-pi5/ankaios/grpc-mqtt.yaml`) maps these JSON keys to Kuksa `Val/Set` updates.

For Fleet Management/Influx/Grafana flow, `fms-forwarder` maps
`Vehicle.Driver.Identifier.Subject` to the telemetry field `driver1Id`
(`header` measurement), which is shown in the Grafana panel
`Driver Identifier (RFID)`.

## Communication workflow diagram

PlantUML source: `devices/raspberry-pi5/communication-workflow.puml`

## Fleet Analysis Backend (runs on Pi 5)

The fleet analysis service runs alongside the Fleet Management Blueprint stack via Docker Compose and
connects to the same InfluxDB instance on the `fms-backend` network.

1. From `external/fleet-management`, start the stack:

```bash
docker compose -f ./fms-blueprint-compose.yaml -f ./fms-blueprint-compose-zenoh.yaml up --detach
```

2. The service will be available at `http://<pi5-ip>:8082/fleet-analysis/api`.

Configuration is done via environment variables:

- `INFLUXDB_STATS_INTERVAL_SECONDS` (default: 30)
- `INFLUXDB_URI` (default: http://influxdb:8086)
- `INFLUXDB_ORG` (default: sdv)
- `INFLUXDB_BUCKET` (default: demo)
- `INFLUXDB_TOKEN_FILE` (mounted from the InfluxDB init job)

## Helpful upstream references

- Fleet Management Blueprint: https://github.com/eclipse-sdv-blueprints/fleet-management
- Ankaios vehicle signals tutorial: https://eclipse-ankaios.github.io/ankaios/latest/usage/tutorial-vehicle-signals/
- Kuksa Databroker 0.6.0: https://github.com/eclipse-kuksa/kuksa-databroker/releases/tag/0.6.0
- Ankaios 0.7.0: https://github.com/eclipse-ankaios/ankaios/releases/tag/v0.7.0
- Kuksa CAN Provider: https://github.com/eclipse-kuksa/kuksa-can-provider
