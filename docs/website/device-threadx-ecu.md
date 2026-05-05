---
sidebar_position: 11
title: "Device: ThreadX SOME/IP ECU"
---

# Driver Input ECU - ThreadX (MXChip AZ3166)

This optional extension adds two MXChip AZ3166 boards that demonstrate **SOME/IP** vehicle-signal communication alongside the existing MQTT-based signal flow. The boards run on **Eclipse ThreadX** with Eclipse ThreadX NetX Duo for networking.

## Hardware

| Component | Details |
| --- | --- |
| **Board** | MXChip AZ3166 (×2) |
| **MCU** | STM32F412RG (100 MHz, 1 MB flash, 256 KB SRAM) |
| **Display** | 128×64 OLED for blinker status visualization |
| **LEDs** | RGB LEDs controlled by P9813 |
| **Input** | Two buttons (A and B) |
| **Connectivity** | Wi-Fi (2.4 GHz) |
| **Sensors** | Temperature/Humidity (HTS221), Pressure (LPS22HB) |

See the [Hardware BOM](./hardware) for sourcing details.

## Responsibilities

- Capture button input (left/right blinker toggle)
- Display current blinker/brake status on the OLED
- Publish and subscribe to VSS signals over MQTT
- Communicate between boards via SOME/IP (OpenSOME/IP over UDP)
- Control RGB LEDs to indicate blinker and brake states

## Communication Modes

The application supports two communication modes that can run simultaneously:

### MQTT Mode (Default)

Communicates with the Mosquitto MQTT broker on the Raspberry Pi 5. Subscribes to `InVehicleTopics` to receive blinker state updates from the joystick ECU.

### SOME/IP Mode (Optional)

Direct UDP-based vehicle signal communication between two AZ3166 boards using OpenSOME/IP:

| Role | Local Endpoint | Target Endpoint |
| --- | --- | --- |
| Device 1 | `192.168.88.91:30490` | `192.168.88.92:30500` |
| Device 2 | `192.168.88.92:30500` | `192.168.88.91:30490` |

**SOME/IP payload:** 5 bytes `[left, right, brake, button_a, button_b]` (each value is 0 or 1)

## Prerequisites

### Development Environment

| Tool | Minimum Version |
| --- | --- |
| CMake | 3.15 |
| Ninja | Latest |
| Arm GNU Embedded Toolchain | 13.3.rel1 |
| Git | With submodule support |

### Installation

**Windows:**

```powershell
winget install --id=Arm.GnuArmEmbeddedToolchain -e
winget install --id=Ninja-build.Ninja -e
winget install --id=Kitware.CMake -e
```

**Ubuntu/Linux:**

```bash
sudo apt install ninja-build cmake
wget https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi.tar.xz
sudo tar xJf arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi.tar.xz -C /opt
export PATH=$PATH:/opt/arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi/bin
```

**macOS:** Download from [Arm GNU Toolchain Downloads](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads).

### Project Setup

Ensure submodules are initialized from the repository root:

```bash
git submodule init
git submodule update --recursive
```

## Building

Build scripts are in `external/challenge-threadx-playRemote/MXChip/AZ3166/scripts/`.

### MQTT-Only Build

```bash
cd external/challenge-threadx-playRemote
# Windows:  MXChip\AZ3166\scripts\build.bat
# Linux/macOS:
./MXChip/AZ3166/scripts/build.sh
```

**Output:** `external/challenge-threadx-playRemote/MXChip/AZ3166/build/app/az3166_app.elf`

### Build with SOME/IP

```bash
cd external/challenge-threadx-playRemote
# Build for Device Role 1:
./MXChip/AZ3166/scripts/build-with-someip.sh 1
# Build for Device Role 2:
./MXChip/AZ3166/scripts/build-with-someip.sh 2
```

### Manual CMake Build

```bash
cd external/challenge-threadx-playRemote/MXChip/AZ3166
cmake -B build -GNinja \
  -DCMAKE_TOOLCHAIN_FILE=../../../cmake/arm-gcc-cortex-m4.cmake \
  -DENABLE_OPENSOMEIP=ON \
  -DSOMEIP_DEVICE_ROLE=1 \
  -DOPENSOMEIP_SOURCE_DIR=../../third_party/opensomeip
cmake --build build
```

## Configuration

### Network Configuration

Edit `external/challenge-threadx-playRemote/MXChip/AZ3166/app/cloud_config.h`:

| Setting | Default | Description |
| --- | --- | --- |
| `WIFI_SSID` | — | Target Wi-Fi network SSID |
| `WIFI_PASSWORD` | — | Wi-Fi network password |
| `MQTT_BROKER_ADDRESS` | `192.168.88.100` | MQTT broker IP (Raspberry Pi 5) |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `SOMEIP_SIGNAL_TARGET_IP` | — | Remote SOME/IP endpoint IP (when SOME/IP enabled) |
| `SOMEIP_SIGNAL_TARGET_PORT` | — | Remote SOME/IP endpoint port |
| `SOMEIP_SIGNAL_SERVICE_ID` | — | Shared SOME/IP service ID |
| `SOMEIP_SIGNAL_EVENT_ID` | — | Shared SOME/IP event ID |
| `SOMEIP_SIGNAL_CLIENT_ID` | — | SOME/IP client identifier |

## Runtime Operation

### User Interface

| Input | Action |
| --- | --- |
| **Button A** | Toggle left blinker / send left signal |
| **Button B** | Toggle right blinker / send right signal |
| **Button A + B (hold 2 sec)** | Graceful shutdown (MQTT unsubscribe/disconnect) |

### LED and Display

- **RGB LEDs**: Blink for active indicators, solid for brake
- **OLED Display**: Shows current button state and blinker status
- When SOME/IP is enabled, displays remote state: `SIP LxRxBx AxBx`

### Serial Debug

Monitor at 115200 baud for `[MQTT]`, `[SOMEIP][TX]`, and `[SOMEIP][RX]` log messages.

## Debugging

### Wireshark SOME/IP Capture

```
udp.port == 30490 || udp.port == 30500
```

Or with the SOME/IP dissector:

```
someip
```

## References

- [Eclipse ThreadX Documentation](https://learn.microsoft.com/en-us/azure/rtos/threadx/)
- [MXChip AZ3166 Documentation](https://docs.mxchip.com/en/nr6ggk/blyezpv6gkqicywi.html)
- [OpenSOME/IP Specification](https://some-ip.io/)
