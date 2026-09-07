/*
 * Copyright (c) 2026 Contributors to the Eclipse Foundation
 *
 * See the NOTICE file(s) distributed with this work for additional
 * information regarding copyright ownership.
 *
 * This program and the accompanying materials are made available under the
 * terms of the Apache License 2.0 which is available at
 * https://www.apache.org/licenses/LICENSE-2.0
 *
 * SPDX-License-Identifier: Apache-2.0
 */
'use strict';

const SSE_ENDPOINT       = '/api/sse/signals';
const INDICATOR_ENDPOINT = '/api/indicator';

// VSS path constants
const PATH_LEFT   = 'Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling';
const PATH_RIGHT  = 'Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling';
const PATH_BRAKE  = 'Vehicle.Body.Lights.Brake.IsActive';
const PATH_DRIVER = 'Vehicle.Driver.Identifier.Subject';
const TRACKED_PATHS = [PATH_LEFT, PATH_RIGHT, PATH_BRAKE, PATH_DRIVER];

// Last known VSS values. The SSE endpoint may emit only changed fields, so
// we merge partial updates into this cache before rendering.
const latestSignals = Object.create(null);

// ── Local button state ────────────────────────────────────────────────────────
const local = { left: false, right: false, brake: false };

// ── DOM references ────────────────────────────────────────────────────────────
const btnLeft      = document.getElementById('btn-left');
const btnRight     = document.getElementById('btn-right');
const btnOff       = document.getElementById('btn-off');
const btnBrake     = document.getElementById('btn-brake');
const btnIdentify  = document.getElementById('btn-identify');
const driverInput  = document.getElementById('driver-id-input');
const pubStatus    = document.getElementById('publish-status');
const ssePill      = document.getElementById('sse-pill');

// Input panel state displays
const stateLeft   = document.getElementById('state-left');
const stateRight  = document.getElementById('state-right');
const stateBrake  = document.getElementById('state-brake');
const stateDriver = document.getElementById('state-driver');

// Actor panel – VSS table cells
const vssLeft   = document.getElementById('vss-left');
const vssRight  = document.getElementById('vss-right');
const vssBrake  = document.getElementById('vss-brake');
const vssDriver = document.getElementById('vss-driver');

// 8 LED elements (index 0 = LED 1 … index 7 = LED 8)
const leds = Array.from({ length: 8 }, (_, i) =>
  document.getElementById(`led-${i + 1}`)
);
// Physical LED layout — mirrors mcu1-led-control-can.ino exactly:
//   Index 0, 1  = LEFT indicators  (Orange, 500 ms blink)
//   Index 2     = Status gap LED   (dim green heartbeat; no function here)
//   Index 3, 4  = BRAKE lights     (Red, solid — no blink)
//   Index 5     = Error gap LED    (idle off)
//   Index 6, 7  = RIGHT indicators (Orange, 500 ms blink)
// Brake and indicators are INDEPENDENT: left + brake =
//   LEDs 0-1 blink amber  AND  LEDs 3-4 glow red simultaneously.
const LEFT_LEDS   = [0, 1];
const STATUS_LED  = 2;
const BRAKE_LEDS  = [3, 4];
const RIGHT_LEDS  = [6, 7];

// ── LED actor logic ───────────────────────────────────────────────────────────
function applyLEDState(leftOn, rightOn, brakeOn) {
  leds.forEach((led, i) => {
    led.classList.remove('led--off', 'led--amber-blink', 'led--red', 'led--green-dim');

    if (LEFT_LEDS.includes(i) && leftOn) {
      // Left indicator: orange blink (same 500 ms period as physical sketch)
      led.classList.add('led--amber-blink');
    } else if (BRAKE_LEDS.includes(i) && brakeOn) {
      // Brake: solid red — no blinkOn guard in physical sketch
      led.classList.add('led--red');
    } else if (RIGHT_LEDS.includes(i) && rightOn) {
      // Right indicator: orange blink
      led.classList.add('led--amber-blink');
    } else if (i === STATUS_LED) {
      // CAN heartbeat LED: always dim green when no error (mirrors physical)
      led.classList.add('led--green-dim');
    } else {
      led.classList.add('led--off');
    }
  });
}

function handleSSEData(data) {
  for (const path of TRACKED_PATHS) {
    if (Object.prototype.hasOwnProperty.call(data, path)) {
      latestSignals[path] = data[path];
    }
  }

  const leftOn  = latestSignals[PATH_LEFT]  === true;
  const rightOn = latestSignals[PATH_RIGHT] === true;
  const brakeVal = latestSignals[PATH_BRAKE];
  const brakeOn  = brakeVal === 'ACTIVE' || brakeVal === 'ADAPTIVE';

  applyLEDState(leftOn, rightOn, brakeOn);

  // Update VSS table
  const fmt = (v) => (v !== undefined && v !== null) ? String(v) : '—';
  vssLeft.textContent  = fmt(latestSignals[PATH_LEFT]);
  vssRight.textContent = fmt(latestSignals[PATH_RIGHT]);
  vssBrake.textContent = fmt(latestSignals[PATH_BRAKE]);
  vssDriver.textContent = fmt(latestSignals[PATH_DRIVER]);

  vssLeft.className  = `vss-val${leftOn  ? ' val--on'    : ''}`;
  vssRight.className = `vss-val${rightOn ? ' val--on'    : ''}`;
  vssBrake.className = `vss-val${brakeOn ? ' val--brake' : ''}`;
}

