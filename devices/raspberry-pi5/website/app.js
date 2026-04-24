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

const STATUS_ENDPOINT = "/api/status";
const POLL_INTERVAL_MS = 5000;

let demoTick = 0;

function byId(id) {
  return document.getElementById(id);
}

function safeGet(obj, path, fallback = null) {
  return path.split(".").reduce((acc, key) => (acc && key in acc ? acc[key] : undefined), obj) ?? fallback;
}

function parseState(connection) {
  if (!connection || !connection.active) {
    return "inactive";
  }
  if (connection.traffic_detected) {
    return "active";
  }
  return "pending";
}

function setStateClass(element, state) {
  if (!element) return;
  element.classList.remove("active", "pending", "inactive");
  element.classList.add(state);
}

function setCardStatus(cardId, label, detail, state) {
  const card = byId(cardId);
  if (!card) return;

  setStateClass(card, state);
  const textEl = card.querySelector(".status-text");
  const detailEl = card.querySelector(".status-detail");
  if (textEl) textEl.textContent = label;
  if (detailEl) detailEl.textContent = detail;
}

function setConnectionState(connectionKey, connectionData) {
  const state = parseState(connectionData);
  const laneState = document.querySelector(`[data-lane-state="${connectionKey}"]`);

  if (laneState) {
    laneState.textContent = state === "active" ? "Active flow" : state === "pending" ? "Reachable, idle" : "Inactive";
  }

  document.querySelectorAll(`[data-conn="${connectionKey}"]`).forEach((element) => {
    setStateClass(element, state);
  });
}

function setNodeState(serviceKey, state) {
  document.querySelectorAll(`[data-service="${serviceKey}"]`).forEach((element) => {
    setStateClass(element, state);
  });
}

function updateTopbar(data, demoMode) {
  const ts = data.timestamp ? new Date(data.timestamp) : new Date();
  byId("last-update").textContent = `Last update: ${ts.toLocaleTimeString()}`;

  const modePill = byId("mode-pill");
  if (demoMode) {
    modePill.textContent = "Demo mode";
    document.body.classList.add("demo-mode");
  } else {
    modePill.textContent = "Live mode";
    document.body.classList.remove("demo-mode");
  }
}

function updateConnectionStates(data) {
  const keys = [
    "mqtt_transfer",
    "databroker_signals",
    "can_feedback",
    "fms_pipeline",
    "ankaios_workloads",
    "dozzle_monitoring",
  ];

  keys.forEach((key) => {
    const info = safeGet(data, `connections.${key}`, { active: false, traffic_detected: false });
    setConnectionState(key, info);
  });

  const mqttService = safeGet(data, "services.mqtt.active", false) ? "active" : "inactive";
  const kuksaService = safeGet(data, "services.kuksa.active", false) ? "active" : "inactive";

  setNodeState("mqtt", mqttService);
  setNodeState("kuksa", kuksaService);

  ["mqtt_transfer", "databroker_signals", "can_feedback", "fms_pipeline", "ankaios_workloads", "dozzle_monitoring"].forEach((key) => {
    const state = parseState(safeGet(data, `connections.${key}`, null));
    setNodeState(key, state);
  });
}

