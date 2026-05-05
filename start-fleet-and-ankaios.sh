#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FLEET_COMPOSE_FILE="${FLEET_COMPOSE_FILE:-${SCRIPT_DIR}/external/fleet-management/fms-blueprint-compose.yaml}"
FLEET_TRANSPORT_COMPOSE_FILE="${FLEET_TRANSPORT_COMPOSE_FILE:-${SCRIPT_DIR}/external/fleet-management/fms-blueprint-compose-zenoh.yaml}"
ANKAIOS_MANIFEST="${ANKAIOS_MANIFEST:-${SCRIPT_DIR}/devices/raspberry-pi5/ankaios/vehicle-signals.yaml}"
ANKAIOS_START_WAIT_SECONDS="${ANKAIOS_START_WAIT_SECONDS:-2}"
DOZZLE_ENABLED="${DOZZLE_ENABLED:-true}"
DOZZLE_IMAGE="${DOZZLE_IMAGE:-amir20/dozzle:latest}"
DOZZLE_CONTAINER_NAME="${DOZZLE_CONTAINER_NAME:-dozzle}"
DOZZLE_PORT="${DOZZLE_PORT:-8080}"
DOZZLE_DOCKER_SOCKET="${DOZZLE_DOCKER_SOCKET:-/var/run/docker.sock}"
WEBSITE_ENABLED="${WEBSITE_ENABLED:-false}"
WEBSITE_SERVER_SCRIPT="${WEBSITE_SERVER_SCRIPT:-${SCRIPT_DIR}/devices/raspberry-pi5/website/api_server.py}"
WEBSITE_HOST="${WEBSITE_HOST:-0.0.0.0}"
WEBSITE_PORT="${WEBSITE_PORT:-8090}"
WEBSITE_PID_FILE="${WEBSITE_PID_FILE:-/tmp/ee-demo-website-server.pid}"
WEBSITE_LOG_FILE="${WEBSITE_LOG_FILE:-/tmp/ee-demo-website-server.log}"
WEBSITE_CONTAINER_BUILD="${WEBSITE_CONTAINER_BUILD:-true}"
WEBSITE_CONTAINER_IMAGE="${WEBSITE_CONTAINER_IMAGE:-localhost/pi5-demo-website:latest}"
WEBSITE_CONTAINER_CONTEXT="${WEBSITE_CONTAINER_CONTEXT:-${SCRIPT_DIR}/devices/raspberry-pi5/website}"
WEBSITE_CONFIG_FILE="${WEBSITE_CONFIG_FILE:-${WEBSITE_CONTAINER_CONTEXT}/site-config.json}"
WEBSITE_CONFIG_EXAMPLE_FILE="${WEBSITE_CONFIG_EXAMPLE_FILE:-${WEBSITE_CONTAINER_CONTEXT}/site-config.json.example}"

log() {
  printf "[start] %s\n" "$*"
}

warn() {
  printf "[start] %s\n" "$*" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf "[start] Missing required command: %s\n" "$1" >&2
    exit 1
  fi
}

require_file() {
  if [ ! -f "$1" ]; then
    printf "[start] Missing required file: %s\n" "$1" >&2
    exit 1
  fi
}

require_cmd docker
require_cmd podman
require_cmd ank
require_file "$FLEET_COMPOSE_FILE"
require_file "$FLEET_TRANSPORT_COMPOSE_FILE"
require_file "$ANKAIOS_MANIFEST"

