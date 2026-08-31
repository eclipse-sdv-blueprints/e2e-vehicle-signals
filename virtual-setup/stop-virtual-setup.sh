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

log() {
  printf "[stop-virtual] %s\n" "$*"
}

warn() {
  printf "[stop-virtual] %s\n" "$*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

if ! have_cmd docker; then
  warn "docker not found. Nothing to stop."
  exit 1
fi

log "Stopping virtual e2e setup (Docker Compose)..."
docker compose \
  -f "$FLEET_COMPOSE_FILE" \
  -f "$FLEET_TRANSPORT_COMPOSE_FILE" \
  down --remove-orphans "$@"

docker compose \
  -f "$VIRTUAL_COMPOSE_FILE" \
  down --remove-orphans "$@"

log "All services stopped."
