#!/usr/bin/python3
"""
Linux equivalent of controller-windows.py.

Bridges VSS signals from the Kuksa Databroker to a virtual gamepad created
through the kernel's uinput subsystem (via python-evdev).

Mapping (Xbox-style layout, as read by SDL2 / SuperTux / SuperTuxKart / Steam):
  Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling   -> D-Pad LEFT  (ABS_HAT0X = -1)
  Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling  -> D-Pad RIGHT (ABS_HAT0X = +1)
  Vehicle.Body.Lights.Brake.IsActive                        -> X button   (BTN_WEST)

Requirements:
  - Linux with /dev/uinput available (modprobe uinput; ensure user has rw access,
    e.g. via a udev rule or by adding the user to the `input` group).
  - pip install python-evdev kuksa-client

Run as a regular user once /dev/uinput is writable:
  python controller-linux.py --host 192.168.88.100 --port 55555 --verbose
"""

import os
import sys
import time
from kuksa_client.grpc import VSSClient

from evdev import UInput, AbsInfo, ecodes as e
from evdev.uinput import UInputError


# VSS paths we care about
VSS_LEFT_INDICATOR = "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling"
VSS_RIGHT_INDICATOR = "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling"
VSS_BRAKE = "Vehicle.Body.Lights.Brake.IsActive"

VSS_PATHS = [VSS_LEFT_INDICATOR, VSS_RIGHT_INDICATOR, VSS_BRAKE]


# Vendor/product IDs of the wired Xbox 360 controller — many games (and SDL2)
# special-case this combination, so reusing it gives the best chance of being
# recognised as a proper gamepad rather than a generic keyboard.
XBOX360_VENDOR_ID = 0x045E
XBOX360_PRODUCT_ID = 0x028E


def _coerce_bool(value):
    """Convert Kuksa values (bool, int, or string like 'true'/'on') to bool."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "on", "yes", "active")
    return bool(value)


def _read_bool(client, path):
    datapoint = client.get_current_values([path]).get(path)
    if datapoint is None:
        return False
    return _coerce_bool(datapoint.value)


def _make_gamepad():
    """Create a uinput virtual gamepad with the bare minimum capabilities we
    actually drive (D-Pad hat + the four face buttons), padded out with the
    common Xbox-360 buttons so SDL recognises it as `XInput` / `Xbox`."""

    capabilities = {
        e.EV_KEY: [
            e.BTN_SOUTH,   # A
            e.BTN_EAST,    # B
            e.BTN_WEST,    # X   <- our brake binding
            e.BTN_NORTH,   # Y
            e.BTN_TL,      # LB
            e.BTN_TR,      # RB
            e.BTN_SELECT,  # Back
            e.BTN_START,   # Start
            e.BTN_MODE,    # Guide
            e.BTN_THUMBL,
            e.BTN_THUMBR,
        ],
        e.EV_ABS: [
            (e.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
            (e.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        ],
    }

    return UInput(
        events=capabilities,
        name="Kuksa Virtual Gamepad",
        vendor=XBOX360_VENDOR_ID,
        product=XBOX360_PRODUCT_ID,
        version=0x0110,
    )


_UINPUT_PERMISSION_HINT = """
Cannot open /dev/uinput for writing.

Pick one of the following:

  1. Run this script with sudo (quick check):
       sudo python controller-linux.py ...

  2. Grant your user permanent access (recommended):
       sudo modprobe uinput
       echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' \\
         | sudo tee /etc/udev/rules.d/99-uinput.rules
       sudo udevadm control --reload-rules && sudo udevadm trigger
       sudo usermod -aG input "$USER"
     Then log out and back in (or reboot) for the new group to take effect.

If /dev/uinput does not exist at all, load the kernel module:
       sudo modprobe uinput
