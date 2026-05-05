---
sidebar_position: 3
title: Hardware Bill of Materials
---

# Hardware Bill of Materials

This page lists all hardware components needed to reproduce the full demo setup.

## Core Components

| Qty | Component | Purpose | Notes |
| --- | --- | --- | --- |
| 1 | [Raspberry Pi 5 (Bundle)](https://www.raspberrypi.com/products/raspberry-pi-5/) | Main compute node (HPC) | 4 GB or 8 GB RAM recommended; bundle includes power supply, case, and SD card |
| 1 | [RS485 CAN Hat (Waveshare)](https://www.waveshare.com/rs485-can-hat.htm) | CAN bus interface for the Raspberry Pi 5 | Directly mounts on the GPIO header |
| 1 | [SunFounder Elite Explorer Kit with Arduino Uno R4 WiFi](https://www.sunfounder.com/collections/kits-with-orignal-arduino-board/products/sunfounder-elite-explorer-kit-with-official-arduino-uno-r4-wifi) | Joystick input ECU | Includes analog joystick module and breadboard |
| 1 | [Arduino Uno R4 WiFi](https://www.digikey.de/de/products/detail/arduino/ABX00087/20371539) | LED control ECU | Drives the WS2812 LED strip via MCP2515 CAN |
| 1 | [MCP2515 CAN Bus Module (TJA1050)](https://www.amazon.de/5PCS-MCP2515-CAN-Module-TJA1050/dp/B0CJCPLMCW) | CAN transceiver for the LED control Arduino | 8 MHz crystal variant |
| 1 | WS2812 LED Strip (8 LEDs) | Physical turn-indicator and brake-light output | Typically included in the SunFounder kit or available separately |
| 1 | 10″ HDMI Display (optional) | Dashboard display for the Raspberry Pi 5 | Connect via HDMI; power via USB |

## Optional Components

| Qty | Component | Purpose | Notes |
| --- | --- | --- | --- |
| 1 | [Raspberry Pi 4 (Bundle)](https://www.raspberrypi.com/) | Secondary HPC / Fleet Analysis host | Placeholder for split deployment |
| 1 | Arduino Uno R4 WiFi + RC522 RFID Module | Door / driver-ID ECU | SPI-connected RFID reader |
| 2 | [MXChip AZ3166](https://www.seeedstudio.com/AZ3166-IOT-Developer-Kit.html) | ThreadX SOME/IP extension | Wi-Fi + buttons + OLED display |

## Wiring Summary

### Joystick ECU (Arduino Uno R4 WiFi)

The joystick connects to analog pins on the Arduino. No CAN hardware is needed — communication is over Wi-Fi/MQTT.

### LED Control ECU (Arduino Uno + MCP2515)

| MCP2515 Pin | Arduino Pin |
| --- | --- |
| VCC | 5 V |
| GND | GND |
| CS | D10 (SPI SS) |
| SO | D12 (SPI MISO) |
| SI | D11 (SPI MOSI) |
| SCK | D13 (SPI SCK) |
| INT | D2 |

The WS2812 LED strip data line connects to a digital output pin (see sketch for the exact pin).

### Raspberry Pi 5 + CAN Hat

The Waveshare RS485 CAN Hat mounts directly on the Pi 5 GPIO header. The device tree overlay must be added to `config.txt`:

```
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
```

### CAN Bus Wiring

Connect the **CAN_H** and **CAN_L** lines between the Waveshare CAN Hat on the Raspberry Pi 5 and the MCP2515 module on the LED control Arduino. Use twisted-pair wiring and add 120 Ω termination resistors at each end of the bus.

## Software Requirements

| Component | Version |
| --- | --- |
| Ubuntu (RPi 5) | 24.04 LTS |
| Eclipse Ankaios | 0.7.0 |
| Kuksa Databroker | 0.6.0 |
| Kuksa CAN Provider | 0.4.4 |
| Podman | Latest from Ubuntu repos |
| Docker + Docker Compose | Latest from Ubuntu repos |
| Arduino IDE | 2.x |
| Python | 3.11+ (for MQTT-to-gRPC bridge) |

## Device Documentation

For detailed setup, configuration and firmware instructions for each device, see:

- [Joystick Input ECU](./device-joystick-ecu) — Arduino joystick wiring and MQTT config
- [LED Control ECU](./device-led-ecu) — MCP2515 wiring, CAN protocol and LED allocation
- [RFID Door ECU](./device-rfid-ecu) — RC522 RFID reader setup
- [ThreadX SOME/IP ECU](./device-threadx-ecu) — MXChip AZ3166 build and SOME/IP configuration
