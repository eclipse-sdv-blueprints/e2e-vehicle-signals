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

#include <WiFiS3.h>
#include <ArduinoMqttClient.h>
#include "arduino_secrets.h"

char ssid[] = SECRET_SSID;    // your network SSID (name)
char pass[] = SECRET_PASS;    // your network password (use for WPA, or use as key for WEP)
int status = WL_IDLE_STATUS;  // the WiFi radio's status

WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

const char broker[] = "192.168.88.100";
const int brokerPort = 1883;
const char topic[] = "InVehicleTopics";

const unsigned long WIFI_RETRY_INTERVAL_MS = 5000;
const unsigned long MQTT_RETRY_INTERVAL_MS = 3000;

const int xPin = A0;  // VRX attach
const int yPin = A1;  // VRY attach
const int swPin = 8;  // SW attach (pressed = LOW)

const int joystickCenter = 512;
const int joystickDeadzone = 120;

bool leftIsSignaling = false;
bool rightIsSignaling = false;
bool brakeIsActive = false;
bool updatePending = false;

unsigned long lastWifiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;

void ensureWifiConnected();
void ensureMqttConnected();

void setup() {
  // set PINs for Joystick
  pinMode(swPin, INPUT_PULLUP);
  Serial.begin(115200);
  while(!Serial) { }

  // check for the WiFi module:
  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println("Communication with WiFi module failed!");
    // don't continue
    while (true)
      ;
  }

  String fv = WiFi.firmwareVersion();
  if (fv < WIFI_FIRMWARE_LATEST_VERSION) {
    Serial.println("Please upgrade the firmware");
  }

  ensureWifiConnected();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("You're connected to the network");
    printCurrentNet();
    printWifiData();
  }

  ensureMqttConnected();
}

void loop() {
  ensureWifiConnected();
  ensureMqttConnected();

  if (WiFi.status() == WL_CONNECTED && mqttClient.connected()) {
    mqttClient.poll();
  }

  int xValue = analogRead(xPin);
  int yValue = analogRead(yPin);
  bool swPressed = (digitalRead(swPin) == LOW);

  bool wantLeft = xValue < (joystickCenter - joystickDeadzone);
  bool wantRight = xValue > (joystickCenter + joystickDeadzone);
  bool wantBrake = yValue > (joystickCenter + joystickDeadzone);

  bool nextLeft = leftIsSignaling;
  bool nextRight = rightIsSignaling;

  if (swPressed) {
    nextLeft = false;
    nextRight = false;
  } else if (wantLeft && !wantRight) {
    nextLeft = true;
    nextRight = false;
  } else if (wantRight && !wantLeft) {
    nextLeft = false;
    nextRight = true;
  }

  if (nextLeft != leftIsSignaling || nextRight != rightIsSignaling || wantBrake != brakeIsActive) {
    leftIsSignaling = nextLeft;
    rightIsSignaling = nextRight;
    brakeIsActive = wantBrake;
    updatePending = true;
  }

  if (updatePending && WiFi.status() == WL_CONNECTED && mqttClient.connected()) {
    sendMqttUpdate(leftIsSignaling, rightIsSignaling, brakeIsActive);
    updatePending = false;
  }

  delay(10);
}

void printWifiData() {
  // print your board's IP address:
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");

  Serial.println(ip);

  // print your MAC address:
  byte mac[6];
  WiFi.macAddress(mac);
  Serial.print("MAC address: ");
  printMacAddress(mac);
}

void printCurrentNet() {
  // print the SSID of the network you're attached to:
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print the MAC address of the router you're attached to:
  byte bssid[6];
  WiFi.BSSID(bssid);
  Serial.print("BSSID: ");
  printMacAddress(bssid);

  // print the received signal strength:
  long rssi = WiFi.RSSI();
  Serial.print("signal strength (RSSI):");
  Serial.println(rssi);

  // print the encryption type:
  byte encryption = WiFi.encryptionType();
  Serial.print("Encryption Type:");
  Serial.println(encryption, HEX);
  Serial.println();
}

void printMacAddress(byte mac[]) {
  for (int i = 5; i >= 0; i--) {
    if (mac[i] < 16) {
      Serial.print("0");
    }
    Serial.print(mac[i], HEX);
    if (i > 0) {
      Serial.print(":");
    }
  }
  Serial.println();
}


void sendMqttUpdate(bool left, bool right, bool brake) {
  String payload = "{";
  payload += "\"Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling\":";
  payload += (left ? "true" : "false");
  payload += ",";
  payload += "\"Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling\":";
  payload += (right ? "true" : "false");
  payload += ",";
  payload += "\"Vehicle.Body.Lights.Brake.IsActive\":";
  payload += (brake ? "\"ACTIVE\"" : "\"INACTIVE\"");
  payload += "}";

  Serial.println("Publishing to MQTT:");
  Serial.println(payload);

  mqttClient.beginMessage(topic);
  mqttClient.print(payload);
  mqttClient.endMessage();
}

void ensureWifiConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  unsigned long now = millis();
  if (now - lastWifiAttemptMs < WIFI_RETRY_INTERVAL_MS) {
    return;
  }

  lastWifiAttemptMs = now;
  Serial.print("Attempting to connect to WPA SSID: ");
  Serial.println(ssid);
  status = WiFi.begin(ssid, pass);
}

void ensureMqttConnected() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (mqttClient.connected()) {
    return;
  }

  unsigned long now = millis();
  if (now - lastMqttAttemptMs < MQTT_RETRY_INTERVAL_MS) {
    return;
  }

  lastMqttAttemptMs = now;
  Serial.print("Attempting to connect to the MQTT broker: ");
  Serial.println(broker);

  if (!mqttClient.connect(broker, brokerPort)) {
    Serial.print("MQTT connection failed! Error code = ");
    Serial.println(mqttClient.connectError());
    return;
  }

  Serial.println("You're connected to the MQTT broker!");
  Serial.println();
  updatePending = true;
}
