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

#include "swspi.h"

void SWSPI::begin(uchar csnPin, uchar sckPin, uchar mosiPin, uchar misoPin) {
    _csnPin  = csnPin;
    _sckPin  = sckPin;
    _mosiPin = mosiPin;
    _misoPin = misoPin;

    pinMode(_csnPin,  OUTPUT);
    pinMode(_sckPin,  OUTPUT);
    pinMode(_mosiPin, OUTPUT);
    pinMode(_misoPin, INPUT);

    digitalWrite(_csnPin, HIGH);
    digitalWrite(_sckPin, LOW);
}

void SWSPI::writeByte(uchar dat) {
    for (int i = 7; i >= 0; i--) {
        digitalWrite(_mosiPin, (dat >> i) & 0x01);
        digitalWrite(_sckPin, HIGH);
        digitalWrite(_sckPin, LOW);
    }
}

uchar SWSPI::readByte(void) {
    uchar result = 0;
    for (int i = 7; i >= 0; i--) {
        digitalWrite(_sckPin, HIGH);
        if (digitalRead(_misoPin)) {
            result |= (1u << i);
        }
        digitalWrite(_sckPin, LOW);
    }
    return result;
}

unsigned char SWSPI::SPI_RW(unsigned char Byte) {
    unsigned char received = 0;
    for (int i = 7; i >= 0; i--) {
        digitalWrite(_mosiPin, (Byte >> i) & 0x01);
        digitalWrite(_sckPin, HIGH);
        if (digitalRead(_misoPin)) {
            received |= (1u << i);
        }
        digitalWrite(_sckPin, LOW);
    }
    return received;
}

unsigned char SWSPI::SPI_RW_Reg(unsigned char reg, unsigned char value) {
    unsigned char status;
    digitalWrite(_csnPin, LOW);
    status = SPI_RW(reg);
    SPI_RW(value);
    digitalWrite(_csnPin, HIGH);
    return status;
}

unsigned char SWSPI::SPI_Read(unsigned char reg) {
    unsigned char value;
    digitalWrite(_csnPin, LOW);
    SPI_RW(reg);
    value = SPI_RW(0x00);
    digitalWrite(_csnPin, HIGH);
    return value;
}

unsigned char SWSPI::readToBuffer(unsigned char reg, unsigned char *pBuf, unsigned char bytes) {
    unsigned char status;
    digitalWrite(_csnPin, LOW);
    status = SPI_RW(reg);
    for (unsigned char i = 0; i < bytes; i++) {
        pBuf[i] = SPI_RW(0x00);
    }
    digitalWrite(_csnPin, HIGH);
    return status;
}

unsigned char SWSPI::writeFromBuffer(unsigned char reg, unsigned char *pBuf, unsigned char bytes) {
    unsigned char status;
    digitalWrite(_csnPin, LOW);
    status = SPI_RW(reg);
    for (unsigned char i = 0; i < bytes; i++) {
        SPI_RW(pBuf[i]);
    }
    digitalWrite(_csnPin, HIGH);
    return status;
}
