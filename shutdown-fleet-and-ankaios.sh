#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FLEET_COMPOSE_FILE="${FLEET_COMPOSE_FILE:-${SCRIPT_DIR}/external/fleet-management/fms-blueprint-compose.yaml}"
FLEET_TRANSPORT_COMPOSE_FILE="${FLEET_TRANSPORT_COMPOSE_FILE:-${SCRIPT_DIR}/external/fleet-management/fms-blueprint-compose-zenoh.yaml}"
DOZZLE_ENABLED="${DOZZLE_ENABLED:-true}"
DOZZLE_CONTAINER_NAME="${DOZZLE_CONTAINER_NAME:-dozzle}"
WEBSITE_ENABLED="${WEBSITE_ENABLED:-false}"
WEBSITE_SERVER_SCRIPT="${WEBSITE_SERVER_SCRIPT:-${SCRIPT_DIR}/devices/raspberry-pi5/website/api_server.py}"
WEBSITE_PID_FILE="${WEBSITE_PID_FILE:-/tmp/ee-demo-website-server.pid}"

log() {
  printf "[shutdown] %s\n" "$*"
}

warn() {
  printf "[shutdown] %s\n" "$*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

stop_fleet_compose() {
  if ! have_cmd docker; then
    warn "docker not found. Skipping Docker Compose shutdown."
    return
  fi

  if [ ! -f "$FLEET_COMPOSE_FILE" ] || [ ! -f "$FLEET_TRANSPORT_COMPOSE_FILE" ]; then
    warn "Compose file(s) missing. Skipping Docker Compose shutdown."
    return
  fi

  log "Stopping Fleet Management services (Docker Compose)..."
  docker compose \
    -f "$FLEET_COMPOSE_FILE" \
    -f "$FLEET_TRANSPORT_COMPOSE_FILE" \
    down --remove-orphans
}

stop_dozzle_container() {
  if [ "${DOZZLE_ENABLED}" != "true" ]; then
    return
  fi

  if ! have_cmd docker; then
    warn "docker not found. Skipping Dozzle shutdown."
    return
  fi

  if ! docker ps -a --format '{{.Names}}' | grep -Fxq "${DOZZLE_CONTAINER_NAME}"; then
    return
  fi

  log "Stopping Dozzle container '${DOZZLE_CONTAINER_NAME}'..."
  docker rm -f "${DOZZLE_CONTAINER_NAME}" >/dev/null || warn "Failed to remove Dozzle container."
}

stop_website_server() {
  local website_pid

  if [ "${WEBSITE_ENABLED}" != "true" ]; then
    return
  fi

  if [ -f "${WEBSITE_PID_FILE}" ]; then
    website_pid="$(cat "${WEBSITE_PID_FILE}" 2>/dev/null || true)"
    if [ -n "${website_pid}" ] && kill -0 "${website_pid}" >/dev/null 2>&1; then
      log "Stopping website server (pid ${website_pid})..."
      kill "${website_pid}" >/dev/null 2>&1 || true
      sleep 1
      if kill -0 "${website_pid}" >/dev/null 2>&1; then
        kill -9 "${website_pid}" >/dev/null 2>&1 || true
      fi
    fi
    rm -f "${WEBSITE_PID_FILE}"
    return
  fi

  if have_cmd pkill; then
    if pgrep -f "${WEBSITE_SERVER_SCRIPT}" >/dev/null 2>&1; then
      log "Stopping website server process(es) matching ${WEBSITE_SERVER_SCRIPT}..."
      pkill -f "${WEBSITE_SERVER_SCRIPT}" || true
    fi
  fi
}

stop_podman_containers() {
  if ! have_cmd podman; then
    warn "podman not found. Skipping Podman shutdown."
    return
  fi

  if [ -z "$(podman ps -q)" ]; then
    log "No running Podman containers found."
    return
  fi

  log "Stopping all running Podman containers..."
  podman stop -a
  log "Remove all Podman containers..."
  podman rm -a -f
}

stop_ankaios_processes() {
  if have_cmd pkill; then
    if pgrep -f "ank-agent" >/dev/null 2>&1; then
      log "Stopping ank-agent process(es)..."
      pkill -f "ank-agent" || true
    fi

    if pgrep -f "ank-server" >/dev/null 2>&1; then
      log "Stopping ank-server process(es)..."
      pkill -f "ank-server" || true
    fi
  fi
}

stop_website_server
stop_dozzle_container
stop_fleet_compose
stop_podman_containers
stop_ankaios_processes

log "Shutdown completed."
