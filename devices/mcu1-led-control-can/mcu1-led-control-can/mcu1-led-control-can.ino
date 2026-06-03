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

// Idle gap LEDs between the function groups double as CAN status / error
// indicators. Index 2 sits between LEFT and BRAKE, index 5 between BRAKE and
// RIGHT — both are off in normal operation aside from the colour-coded
// heartbeat / error pattern below.
static uint8_t const STATUS_LED_INDEX = 2;
static uint8_t const ERROR_LED_INDEX  = 5;

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

// CAN RX error classes. The LED renderer maps each to a distinct colour on
// ERROR_LED_INDEX so a glance at the strip tells you whether the link is fine
// or actively misbehaving. We deliberately do NOT treat "no frames for a
// while" as an error — the kuksa-can-provider is purely event-driven and a
// quiet bus is the normal idle state.
static uint8_t const CAN_ERR_NONE           = 0;
static uint8_t const CAN_ERR_BUFFER_OVERRUN = 1; // frame dropped (loop too slow or MCP2515 RX overflow)
static uint8_t const CAN_ERR_BAD_FRAME      = 2; // unexpected ID or zero-length payload
static uint8_t const CAN_ERR_BUS_FAULT      = 3; // MCP2515 reports error-passive / bus-off

static uint32_t const CAN_ERROR_LATCH_MS    = 750;  // minimum on-time for a transient error
static uint32_t const CAN_EFLG_POLL_MS      = 200;  // how often we poll MCP2515 EFLG

// MCP2515 register addresses & SPI opcodes we use directly to inspect bus health.
static uint8_t const MCP2515_CMD_READ        = 0x03;
static uint8_t const MCP2515_CMD_BIT_MODIFY  = 0x05;
static uint8_t const MCP2515_REG_EFLG        = 0x2D;
static uint8_t const MCP2515_EFLG_RX1OVR     = 0x80;
static uint8_t const MCP2515_EFLG_RX0OVR     = 0x40;
static uint8_t const MCP2515_EFLG_TXBO       = 0x20; // bus-off
static uint8_t const MCP2515_EFLG_TXEP       = 0x10; // TX error-passive
static uint8_t const MCP2515_EFLG_RXEP       = 0x08; // RX error-passive
static uint8_t const MCP2515_EFLG_FAULT_MASK = MCP2515_EFLG_TXBO | MCP2515_EFLG_TXEP | MCP2515_EFLG_RXEP;
static uint8_t const MCP2515_EFLG_OVR_MASK   = MCP2515_EFLG_RX0OVR | MCP2515_EFLG_RX1OVR;


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
volatile uint8_t canIsrError = CAN_ERR_NONE;  // last error raised from ISR context

LightState requestedState = {false, false, false};

typedef struct {
  uint32_t ts;
  uint32_t id;
  uint8_t  len;
  uint8_t  data[8];
} CanRxFrame;

// Tiny ring buffer for incoming CAN frames. The MCP2515 has two hardware RX
// buffers (RXB0 + RXB1), and the library may drain both inside the same ISR
// call — our previous 1-deep mailbox was overrunning itself on back-to-back
// frames. A power-of-two size lets the index masking compile to a single AND.
static uint8_t const CAN_RX_QUEUE_SIZE = 4; // must be power of two
static uint8_t const CAN_RX_QUEUE_MASK = CAN_RX_QUEUE_SIZE - 1;
volatile CanRxFrame canRxQueue[CAN_RX_QUEUE_SIZE];
volatile uint8_t    canRxHead = 0; // next slot to write (ISR)
volatile uint8_t    canRxTail = 0; // next slot to read  (loop)

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

// Raw SPI read of a single MCP2515 register. We share the bus with the
// library's ISR, so guard the transaction with noInterrupts().
static uint8_t mcp2515ReadRegister(uint8_t addr) {
  uint8_t value;
  noInterrupts();
  digitalWrite(MKRCAN_MCP2515_CS_PIN, LOW);
  SPI.transfer(MCP2515_CMD_READ);
  SPI.transfer(addr);
  value = SPI.transfer(0x00);
  digitalWrite(MKRCAN_MCP2515_CS_PIN, HIGH);
  interrupts();
  return value;
}

