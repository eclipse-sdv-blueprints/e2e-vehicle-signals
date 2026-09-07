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

set -euo pipefail

door_ip="${1:-192.168.88.101}"
door_port="${2:-30501}"

validate_port() {
  local p="$1"
  [[ "$p" =~ ^[0-9]+$ ]] || return 1
  (( p >= 1 && p <= 65535 )) || return 1
}

send_door_command() {
  local is_open="$1"
  local last_byte="\\x00"
  local state="CLOSED"
  local payload_hex="43 01 80 02 00 00 00 09 D0 01 00 01 01 01 02 00 00"

  if [[ "$is_open" == "1" ]]; then
    last_byte="\\x01"
    state="OPEN"
    payload_hex="43 01 80 02 00 00 00 09 D0 01 00 01 01 01 02 00 01"
  fi

  # Minimal SOME/IP UDP frame expected by driver-door-ecu.ino
  printf '\\x43\\x01\\x80\\x02\\x00\\x00\\x00\\x09\\xD0\\x01\\x00\\x01\\x01\\x01\\x02\\x00%b' "$last_byte" >"/dev/udp/${door_ip}/${door_port}"

  echo "Sent ${state} command to ${door_ip}:${door_port}"
  echo "Payload: ${payload_hex}"
}

show_menu() {
  echo
  echo "Door SOME/IP UDP Tester"
  echo "Target: ${door_ip}:${door_port}"
  echo "[1] Open door"
  echo "[2] Close door"
  echo "[3] Set target IP"
  echo "[4] Set target port"
  echo "[5] Send open then close (2s gap)"
  echo "[q] Quit"
}

while true; do
  show_menu
  read -r -p "Choose: " choice

  case "${choice}" in
    1)
      send_door_command 1
      ;;
    2)
      send_door_command 0
      ;;
    3)
      read -r -p "Enter door ECU IP: " new_ip
      if [[ -n "${new_ip// }" ]]; then
        door_ip="${new_ip}"
        echo "Target IP updated to ${door_ip}"
      fi
      ;;
    4)
      read -r -p "Enter door ECU UDP port: " new_port
      if validate_port "$new_port"; then
        door_port="$new_port"
        echo "Target port updated to ${door_port}"
      else
        echo "Invalid port. Keep current value: ${door_port}"
      fi
      ;;
    5)
      send_door_command 1
      sleep 2
      send_door_command 0
      ;;
    q|Q)
      echo "Bye."
      exit 0
      ;;
    *)
      echo "Unknown option: ${choice}"
      ;;
  esac
done
