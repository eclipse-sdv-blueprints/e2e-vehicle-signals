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
  Arduino Uno R4 WiFi + SG90 servo:
  - receives door actuator commands over minimal SOME/IP/UDP
  - moves servo as opening/closing actuator
  - publishes current door state over minimal SOME/IP/UDP
*/

#include <WiFiS3.h>
#include <WiFiUdp.h>
#include <Servo.h>
#include "arduino_secrets.h"
#include "arduino_config.h"

char ssid[] = SECRET_SSID;    // your network SSID (name)
char pass[] = SECRET_PASS;    // your network password (use for WPA, or use as key for WEP)
int status = WL_IDLE_STATUS;

WiFiClient wifiClient;
WiFiUDP udp;
Servo doorServo;

unsigned long lastWifiAttemptMs = 0;
unsigned long lastServoStepMs = 0;

int servoAngle = SERVO_MIN_ANGLE;
bool hasPrintedWifiIp = false;
bool doorTargetOpen = false;
bool lastPublishedDoorOpen = false;
bool hasPublishedDoorState = false;
bool pendingDoorStatePublish = false;
bool pendingDoorStateValue = false;
uint16_t someipSessionId = 1;

void ensureWifiConnected();
void receiveDoorTarget();
bool decodeDoorTarget(const uint8_t *packet, int packetSize, bool &targetOpen);
void updateServoActuator();
void publishDoorState(bool isOpen);
void writeUint16(uint8_t *buffer, uint16_t value);
void writeUint32(uint8_t *buffer, uint32_t value);
uint16_t readUint16(const uint8_t *buffer);
uint32_t readUint32(const uint8_t *buffer);

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
  udp.begin(SOMEIP_LOCAL_PORT);

  doorServo.attach(SERVO_PIN);
  doorServo.write(servoAngle);
}

void loop() {
  ensureWifiConnected();
  receiveDoorTarget();

  if (!hasPublishedDoorState && WiFi.status() == WL_CONNECTED) {
    publishDoorState(servoAngle >= SERVO_MAX_ANGLE);
  }

  if (pendingDoorStatePublish && WiFi.status() == WL_CONNECTED) {
    publishDoorState(pendingDoorStateValue);
    pendingDoorStatePublish = false;
  }

  updateServoActuator();
  delay(10);
}

void ensureWifiConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!hasPrintedWifiIp) {
      Serial.print("WiFi connected, IP: ");
      Serial.println(WiFi.localIP());
      hasPrintedWifiIp = true;
    }
    return;
  }

  hasPrintedWifiIp = false;

  unsigned long now = millis();
  if (now - lastWifiAttemptMs < WIFI_RETRY_INTERVAL_MS) {
    return;
  }

  lastWifiAttemptMs = now;
  Serial.print("Connecting WiFi SSID: ");
  Serial.println(ssid);
  status = WiFi.begin(ssid, pass);
}

void receiveDoorTarget() {
  int packetSize = udp.parsePacket();
  if (packetSize <= 0 || packetSize > SOMEIP_PACKET_SIZE) {
    return;
  }

  uint8_t packet[SOMEIP_PACKET_SIZE];
  int received = udp.read(packet, packetSize);
  bool targetOpen = false;
  if (!decodeDoorTarget(packet, received, targetOpen)) {
    return;
  }

  if (doorTargetOpen != targetOpen) {
    doorTargetOpen = targetOpen;
    Serial.print("SOME/IP door target received: ");
    Serial.println(doorTargetOpen ? "OPEN" : "CLOSED");
  }
}

bool decodeDoorTarget(const uint8_t *packet, int packetSize, bool &targetOpen) {
  if (packetSize != SOMEIP_PACKET_SIZE || readUint16(packet) != SOMEIP_SERVICE_ID ||
      readUint16(packet + 2) != SOMEIP_TARGET_EVENT_ID || readUint32(packet + 4) != 9 ||
      packet[12] != 1 || packet[13] != SOMEIP_INTERFACE_VERSION || packet[14] != 0x02 ||
      packet[15] != 0x00) {
    return false;
  }
  targetOpen = packet[16] != 0;
  return true;
}

void updateServoActuator() {
  unsigned long now = millis();
  if (now - lastServoStepMs < SERVO_STEP_INTERVAL_MS) {
    return;
  }

  lastServoStepMs = now;
  int targetAngle = doorTargetOpen ? SERVO_MAX_ANGLE : SERVO_MIN_ANGLE;

  if (servoAngle < targetAngle) {
    servoAngle += SERVO_STEP_DEGREES;
    if (servoAngle > targetAngle) {
      servoAngle = targetAngle;
    }
  } else if (servoAngle > targetAngle) {
    servoAngle -= SERVO_STEP_DEGREES;
    if (servoAngle < targetAngle) {
      servoAngle = targetAngle;
    }
  } else {
    return;
  }

  doorServo.write(servoAngle);

  bool isOpen = (servoAngle >= SERVO_MAX_ANGLE);
  if (!hasPublishedDoorState || isOpen != lastPublishedDoorOpen) {
    if (WiFi.status() == WL_CONNECTED) {
      publishDoorState(isOpen);
    } else {
      pendingDoorStatePublish = true;
      pendingDoorStateValue = isOpen;
    }
  }
}

void publishDoorState(bool isOpen) {
  uint8_t packet[SOMEIP_PACKET_SIZE] = {0};
  writeUint16(packet, SOMEIP_SERVICE_ID);
  writeUint16(packet + 2, SOMEIP_STATE_EVENT_ID);
  writeUint32(packet + 4, 9);
  writeUint16(packet + 8, SOMEIP_CLIENT_ID);
  writeUint16(packet + 10, someipSessionId++);
  packet[12] = 1;
  packet[13] = SOMEIP_INTERFACE_VERSION;
  packet[14] = 0x02;
  packet[15] = 0x00;
  packet[16] = isOpen ? 1 : 0;

  udp.beginPacket(SOMEIP_BRIDGE_IP, SOMEIP_BRIDGE_PORT);
  udp.write(packet, sizeof(packet));
  udp.endPacket();

  Serial.print("SOME/IP door state sent: ");
  Serial.println(isOpen ? "OPEN" : "CLOSED");

  lastPublishedDoorOpen = isOpen;
  hasPublishedDoorState = true;
}

void writeUint16(uint8_t *buffer, uint16_t value) {
  buffer[0] = (uint8_t)(value >> 8);
  buffer[1] = (uint8_t)value;
}

void writeUint32(uint8_t *buffer, uint32_t value) {
  buffer[0] = (uint8_t)(value >> 24);
  buffer[1] = (uint8_t)(value >> 16);
  buffer[2] = (uint8_t)(value >> 8);
  buffer[3] = (uint8_t)value;
}

uint16_t readUint16(const uint8_t *buffer) {
  return ((uint16_t)buffer[0] << 8) | buffer[1];
}

uint32_t readUint32(const uint8_t *buffer) {
  return ((uint32_t)buffer[0] << 24) | ((uint32_t)buffer[1] << 16) |
         ((uint32_t)buffer[2] << 8) | buffer[3];
}
