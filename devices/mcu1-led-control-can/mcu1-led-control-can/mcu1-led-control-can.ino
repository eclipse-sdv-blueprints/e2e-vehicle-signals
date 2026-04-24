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

#include <FastLED.h>  // Include FastLED library
#include <SPI.h>
#include <107-Arduino-MCP2515.h>
#undef max
#undef min

/**Globals for LED Strip**/
#define NUM_LEDS 8    // Number of LEDs in the chain
#define DATA_PIN 6    // Data pin for LED control

static uint8_t const LEFT_LED_INDEXES[]  = {0, 1};
static uint8_t const BRAKE_LED_INDEXES[] = {3, 4};
static uint8_t const RIGHT_LED_INDEXES[] = {6, 7};

CRGB leds[NUM_LEDS];  // Array to hold LED color data
/**END Globals for LED Strip**/

/*Globals for CAN MCP2515 */
static int const MKRCAN_MCP2515_CS_PIN  = 10;
static int const MKRCAN_MCP2515_INT_PIN = 2;
static uint16_t const CAN_ID_COMMAND = 0x120;
static uint16_t const CAN_ID_STATUS  = 0x121;
static uint8_t const CAN_SIGNAL_LEFT_BIT  = 0;
static uint8_t const CAN_SIGNAL_RIGHT_BIT = 1;
static uint8_t const CAN_SIGNAL_BRAKE_BIT = 2;

/**************************************************************************************
 * FUNCTION DECLARATION
 **************************************************************************************/

void onReceiveBufferFull(uint32_t const, uint32_t const, uint8_t const *, uint8_t const);

/**************************************************************************************
 * TYPEDEF
 **************************************************************************************/

struct LightState {
  bool left;
  bool right;
  bool brake;
};

bool canRxPending = false;

LightState requestedState = {false, false, false};

typedef struct {
  uint32_t ts;
  uint32_t id;
  uint8_t  len;
  uint8_t  data[8];
} CanRxFrame;

CanRxFrame rxFrame;

/**************************************************************************************
 * GLOBAL CONSTANTS
 **************************************************************************************/

/*END Globals for CAN MCP2515 */

// void onReceiveBufferFull(uint32_t const timestamp_us, uint32_t const id, uint8_t const * data, uint8_t const len)
// {
//   Serial.println(id, HEX);
// }
void onTransmitBufferEmpty(ArduinoMCP2515 * this_ptr)
{
  /* You can use this callback to refill the transmit buffer via this_ptr->transmit(...) */
}
/*CAN MCP2515 */
ArduinoMCP2515 mcp2515([]() { digitalWrite(MKRCAN_MCP2515_CS_PIN, LOW); },
                       []() { digitalWrite(MKRCAN_MCP2515_CS_PIN, HIGH); },
                       [](uint8_t const d) { return SPI.transfer(d); },
                       micros,
                       millis,
                       onReceiveBufferFull,
                       nullptr);
/*CAN MCP2515 */

void setup() {
  Serial.begin(115200);
  while(!Serial) { }

  SPI.begin();
  pinMode(MKRCAN_MCP2515_CS_PIN, OUTPUT);
  digitalWrite(MKRCAN_MCP2515_CS_PIN, HIGH);

  /* Attach interrupt handler to register MCP2515 signaled by taking INT low */
  pinMode(MKRCAN_MCP2515_INT_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(MKRCAN_MCP2515_INT_PIN), [](){ mcp2515.onExternalEventHandler(); }, FALLING);


  mcp2515.begin();
  mcp2515.setBitRate(CanBitRate::BR_500kBPS_8MHZ); // CAN bitrate and clock speed of MCP2515
  mcp2515.setNormalMode();
  /**Init LED Stripe**/
  FastLED.addLeds<NEOPIXEL, DATA_PIN>(leds, NUM_LEDS);  // Initialize LEDs
}

/**************************************************************************************
 * FUNCTION DEFINITION
 **************************************************************************************/
void onReceiveBufferFull(uint32_t const timestamp_us,
                         uint32_t const id,
                         uint8_t const * data,
                         uint8_t const len)
{
  if (canRxPending) return; // drop frame if not processed yet

  rxFrame.ts  = timestamp_us;
  rxFrame.id  = id;
  rxFrame.len = len;

  for (uint8_t i = 0; i < len; i++) {
    rxFrame.data[i] = data[i];
  }

  canRxPending = true;
}

// void onReceiveBufferFull(uint32_t const timestamp_us, uint32_t const id, uint8_t const * data, uint8_t const len)
// {
//   Serial.print("[ ");
//   Serial.print(timestamp_us);
//   Serial.print("] ");

//   Serial.print("ID");
//   if(id & MCP2515::CAN_EFF_BITMASK) Serial.print("(EXT)");
//   if(id & MCP2515::CAN_RTR_BITMASK) Serial.print("(RTR)");
//   Serial.print(" ");
//   Serial.print(id, HEX);

//   Serial.print(" DATA[");
//   Serial.print(len);
//   Serial.print("] ");
//   std::for_each(data,
//                 data+len,
//                 [](uint8_t const elem) {
//                   Serial.print(elem, HEX);
//                   Serial.print(" ");
//                 });
//   Serial.println();
// }

void loop() {
  static uint32_t lastBlinkToggle = 0;
  static uint32_t lastCanTx     = 0;
  static bool     blinkOn       = false;

  uint32_t now = millis();

  if (canRxPending) {
    noInterrupts();
    CanRxFrame f = rxFrame;
    canRxPending = false;
    interrupts();

    uint32_t normalized_id = f.id & ~(MCP2515::CAN_EFF_BITMASK | MCP2515::CAN_RTR_BITMASK);
    if (normalized_id == CAN_ID_COMMAND && f.len >= 1) {
      uint8_t flags = f.data[0];
      requestedState.left = (flags >> CAN_SIGNAL_LEFT_BIT) & 0x01;
      requestedState.right = (flags >> CAN_SIGNAL_RIGHT_BIT) & 0x01;
      requestedState.brake = (flags >> CAN_SIGNAL_BRAKE_BIT) & 0x01;
    }
  }

  /* ---------- LED animation (non-blocking) ---------- */
  if (now - lastBlinkToggle >= 500) {
    lastBlinkToggle = now;
    blinkOn = !blinkOn;
  }

  fill_solid(leds, NUM_LEDS, CRGB::Black);

  if (requestedState.left && blinkOn) {
    for (uint8_t index : LEFT_LED_INDEXES) {
      leds[index] = CRGB::Orange;
    }
  }

  if (requestedState.right && blinkOn) {
    for (uint8_t index : RIGHT_LED_INDEXES) {
      leds[index] = CRGB::Orange;
    }
  }

  if (requestedState.brake) {
    for (uint8_t index : BRAKE_LED_INDEXES) {
      leds[index] = CRGB::Red;
    }
  }

  FastLED.show();

  /* ---------- CAN transmit (rate limited) ----------- */
  if (now - lastCanTx >= 100) {
    lastCanTx = now;

    uint8_t data[8] = {0};
    data[0] = (requestedState.left ? (1 << CAN_SIGNAL_LEFT_BIT) : 0) |
              (requestedState.right ? (1 << CAN_SIGNAL_RIGHT_BIT) : 0) |
              (requestedState.brake ? (1 << CAN_SIGNAL_BRAKE_BIT) : 0);

    mcp2515.transmit(CAN_ID_STATUS, data, 1);
  }
}
