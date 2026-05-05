# Driver Input ECU (ThreadX board)

This node represents a ThreadX IoT board (MXChip AZ3166) with buttons and an OLED display for blinker status. It serves as an edge device that captures button input and communicates vehicle signals over the network using MQTT and/or SOME/IP protocols.

## Hardware

**Board:** MXChip AZ3166

**Key Features:**
- STM32F412RG MCU (100MHz, 1MB flash, 256KB SRAM)
- 128×64 OLED display for status visualization
- RGB LED indicators controlled by P9813
- Two buttons for user input
- WiFi connectivity (2.4GHz)
- Temperature/Humidity sensor (HTS221)
- Atmospheric pressure sensor (LPS22HB)

## Responsibilities

- Capture button input from two buttons on the board
- Display current blinker/brake status on the OLED display
- Publish and subscribe to VSS (Vehicle Signal Specification) signals over MQTT
- Support SOME/IP protocol for bi-directional signal communication with other ECUs
- Control RGB LEDs to indicate blinker and brake states

## Architecture

The application runs on Eclipse ThreadX with Eclipse ThreadX NetX Duo for networking. It supports two communication modes:

1. **MQTT Mode** (default): Communicates with an MQTT broker on the network
2. **SOME/IP Mode** (optional): Direct UDP-based vehicle signal communication using OpenSOME/IP

Both modes can be enabled simultaneously for flexible signal distribution.

## Prerequisites

### Development Environment

The source code is built using:
- **CMake** 3.15 or later
- **Ninja** build system
- **Arm GNU Embedded Toolchain** (arm-none-eabi-gcc)
- **Git** with submodule support

### Installation

#### Windows
```powershell
winget install --id=Arm.GnuArmEmbeddedToolchain -e
winget install --id=Ninja-build.Ninja -e
winget install --id=Kitware.CMake -e
```

#### Ubuntu/Linux
```bash
sudo apt install ninja-build cmake

# Download and install Arm GNU Toolchain 13.3.rel1
wget https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi.tar.xz
sudo tar xJf arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi.tar.xz -C /opt

# Add to PATH
export PATH=$PATH:/opt/arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi/bin
```

#### macOS
Download and install the appropriate package for your CPU architecture from [Arm GNU Toolchain Downloads](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)

### Project Setup

Ensure submodules are initialized:
```bash
cd ../../..  # Navigate to eclipse-sdv-e2e-demo-blueprint root
git submodule init
git submodule update --recursive
```

## Building the Application

The build scripts are located in `external/challenge-threadx-playRemote/MXChip/AZ3166/scripts/`

### Option 1: Default Build (MQTT only)

**Windows**
```bat
cd external\challenge-threadx-playRemote
MXChip\AZ3166\scripts\build.bat
```

**Linux / macOS**
```bash
cd external/challenge-threadx-playRemote
./MXChip/AZ3166/scripts/build.sh
```

**Output:** `external/challenge-threadx-playRemote/MXChip/AZ3166/build/app/az3166_app.elf`

### Option 2: Build with OpenSOME/IP Support

This option enables direct SOME/IP communication for low-latency vehicle signal distribution between ECUs.

**Windows**
```bat
cd external\challenge-threadx-playRemote
MXChip\AZ3166\scripts\build-with-someip.bat 1
MXChip\AZ3166\scripts\build-with-someip.bat 2
```

**Linux / macOS**
```bash
cd external/challenge-threadx-playRemote
./MXChip/AZ3166/scripts/build-with-someip.sh 1
./MXChip/AZ3166/scripts/build-with-someip.sh 2
```

**Manual Build (Optional):**

**Windows (PowerShell)**
```powershell
cd external/challenge-threadx-playRemote/MXChip/AZ3166
cmake -B build -GNinja `
  -DCMAKE_TOOLCHAIN_FILE="../../../cmake/arm-gcc-cortex-m4.cmake" `
  -DENABLE_OPENSOMEIP=ON `
  -DSOMEIP_DEVICE_ROLE=1 `
  -DOPENSOMEIP_SOURCE_DIR="../../third_party/opensomeip"
cmake --build build
```