(persist with `echo uinput | sudo tee /etc/modules-load.d/uinput.conf`)
""".strip()


def _make_gamepad_or_exit():
    try:
        return _make_gamepad()
    except (PermissionError, UInputError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if not os.path.exists("/dev/uinput"):
            print("ERROR: /dev/uinput is missing — run `sudo modprobe uinput`.", file=sys.stderr)
        print(_UINPUT_PERMISSION_HINT, file=sys.stderr)
        sys.exit(1)


def _reset_gamepad(gamepad):
    """Release everything so no button / hat is left held."""
    gamepad.write(e.EV_KEY, e.BTN_WEST, 0)
    gamepad.write(e.EV_ABS, e.ABS_HAT0X, 0)
    gamepad.write(e.EV_ABS, e.ABS_HAT0Y, 0)
    gamepad.syn()


def _run_session(client, gamepad, interval, verbose):
    """One connected session: poll signals and drive the gamepad until the
    databroker connection drops (raises) or Ctrl-C is pressed."""

    last_left = False
    last_right = False
    last_brake = False
    last_hat_x = 0  # current ABS_HAT0X value emitted

    while True:
        left = _read_bool(client, VSS_LEFT_INDICATOR)
        right = _read_bool(client, VSS_RIGHT_INDICATOR)
        brake = _read_bool(client, VSS_BRAKE)

        changed = False

        # D-Pad horizontal axis: -1 = left, +1 = right, 0 = centre.
        # If both indicators are on (hazard lights), prefer centred so the game
        # doesn't see a jittery axis.
        if left and not right:
            new_hat_x = -1
        elif right and not left:
            new_hat_x = 1
        else:
            new_hat_x = 0

        if new_hat_x != last_hat_x:
            gamepad.write(e.EV_ABS, e.ABS_HAT0X, new_hat_x)
            last_hat_x = new_hat_x
            changed = True
            if verbose:
                print(f"D-Pad X -> {new_hat_x} (L={left} R={right})", flush=True)

        if left != last_left:
            last_left = left
            if verbose:
                print(f"LEFT indicator -> {left}", flush=True)

        if right != last_right:
            last_right = right
            if verbose:
                print(f"RIGHT indicator -> {right}", flush=True)

        if brake != last_brake:
            gamepad.write(e.EV_KEY, e.BTN_WEST, 1 if brake else 0)
            last_brake = brake
            changed = True
            if verbose:
                print(f"BRAKE -> {brake}", flush=True)

        if changed:
            gamepad.syn()

        time.sleep(interval)


def fetch_and_update_control(
    databroker_host,
    databroker_port,
    interval=0.05,
    verbose=False,
    reconnect_delay=2.0,
    reconnect_delay_max=30.0,
):
    """
    Reads indicator and brake signals from the Kuksa Databroker and forwards
    them as virtual gamepad events through /dev/uinput.

    The databroker connection is established with an exponential back-off retry
    loop — the script will wait until the databroker comes up and will
    automatically reconnect if the connection drops mid-run.
    """
    gamepad = _make_gamepad_or_exit()
    print(f"Created virtual gamepad: {gamepad.device.path}", flush=True)

    delay = reconnect_delay
    try:
        while True:
            client = VSSClient(databroker_host, databroker_port)
            try:
                client.connect()
            except Exception as exc:
                print(
                    f"Kuksa connect failed ({exc}) — retrying in {delay:.1f}s",
                    flush=True,
                )
                _reset_gamepad(gamepad)
                time.sleep(delay)
                delay = min(delay * 2.0, reconnect_delay_max)
                continue

            print(
                f"Connected to Kuksa Data Broker at {databroker_host}:{databroker_port}.",
                flush=True,
            )
            delay = reconnect_delay  # reset back-off on a successful connect

            try:
                _run_session(client, gamepad, interval, verbose)
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001
                print(
                    f"Kuksa connection lost ({exc}) — retrying in {delay:.1f}s",
                    flush=True,
                )
            finally:
                try:
                    client.disconnect()
                except Exception:
                    pass

            _reset_gamepad(gamepad)
            time.sleep(delay)
            delay = min(delay * 2.0, reconnect_delay_max)
    except KeyboardInterrupt:
        print("Shutdown requested.")
    finally:
        _reset_gamepad(gamepad)
        try:
            gamepad.close()
        except Exception:
            pass


if __name__ == "__main__":
    import argparse

    description = (
        "Bridges Kuksa VSS signals (turn indicators + brake light) to a "
        "virtual gamepad via uinput (Linux)."
    )
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        "-th", "--host", type=str, default="localhost",
        help="Hostname of the Kuksa Data Broker (default: localhost)",
    )
    parser.add_argument(
        "-tp", "--port", type=int, default=55555,
        help="Port of the Kuksa Data Broker (default: 55555)",
    )
    parser.add_argument(
        "-i", "--interval", type=float, default=0.05,
        help="Polling interval in seconds (default: 0.05)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print signal state changes to stdout",
    )
    parser.add_argument(
        "--reconnect-delay", type=float, default=2.0,
        help="Initial reconnect back-off in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--reconnect-delay-max", type=float, default=30.0,
        help="Maximum reconnect back-off in seconds (default: 30.0)",
    )

    args = parser.parse_args()

    fetch_and_update_control(
        databroker_host=args.host,
        databroker_port=args.port,
        interval=args.interval,
        verbose=args.verbose,
        reconnect_delay=args.reconnect_delay,
        reconnect_delay_max=args.reconnect_delay_max,
    )