// ── SSE connection ────────────────────────────────────────────────────────────
let evtSource = null;
let reconnectTimer = null;

function connectSSE() {
  if (evtSource) {
    evtSource.close();
  }
  evtSource = new EventSource(SSE_ENDPOINT);

  evtSource.onopen = () => {
    ssePill.textContent = 'Live';
    ssePill.className   = 'pill pill--ok';
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  };

  evtSource.onmessage = (evt) => {
    try {
      handleSSEData(JSON.parse(evt.data));
    } catch (e) {
      console.warn('SSE parse error', e);
    }
  };

  evtSource.onerror = () => {
    ssePill.textContent = 'Reconnecting…';
    ssePill.className   = 'pill pill--warn';
    evtSource.close();
    reconnectTimer = setTimeout(connectSSE, 3000);
  };
}

connectSSE();

// ── Input panel state sync ────────────────────────────────────────────────────
function refreshInputDisplay() {
  stateLeft.textContent = local.left  ? 'ON'     : 'off';
  stateLeft.className   = `state-val${local.left  ? ' val--on' : ''}`;
  stateRight.textContent = local.right ? 'ON'    : 'off';
  stateRight.className  = `state-val${local.right ? ' val--on' : ''}`;
  stateBrake.textContent = local.brake ? 'ACTIVE' : 'INACTIVE';
  stateBrake.className  = `state-val${local.brake ? ' val--brake' : ''}`;

  btnLeft.classList.toggle('btn--active',  local.left);
  btnRight.classList.toggle('btn--active', local.right);
  btnBrake.textContent = `Brake ${local.brake ? 'ACTIVE' : 'INACTIVE'}`;
  btnBrake.classList.toggle('btn--active', local.brake);
}

// ── Status flash ──────────────────────────────────────────────────────────────
let statusTimer = null;
function showStatus(msg, ok) {
  pubStatus.textContent = msg;
  pubStatus.className   = `publish-status ${ok ? 'status--ok' : 'status--err'}`;
  if (statusTimer) clearTimeout(statusTimer);
  statusTimer = setTimeout(() => {
    pubStatus.textContent = '';
    pubStatus.className   = 'publish-status';
  }, 2500);
}

// ── MQTT publish via POST /api/indicator ─────────────────────────────────────
// Left and right are a paired, mutually-exclusive group: turning one on always
// turns the other off.  They are sent together in one message so Kuksa sees a
// consistent state for both paths atomically.
// Brake and Driver ID are completely independent — never included here.
async function sendIndicatorPair() {
  try {
    const res = await fetch(INDICATOR_ENDPOINT, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ [PATH_LEFT]: local.left, [PATH_RIGHT]: local.right }),
    });
    if (res.ok) {
      showStatus('Published ✓', true);
    } else {
      const body = await res.json().catch(() => ({}));
      showStatus(`Error: ${body.error || res.statusText}`, false);
    }
  } catch (err) {
    showStatus(`Network error: ${err.message}`, false);
  }
}

// Single-signal publish — used for brake and driver ID so they never touch
// the indicator state.
async function sendSignal(path, value) {
  try {
    const res = await fetch(INDICATOR_ENDPOINT, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ [path]: value }),
    });
    if (res.ok) {
      showStatus('Published ✓', true);
    } else {
      const body = await res.json().catch(() => ({}));
      showStatus(`Error: ${body.error || res.statusText}`, false);
    }
  } catch (err) {
    showStatus(`Network error: ${err.message}`, false);
  }
}

async function sendDriverId() {
  const id = driverInput.value.trim().slice(0, 64);
  if (!id) return;
  stateDriver.textContent = id;
  await sendSignal(PATH_DRIVER, id);
}

// ── Button event listeners ────────────────────────────────────────────────────
// ◄ Left  — turns on left, releases right; brake/driverId unaffected.
btnLeft.addEventListener('click', () => {
  local.left  = !local.left;
  if (local.left) local.right = false;
  refreshInputDisplay();
  sendIndicatorPair();
});

// Right ► — turns on right, releases left; brake/driverId unaffected.
btnRight.addEventListener('click', () => {
  local.right = !local.right;
  if (local.right) local.left = false;
  refreshInputDisplay();
  sendIndicatorPair();
});

// ■ Off — releases both indicators; brake/driverId unaffected.
btnOff.addEventListener('click', () => {
  local.left  = false;
  local.right = false;
  refreshInputDisplay();
  sendIndicatorPair();
});

// Brake — fully independent; never touches left/right or driverId.
btnBrake.addEventListener('click', () => {
  local.brake = !local.brake;
  refreshInputDisplay();
  sendSignal(PATH_BRAKE, local.brake ? 'ACTIVE' : 'INACTIVE');
});

btnIdentify.addEventListener('click', sendDriverId);
driverInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendDriverId(); });

// ── Initial render ────────────────────────────────────────────────────────────
refreshInputDisplay();
applyLEDState(false, false, false);
