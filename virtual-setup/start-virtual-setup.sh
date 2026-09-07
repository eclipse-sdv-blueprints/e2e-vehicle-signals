#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

FLEET_COMPOSE_FILE="${FLEET_COMPOSE_FILE:-${REPO_DIR}/external/fleet-management/fms-blueprint-compose.yaml}"
FLEET_TRANSPORT_COMPOSE_FILE="${FLEET_TRANSPORT_COMPOSE_FILE:-${REPO_DIR}/external/fleet-management/fms-blueprint-compose-zenoh.yaml}"
VIRTUAL_COMPOSE_FILE="${VIRTUAL_COMPOSE_FILE:-${SCRIPT_DIR}/virtual-e2e-compose.yaml}"

# Bind all services to 0.0.0.0 so they are reachable from a Windows browser
# when Docker is running inside WSL2.
FMS_INFLUXDB_BIND_HOST="${FMS_INFLUXDB_BIND_HOST:-0.0.0.0}"
FMS_GRAFANA_BIND_HOST="${FMS_GRAFANA_BIND_HOST:-0.0.0.0}"
FMS_SERVER_BIND_HOST="${FMS_SERVER_BIND_HOST:-0.0.0.0}"
FMS_DATABROKER_BIND_HOST="${FMS_DATABROKER_BIND_HOST:-0.0.0.0}"
FMS_FLEET_ANALYSIS_BIND_HOST="${FMS_FLEET_ANALYSIS_BIND_HOST:-0.0.0.0}"
FMS_ZENOH_BIND_HOST="${FMS_ZENOH_BIND_HOST:-0.0.0.0}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
export FMS_INFLUXDB_BIND_HOST
export FMS_GRAFANA_BIND_HOST
export FMS_SERVER_BIND_HOST
export FMS_DATABROKER_BIND_HOST
export FMS_FLEET_ANALYSIS_BIND_HOST
export FMS_ZENOH_BIND_HOST
export LOG_LEVEL

log() {
  printf "[start-virtual] %s\n" "$*"
}

warn() {
  printf "[start-virtual] %s\n" "$*" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf "[start-virtual] Missing required command: %s\n" "$1" >&2
    exit 1
  fi
}

require_file() {
  if [ ! -f "$1" ]; then
    printf "[start-virtual] Missing required file: %s\n" "$1" >&2
    exit 1
  fi
}

require_cmd docker
require_file "$FLEET_COMPOSE_FILE"
require_file "$FLEET_TRANSPORT_COMPOSE_FILE"
require_file "$VIRTUAL_COMPOSE_FILE"

log "Starting virtual e2e setup (Docker Compose)..."
log "  Fleet:     $FLEET_COMPOSE_FILE"
log "  Transport: $FLEET_TRANSPORT_COMPOSE_FILE"
log "  Virtual:   $VIRTUAL_COMPOSE_FILE"
log "  LOG_LEVEL: $LOG_LEVEL"

docker compose \
  -f "$FLEET_COMPOSE_FILE" \
  -f "$FLEET_TRANSPORT_COMPOSE_FILE" \
  up --detach"$@"

docker compose \
  -f "$VIRTUAL_COMPOSE_FILE" \
  up --detach --build "$@"

log "All services started."
log "  Note: The ports listed below are Docker Compose internal service ports."
log "        Published host ports may differ if your compose files or overrides remap them."
log "  Grafana (internal):            http://localhost:3000  (user: sdv / sdv)"
log "  InfluxDB (internal):           http://localhost:8086"
log "  FMS Server (internal):         http://localhost:8081"
log "  Fleet Analysis (internal):     http://localhost:8082"
log "  Demo Website (internal):       http://localhost:8090"
log "  Virtual Indicator (internal):  http://localhost:8091"
log "  MQTT Broker (internal):        localhost:1883"
log "  Databroker (gRPC internal):    localhost:55556"
