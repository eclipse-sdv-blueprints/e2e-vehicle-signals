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
# TOSCA lifecycle operation: delete
# Stops and removes all virtual stack containers, networks, and volumes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="${SCRIPT_DIR}/../../.."   # virtual-setup/

echo "[teardown] Stopping and removing virtual stack..."
docker compose -f "${COMPOSE_DIR}/docker-compose.yaml" down --remove-orphans

echo "[teardown] Done."
