#!/usr/bin/env bash
# /********************************************************************************
# * Copyright (c) 2026 Contributors to the Eclipse Foundation
# *
# * See the NOTICE file(s) distributed with this work for additional
# * information regarding copyright ownership.
# *
# * This program and the accompanying materials are made available under the
# * terms of the Apache License 2.0 which is available at
# * https://www.apache.org/licenses/LICENSE-2.0
# *
# * SPDX-License-Identifier: Apache-2.0
# ********************************************************************************/
#
# TOSCA lifecycle operation: configure
# Builds images and starts the virtual stack via Docker Compose.
# Called by the OpenTOSCA Container or winery-deploy after node creation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="${SCRIPT_DIR}/../../.."   # virtual-setup/

echo "[deploy-compose] Building images..."
docker compose -f "${COMPOSE_DIR}/docker-compose.yaml" build

echo "[deploy-compose] Starting services..."
docker compose -f "${COMPOSE_DIR}/docker-compose.yaml" up -d

echo "[deploy-compose] Stack is up."
echo "  Indicator UI  → http://localhost:8091"
echo "  Demo Website  → http://localhost:8090"
echo "  Kuksa gRPC    → localhost:55555"
echo ""
echo "Optional – Fleet Management (separate stack):"
echo "  docker compose -f ${COMPOSE_DIR}/../external/fleet-management/fms-blueprint-compose.yaml \\"
echo "                 -f ${COMPOSE_DIR}/../external/fleet-management/fms-blueprint-compose-zenoh.yaml \\"
echo "                 up --detach"
