# Kuksa → Virtual Gamepad Bridge

Bridges VSS signals from the [Kuksa Databroker](https://github.com/eclipse-kuksa/kuksa-databroker) to a **virtual Xbox 360 gamepad**, so any game that accepts an XInput controller can be driven by the demo signals.

Built for the motorbike-blinker demo — left/right turn indicators steer, the brake light fires the `X` button (e.g. SuperTux "action").

| VSS path | Gamepad action |
| --- | --- |
| `Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling` | D-Pad **LEFT** (held while `true`) |
| `Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling` | D-Pad **RIGHT** (held while `true`) |
| `Vehicle.Body.Lights.Brake.IsActive` | **X** button (held while `true`) |

Two platform-specific entry points are provided — pick the one matching the host where the game runs:

| Script | Platform | Backend |
| --- | --- | --- |
| `controller-windows.py` | Windows 10/11 | [`vgamepad`](https://pypi.org/project/vgamepad/) + [ViGEmBus](https://github.com/nefarius/ViGEmBus) (virtual Xbox 360) |
| `controller-linux.py`   | Linux | [`evdev`](https://python-evdev.readthedocs.io/) + `/dev/uinput` (Xbox-style HID) |

Both share the same CLI flags, the same VSS mapping, and the same exponential-backoff reconnect logic.

## Requirements

- **Python 3.10+** on the host running the bridge.
- A reachable Kuksa Databroker (e.g. `192.168.88.100:55555` on the Pi 5).
- **Windows variant:** the [ViGEmBus driver](https://github.com/nefarius/ViGEmBus/releases) installed (one-time).
- **Linux variant:** the `uinput` kernel module loaded and `/dev/uinput` writable by the running user. Either:
  - run the script with `sudo`, **or**
  - add a udev rule so your user (or the `input` group) can open `/dev/uinput`:

    ```bash
    sudo modprobe uinput
    echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' \
      | sudo tee /etc/udev/rules.d/99-uinput.rules
    sudo udevadm control --reload-rules && sudo udevadm trigger
    sudo usermod -aG input "$USER"   # log out + back in for this to take effect
    ```

## Install

### Install `pip` (if missing)

`pip` ships with the official Python distributions, but some minimal Linux
installs (e.g. Raspberry Pi OS Lite, Debian Slim) ship Python without it.

**Windows** — installed automatically with the [python.org installer](https://www.python.org/downloads/windows/).
If it's somehow missing, bootstrap with `ensurepip`:

```powershell
python -m ensurepip --upgrade
python -m pip install --upgrade pip
```

**Linux (Debian / Ubuntu / Raspberry Pi OS):**

```bash
sudo apt update
sudo apt install python3-pip python3-venv
python3 -m pip install --upgrade pip
```

**Linux (Fedora / RHEL):**

```bash
sudo dnf install python3-pip
python3 -m pip install --upgrade pip
```

Verify with `pip --version` (or `python -m pip --version`).

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The `requirements.txt` uses PEP-508 platform markers, so `vgamepad` is only pulled in on Windows and `evdev` only on Linux.

### Install SuperTux (the demo target game)

On Debian / Ubuntu / Raspberry Pi OS:

```bash
sudo apt update
sudo apt install supertux
```

On Windows: download from <https://www.supertux.org/download.html> or install via `winget install SuperTuxTeam.SuperTux`.

Inside SuperTux, open **Options → Controls → Joystick** once and re-bind the actions to the virtual gamepad device (it shows up as `Xbox 360 Controller for Windows` on Windows and `Kuksa Virtual Gamepad` on Linux). Confirm that the D-Pad and the `X` button are detected.

## Run

Windows:

```powershell
python controller-windows.py --host 192.168.88.100 --port 55555 --verbose
```

Linux:

```bash
python controller-linux.py --host 192.168.88.100 --port 55555 --verbose
```

CLI flags (identical for both scripts):

| Flag | Default | Description |
| --- | --- | --- |
| `-th`, `--host` | `localhost` | Kuksa Databroker hostname / IP |
| `-tp`, `--port` | `55555` | Kuksa Databroker port |
| `-i`, `--interval` | `0.05` | Poll interval in seconds |
| `--verbose` | off | Log every signal state change to stdout |
| `--reconnect-delay` | `2.0` | Initial reconnect back-off in seconds |
| `--reconnect-delay-max` | `30.0` | Maximum reconnect back-off in seconds |

Stop the bridge with `Ctrl-C`; the script resets the virtual gamepad on exit so no button is left "stuck".

## Connection stability

The script **never exits** because the databroker isn't reachable — it logs

```
Kuksa connect failed (...) — retrying in Xs
```

sleeps with an **exponential back-off** capped at `--reconnect-delay-max`, and
keeps trying. The same applies if the gRPC connection drops mid-run: a
`Kuksa connection lost (...) — retrying in Xs` is logged and the script
reconnects automatically (the back-off resets on every successful connect).
Between reconnects the virtual gamepad is reset, so a transient outage cannot
leave the turn indicator or brake button latched.

This mirrors the resilient connection behaviour of the
[Kuksa-to-LIVI Telemetry Bridge](../../raspberry-pi5/grpc-to-LIVI-telemetry-bridge/README.md),
so the controller bridge can be started in any order relative to the
databroker.

## How it works

1. Connects to the databroker via `kuksa_client.grpc.VSSClient`.
2. Polls the three signals every `--interval` seconds.
3. Performs **edge detection**: `press_button` / `release_button` is only called when a signal actually changes, so the held-button behaviour matches the underlying VSS state (good for turn-indicator pulses).
4. Coerces VSS values to `bool` — accepts native bools, `0/1`, and string forms (`"true"`, `"on"`, `"active"`, …) since the brake light is published as a string in the demo's `grpc-mqtt.yaml`.

## Troubleshooting

### Windows

- **`OSError: ViGEmBus is not installed`** — install the driver from the link above and reboot.
- **Buttons stay stuck after an abnormal exit** — re-run the script and exit cleanly with `Ctrl-C`, or unplug/replug the virtual device via Device Manager.

### Linux

- **`PermissionError: [Errno 13] Permission denied: '/dev/uinput'`** — apply the udev rule above (or run with `sudo` as a quick check). Re-login after `usermod -aG input`.
- **`FileNotFoundError: /dev/uinput`** — load the kernel module: `sudo modprobe uinput` (add to `/etc/modules-load.d/uinput.conf` to persist).
- **Game doesn't see a gamepad** — verify the virtual device exists with `ls /dev/input/by-id/ | grep -i kuksa` or `evtest`, and that SDL/the game picks it up (`SDL_GAMECONTROLLER_USE_BUTTON_LABELS=1 jstest /dev/input/jsX`).

### Both

- **Gamepad detected but no input in-game** — bind the gamepad inside the game's controls menu; some games need the controller plugged in *before* startup.
- **`Failed to connect to Kuksa Data Broker`** — the script no longer aborts on this; it keeps retrying with back-off. Check `--host` / `--port`, that the databroker is reachable (firewall / TLS settings), and watch for the periodic retry log line.
