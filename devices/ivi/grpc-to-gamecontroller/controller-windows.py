#!/usr/bin/python3
"""
Bridges VSS signals from the Kuksa Databroker to a virtual Xbox 360 gamepad.

Mapping:
  Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling   -> D-Pad LEFT
  Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling  -> D-Pad RIGHT
  Vehicle.Body.Lights.Brake.IsActive                        -> X button
"""

import time
from kuksa_client.grpc import VSSClient

import vgamepad as vg


# VSS paths we care about
VSS_LEFT_INDICATOR = "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling"
VSS_RIGHT_INDICATOR = "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling"
VSS_BRAKE = "Vehicle.Body.Lights.Brake.IsActive"

VSS_PATHS = [VSS_LEFT_INDICATOR, VSS_RIGHT_INDICATOR, VSS_BRAKE]


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


def _run_session(client, gamepad, interval, verbose):
    """One connected session: poll signals and drive the gamepad until the
    databroker connection drops (raises) or Ctrl-C is pressed."""

    last_left = False
    last_right = False
    last_brake = False

    while True:
        left = _read_bool(client, VSS_LEFT_INDICATOR)
        right = _read_bool(client, VSS_RIGHT_INDICATOR)
        brake = _read_bool(client, VSS_BRAKE)

        changed = False

        if left != last_left:
            if left:
                gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
            else:
                gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
            last_left = left
            changed = True
            if verbose:
                print(f"LEFT indicator -> {left}")

        if right != last_right:
            if right:
                gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
            else:
                gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
            last_right = right
            changed = True
            if verbose:
                print(f"RIGHT indicator -> {right}")

        if brake != last_brake:
            if brake:
                gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
            else:
                gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
            last_brake = brake
            changed = True
            if verbose:
                print(f"BRAKE -> {brake}")

        if changed:
            gamepad.update()

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
    them as virtual gamepad button presses.

    The databroker connection is established with an exponential back-off retry
    loop — the script will wait until the databroker comes up and will
    automatically reconnect if the connection drops mid-run.

    Parameters:
        databroker_host     (str)   : Databroker hostname or IP.
        databroker_port     (int)   : Databroker port.
        interval            (float) : Polling interval in seconds (default: 0.05).
        verbose             (bool)  : Print state changes to stdout.
        reconnect_delay     (float) : Initial reconnect back-off in seconds.
        reconnect_delay_max (float) : Maximum reconnect back-off in seconds.
    """
    gamepad = vg.VX360Gamepad()

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
                # Make sure no button is "stuck" while we wait for the broker.
                gamepad.reset()
                gamepad.update()
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

            # Release everything between sessions so a temporary outage doesn't
            # leave a button latched while we reconnect.
            gamepad.reset()
            gamepad.update()
            time.sleep(delay)
            delay = min(delay * 2.0, reconnect_delay_max)
    except KeyboardInterrupt:
        print("Shutdown requested.")
    finally:
        gamepad.reset()
        gamepad.update()


if __name__ == "__main__":
    import argparse

    description = (
        "Bridges Kuksa VSS signals (turn indicators + brake light) to a "
        "virtual Xbox 360 gamepad."
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
