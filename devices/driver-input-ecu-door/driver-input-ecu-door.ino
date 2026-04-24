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

/*
  Arduino Uno R4 WiFi + RC522 reader:
  - scan RFID UID
  - publish to MQTT broker on Raspberry Pi 5
  - payload key: Vehicle.Driver.Identifier.Subject
*/

#include <WiFiS3.h>
#include <ArduinoMqttClient.h>
#include "rfid1.h"
#include "arduino_secrets.h"

char ssid[] = SECRET_SSID;    // your network SSID (name)
char pass[] = SECRET_PASS;    // your network password (use for WPA, or use as key for WEP)
int status = WL_IDLE_STATUS;

WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);
RFID1 rfid;

const char broker[] = "192.168.88.100";
const int brokerPort = 1883;
const char topic[] = "InVehicleTopics";

const unsigned long WIFI_RETRY_INTERVAL_MS = 5000;
const unsigned long MQTT_RETRY_INTERVAL_MS = 3000;
const unsigned long RFID_REPUBLISH_INTERVAL_MS = 1500;

unsigned long lastWifiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;
unsigned long lastUidPublishMs = 0;

String pendingUid = "";
String lastUidPublished = "";

void ensureWifiConnected();
void ensureMqttConnected();
bool readRfidUid(String &uid);
void publishRfidUid(const String &uid);

void setup() {
  Serial.begin(115200);
  while (!Serial) {
  }

  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println("Communication with WiFi module failed!");
    while (true) {
    }
  }

  ensureWifiConnected();
  ensureMqttConnected();

  // IRQ_PIN, SCK_PIN, MOSI_PIN, MISO_PIN, SDA_PIN, RST_PIN
  rfid.begin(7, 5, 4, 3, 6, 2);
  delay(100);
  rfid.init();
}

void loop() {
  ensureWifiConnected();
  ensureMqttConnected();

  if (WiFi.status() == WL_CONNECTED && mqttClient.connected()) {
    mqttClient.poll();
  }

  if (pendingUid.length() > 0 && WiFi.status() == WL_CONNECTED && mqttClient.connected()) {
    publishRfidUid(pendingUid);
    pendingUid = "";
  }

  String uid = "";
  if (!readRfidUid(uid)) {
    delay(50);
    return;
  }

  unsigned long now = millis();
  if (uid == lastUidPublished && (now - lastUidPublishMs) < RFID_REPUBLISH_INTERVAL_MS) {
    delay(150);
    return;
  }

  if (WiFi.status() == WL_CONNECTED && mqttClient.connected()) {
    publishRfidUid(uid);
  } else {
    pendingUid = uid;
  }

  delay(150);
}

bool readRfidUid(String &uid) {
  uchar statusCode;
  uchar str[MAX_LEN];

  statusCode = rfid.request(PICC_REQIDL, str);
  if (statusCode != MI_OK) {
    return false;
  }

  statusCode = rfid.anticoll(str);
  if (statusCode != MI_OK) {
    return false;
  }

  uid = "";
  for (int i = 0; i < 4; i++) {
    if (str[i] < 0x10) {
      uid += "0";
    }
    uid += String(str[i], HEX);
  }
  uid.toUpperCase();
  rfid.halt();

  Serial.print("RFID UID: ");
  Serial.println(uid);
  return true;
}

void publishRfidUid(const String &uid) {
  String payload = "{\"Vehicle.Driver.Identifier.Subject\":\"";
  payload += uid;
  payload += "\"}";

  Serial.print("Publishing to MQTT ");
  Serial.print(topic);
  Serial.print(": ");
  Serial.println(payload);

  mqttClient.beginMessage(topic);
  mqttClient.print(payload);
  mqttClient.endMessage();

  lastUidPublished = uid;
  lastUidPublishMs = millis();
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
  Serial.print("Connecting WiFi SSID: ");
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
  Serial.print("Connecting MQTT broker: ");
  Serial.print(broker);
  Serial.print(":");
  Serial.println(brokerPort);

  if (!mqttClient.connect(broker, brokerPort)) {
    Serial.print("MQTT connection failed, error=");
    Serial.println(mqttClient.connectError());
    return;
  }

  Serial.println("Connected to MQTT broker");
}
