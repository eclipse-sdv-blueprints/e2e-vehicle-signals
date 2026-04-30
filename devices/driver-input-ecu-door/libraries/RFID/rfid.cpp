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

#include "rfid.h"

/* ── MFRC522 register addresses ───────────────────────────────────────────── */
/* Page 0: Command and status                                                   */
#define REG_COMMAND       0x01  /* starts/stops command execution               */
#define REG_COM_I_EN      0x02  /* enable/disable IRQ request control bits       */
#define REG_DIV_I_EN      0x03  /* enable/disable interrupt request control bits */
#define REG_COM_IRQ       0x04  /* interrupt request bits                        */
#define REG_DIV_IRQ       0x05  /* interrupt request bits                        */
#define REG_ERROR         0x06  /* error bits for last command                   */
#define REG_FIFO_DATA     0x09  /* I/O to/from FIFO                             */
#define REG_FIFO_LEVEL    0x0A  /* number of bytes stored in FIFO               */
#define REG_CONTROL       0x0C  /* miscellaneous control register                */
#define REG_BIT_FRAMING   0x0D  /* bit-oriented frame adjustments               */

/* Page 1: Communication                                                        */
#define REG_MODE          0x11  /* defines general modes for transmitting/rx     */
#define REG_TX_CONTROL    0x14  /* controls antenna driver pins TX1 and TX2      */
#define REG_TX_ASK        0x15  /* controls the setting of the transmission ASK  */

/* Page 2: Configuration                                                        */
#define REG_CRC_RESULT_M  0x21  /* MSB of CRC calculation                       */
#define REG_CRC_RESULT_L  0x22  /* LSB of CRC calculation                       */
#define REG_T_MODE        0x2A  /* timer settings                                */
#define REG_T_PRESCALER   0x2B  /* timer prescaler                               */
#define REG_T_RELOAD_H    0x2C  /* timer reload value, high byte                 */
#define REG_T_RELOAD_L    0x2D  /* timer reload value, low byte                  */

/* ── MFRC522 SPI address encoding ────────────────────────────────────────────
 *   Write: (addr << 1) & 0x7E          — MSB = 0, bits[6:1] = addr, LSB = 0
 *   Read:  ((addr << 1) & 0x7E) | 0x80 — MSB = 1, bits[6:1] = addr, LSB = 0
 * ─────────────────────────────────────────────────────────────────────────── */
#define ADDR_WRITE(a)  (((a) << 1) & 0x7E)
#define ADDR_READ(a)   (((a) << 1) & 0x7E | 0x80)

/* ── Antenna control bit mask in TxControlReg ─────────────────────────────── */
#define TX_CONTROL_ANTENNA_MASK 0x03   /* Tx1RFEn | Tx2RFEn */

/* ── toCard() finite loop iteration count (prevents infinite blocking) ─────── */
#define TOCARD_TIMEOUT_ITER 2000u

/* ── calulateCRC() finite loop iteration count ───────────────────────────── */
#define CRC_TIMEOUT_ITER 0xFFu

/* ═══════════════════════════════════════════════════════════════════════════ *
 *  Lifecycle                                                                  *
 * ═══════════════════════════════════════════════════════════════════════════ */

void RFID::begin(uchar csnPin, uchar sckPin, uchar mosiPin, uchar misoPin,
                 uchar chipSelectPin, uchar NRSTPD) {
    _chipSelectPin = chipSelectPin;
    _nrstpd        = NRSTPD;

    spi.begin(csnPin, sckPin, mosiPin, misoPin);

    pinMode(_chipSelectPin, OUTPUT);
    pinMode(_nrstpd,        OUTPUT);

    digitalWrite(_chipSelectPin, HIGH);
}

void RFID::init(void) {
    /* Release reader from power-down / reset state */
    digitalWrite(_nrstpd, HIGH);

    reset();

    /* Timer: auto-start after each transmission                               *
     *   TAuto=1, fTimer = 13.56 MHz / (2 * 0x0D3E + 1) ≈ 1.7 kHz           *
     *   Reload = 0x001E → ~17.6 ms timeout, sufficient for ISO 14443A        */
    writeTo(REG_T_MODE,      0x8D);
    writeTo(REG_T_PRESCALER, 0x3E);
    writeTo(REG_T_RELOAD_L,  0x1E);
    writeTo(REG_T_RELOAD_H,  0x00);

    /* 100% ASK modulation */
    writeTo(REG_TX_ASK, 0x40);

    /* CRC preset value 0x6363 (ISO 14443A) */
    writeTo(REG_MODE, 0x3D);

    antennaOn();
}

void RFID::reset(void) {
    writeTo(REG_COMMAND, PCD_RESETPHASE);
}

/* ═══════════════════════════════════════════════════════════════════════════ *
 *  Antenna control                                                             *
 * ═══════════════════════════════════════════════════════════════════════════ */

