# Kuksa OpenSOME/IP Door Provider

This provider uses `vtz/opensomeip` for SOME/IP-over-UDP transport and a copied, Apache-2.0 licensed Kuksa Databroker feeder from `kuksa-someip-provider`.

It implements the current minimal door contract without service discovery:

| Direction | Service | Event | Payload | UDP port |
| --- | --- | --- | --- | --- |
| Door ECU to provider | `0x4301` | `0x8001` | `0` closed, `1` open | `30500` |
| Provider to door ECU | `0x4301` | `0x8002` | `0` close, `1` open | `30501` |

The provider writes incoming events to the current value of
`Vehicle.Cabin.Door.Row1.DriverSide.IsOpen` and subscribes to the same path's
actuator target value for outgoing commands.

## Run locally

```bash
cmake -S . -B build -DBUILD_TESTS=OFF -DBUILD_EXAMPLES=OFF -DOPENSOMEIP_SOURCE_DIR=../../../external/opensomeip
cmake --build build --parallel
./build/kuksa-opensomeip-door-provider --broker localhost:55555 --door-host 192.168.88.101
```

## Container

```bash
docker build -t kuksa-opensomeip-door-provider -f devices/raspberry-pi5/kuksa-opensomeip-door-provider/Dockerfile .
docker run --rm --net=host kuksa-opensomeip-door-provider \
  --broker localhost:55555 --door-host 192.168.88.101
```

The published image is available at `ghcr.io/<owner>/e2e-vehicle-signals/kuksa-opensomeip-door-provider:main` (built by the [`publish-kuksa-opensomeip-door-provider`](../../../.github/workflows/publish-kuksa-opensomeip-door-provider.yml) workflow).

## Local tests
Start the Kuksa databroker
````
docker run -d \
  --name kuksa-databroker \
  --restart unless-stopped \
  --network host \
  ghcr.io/eclipse-kuksa/kuksa-databroker:0.6.0
````
Start the kuksa-opensomeip-door-provider with the right IP to the door host!
````
docker run --rm --net=host kuksa-opensomeip-door-provider \
  --broker localhost:55555 --door-host 192.168.88.101
````


Start the Kuksa client:
````
docker run -it --rm --network host \
  ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main \
  --server http://127.0.0.1:55555 \
  --protocol kuksa.val.v1
````
````
actuate Vehicle.Cabin.Door.Row1.DriverSide.IsOpen true
actuate Vehicle.Cabin.Door.Row1.DriverSide.IsOpen false
````