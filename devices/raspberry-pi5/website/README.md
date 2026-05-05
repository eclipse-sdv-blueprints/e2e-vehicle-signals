# Raspberry Pi 5 Interactive Demo Website

This folder contains an interactive website for live audience explanations on the Raspberry Pi 5 display.

## What is implemented

The website has three views:

1. **Architecture**
   - Graphical component map inspired by [full-architecture.puml](../../../docs/full-architecture.puml).
   - Uses [demostrator-bg.png](../../../docs/demostrator-bg.png) as the visual background.
   - Live connection lines are highlighted when active.

2. **Signal Flow**
   - Live workflow lanes based on [communication-workflow.puml](../communication-workflow.puml).
   - Shows activity state for:
     - MQTT transfer
     - Databroker signal path
     - CAN feedback path
     - FMS pipeline
     - Ankaios workload management path
     - Dozzle monitoring path

3. **Dashboards**
   - Status cards for MQTT, Kuksa Databroker, Ankaios, and Dozzle.
   - Embedded iframes for Ankaios dashboard and Dozzle.
   - Running container table (Podman + Docker).

## Folder content

- `index.html`: UI layout
- `styles.css`: styling + animations
- `app.js`: live polling + rendering logic
- `api_server.py`: local API server + static host
- `Dockerfile`: container image for the website server
- `requirements.txt`: Python dependencies for container/runtime
- `site-config.json.example`: endpoint/container matching template

## Run with Ankaios (recommended)

The Ankaios manifest `devices/raspberry-pi5/ankaios/vehicle-signals.yaml` includes a `pi5-demo-website` workload that runs this website on port `8090`.

When you start the stack via `start-fleet-and-ankaios.sh`, the script reads `devices/raspberry-pi5/website/site-config.json` and injects its contents into the website workload before `ank apply`. If that file does not exist, it falls back to `site-config.json.example`.

Build the container image locally on Pi5:

```bash
podman build -t localhost/pi5-demo-website:latest devices/raspberry-pi5/website
```

Build the website image locally on Pi5 with Docker:

```bash
docker build -t pi5-demo-website:latest devices/raspberry-pi5/website
```

If you want to use the image with the Ankaios workload from `vehicle-signals.yaml`, prefer the Podman build above, because that workload runs with Podman and expects `localhost/pi5-demo-website:latest`.

Apply manifest:

```bash
ank -k apply devices/raspberry-pi5/ankaios/vehicle-signals.yaml
```

If you apply the manifest manually, it uses the `website_config` block embedded in `vehicle-signals.yaml`. To keep the website container aligned with your local JSON config, prefer `start-fleet-and-ankaios.sh` or update the embedded block as well.

Open:

```text
http://<pi5-ip>:8090
```

## Run standalone on Raspberry Pi 5

1. Go to the website folder:

```bash
cd devices/raspberry-pi5/website
```

2. Create local config (optional but recommended):

```bash
cp site-config.json.example site-config.json
```

3. Adjust `site-config.json` values for your environment:
   - `mqtt.host` / `mqtt.port`
   - `kuksa.host` / `kuksa.port`
   - `ankaios_dashboard_url`
   - `dozzle_url`
   - `status_cache_seconds` to reduce backend probe frequency
   - `can_observer.interface` / `can_observer.min_poll_interval_seconds`
   - container name patterns under `containers`

4. Start the website server:

```bash
python3 api_server.py --host 0.0.0.0 --port 8090
```

5. Open in browser:

```text
http://<pi5-ip>:8090
```

## Run on a second PC with Docker

If you want to run the website on another PC, there are two separate concerns:

- the website server itself must listen on port `8090`
- `site-config.json` must point to the systems the website should probe

Important:

- `http://localhost:8090/` only works if the website process or container is running on that same PC and port `8090` is published to the host
- `localhost` inside `site-config.json` means "this machine" or, in Docker, "this container"
- if MQTT/Kuksa/Ankaios/Dozzle still run on the Raspberry Pi 5, do not change those config entries to `localhost`; keep them on the Pi IP such as `192.168.88.100`
- the same applies to the fleet endpoints: set `fleet.grafana_url` and `fleet.fms_server_url` to the Pi IP when the website runs on a second PC

Build on the second PC:

```bash
docker build -t pi5-demo-website:latest devices/raspberry-pi5/website
```

Run on the second PC:

```bash
docker run --rm -p 8090:8090 -v "$(pwd)/devices/raspberry-pi5/website/site-config.json:/app/site-config.json:ro" pi5-demo-website:latest
```

PowerShell variant:

```powershell
docker run --rm -p 8090:8090 -v "${PWD}\devices\raspberry-pi5\website\site-config.json:/app/site-config.json:ro" pi5-demo-website:latest
```

Then open:

```text
http://localhost:8090/
```

If it still does not connect, check these first:

1. The container is actually running: `docker ps`
2. Port mapping exists: look for `0.0.0.0:8090->8090/tcp`
3. The server did not exit on startup: `docker logs <container-id>`

Remote probing note:

- in the current fleet compose setup, Grafana is published on `3000`, Databroker on `55555`, and `fms-server` on `8081`
- from a second PC, set `fleet.grafana_url` to `http://192.168.88.100:3000` and `fleet.fms_server_url` to `http://192.168.88.100:8081`

## How live status is detected

The backend (`api_server.py`) polls:

- TCP reachability
  - MQTT broker (`host:1883` by default)
  - Kuksa Databroker (`host:55555` by default)
- HTTP reachability
  - Ankaios dashboard URL
  - Dozzle URL
- Container runtime state
  - `podman ps`
  - `docker ps`
- Optional recent activity hints from logs
  - `podman logs` / `docker logs` for bridge and databroker containers
- Optional direct signal observation via Kuksa Python client
  - reads configured VSS paths from Databroker (`kuksa_observer` in `site-config.json`)
  - marks command/feedback flows active when signal changes are observed
- Optional throttled SocketCAN observation via `candump`
  - samples a single frame on the configured CAN interface (`can_observer.interface`)
  - caches the result for `can_observer.min_poll_interval_seconds` so `/api/status` polling does not run `candump` every second
  - requires `can-utils` in the image and privileged container access when running in Podman
- Whole-status response caching
  - `status_cache_seconds` caches the full `/api/status` payload to avoid repeated `podman ps`, `docker ps`, log reads, and other heavy probes on every browser poll
  - the UI refresh button bypasses the cache when you need an immediate update
- Optional Ankaios workload query
  - attempts `ank` CLI commands (version-dependent)

The UI marks each path as:
- **Active**: endpoints are up and traffic hints are found
- **Reachable, idle**: endpoints are up but no recent traffic hints
- **Inactive**: endpoint/container path is not currently reachable

## Notes

- If `/api/status` is unreachable, the frontend switches to a simulated fallback mode so the page still demonstrates the UI behavior.
- If iframe embedding is blocked by remote headers (`X-Frame-Options`/`CSP`), use the "Open in new tab" links.