function updateServiceCards(data) {
  const mqttConn = safeGet(data, "connections.mqtt_transfer", { active: false, traffic_detected: false });
  const mqttSvc = safeGet(data, "services.mqtt", { detail: "no data" });
  const mqttState = parseState(mqttConn);
  setCardStatus(
    "svc-mqtt",
    mqttState === "active" ? "Active transfer" : mqttState === "pending" ? "Reachable, no traffic" : "Inactive",
    `${mqttSvc.detail}; traffic: ${mqttConn.traffic_detected ? "detected" : "not detected"}`,
    mqttState
  );

  const kuksaConn = safeGet(data, "connections.databroker_signals", { active: false, traffic_detected: false });
  const kuksaSvc = safeGet(data, "services.kuksa", { detail: "no data" });
  const kuksaState = parseState(kuksaConn);
  setCardStatus(
    "svc-kuksa",
    kuksaState === "active" ? "Signals active" : kuksaState === "pending" ? "Reachable, idle" : "Inactive",
    `${kuksaSvc.detail}; traffic: ${kuksaConn.traffic_detected ? "detected" : "not detected"}`,
    kuksaState
  );

  const ankConn = safeGet(data, "connections.ankaios_workloads", { active: false, traffic_detected: false });
  const ankDetail = safeGet(data, "connections.ankaios_workloads.detail", safeGet(data, "activity.ank_cli.detail", "no data"));
  const ankState = parseState(ankConn);
  setCardStatus(
    "svc-ankaios",
    ankState === "active" ? "Workloads visible" : ankState === "pending" ? "Reachable, low activity" : "Inactive",
    ankDetail,
    ankState
  );

  const dozzleConn = safeGet(data, "connections.dozzle_monitoring", { active: false, traffic_detected: false });
  const dozzleSvc = safeGet(data, "services.dozzle", { detail: "no data" });
  const dozzleState = parseState(dozzleConn);
  setCardStatus(
    "svc-dozzle",
    dozzleState === "active" ? "Monitoring active" : dozzleState === "pending" ? "Reachable, low activity" : "Inactive",
    dozzleSvc.detail,
    dozzleState
  );
}

function updateFrames(data) {
  const ankUrl = safeGet(data, "dashboards.ankaios.url", "");
  const dozzleUrl = safeGet(data, "dashboards.dozzle.url", "");

  const ankFrame = byId("ank-frame");
  const dozzleFrame = byId("dozzle-frame");
  const ankText = byId("ank-url");
  const dozzleText = byId("dozzle-url");
  const ankLink = byId("ank-open-link");
  const dozzleLink = byId("dozzle-open-link");

  if (ankText) ankText.textContent = ankUrl || "URL not configured";
  if (dozzleText) dozzleText.textContent = dozzleUrl || "URL not configured";

  if (ankLink) ankLink.href = ankUrl || "#";
  if (dozzleLink) dozzleLink.href = dozzleUrl || "#";

  if (ankFrame && ankUrl && ankFrame.getAttribute("src") !== ankUrl) {
    ankFrame.setAttribute("src", ankUrl);
  }
  if (dozzleFrame && dozzleUrl && dozzleFrame.getAttribute("src") !== dozzleUrl) {
    dozzleFrame.setAttribute("src", dozzleUrl);
  }
}

function updateContainerTable(data) {
  const rowsRoot = byId("container-rows");
  if (!rowsRoot) return;

  const containers = safeGet(data, "containers.running", []);
  if (!containers.length) {
    rowsRoot.innerHTML = '<tr><td colspan="4">No running containers detected</td></tr>';
    return;
  }

  rowsRoot.innerHTML = containers
    .slice(0, 30)
    .map((item) => {
      const runtime = item.runtime || "-";
      const name = item.name || "-";
      const image = item.image || "-";
      const status = item.status || item.state || "-";
      return `<tr><td>${runtime}</td><td>${name}</td><td>${image}</td><td>${status}</td></tr>`;
    })
    .join("");
}

function updateEventLog(data, demoMode) {
  const logRoot = byId("event-log");
  if (!logRoot) return;

  const events = [];
  const connections = data.connections || {};

  Object.entries(connections).forEach(([name, info]) => {
    const state = parseState(info);
    const readableName = name.replaceAll("_", " ");
    if (state === "active") {
      events.push(`${readableName}: active traffic`);
    } else if (state === "pending") {
      events.push(`${readableName}: reachable, waiting for traffic`);
    } else {
      events.push(`${readableName}: inactive`);
    }
  });

  const bridgeLines = safeGet(data, "activity.bridge.lines", null);
  const dbLines = safeGet(data, "activity.databroker.lines", null);
  if (bridgeLines !== null) events.push(`grpc-mqtt-bridge logs in window: ${bridgeLines}`);
  if (dbLines !== null) events.push(`databroker logs in window: ${dbLines}`);

  events.push(`containers detected: ${safeGet(data, "containers.running_count", 0)}`);
  events.push(`source mode: ${demoMode ? "simulated fallback" : "live probes"}`);

  logRoot.innerHTML = events.slice(0, 12).map((line) => `<li>${line}</li>`).join("");
}

