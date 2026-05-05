/********************************************************************************
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
 ********************************************************************************/

#ifndef RFID_H
#define RFID_H

#include <Arduino.h>
#include "swspi.h"

/* ── Type aliases ─────────────────────────────────────────────────────────── */

typedef unsigned char uchar;
typedef unsigned int  uint;

/* ── Buffer size ──────────────────────────────────────────────────────────── */

#define MAX_LEN 16

/* ── Result codes ─────────────────────────────────────────────────────────── */

#define MI_OK       0
#define MI_NOTAGERR 1
#define MI_ERR      2

/* ── PICC request mode constants ──────────────────────────────────────────── */

#define PICC_REQIDL  0x26   /* search for cards not in HALT state */
#define PICC_REQALL  0x52   /* search for all cards including HALT state */

/* ── PICC command constants ───────────────────────────────────────────────── */

#define PICC_ANTICOLL   0x93
#define PICC_SElECTTAG  0x93
#define PICC_AUTHENT1A  0x60
#define PICC_AUTHENT1B  0x61
#define PICC_READ       0x30
#define PICC_WRITE      0xA0
#define PICC_DECREMENT  0xC0
#define PICC_INCREMENT  0xC1
#define PICC_RESTORE    0xC2
#define PICC_TRANSFER   0xB0
#define PICC_HALT       0x50

/* ── PCD command constants ────────────────────────────────────────────────── */

#define PCD_IDLE        0x00
#define PCD_AUTHENT     0x0E
#define PCD_RECEIVE     0x08
#define PCD_TRANSMIT    0x04
#define PCD_TRANSCEIVE  0x0C
#define PCD_RESETPHASE  0x0F
#define PCD_CALCCRC     0x03

/* ── RFID class ───────────────────────────────────────────────────────────── */

/**
 * High-level interface for the MFRC522-compatible RFID/NFC reader module
 * over a software SPI transport.
 *
 * Required call sequence:
 *   1. begin(...)   – configure GPIO pins
 *   2. init()       – release reset, configure reader, enable antenna
 *   3. request(...) – probe for a card
 *   4. anticoll(...)– retrieve 4-byte UID
 *   5. halt()       – place card in HALT state
 */
class RFID {
public:
    /**
     * Configure SPI GPIO pins and reader control pins.
     *
     * Must be called exactly once before any other method.
     *
     * @param csnPin         SPI chip-select pin used by the SWSPI transport.
     * @param sckPin         SPI clock pin.
     * @param mosiPin        SPI MOSI pin.
     * @param misoPin        SPI MISO pin.
     * @param chipSelectPin  Reader SDA/SS chip-select pin for register access.
     * @param NRSTPD         Reader reset/power-down pin.
     */
    void begin(uchar csnPin, uchar sckPin, uchar mosiPin, uchar misoPin,
               uchar chipSelectPin, uchar NRSTPD);

    /**
     * Initialize the reader to the operational state.
     *
     * Releases reset, issues a soft reset, configures the timer/modulation/CRC
     * registers for ISO 14443A, enables 100% ASK, and enables the antenna.
     * Must be called after begin().
     */
    void init(void);

    /** Issue a soft reset to the reader, restoring register defaults. */
    void reset(void);

    /** Enable the RF antenna output (no-op if already enabled). */
    void antennaOn(void);

    /** Disable the RF antenna output. */
    void antennaOff(void);

    /**
     * Write one byte to a reader register.
     * Address encoding follows the MFRC522 SPI write protocol.
     */
    void writeTo(uchar addr, uchar val);

    /**
     * Read one byte from a reader register.
     * Address encoding follows the MFRC522 SPI read protocol.
     * Returns the byte value read from the addressed register.
     */
    uchar readFrom(uchar addr);

    /** Set bits specified by mask in register reg (read-modify-write). */
    void setBitMask(uchar reg, uchar mask);

    /** Clear bits specified by mask in register reg (read-modify-write). */
    void clearBitMask(uchar reg, uchar mask);

    /**
     * Probe the RF field for a card and obtain the ATQA card type bytes.
     *
     * @param reqMode  PICC_REQIDL or PICC_REQALL.
     * @param TagType  Caller-supplied buffer of at least 2 bytes; receives ATQA.
     * @return MI_OK on success, MI_ERR on any failure.
     */
    uchar request(uchar reqMode, uchar *TagType);

    /**
     * Execute a raw reader command exchange with the card.
     *
     * @param command   PCD_AUTHENT or PCD_TRANSCEIVE.
     * @param sendData  Outbound data bytes.
     * @param sendLen   Number of outbound bytes.
     * @param backData  Caller-supplied buffer for the card response (≥ MAX_LEN bytes).
     * @param backLen   Receives the response length in bits.
     * @return MI_OK, MI_NOTAGERR, or MI_ERR.
     */
    uchar toCard(uchar command, uchar *sendData, uchar sendLen,
                 uchar *backData, uint *backLen);

    /**
     * Execute ISO 14443A single-cascade anti-collision and retrieve a 4-byte UID.
     *
     * @param serNum  Caller-supplied buffer of at least 5 bytes;
     *                receives UID bytes [0..3] and BCC byte [4].
     * @return MI_OK on success (BCC verified), MI_ERR on failure.
     */
    uchar anticoll(uchar *serNum);

    /**
     * Compute a 2-byte CRC over len bytes using the reader hardware CRC engine.
     *
     * @param pIndata   Input data.
     * @param len       Number of input bytes.
     * @param pOutData  Caller-supplied buffer of at least 2 bytes; receives CRC.
     */
    void calulateCRC(uchar *pIndata, uchar len, uchar *pOutData);

    /**
     * Write a 16-byte block to the card (MIFARE Classic write sequence).
     *
     * The target sector must be authenticated by the caller before use.
     *
     * @param blockAddr  Target block address on the card.
     * @param writeData  Exactly 16 bytes of data to write.
     * @return MI_OK on success, MI_ERR on any failure.
     */
    uchar write(uchar blockAddr, uchar *writeData);

    /**
     * Print the 4-byte card UID to Serial as 8 uppercase hex digits.
     * No separators or newline are appended.
     * Serial must be initialized by the caller.
     *
     * @param id  Pointer to a buffer of at least 4 UID bytes.
     */
    void showCardID(uchar *id);

    /**
     * Print "Card type: <label>\n" to Serial and return the label pointer.
     * Callers MUST NOT use the return value.
     *
     * @param type  Pointer to at least 2 card type bytes from request().
     */
    char *showCardType(uchar *type);

    /**
     * Return a string literal identifying the card type.
     * Returns "Unknown" for unrecognized type bytes.
     *
     * @param type  Pointer to at least 2 card type bytes from request().
     */
    char *readCardType(uchar *type);

    /**
     * Instruct the card to enter HALT state.
     * Transmits the ISO 14443A HALT command with a valid CRC.
     */
    void halt(void);

private:
    SWSPI spi;
    uchar _chipSelectPin;
    uchar _nrstpd;
};

#endif /* RFID_H */