start_dozzle_container() {
  if [ "${DOZZLE_ENABLED}" != "true" ]; then
    log "Dozzle disabled via DOZZLE_ENABLED=${DOZZLE_ENABLED}."
    return
  fi

  if [ ! -S "${DOZZLE_DOCKER_SOCKET}" ]; then
    warn "Docker socket not found at ${DOZZLE_DOCKER_SOCKET}. Skipping Dozzle startup."
    return
  fi

  if docker ps --format '{{.Names}}' | grep -Fxq "${DOZZLE_CONTAINER_NAME}"; then
    log "Dozzle container '${DOZZLE_CONTAINER_NAME}' is already running."
    return
  fi

  if docker ps -a --format '{{.Names}}' | grep -Fxq "${DOZZLE_CONTAINER_NAME}"; then
    log "Starting existing Dozzle container '${DOZZLE_CONTAINER_NAME}'..."
    docker start "${DOZZLE_CONTAINER_NAME}" >/dev/null
    log "Dozzle available at: http://<host>:${DOZZLE_PORT}"
    return
  fi

  log "Starting Dozzle container '${DOZZLE_CONTAINER_NAME}' on port ${DOZZLE_PORT}..."
  if docker run -d \
    --name "${DOZZLE_CONTAINER_NAME}" \
    --restart unless-stopped \
    -p "${DOZZLE_PORT}:8080" \
    -v "${DOZZLE_DOCKER_SOCKET}:/var/run/docker.sock:ro" \
    "${DOZZLE_IMAGE}" >/dev/null; then
    log "Dozzle available at: http://<host>:${DOZZLE_PORT}"
  else
    warn "Dozzle startup failed. Continuing without Dozzle."
  fi
}

run_podman() {
  if command -v sudo >/dev/null 2>&1; then
    sudo podman "$@"
  else
    podman "$@"
  fi
}

build_website_container_image() {
  if [ "${WEBSITE_CONTAINER_BUILD}" != "true" ]; then
    log "Website container build disabled via WEBSITE_CONTAINER_BUILD=${WEBSITE_CONTAINER_BUILD}."
    return
  fi

  if [ ! -d "${WEBSITE_CONTAINER_CONTEXT}" ]; then
    warn "Website container context not found: ${WEBSITE_CONTAINER_CONTEXT}. Skipping build."
    return
  fi

  if [ ! -f "${WEBSITE_CONTAINER_CONTEXT}/Dockerfile" ]; then
    warn "Website Dockerfile not found in: ${WEBSITE_CONTAINER_CONTEXT}. Skipping build."
    return
  fi

  log "Building website image '${WEBSITE_CONTAINER_IMAGE}'..."
  if run_podman build -t "${WEBSITE_CONTAINER_IMAGE}" "${WEBSITE_CONTAINER_CONTEXT}"; then
    log "Website image build complete: ${WEBSITE_CONTAINER_IMAGE}"
    return
  fi

  warn "Website image build failed."
  if run_podman image exists "${WEBSITE_CONTAINER_IMAGE}"; then
    warn "Using previously built image: ${WEBSITE_CONTAINER_IMAGE}"
    return
  fi

  warn "No usable website image available. Aborting."
  exit 1
}

resolve_website_config_file() {
  if [ -f "${WEBSITE_CONFIG_FILE}" ]; then
    printf "%s\n" "${WEBSITE_CONFIG_FILE}"
    return
  fi

  if [ -f "${WEBSITE_CONFIG_EXAMPLE_FILE}" ]; then
    warn "Website config not found at ${WEBSITE_CONFIG_FILE}. Falling back to ${WEBSITE_CONFIG_EXAMPLE_FILE}."
    printf "%s\n" "${WEBSITE_CONFIG_EXAMPLE_FILE}"
    return
  fi

  warn "No website config file found. Checked ${WEBSITE_CONFIG_FILE} and ${WEBSITE_CONFIG_EXAMPLE_FILE}."
  return 1
}

render_ankaios_manifest() {
  local source_manifest="$1"
  local config_file="$2"
  local rendered_manifest

  rendered_manifest="$(mktemp)"

  if ! awk -v cfg="${config_file}" '
    BEGIN {
      injected = 0
      skipping = 0
    }

    skipping == 1 {
      if ($0 ~ /^  [^[:space:]][^:]*: *[|>]?$/ && $0 !~ /^  website_config: *[|>]$/) {
        skipping = 0
      } else {
        next
      }
    }

    $0 ~ /^  website_config: *[|>]$/ {
      print
      while ((getline line < cfg) > 0) {
        print "    " line
      }
      close(cfg)
      injected = 1
      skipping = 1
      next
    }

    {
      print
    }

    END {
      if (injected != 1) {
        exit 42
      }
    }
  ' "${source_manifest}" > "${rendered_manifest}"; then
    rm -f "${rendered_manifest}"
    warn "Failed to render Ankaios manifest with website config from ${config_file}."
    return 1
  fi

  printf "%s\n" "${rendered_manifest}"
}

