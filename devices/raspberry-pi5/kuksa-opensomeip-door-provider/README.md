# Kuksa OpenSOME/IP Door Provider

This provider uses `vtz/opensomeip` for SOME/IP-over-UDP transport and a copied,
Apache-2.0 licensed Kuksa Databroker feeder from `kuksa-someip-provider`.

It implements the current minimal door contract without service discovery:

| Direction | Service | Event | Payload | UDP port |
| --- | --- | --- | --- | --- |
| Door ECU to provider | `0x4301` | `0x8001` | `0` closed, `1` open | `30500` |
| Provider to door ECU | `0x4301` | `0x8002` | `0` close, `1` open | `30501` |

The provider writes incoming events to the current value of
`Vehicle.Cabin.Door.Row1.DriverSide.IsOpen` and subscribes to the same path's
actuator target value for outgoing commands.

Run with host networking:

```sh
podman run --rm --net=host kuksa-opensomeip-door-provider:latest \
  --broker localhost:55555 --door-host 192.168.88.101
```