function applyStatus(data, demoMode) {
  updateTopbar(data, demoMode);
  updateConnectionStates(data);
  updateServiceCards(data);
  updateFrames(data);
  updateContainerTable(data);
  updateEventLog(data, demoMode);
}

function buildDemoStatus() {
  demoTick += 1;
  const cycle = demoTick % 6;
  const highTraffic = cycle === 1 || cycle === 2 || cycle === 4;
  const lowTraffic = cycle === 0 || cycle === 5;

  return {
    timestamp: new Date().toISOString(),
    services: {
      mqtt: { active: true, detail: "TCP reachable at 127.0.0.1:1883" },
      kuksa: { active: true, detail: "TCP reachable at 127.0.0.1:55555" },
      ankaios_dashboard: { active: true, detail: "HTTP 200" },
      dozzle: { active: true, detail: "HTTP 200" },
    },
    dashboards: {
      ankaios: { url: "http://127.0.0.1:8084", reachable: true },
      dozzle: { url: "http://127.0.0.1:8080", reachable: true },
    },
    containers: {
      running_count: 6,
      running: [
        { runtime: "podman", name: "mosquitto-broker", image: "eclipse-mosquitto", status: "running" },
        { runtime: "podman", name: "grpc-mqtt-bridge", image: "grpc-mqtt-bridge", status: "running" },
        { runtime: "podman", name: "kuksa-can-provider", image: "kuksa-can-provider", status: "running" },
        { runtime: "docker", name: "fms-forwarder", image: "fms-forwarder", status: "running" },
        { runtime: "docker", name: "grafana", image: "grafana", status: "running" },
        { runtime: "docker", name: "dozzle", image: "dozzle", status: "running" },
      ],
    },
    activity: {
      bridge: { lines: highTraffic ? 22 : 3, keyword_hits: highTraffic ? 16 : 1 },
      databroker: { lines: highTraffic ? 18 : 2, keyword_hits: highTraffic ? 13 : 1 },
      ank_cli: { detail: "ank CLI unavailable in browser-only demo mode" },
    },
    connections: {
      mqtt_transfer: { active: true, traffic_detected: highTraffic },
      databroker_signals: { active: true, traffic_detected: highTraffic || lowTraffic },
      can_feedback: { active: true, traffic_detected: highTraffic },
      fms_pipeline: { active: false, traffic_detected: false },
      ankaios_workloads: { active: false, traffic_detected: false, detail: "Ankaios not detected in demo mode" },
      dozzle_monitoring: { active: true, traffic_detected: true },
    },
  };
}

async function fetchStatus(forceRefresh = false) {
  const endpoint = forceRefresh ? `${STATUS_ENDPOINT}?fresh=1` : STATUS_ENDPOINT;
  const response = await fetch(endpoint, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`status endpoint returned ${response.status}`);
  }
  return response.json();
}

async function pollStatus(forceRefresh = false) {
  try {
    const data = await fetchStatus(forceRefresh);
    applyStatus(data, false);
  } catch (error) {
    const fallback = buildDemoStatus();
    applyStatus(fallback, true);
  }
}

function installTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  const views = document.querySelectorAll(".view");

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.getAttribute("data-tab-target");
      buttons.forEach((entry) => entry.classList.remove("active"));
      button.classList.add("active");
      views.forEach((view) => {
        const matches = view.id === target;
        view.classList.toggle("active", matches);
      });
    });
  });
}

function installRefreshButton() {
  const button = byId("refresh-btn");
  if (!button) return;
  button.addEventListener("click", () => {
    pollStatus(true);
  });
}

function boot() {
  installTabs();
  installRefreshButton();
  pollStatus();
  setInterval(pollStatus, POLL_INTERVAL_MS);
}

boot();
