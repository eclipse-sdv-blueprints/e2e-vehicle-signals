---
sidebar_position: 4
title: Raspberry Pi 5 Setup Guide
---

# Raspberry Pi 5 Setup Guide

This page walks through setting up the Raspberry Pi 5 as the main compute node for the demo.

## Prerequisites

- Raspberry Pi 5 with Waveshare RS485 CAN Hat mounted
- MicroSD card (32 GB+ recommended)
- 10″ HDMI display (optional but helpful)
- Internet-connected Wi-Fi network shared with all ECU devices

## 1. Flash the SD Card

Flash **Ubuntu 24.04 Desktop** using the [Raspberry Pi Imager](https://www.raspberrypi.com/software/). After flashing, open `config.txt` on the boot partition and add:

```
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
```

Insert the SD card and boot the Pi. Complete the setup wizard and connect to your Wi-Fi network.

:::tip
Ensure **all demo devices** (Arduinos, AZ3166 boards, Raspberry Pi) are on the **same Wi-Fi network** with a strong signal. MQTT connection loss can occur with weak signal or congested routers.
:::

## 2. Clone the Repository

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/chheis/eclipse-sdv-e2e-demo-blueprint --recurse-submodules
cd eclipse-sdv-e2e-demo-blueprint/devices/raspberry-pi5/
chmod +x setup.sh
```

If you forgot `--recurse-submodules`:

```bash
git submodule init
git pull --recurse-submodules
```

## 3. Run the Automated Setup Script

The setup script installs all required packages, configures SocketCAN, installs Docker and Ankaios, and deploys CAN provider assets:

```bash
export ANKAIOS_INSTALL_URL="https://github.com/eclipse-ankaios/ankaios/releases/latest/download/install.sh"
sudo -E ./setup.sh
```

The script performs the following steps automatically:

1. Installs `can-utils`, `net-tools`, `curl`, `vim`, `podman`
2. Installs Docker Engine and Docker Compose plugin
3. Disables Wi-Fi power saving (sets `wifi.powersave = 2`)
4. Installs Eclipse Ankaios via the official install script
5. Configures SocketCAN via `systemd-networkd` (`80-can.network`)
6. Copies CAN provider configuration files to `/opt/kuksa/can-provider/`

## 4. Manual Setup (Alternative)

If you prefer to set up manually instead of using the script:

### 4.1 Install Packages

```bash
sudo apt-get install -y can-utils net-tools curl vim podman
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
```

### 4.2 Disable Wi-Fi Power Saving

Edit `/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf`:

```ini
[connection]
wifi.powersave = 2
```

Restart NetworkManager:

```bash
sudo systemctl restart NetworkManager
```

### 4.3 Configure SocketCAN

Create `/etc/systemd/network/80-can.network` and enable:

```bash
sudo systemctl enable systemd-networkd
sudo systemctl restart systemd-networkd
```

### 4.4 Install Eclipse Ankaios

```bash
curl -sfL https://github.com/eclipse-ankaios/ankaios/releases/latest/download/install.sh | bash -
```

### 4.5 Deploy CAN Provider Assets

Copy the following files to `/opt/kuksa/can-provider/`:

- `can-provider-config.ini`
- `motorbike-blinker-vss.json`
- `motorbike-blinker-command.dbc`
- `motorbike-blinker-defaults.json`

## 5. Build the MQTT-to-gRPC Bridge Image

Build locally on the Raspberry Pi 5:

```bash
# Using Podman
podman build -t grpc-mqtt-bridge:latest devices/raspberry-pi5/grpc-mqtt-bridge

# Or using Docker
docker build -t grpc-mqtt-bridge:latest devices/raspberry-pi5/grpc-mqtt-bridge
```

:::caution Image Tag
The Ankaios manifest (`vehicle-signals.yaml`) references the GHCR image `ghcr.io/chheis/eclipse-sdv-e2e-demo-blueprint/grpc-mqtt-bridge:main`. If you build locally with tag `:latest`, either re-tag the image:
```bash
podman tag grpc-mqtt-bridge:latest ghcr.io/chheis/eclipse-sdv-e2e-demo-blueprint/grpc-mqtt-bridge:main
```
or edit the manifest to use your local tag.
:::

The GitHub Actions workflow also publishes this image to `ghcr.io` on pushes to `main`.

## 6. Start Everything

From the repository root:

```bash
sudo ./start-fleet-and-ankaios.sh
```

This startup script:

1. Starts the Fleet Management Docker Compose stack (Zenoh variant)
2. Applies the Ankaios workload manifest (`vehicle-signals.yaml`)
3. Starts **Dozzle** at `http://<pi-ip>:8080` for container log monitoring
4. Builds and starts the **demo website** at `http://<pi-ip>:8090`

:::tip Website Configuration
The startup script injects `devices/raspberry-pi5/website/site-config.json` into the Ankaios website workload before applying the manifest. Edit this file to customize the dashboard.

The website container runs **privileged** so it can probe SocketCAN activity (`candump` on `can0`). An optional legacy host-process mode can be enabled with `WEBSITE_ENABLED=true`.
:::

:::note
The first run takes a long time because all container images must be pulled or built locally.
:::

## 7. Verify the Setup

### Check Ankaios Workloads

```bash
ank get workloads
```

Or use the CLI helper script:

```bash
python3 devices/raspberry-pi5/ank-workloads-cli.py
```

### Check CAN Bus

```bash
candump can0
```

You should see CAN frames when the joystick ECU is active.

### Test MQTT Manually

```bash
mosquitto_pub -h localhost -p 1883 -t InVehicleTopics -q 0 \
  -m '{"Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling":true,"Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling":false,"Vehicle.Body.Lights.Brake.IsActive":"INACTIVE"}'
```

### Access the Services

| Service | URL |
| --- | --- |
| Demo website | `http://<pi-ip>:8090` |
| Dozzle (container logs) | `http://<pi-ip>:8080` |
| Grafana | `http://<pi-ip>:3000` |
| rFMS API | `http://<pi-ip>:8081` |
| Fleet Analysis API | `http://<pi-ip>:8082/fleet-analysis/api` |

## Arduino ECU Configuration

Point the Arduino MQTT broker IP addresses to the Raspberry Pi 5. The default in the sketches is `192.168.88.100`. Update the `arduino_secrets.h` files for your network:

- `devices/driver-input-ecu-arduino/mcu2-joystick-input/arduino_secrets.h`
- `devices/driver-input-ecu-door/arduino_secrets.h`

For detailed device-specific setup, wiring and firmware instructions, see:

- [Joystick Input ECU](./device-joystick-ecu) — Joystick wiring, MQTT config and sketch upload
- [LED Control ECU](./device-led-ecu) — MCP2515 wiring, CAN protocol and LED allocation
- [RFID Door ECU](./device-rfid-ecu) — RC522 RFID reader setup
- [ThreadX SOME/IP ECU](./device-threadx-ecu) — MXChip AZ3166 build, flash and SOME/IP configuration

## Shutdown

```bash
sudo ./shutdown-fleet-and-ankaios.sh
```
