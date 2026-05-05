# Raspberry Pi 4 (HCP / Connectivity Unit)

This node coordinates blinking logic or higher‑level control loops that sit above the CAN‑connected Arduino ECU.

## Suggested stack

- Linux distribution suitable for Raspberry Pi 5
- Eclipse S‑CORE or equivalent runtime for higher‑level control apps
- Network connectivity (Ethernet/Wi‑Fi) to the Raspberry Pi 5 and Fleet Management services

## Responsibilities

- Orchestrate or override blinker requests when required.
- Emit VSS signals to the Kuksa Databroker (through the Raspberry Pi 5).