**Linux / macOS**
```bash
cd external/challenge-threadx-playRemote/MXChip/AZ3166
cmake -B build -GNinja \
  -DCMAKE_TOOLCHAIN_FILE=../../../cmake/arm-gcc-cortex-m4.cmake \
  -DENABLE_OPENSOMEIP=ON \
  -DSOMEIP_DEVICE_ROLE=1 \
  -DOPENSOMEIP_SOURCE_DIR=../../third_party/opensomeip
cmake --build build
```

**Parameters:**
- `SOMEIP_DEVICE_ROLE`: Set to `1` or `2` to select the local/target SOME/IP endpoint profile
  - Role 1: Local IP 192.168.88.91:30490, Target 192.168.88.92:30500
  - Role 2: Local IP 192.168.88.92:30500, Target 192.168.88.91:30490

## Configuration

### Network Configuration

Edit `external/challenge-threadx-playRemote/MXChip/AZ3166/app/cloud_config.h` to configure:

- **WiFi Credentials:**
  - `WIFI_SSID`: Target WiFi network SSID
  - `WIFI_PASSWORD`: WiFi network password

- **MQTT Settings:**
  - `MQTT_BROKER_ADDRESS`: IP address of MQTT broker (default: 192.168.88.100)
  - `MQTT_BROKER_PORT`: MQTT broker port (default: 1883)

- **SOME/IP Settings (when enabled):**
  - `SOMEIP_SIGNAL_TARGET_IP`: Remote SOME/IP endpoint IP
  - `SOMEIP_SIGNAL_TARGET_PORT`: Remote SOME/IP endpoint port
  - `SOMEIP_SIGNAL_SERVICE_ID`: Shared service ID
  - `SOMEIP_SIGNAL_EVENT_ID`: Shared event ID
  - `SOMEIP_SIGNAL_CLIENT_ID`: Client identifier

### Payload Format

**MQTT Topic:** `InVehicleTopics`

**SOME/IP Payload:** 5 bytes `[left, right, brake, button_a, button_b]` (each value is 0 or 1)

## Runtime Operation

### User Interface

- **Button A:** Toggle left blinker / Send left signal
- **Button B:** Toggle right blinker / Send right signal
- **Button A + B (hold 2 sec):** Graceful shutdown (MQTT unsubscribe/disconnect)

### LED Display

**RGB LEDs:**
- **Left indicator:** Blinks when left blinker is active
- **Right indicator:** Blinks when right blinker is active
- **Brake indicator:** Solid when brake is active

**OLED Display:**
- Shows current button state and blinker status
- When SOME/IP is enabled, displays remote state: `SIP LxRxBx AxBx`

### Serial Debug Output

Monitor the serial port (115200 baud) for debug logs:
- `[MQTT]` messages for MQTT activity
- `[SOMEIP][TX]` for transmitted SOME/IP notifications
- `[SOMEIP][RX]` for received SOME/IP notifications

## Debugging

### Packet Capture

To verify SOME/IP UDP traffic using Wireshark:

**Display filter:**
```
udp.port == 30490 || udp.port == 30500
```

Or if SOME/IP dissector is available:
```
someip
```

## References

- [Eclipse ThreadX Documentation](https://learn.microsoft.com/en-us/azure/rtos/threadx/)
- [MXChip AZ3166 Documentation](https://docs.mxchip.com/en/nr6ggk/blyezpv6gkqicywi.html)
- [Challenge ThreadX Project](../../../external/challenge-threadx-playRemote)
- [OpenSOME/IP Specification](https://some-ip.io/)

## Status

The application is fully functional for both MQTT and SOME/IP communication modes. It demonstrates signal aggregation and distribution patterns for edge ECU nodes in the vehicle architecture.