void RFID::antennaOn(void) {
    uchar tmp = readFrom(REG_TX_CONTROL);
    if (!(tmp & TX_CONTROL_ANTENNA_MASK)) {
        setBitMask(REG_TX_CONTROL, TX_CONTROL_ANTENNA_MASK);
    }
}

void RFID::antennaOff(void) {
    clearBitMask(REG_TX_CONTROL, TX_CONTROL_ANTENNA_MASK);
}

/* ═══════════════════════════════════════════════════════════════════════════ *
 *  Low-level register access                                                   *
 * ═══════════════════════════════════════════════════════════════════════════ */

void RFID::writeTo(uchar addr, uchar val) {
    digitalWrite(_chipSelectPin, LOW);
    spi.SPI_RW(ADDR_WRITE(addr));
    spi.SPI_RW(val);
    digitalWrite(_chipSelectPin, HIGH);
}

uchar RFID::readFrom(uchar addr) {
    uchar result;
    digitalWrite(_chipSelectPin, LOW);
    spi.SPI_RW(ADDR_READ(addr));
    result = spi.SPI_RW(0x00);
    digitalWrite(_chipSelectPin, HIGH);
    return result;
}

void RFID::setBitMask(uchar reg, uchar mask) {
    writeTo(reg, readFrom(reg) | mask);
}

void RFID::clearBitMask(uchar reg, uchar mask) {
    writeTo(reg, readFrom(reg) & (~mask));
}

/* ═══════════════════════════════════════════════════════════════════════════ *
 *  Core command exchange                                                       *
 * ═══════════════════════════════════════════════════════════════════════════ */

uchar RFID::toCard(uchar command, uchar *sendData, uchar sendLen,
                   uchar *backData, uint *backLen) {
    uchar status  = MI_ERR;
    uchar irqEn   = 0x00;
    uchar waitIRq = 0x00;

    switch (command) {
        case PCD_AUTHENT:
            irqEn   = 0x12;   /* IdleIEn | ErrIEn */
            waitIRq = 0x10;   /* IdleIRq */
            break;
        case PCD_TRANSCEIVE:
            irqEn   = 0x77;   /* TxIEn | RxIEn | IdleIEn | LoAlertIEn | ErrIEn | TimerIEn */
            waitIRq = 0x30;   /* RxIRq | IdleIRq */
            break;
        default:
            break;
    }

    /* Enable the requested IRQ sources, allow propagation to IRQ pin */
    writeTo(REG_COM_I_EN,   irqEn | 0x80);
    /* Clear all interrupt request bits */
    clearBitMask(REG_COM_IRQ, 0x80);
    /* Flush FIFO */
    setBitMask(REG_FIFO_LEVEL, 0x80);
    /* Idle (stop active command) */
    writeTo(REG_COMMAND, PCD_IDLE);

    /* Write data into FIFO */
    for (uchar i = 0; i < sendLen; i++) {
        writeTo(REG_FIFO_DATA, sendData[i]);
    }

    /* Execute command */
    writeTo(REG_COMMAND, command);

    /* For TRANSCEIVE, set StartSend to trigger transmission */
    if (command == PCD_TRANSCEIVE) {
        setBitMask(REG_BIT_FRAMING, 0x80);
    }

    /* Wait for completion or timeout */
    uchar n;
    uint  i = TOCARD_TIMEOUT_ITER;
    do {
        n = readFrom(REG_COM_IRQ);
        i--;
    } while ((i != 0) && !(n & 0x01) && !(n & waitIRq));

    /* Clear StartSend */
    clearBitMask(REG_BIT_FRAMING, 0x80);

    if (i != 0) {
        /* No buffer-overflow, collision, CRC, framing, or protocol errors */
        if (!(readFrom(REG_ERROR) & 0x1B)) {
            status = MI_OK;

            /* Timer IRQ fired with no tag response */
            if (n & irqEn & 0x01) {
                status = MI_NOTAGERR;
            }

            if (command == PCD_TRANSCEIVE) {
                uchar byteCount = readFrom(REG_FIFO_LEVEL);
                uchar lastBits  = readFrom(REG_CONTROL) & 0x07;

                if (lastBits != 0) {
                    *backLen = ((uint)(byteCount - 1) * 8) + lastBits;
                } else {
                    *backLen = (uint)byteCount * 8;
                }

                if (byteCount == 0) {
                    byteCount = 1;
                }
                if (byteCount > MAX_LEN) {
                    byteCount = MAX_LEN;
                }

                for (uchar j = 0; j < byteCount; j++) {
                    backData[j] = readFrom(REG_FIFO_DATA);
                }
            }
        } else {
            status = MI_ERR;
        }
    }

    return status;
}

/* ═══════════════════════════════════════════════════════════════════════════ *
 *  High-level card operations                                                  *
 * ═══════════════════════════════════════════════════════════════════════════ */