find_python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    printf "python3"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    printf "python"
    return
  fi
  return 1
}

start_website_server() {
  local python_cmd
  local website_pid

  if [ "${WEBSITE_ENABLED}" != "true" ]; then
    log "Website server disabled via WEBSITE_ENABLED=${WEBSITE_ENABLED}."
    return
  fi

  if grep -q "pi5-demo-website" "${ANKAIOS_MANIFEST}" 2>/dev/null; then
    log "Website workload is defined in Ankaios manifest. Skipping host website server."
    return
  fi

  if [ ! -f "${WEBSITE_SERVER_SCRIPT}" ]; then
    warn "Website server script not found: ${WEBSITE_SERVER_SCRIPT}. Skipping website startup."
    return
  fi

  if ! python_cmd="$(find_python_cmd)"; then
    warn "python3/python not found. Skipping website startup."
    return
  fi

  if [ -f "${WEBSITE_PID_FILE}" ]; then
    website_pid="$(cat "${WEBSITE_PID_FILE}" 2>/dev/null || true)"
    if [ -n "${website_pid}" ] && kill -0 "${website_pid}" >/dev/null 2>&1; then
      log "Website server already running (pid ${website_pid})."
      return
    fi
    rm -f "${WEBSITE_PID_FILE}"
  fi

  if pgrep -f "${WEBSITE_SERVER_SCRIPT}" >/dev/null 2>&1; then
    log "Website server already running (process match on ${WEBSITE_SERVER_SCRIPT})."
    return
  fi

  log "Starting website server on ${WEBSITE_HOST}:${WEBSITE_PORT}..."
  if nohup "${python_cmd}" "${WEBSITE_SERVER_SCRIPT}" \
      --host "${WEBSITE_HOST}" \
      --port "${WEBSITE_PORT}" >>"${WEBSITE_LOG_FILE}" 2>&1 & then
    website_pid=$!
    printf "%s\n" "${website_pid}" > "${WEBSITE_PID_FILE}"
    log "Website available at: http://<host>:${WEBSITE_PORT}"
  else
    warn "Website server startup failed. Check log: ${WEBSITE_LOG_FILE}"
  fi
}

log "Starting Fleet Management services (Docker Compose)..."
docker compose \
  -f "$FLEET_COMPOSE_FILE" \
  -f "$FLEET_TRANSPORT_COMPOSE_FILE" \
  up --detach

start_dozzle_container

log "Starting Ankaios control plane services as terminal calls (ank-server, ank-agent)..."

if command -v sudo >/dev/null 2>&1; then
  sudo ank-server &
else
  ank-server &
fi

if command -v sudo >/dev/null 2>&1; then
  sudo ank-agent --insecure --name agent_B &
else
  ank-agent --insecure --name agent_B &
fi


log "Waiting ${ANKAIOS_START_WAIT_SECONDS}s for Ankaios startup..."
sleep "${ANKAIOS_START_WAIT_SECONDS}"

log "Logging into ghcr.io (podman login)..."
if command -v sudo >/dev/null 2>&1; then
  sudo podman login ghcr.io
else
  podman login ghcr.io
fi

log "Applying Ankaios workload manifest: ${ANKAIOS_MANIFEST}"
build_website_container_image
WEBSITE_CONFIG_RESOLVED="$(resolve_website_config_file)"
RENDERED_ANKAIOS_MANIFEST="$(render_ankaios_manifest "${ANKAIOS_MANIFEST}" "${WEBSITE_CONFIG_RESOLVED}")"
trap 'if [ -n "${RENDERED_ANKAIOS_MANIFEST:-}" ] && [ -f "${RENDERED_ANKAIOS_MANIFEST}" ]; then rm -f "${RENDERED_ANKAIOS_MANIFEST}"; fi' EXIT
log "Using website config from: ${WEBSITE_CONFIG_RESOLVED}"
ank -k apply "${RENDERED_ANKAIOS_MANIFEST}"

start_website_server

log "Fleet Management and Ankaios workloads started."
