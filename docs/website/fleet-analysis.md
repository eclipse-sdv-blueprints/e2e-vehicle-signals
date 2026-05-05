---
sidebar_position: 7
title: Fleet Analysis Backend
---

# Fleet Analysis Backend

The E2E demo includes a **Jakarta EE 11** backend service that provides fleet-level analytics on top of the telemetry stored by the Fleet Management Blueprint.

## Overview

The fleet analysis backend runs alongside the Fleet Management stack and connects to the same InfluxDB instance. It provides REST APIs for:

- Computing summary statistics from vehicle telemetry snapshots
- Ingesting telemetry data into InfluxDB
- Reading periodically refreshed fleet statistics

## Architecture

```mermaid
graph LR
    KDB[Kuksa Databroker] -->|VSS signals| FWD[FMS Forwarder]
    FWD -->|uProtocol / Zenoh| CONS[FMS Consumer]
    CONS -->|write| INFLUX[(InfluxDB 2.7)]
    
    ANALYTICS[Fleet Analysis Backend<br/>Jakarta EE :8082] -->|read/write| INFLUX
    FMS_SRV[FMS Server :8081] -->|query| INFLUX
    GRAFANA[Grafana :3000] -->|dashboard queries| INFLUX
    
    USER[Fleet Operator] --> ANALYTICS
    USER --> GRAFANA
    USER --> FMS_SRV
```

## API Endpoints

### `POST /api/analysis/summary`

Accepts a JSON array of vehicle snapshots and returns computed summary statistics.

**Request body:**

```json
[
  { "vehicleId": "truck-01", "speedKph": 85.2, "batterySoc": 0.78, "brakeActive": false, "updatedAt": "2024-06-10T10:15:30Z" },
  { "vehicleId": "truck-02", "speedKph": 60.0, "batterySoc": 0.52, "brakeActive": true, "updatedAt": "2024-06-10T10:15:32Z" }
]
```

**Response:**

```json
{
  "vehicleCount": 2,
  "averageSpeedKph": 72.6,
  "minBatterySoc": 0.52,
  "maxBatterySoc": 0.78,
  "brakingVehicles": 1
}
```

### `POST /api/telemetry/ingest`

Writes header and/or snapshot measurements into InfluxDB. Used for ingesting telemetry data from external sources.

**Request body:**

```json
{
  "vin": "truck-001",
  "trigger": "periodic",
  "createdDateTime": 1737940602000,
  "header": {
    "hrTotalVehicleDistance": 12345.6,
    "grossCombinationVehicleWeight": 18100.2,
    "totalEngineHours": 82.5,
    "engineTotalFuelUsed": 221.9,
    "driver1Id": "driver-01",
    "driver1IdCardIssuer": "fleet"
  },
  "snapshot": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "speed": 54.2,
    "positionDateTime": 1737940602,
    "wheelBasedSpeed": 53.7,
    "fuelLevel1": 0.42,
    "parkingBrakeSwitch": false
  }
}
```

### `GET /api/analysis/stats`

Returns the latest fleet statistics snapshot from InfluxDB, periodically refreshed (default: every 30 seconds).

**Response:**

```json
{
  "vehicleCount": 5,
  "headerCount": 120,
  "snapshotCount": 480,
  "totalCount": 600,
  "generatedAt": "2025-01-15T10:30:00Z"
}
```

## Configuration

The service is configured via environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `INFLUXDB_URI` | `http://influxdb:8086` | InfluxDB connection URI |
| `INFLUXDB_ORG` | `sdv` | InfluxDB organization |
| `INFLUXDB_BUCKET` | `demo` | InfluxDB bucket |
| `INFLUXDB_TOKEN` | — | InfluxDB authentication token |
| `INFLUXDB_TOKEN_FILE` | — | Path to token file (alternative to `INFLUXDB_TOKEN`) |
| `INFLUXDB_STATS_INTERVAL_SECONDS` | `30` | Interval for refreshing fleet statistics |
| `INFLUXDB_STATS_INITIAL_DELAY_SECONDS` | `10` | Initial delay before the first stats run |

## Build and Run

### Build with Maven

```bash
cd devices/backend-fleet-analysis-java
mvn package
```

### Run Standalone (Payara Micro)

Download [Payara Micro 6](https://www.payara.fish/downloads/payara-platform-community-edition/), then deploy:

```bash
java -jar payara-micro.jar \
  --deploy target/fleet-analysis-backend.war \
  --contextRoot /fleet-analysis
```

The API will be available at `http://localhost:8080/fleet-analysis/api`.

### Build Docker Image

```bash
docker build -t fleet-analysis-backend:local devices/backend-fleet-analysis-java
```

### Run with Docker Compose (Recommended)

The service is included in the Fleet Management Docker Compose stack. Start from the repository root:

```bash
docker compose \
  -f external/fleet-management/fms-blueprint-compose.yaml \
  -f external/fleet-management/fms-blueprint-compose-zenoh.yaml \
  up --detach
```

The analytics service will be available at `http://<host>:8082/fleet-analysis/api`.

## Integration with Fleet Management

The fleet analysis backend integrates with the upstream Fleet Management Blueprint:

- **Data source**: Reads from the same InfluxDB instance where the FMS Consumer writes vehicle telemetry
- **Network**: Joins the `fms-backend` Docker network
- **Token sharing**: Uses the same InfluxDB token created by the Influx init job (mounted via `INFLUXDB_TOKEN_FILE`)
- **RFID driver identification**: The `Vehicle.Driver.Identifier.Subject` signal from the RFID door ECU is forwarded by the FMS Forwarder as the `driver1Id` field in the `header` measurement, visible in the Grafana "Driver Identifier (RFID)" panel