uchar RFID::request(uchar reqMode, uchar *TagType) {
    uint backBits;

    /* Short frame: only 7 bits in the last (and only) transmitted byte */
    writeTo(REG_BIT_FRAMING, 0x07);

    TagType[0] = reqMode;
    uchar status = toCard(PCD_TRANSCEIVE, TagType, 1, TagType, &backBits);

    /* A valid ATQA response is exactly 16 bits */
    if ((status != MI_OK) || (backBits != 16)) {
        status = MI_ERR;
    }

    return status;
}

uchar RFID::anticoll(uchar *serNum) {
    uint unLen;

    /* Full byte transmission: TxLastBits = 0 */
    writeTo(REG_BIT_FRAMING, 0x00);

    serNum[0] = PICC_ANTICOLL;
    serNum[1] = 0x20;   /* NVB: 2 command bytes, 0 UID bytes sent */

    uchar status = toCard(PCD_TRANSCEIVE, serNum, 2, serNum, &unLen);

    if (status == MI_OK) {
        /* Verify BCC: XOR of UID bytes 0..3 must equal byte 4 */
        uchar bcc = 0;
        for (uchar i = 0; i < 4; i++) {
            bcc ^= serNum[i];
        }
        if (bcc != serNum[4]) {
            status = MI_ERR;
        }
    }

    return status;
}

void RFID::calulateCRC(uchar *pIndata, uchar len, uchar *pOutData) {
    /* Clear CRC IRQ flag */
    clearBitMask(REG_DIV_IRQ, 0x04);
    /* Flush FIFO */
    setBitMask(REG_FIFO_LEVEL, 0x80);

    for (uchar i = 0; i < len; i++) {
        writeTo(REG_FIFO_DATA, pIndata[i]);
    }
    writeTo(REG_COMMAND, PCD_CALCCRC);

    /* Wait for CRC engine to complete (finite timeout) */
    uchar i = CRC_TIMEOUT_ITER;
    uchar n;
    do {
        n = readFrom(REG_DIV_IRQ);
        i--;
    } while ((i != 0) && !(n & 0x04));  /* CRCIRq bit */

    pOutData[0] = readFrom(REG_CRC_RESULT_L);
    pOutData[1] = readFrom(REG_CRC_RESULT_M);
}

uchar RFID::write(uchar blockAddr, uchar *writeData) {
    uint  recvBits;
    uchar buff[18];

    /* Phase 1: send WRITE command + block address + CRC */
    buff[0] = PICC_WRITE;
    buff[1] = blockAddr;
    calulateCRC(buff, 2, &buff[2]);

    uchar status = toCard(PCD_TRANSCEIVE, buff, 4, buff, &recvBits);
    if ((status != MI_OK) || (recvBits != 4) || ((buff[0] & 0x0F) != 0x0A)) {
        return MI_ERR;
    }

    /* Phase 2: send 16 data bytes + CRC */
    for (uchar i = 0; i < 16; i++) {
        buff[i] = writeData[i];
    }
    calulateCRC(buff, 16, &buff[16]);

    status = toCard(PCD_TRANSCEIVE, buff, 18, buff, &recvBits);
    if ((status != MI_OK) || (recvBits != 4) || ((buff[0] & 0x0F) != 0x0A)) {
        return MI_ERR;
    }

    return MI_OK;
}

void RFID::halt(void) {
    uchar buff[4];
    uint  unLen;

    buff[0] = PICC_HALT;
    buff[1] = 0x00;
    calulateCRC(buff, 2, &buff[2]);
    toCard(PCD_TRANSCEIVE, buff, 4, buff, &unLen);
}

/* ═══════════════════════════════════════════════════════════════════════════ *
 *  Serial output helpers                                                       *
 * ═══════════════════════════════════════════════════════════════════════════ */

void RFID::showCardID(uchar *id) {
    for (int i = 0; i < 4; i++) {
        if (id[i] < 0x10) {
            Serial.print('0');
        }
        Serial.print(id[i], HEX);   /* Arduino HEX prints uppercase */
    }
}

char *RFID::readCardType(uchar *type) {
    if (type[0] == 0x04 && type[1] == 0x00) return (char *)"MFOne-S50";
    if (type[0] == 0x02 && type[1] == 0x00) return (char *)"MFOne-S70";
    if (type[0] == 0x44 && type[1] == 0x00) return (char *)"MF-UltraLight";
    if (type[0] == 0x08 && type[1] == 0x00) return (char *)"MF-Pro";
    if (type[0] == 0x44 && type[1] == 0x03) return (char *)"MF Desire";
    return (char *)"Unknown";
}

char *RFID::showCardType(uchar *type) {
    Serial.print("Card type: ");
    char *label = readCardType(type);
    Serial.println(label);
    return label;
}
