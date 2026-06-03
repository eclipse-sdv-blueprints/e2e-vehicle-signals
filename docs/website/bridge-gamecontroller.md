---
sidebar_position: 14
title: Kuksa → Virtual Gamepad Bridge
---

# Kuksa → Virtual Gamepad Bridge

The **Kuksa-to-Gamepad bridge** turns live VSS signals into virtual Xbox 360 controller input on a Windows host, so any XInput-aware game (such as **SuperTux**) can be driven by the same demo signals the rest of the blueprint uses.

It complements the [IVI Head Unit (LIVI)](./device-ivi-livi.md) and the [MQTT-to-Kuksa gRPC Bridge](./bridge-mqtt-grpc.md) as a third consumer of the central databroker.

Source: [`devices/ivi/grpc-to-gamecontroller/`](https://github.com/eclipse-sdv-blueprints/e2e-vehicle-signals/tree/main/devices/ivi/grpc-to-gamecontroller)

## Role in the system

```mermaid
flowchart LR
    subgraph PI5["Raspberry Pi 5 (Ankaios)"]
        KDB[Kuksa Databroker<br/>gRPC :55555]
    end
    subgraph WIN["Windows gaming host"]
        CTRL[controller.py<br/>VSSClient + vgamepad]
        VGEM[ViGEmBus<br/>virtual Xbox 360 device]
        GAME[SuperTux / XInput game]
        CTRL -->|XUSB_BUTTON.*| VGEM
        VGEM -.XInput.-> GAME
    end
    KDB -->|get_current_values| CTRL
```

## Signal mapping

| VSS path | Gamepad action |
| --- | --- |
| `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` | D-Pad **LEFT** held while `true` |
| `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` | D-Pad **RIGHT** held while `true` |
| `Vehicle.Body.Lights.Brake.IsActive` | **X** button held while `true` |

Edge-detected: a press / release is only sent when a signal actually changes, so a turn-indicator pulse keeps the D-Pad held for the full duration of the VSS state.

## Requirements

- **Windows 10/11** — `vgamepad` is backed by [ViGEmBus](https://github.com/nefarius/ViGEmBus), which is Windows-only.
- **Python 3.10+**
- **ViGEmBus driver** installed (one-time, from the link above).
- Network reach to the Pi 5's Kuksa Databroker (default `192.168.88.100:55555`).

## Install

```powershell
cd devices\ivi\grpc-to-gamecontroller
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Install SuperTux (demo target game)

On Debian / Ubuntu / Raspberry Pi OS:

```bash
sudo apt update
sudo apt install supertux
```

On Windows:

```powershell
winget install SuperTuxTeam.SuperTux
```

Inside SuperTux, open **Options → Controls → Joystick** once and re-bind actions to the `Xbox 360 Controller for Windows` device so the D-Pad and `X` button are recognised.

## Run

```powershell
python controller.py --host 192.168.88.100 --port 55555 --verbose
```

| Flag | Default | Description |
| --- | --- | --- |
| `-th`, `--host` | `localhost` | Kuksa Databroker hostname / IP |
| `-tp`, `--port` | `55555` | Kuksa Databroker port |
| `-i`, `--interval` | `0.05` | Poll interval in seconds |
| `--verbose` | off | Log every signal state change |
| `--reconnect-delay` | `2.0` | Initial reconnect back-off in seconds |
| `--reconnect-delay-max` | `30.0` | Maximum reconnect back-off in seconds |

## Connection stability

The bridge **never exits** because the databroker isn't up yet:

- On startup, if `client.connect()` fails it logs `Kuksa connect failed (…) — retrying in Xs` and waits.
- Back-off is **exponential** (×2 per failure) and capped at `--reconnect-delay-max`; it resets to `--reconnect-delay` on every successful connect.
- If the gRPC connection drops mid-run it logs `Kuksa connection lost (…) — retrying in Xs` and reconnects.
- Between reconnects the virtual gamepad is reset, so a transient outage cannot leave the indicator D-Pad or the `X` button latched.

This mirrors the connection behaviour of the [Kuksa-to-LIVI Telemetry Bridge](./device-ivi-livi.md), so the controller bridge can be started in any order relative to the databroker.

## Troubleshooting

- **`OSError: ViGEmBus is not installed`** — install the driver from <https://github.com/nefarius/ViGEmBus/releases> and reboot.
- **Gamepad detected but no input in-game** — bind the gamepad inside the game's controls menu; some games need the controller plugged in *before* startup.
- **Connect log loop with no recovery** — confirm the Pi 5's databroker is exposing `:55555` on the LAN (`ss -ltn | grep 55555`) and that the Windows host can reach it (`Test-NetConnection 192.168.88.100 -Port 55555`).
- **Buttons stay stuck after an abnormal exit** — re-run the script and exit cleanly with `Ctrl-C` (clean exit calls `gamepad.reset()`), or unplug/replug the virtual device via Device Manager.

## Related pages

- [Architecture](./architecture.md)
- [Signal Mapping](./signal-mapping.md)
- [IVI Head Unit (LIVI)](./device-ivi-livi.md)
- [MQTT-to-Kuksa gRPC Bridge](./bridge-mqtt-grpc.md)
