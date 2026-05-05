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

#ifndef SWSPI_H
#define SWSPI_H

#include <Arduino.h>

typedef unsigned char uchar;

/**
 * Software (bit-banged) SPI transport for the MFRC522 RFID reader.
 *
 * All transfers use SPI Mode 0 (CPOL=0, CPHA=0): clock idle LOW,
 * data sampled on the rising edge, MSB first.
 */
class SWSPI {
public:
    /**
     * Configure GPIO pins and set their initial direction/state.
     *
     * @param csnPin   SPI chip-select output pin (driven LOW during transfers).
     * @param sckPin   SPI clock output pin.
     * @param mosiPin  SPI MOSI output pin.
     * @param misoPin  SPI MISO input pin.
     */
    void begin(uchar csnPin, uchar sckPin, uchar mosiPin, uchar misoPin);

    /**
     * Transmit one byte MSB-first over MOSI (no chip-select, no return value).
     */
    void writeByte(uchar dat);

    /**
     * Receive one byte MSB-first from MISO (no chip-select).
     */
    uchar readByte(void);

    /**
     * Full-duplex byte exchange: simultaneously transmit Byte on MOSI and
     * sample one byte from MISO. Returns the received byte.
     */
    unsigned char SPI_RW(unsigned char Byte);

    /**
     * Two-byte transfer of reg then value, with CSN framing.
     * Returns the first byte received (status byte).
     */
    unsigned char SPI_RW_Reg(unsigned char reg, unsigned char value);

    /**
     * Two-byte transfer of reg then 0x00, with CSN framing.
     * Returns the second received byte (register value).
     */
    unsigned char SPI_Read(unsigned char reg);

    /**
     * Multi-byte read of bytes bytes from reg into pBuf, with CSN framing.
     * Returns the status byte received while transmitting reg.
     */
    unsigned char readToBuffer(unsigned char reg, unsigned char *pBuf, unsigned char bytes);

    /**
     * Multi-byte write of bytes bytes from pBuf into reg, with CSN framing.
     * Returns the status byte received while transmitting reg.
     */
    unsigned char writeFromBuffer(unsigned char reg, unsigned char *pBuf, unsigned char bytes);

private:
    uchar _csnPin;
    uchar _sckPin;
    uchar _mosiPin;
    uchar _misoPin;
};

#endif /* SWSPI_H */