// Clear the latched RX overflow flags so we can detect a fresh overrun next time.
static void mcp2515ClearRxOverflow() {
  noInterrupts();
  digitalWrite(MKRCAN_MCP2515_CS_PIN, LOW);
  SPI.transfer(MCP2515_CMD_BIT_MODIFY);
  SPI.transfer(MCP2515_REG_EFLG);
  SPI.transfer(MCP2515_EFLG_OVR_MASK); // mask: bits we want to touch
  SPI.transfer(0x00);                  // data:  clear them
  digitalWrite(MKRCAN_MCP2515_CS_PIN, HIGH);
  interrupts();
}

static const char * canErrorName(uint8_t err) {
  switch (err) {
    case CAN_ERR_NONE:           return "NONE";
    case CAN_ERR_BUFFER_OVERRUN: return "BUFFER_OVERRUN";
    case CAN_ERR_BAD_FRAME:      return "BAD_FRAME";
    case CAN_ERR_BUS_FAULT:      return "BUS_FAULT";
    default:                     return "UNKNOWN";
  }
}

// Print human-readable CAN error transitions on the serial console. Includes
// the raw MCP2515 EFLG byte when a fault is detected so the operator can tell
// bus-off from error-passive from RX overflow at a glance.
static void reportCanError(uint8_t err, uint32_t now, uint8_t eflg) {
  Serial.print("[");
  Serial.print(now);
  Serial.print(" ms] CAN error: ");
  Serial.print(canErrorName(err));
  if (err == CAN_ERR_BUS_FAULT || err == CAN_ERR_BUFFER_OVERRUN) {
    Serial.print(" (EFLG=0x");
    if (eflg < 0x10) Serial.print('0');
    Serial.print(eflg, HEX);
    Serial.print(")");
  }
  Serial.println();
}

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
  uint8_t nextHead = (canRxHead + 1) & CAN_RX_QUEUE_MASK;
  if (nextHead == canRxTail) {
    // Queue full — loop() can't keep up. Drop the frame and surface it.
    canIsrError = CAN_ERR_BUFFER_OVERRUN;
    return;
  }

  volatile CanRxFrame & slot = canRxQueue[canRxHead];
  slot.ts  = timestamp_us;
  slot.id  = id;
  slot.len = len;
  for (uint8_t i = 0; i < len && i < 8; i++) {
    slot.data[i] = data[i];
  }

  canRxHead = nextHead;
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
  static uint32_t lastCanTx       = 0;
  static uint32_t lastValidRxMs   = 0;
  static uint32_t lastEflgPoll    = 0;
  static uint32_t errorLatchedAt  = 0;
  static uint8_t  canError        = CAN_ERR_NONE;
  static uint8_t  reportedError   = CAN_ERR_NONE;
  static uint8_t  lastEflg        = 0x00;
  static bool     blinkOn         = false;

  uint32_t now = millis();

  // Drain any ISR-raised error first so it cannot get lost between iterations.
  noInterrupts();
  uint8_t isrErr = canIsrError;
  canIsrError = CAN_ERR_NONE;
  interrupts();
  if (isrErr != CAN_ERR_NONE) {
    canError = isrErr;
    errorLatchedAt = now;
  }

  // Drain every queued frame this iteration so a burst doesn't pile up.
  while (canRxTail != canRxHead) {
    noInterrupts();
    CanRxFrame f = const_cast<CanRxFrame &>(canRxQueue[canRxTail]);
    canRxTail = (canRxTail + 1) & CAN_RX_QUEUE_MASK;
    interrupts();

    uint32_t normalized_id = f.id & ~(MCP2515::CAN_EFF_BITMASK | MCP2515::CAN_RTR_BITMASK);
    if (normalized_id == CAN_ID_COMMAND && f.len >= 1) {
      uint8_t flags = f.data[0];
      requestedState.left  = (flags >> CAN_SIGNAL_LEFT_BIT) & 0x01;
      requestedState.right = (flags >> CAN_SIGNAL_RIGHT_BIT) & 0x01;
      requestedState.brake = (flags >> CAN_SIGNAL_BRAKE_BIT) & 0x01;

      lastValidRxMs = now;
      // Clear transient errors once a fresh valid frame and the latch window
      // have passed — keeps short blips visible long enough to be noticed.
      if (canError != CAN_ERR_NONE && (now - errorLatchedAt) >= CAN_ERROR_LATCH_MS) {
        canError = CAN_ERR_NONE;
      }
    } else if (normalized_id != CAN_ID_STATUS) {
      // Ignore self-echoes of our own status frame (some MCP2515 setups can
      // see them); only foreign IDs count as bad frames.
      canError = CAN_ERR_BAD_FRAME;
      errorLatchedAt = now;
    }
  }

  // Poll the MCP2515 error flags. Only real controller-level faults
  // (bus-off, error-passive, RX FIFO overflow) raise an error here; a quiet
  // bus with no frames is treated as healthy idle.
  if (now - lastEflgPoll >= CAN_EFLG_POLL_MS) {
    lastEflgPoll = now;
    uint8_t eflg = mcp2515ReadRegister(MCP2515_REG_EFLG);
    lastEflg = eflg;

    if (eflg & MCP2515_EFLG_FAULT_MASK) {
      canError = CAN_ERR_BUS_FAULT;
      errorLatchedAt = now;
    } else if (eflg & MCP2515_EFLG_OVR_MASK) {
      canError = CAN_ERR_BUFFER_OVERRUN;
      errorLatchedAt = now;
      mcp2515ClearRxOverflow(); // latch is sticky in hardware — clear it
    } else if (canError != CAN_ERR_NONE && (now - errorLatchedAt) >= CAN_ERROR_LATCH_MS) {
      // No fault flags set and the latch window has elapsed — clear LED.
      canError = CAN_ERR_NONE;
    }
  }

  // Emit a serial line whenever the CAN error class changes so operators can
  // correlate LED indications with what happened on the bus.
  if (canError != reportedError) {
    reportCanError(canError, now, lastEflg);
    reportedError = canError;
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

  /* ---------- CAN status / error indicator ---------- */
  // Heartbeat: dim green pulse on STATUS_LED_INDEX whenever the controller
  // reports no faults. A briefly brighter blip on each valid RX gives a
  // visual cue of incoming traffic without making silence look like an error.
  if (canError == CAN_ERR_NONE) {
    bool recentRx = (lastValidRxMs != 0 && (now - lastValidRxMs) <= 250);
    // Dim teal blip on RX so it's colour-distinct from the green heartbeat
    // without being bright enough to draw the eye.
    leds[STATUS_LED_INDEX] = recentRx ? CRGB(0, 8, 8)
                                       : (blinkOn ? CRGB(0, 16, 0) : CRGB(0, 4, 0));
  }

  // Distinct colour per error class, blinked so it's hard to miss.
  switch (canError) {
    case CAN_ERR_BUFFER_OVERRUN:
      leds[ERROR_LED_INDEX] = blinkOn ? CRGB::Yellow : CRGB::Black;
      break;
    case CAN_ERR_BAD_FRAME:
      leds[ERROR_LED_INDEX] = blinkOn ? CRGB::Purple : CRGB::Black;
      break;
    case CAN_ERR_BUS_FAULT:
      // Real controller-level fault (bus-off / error-passive) — solid red on
      // both gap LEDs so it's unmistakable.
      leds[STATUS_LED_INDEX] = CRGB::Red;
      leds[ERROR_LED_INDEX]  = CRGB::Red;
      break;
    case CAN_ERR_NONE:
    default:
      break;
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
