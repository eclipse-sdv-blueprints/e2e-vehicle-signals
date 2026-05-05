# RFID1 Library Requirements Specification

## Conventions

The key words MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT, MAY, and OPTIONAL in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## 1. Scope

This document specifies the requirements for the `RFID` Arduino library. The library provides an interface for communicating with an MFRC522-compatible contactless RFID/NFC reader module over a software SPI transport.

The library SHALL expose the following capabilities:

- reader initialization and reset
- low-level reader register read/write access
- antenna control
- card presence detection
- anti-collision and UID retrieval
- card type identification
- CRC calculation
- MIFARE Classic block write
- card halt

## 2. Environment Requirements

### 2.1 Platform

- The library SHALL be compatible with an Arduino runtime environment.
- The library SHALL depend only on `Arduino.h` standard facilities: `pinMode`, `digitalWrite`, `digitalRead`, and `Serial`.
- The library SHALL NOT depend on Arduino hardware SPI.

### 2.2 Hardware

- The library SHALL communicate with an MFRC522-compatible RFID reader module.
- The transport between the host MCU and the reader module SHALL be software-implemented SPI (bit-banged GPIO).

### 2.3 Headers

- `rfid.h` SHALL be the primary include file for consumers.
- `rfid.h` SHALL expose the `RFID` class and all public constants required to call its methods.

## 3. Types and Constants

### 3.1 Type aliases

The library SHALL declare the following type aliases accessible from consumer code:

```cpp
typedef unsigned char uchar;
typedef unsigned int uint;
```

### 3.2 Buffer size

The library SHALL define:

```cpp
#define MAX_LEN 16
```

`MAX_LEN` defines the maximum number of bytes that any single card exchange response may occupy in a caller-supplied buffer.

### 3.3 Result codes

The library SHALL define the following result code constants:

```cpp
#define MI_OK       0
#define MI_NOTAGERR 1
#define MI_ERR      2
```

Semantics:

- `MI_OK` SHALL indicate the operation completed successfully.
- `MI_NOTAGERR` SHALL indicate no card was detected during a reader exchange.
- `MI_ERR` SHALL indicate any other failure, including framing, CRC, collision, protocol, or timeout conditions.

### 3.4 PICC request mode constants

The library SHALL define the following card request modes for use as the `reqMode` argument of `request(...)`:

```cpp
#define PICC_REQIDL  0x26   // search for cards not in HALT state
#define PICC_REQALL  0x52   // search for all cards including those in HALT state
```

### 3.5 PICC command constants

The library SHALL define the following card command constants:

```cpp
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
```

### 3.6 PCD command constants

The library SHALL define the following reader command constants for use with `toCard(...)`:

```cpp
#define PCD_IDLE        0x00
#define PCD_AUTHENT     0x0E
#define PCD_RECEIVE     0x08
#define PCD_TRANSMIT    0x04
#define PCD_TRANSCEIVE  0x0C
#define PCD_RESETPHASE  0x0F
#define PCD_CALCCRC     0x03
```

## 4. Architecture Requirements

### 4.1 `RFID` class

The library SHALL expose a class named `RFID` that provides all high-level and low-level reader API methods described in this specification.

### 4.2 `SWSPI` class

The library SHALL provide a software SPI transport class named `SWSPI` that manages GPIO-based SPI communication. `SWSPI` SHALL be available as a supporting header but is not required to be part of the consumer-facing API surface.

### 4.3 Single-instance transport constraint

The library is NOT REQUIRED to support simultaneous use of multiple independent `RFID` instances on the same host MCU. A consumer MUST NOT create more than one active `RFID` instance at a time.

## 5. Lifecycle Requirements

Consumers SHALL follow this call sequence:

1. Construct an `RFID` object.
2. Call `begin(...)` exactly once before accessing any other method.
3. Call `init()` exactly once after `begin(...)` and before any card operation.
4. Repeatedly call `request(...)` to detect card presence.
5. On detection, call `anticoll(...)` to retrieve the card UID.
6. Optionally call additional methods as needed.
7. Call `halt()` at the end of each card transaction.

Methods that access reader hardware MUST NOT be called before `begin(...)` has been called. Card detection and UID retrieval methods MUST NOT be called before `init()` has been called.

## 6. `RFID` API Requirements

## 6.1 `void begin(uchar csnPin, uchar sckPin, uchar mosiPin, uchar misoPin, uchar chipSelectPin, uchar NRSTPD)`

### Purpose

Configure the SPI GPIO pins and the reader control pins.

### Parameters

- `csnPin`: SPI chip-select pin used by the software SPI transport.
- `sckPin`: SPI clock pin.
- `mosiPin`: SPI MOSI pin.
- `misoPin`: SPI MISO pin.
- `chipSelectPin`: reader chip-select pin used by register access operations.
- `NRSTPD`: reader reset/power-down pin.

All pin numbers MUST be valid Arduino digital pin identifiers.

### Requirements

- The library SHALL configure the SPI transport with the provided pin assignments.
- The library SHALL configure `chipSelectPin` as a digital output.
- The library SHALL configure `NRSTPD` as a digital output.
- The library SHALL retain `chipSelectPin` and `NRSTPD` for use by subsequent register access and initialization calls.
- After `begin(...)` returns, all register access methods SHALL be usable.

## 6.2 `void showCardID(uchar *id)`

### Purpose

Print a card UID to `Serial` in hexadecimal.

### Parameters

- `id`: pointer to a buffer containing at least 4 UID bytes.

### Requirements

- The library SHALL read exactly 4 bytes from `id`.
- The library SHALL print each byte as exactly 2 uppercase hexadecimal digits to `Serial`.
- The output SHALL be 8 consecutive hexadecimal characters with no separators and no trailing newline.
- `Serial` MUST be initialized by the caller before invoking this method.

### Output example

For UID bytes `{0xDE, 0xAD, 0xBE, 0xEF}`, the output SHALL be:

```text
DEADBEEF
```

## 6.3 `char* showCardType(uchar* type)`

### Purpose

Print a textual card type label to `Serial`.

### Parameters

- `type`: pointer to a buffer containing at least 2 card type bytes as returned by `request(...)`.

### Requirements

- The library SHALL print `Card type: ` followed by the card type label to `Serial`.
- The label SHALL be selected according to the card type mapping table in section 8.3.
- For unrecognized type bytes, the label SHALL be `Unknown`.
- Callers MUST NOT use the declared `char*` return value of this method.

## 6.4 `char* readCardType(uchar* type)`

### Purpose

Return a string identifying the card type.

### Parameters

- `type`: pointer to a buffer containing at least 2 card type bytes as returned by `request(...)`.

### Requirements

- The library SHALL return a pointer to a null-terminated string identifying the card type.
- The returned string SHALL be selected according to the card type mapping table in section 8.3.
- For unrecognized type bytes, the library SHALL return `"Unknown"`.
- The returned pointer SHALL remain valid for the lifetime of the program (i.e., the string SHALL be a string literal).

## 6.5 `void writeTo(uchar addr, uchar val)`

### Purpose

Write one byte to a reader register.

### Parameters

- `addr`: reader register address.
- `val`: byte value to write.

### Requirements

- The library SHALL write `val` to the register at `addr` using the SPI transport and the stored chip-select pin.
- The register address encoding SHALL comply with the MFRC522 SPI protocol (write direction bit in MSB, address in bits 6:1, LSB zero).
- `begin(...)` MUST have been called before this method is used.

## 6.6 `uchar readFrom(uchar addr)`

### Purpose

Read one byte from a reader register.

### Parameters

- `addr`: reader register address.

### Requirements

- The library SHALL read and return one byte from the register at `addr` using the SPI transport and the stored chip-select pin.
- The register address encoding SHALL comply with the MFRC522 SPI protocol (read direction bit in MSB, address in bits 6:1, LSB zero).
- `begin(...)` MUST have been called before this method is used.

### Returns

- The byte value read from the addressed register.

## 6.7 `void setBitMask(uchar reg, uchar mask)`

### Purpose

Set one or more bits in a reader register without altering other bits.

### Requirements

- The library SHALL read the current register value, OR it with `mask`, and write the result back to the same register.

## 6.8 `void clearBitMask(uchar reg, uchar mask)`

### Purpose

Clear one or more bits in a reader register without altering other bits.

### Requirements

- The library SHALL read the current register value, AND it with the bitwise NOT of `mask`, and write the result back to the same register.

## 6.9 `void antennaOn(void)`

### Purpose

Enable the reader antenna driver.

### Requirements

- The library SHALL enable the reader RF antenna output.
- If the antenna driver is already enabled, the library SHALL NOT perform a redundant enable operation.
- Callers SHOULD wait at least 1 ms after calling this method before initiating a card transaction.

## 6.10 `void antennaOff(void)`

### Purpose

Disable the reader antenna driver.

### Requirements

- The library SHALL disable the reader RF antenna output.
- Callers SHOULD wait at least 1 ms after calling this method before re-enabling the antenna.

## 6.11 `void reset(void)`

### Purpose

Issue a soft reset to the reader.

### Requirements

- The library SHALL issue a soft reset command to the reader that restores the reader's register defaults.

## 6.12 `void init(void)`

### Purpose

Initialize the reader to the operational state required by this library.

### Requirements

- The library SHALL release the reader from reset or power-down state.
- The library SHALL issue a soft reset.
- The library SHALL configure the reader timer, modulation, and CRC registers to values that produce correct ISO14443A communication.
- The library SHALL enable 100% ASK modulation.
- The library SHALL enable the antenna on completion.
- After `init()` returns, the reader SHALL be ready to accept `request(...)`, `anticoll(...)`, `write(...)`, and `halt()` calls.

## 6.13 `uchar request(uchar reqMode, uchar *TagType)`

### Purpose

Probe the RF field for a card and obtain the card type (ATQA).

### Parameters

- `reqMode`: the request mode; SHALL be `PICC_REQIDL` or `PICC_REQALL`.
- `TagType`: caller-supplied writable buffer of at least 2 bytes.

### Requirements

- The library SHALL transmit a request frame to the reader for the given mode.
- A card detection SHALL be considered successful only when a valid 16-bit ATQA response is received from the field.
- On success, the library SHALL populate `TagType[0]` and `TagType[1]` with the ATQA bytes returned by the card.
- The library SHALL return `MI_OK` on success.
- The library SHALL return `MI_ERR` on any failure, including no card present.

### Returns

- `MI_OK` if a card was detected and a valid response received.
- `MI_ERR` otherwise.

## 6.14 `uchar toCard(uchar command, uchar *sendData, uchar sendLen, uchar *backData, uint *backLen)`

### Purpose

Execute a raw reader command exchange with the card.

### Parameters

- `command`: reader command to issue; SHALL be `PCD_AUTHENT` or `PCD_TRANSCEIVE`.
- `sendData`: pointer to outbound data bytes.
- `sendLen`: number of outbound bytes.
- `backData`: caller-supplied writable buffer to receive the card's response.
- `backLen`: pointer to a variable that receives the response length in bits.

### Requirements

- The library SHALL transmit `sendLen` bytes from `sendData` to the reader and execute the specified command.
- The library SHALL wait for completion or timeout before returning.
- On successful completion without reader-detected errors, the library SHALL return `MI_OK`.
- If the completion condition indicates no tag was present, the library SHALL return `MI_NOTAGERR`.
- On timeout or any reader-detected error (buffer overflow, collision, CRC error, protocol error), the library SHALL return `MI_ERR`.
- For `PCD_TRANSCEIVE`, on success the library SHALL:
  - write the received bit count to `*backLen`.
  - copy up to `MAX_LEN` received bytes into `backData`.
- The library SHALL NOT copy more than `MAX_LEN` bytes into `backData` regardless of response length.

### Returns

- `MI_OK`, `MI_NOTAGERR`, or `MI_ERR`.

## 6.15 `uchar anticoll(uchar *serNum)`

### Purpose

Execute the ISO14443A single-cascade anti-collision sequence and retrieve a 4-byte card UID.

### Parameters

- `serNum`: caller-supplied writable buffer of at least 5 bytes.

### Requirements

- The library SHALL execute the ISO14443A anti-collision sequence for a 4-byte UID.
- On success, the library SHALL populate `serNum[0]` through `serNum[3]` with the 4 UID bytes.
- The library SHALL populate `serNum[4]` with the BCC (block check character) byte returned by the card.
- The library SHALL verify the BCC by XORing `serNum[0]` through `serNum[3]` and comparing the result with `serNum[4]`.
- The library SHALL return `MI_OK` only when the exchange succeeds and the BCC verification passes.
- The library SHALL return `MI_ERR` if the exchange fails or the BCC does not match.

### Returns

- `MI_OK` on success.
- `MI_ERR` on failure or BCC mismatch.

### Constraint

- This method SHALL only support the single anti-collision pass used for 4-byte UIDs. It is NOT REQUIRED to support ISO14443A UID cascade levels 2 or 3.

## 6.16 `void calulateCRC(uchar *pIndata, uchar len, uchar *pOutData)`

### Purpose

Compute a 2-byte CRC over the supplied data using the reader's hardware CRC engine.

### Parameters

- `pIndata`: pointer to `len` input bytes.
- `len`: number of bytes to include in the CRC computation.
- `pOutData`: caller-supplied writable buffer of at least 2 bytes.

### Requirements

- The library SHALL compute the CRC over `len` bytes starting at `pIndata` using the reader's CRC calculation command.
- The library SHALL write the low CRC byte to `pOutData[0]` and the high CRC byte to `pOutData[1]`.
- The library SHALL wait for CRC completion before returning.

## 6.17 `uchar write(uchar blockAddr, uchar *writeData)`

### Purpose

Write a 16-byte block of data to the card using the MIFARE Classic write command sequence.

### Parameters

- `blockAddr`: target block address on the card.
- `writeData`: pointer to exactly 16 bytes of data to write.

### Requirements

- The library SHALL transmit the MIFARE WRITE command frame containing `blockAddr` and a CRC to the reader.
- The library SHALL verify that the card acknowledges the write command with a 4-bit ACK of value `0x0A` (low nibble).
- If the command phase is acknowledged, the library SHALL transmit the 16 data bytes from `writeData` together with a CRC.
- The library SHALL verify that the card acknowledges the data phase with a 4-bit ACK of value `0x0A` (low nibble).
- The library SHALL return `MI_OK` only if both ACK checks pass.
- The library SHALL return `MI_ERR` if either the command phase or the data phase fails to produce a valid ACK.

### Returns

- `MI_OK` on success.
- `MI_ERR` on any failure.

### Note

- The caller is responsible for ensuring the target sector has been authenticated before invoking `write(...)`. The library does not perform authentication.

## 6.18 `void halt(void)`

### Purpose

Instruct the card to enter the HALT state.

### Requirements

- The library SHALL transmit the ISO14443A HALT command frame to the reader.
- The HALT frame SHALL include a valid CRC.

## 7. `SWSPI` API Requirements

### 7.1 `void begin(uchar csnPin, uchar sckPin, uchar mosiPin, uchar misoPin)`

- The library SHALL configure `csnPin`, `sckPin`, and `mosiPin` as digital outputs.
- The library SHALL configure `misoPin` as a digital input.
- The library SHALL retain all four pin numbers for use by subsequent transfer operations.

### 7.2 `void writeByte(uchar dat)`

- The library SHALL transmit all 8 bits of `dat` MSB-first over the MOSI line, clocking each bit with one SCK toggle cycle.

### 7.3 `uchar readByte(void)`

- The library SHALL sample 8 bits from the MISO line, clocking each bit with one SCK toggle cycle, and return the assembled byte.

### 7.4 `unsigned char SPI_RW(unsigned char Byte)`

- The library SHALL simultaneously transmit the 8 bits of `Byte` on MOSI and sample 8 bits from MISO, clocking each bit with one SCK toggle cycle.
- The library SHALL return the 8 bits received from MISO as the result.

### 7.5 `unsigned char SPI_RW_Reg(unsigned char reg, unsigned char value)`

- The library SHALL perform a two-byte SPI transfer of `reg` followed by `value`, driving the CSN pin low for the duration of the transfer.
- The library SHALL return the first byte received during the transfer.

### 7.6 `unsigned char SPI_Read(unsigned char reg)`

- The library SHALL perform a two-byte SPI transfer of `reg` followed by a zero byte, driving the CSN pin low for the duration of the transfer.
- The library SHALL return the second received byte.

### 7.7 `unsigned char readToBuffer(unsigned char reg, unsigned char *pBuf, unsigned char bytes)`

- The library SHALL perform a multi-byte SPI read of `bytes` bytes from `reg`, storing received bytes into `pBuf`, driving the CSN pin low for the duration of the transfer.
- The library SHALL return the status byte received while transmitting `reg`.

### 7.8 `unsigned char writeFromBuffer(unsigned char reg, unsigned char *pBuf, unsigned char bytes)`

- The library SHALL perform a multi-byte SPI write of `bytes` bytes from `pBuf` into `reg`, driving the CSN pin low for the duration of the transfer.
- The library SHALL return the status byte received while transmitting `reg`.

## 8. Behavioral Requirements

### 8.1 Initialization

After `begin(...)` and `init()` complete:

- The reader MUST be out of reset state.
- The reader antenna MUST be active.
- The reader MUST be configured for ISO14443A communication with 100% ASK modulation.

### 8.2 Card detection

- `request(...)` SHALL succeed only if a card is present in the RF field and produces a valid 16-bit ATQA response.
- `request(...)` SHALL fail for any other condition, including no card present, framing errors, and collision.

### 8.3 Card type mapping

`showCardType(...)` and `readCardType(...)` SHALL map card type bytes as follows:

| `type[0]` | `type[1]` | Label |
| --- | --- | --- |
| `0x04` | `0x00` | `MFOne-S50` |
| `0x02` | `0x00` | `MFOne-S70` |
| `0x44` | `0x00` | `MF-UltraLight` |
| `0x08` | `0x00` | `MF-Pro` |
| `0x44` | `0x03` | `MF Desire` |
| any other | any other | `Unknown` |

### 8.4 UID validity

- `anticoll(...)` SHALL validate the received UID by checking that the XOR of bytes 0 through 3 equals byte 4 (BCC).
- A UID that fails BCC validation SHALL cause `anticoll(...)` to return `MI_ERR`.

### 8.5 Write acknowledgement

- `write(...)` SHALL consider a write phase successful only when the card returns a 4-bit ACK with value `0x0A` in the low nibble.

### 8.6 Receive buffer limit

- No API method SHALL write more than `MAX_LEN` (16) bytes into any caller-supplied receive buffer.

## 9. Output Format Requirements

### 9.1 UID serial output

- `showCardID(...)` SHALL produce exactly 8 hexadecimal characters for a 4-byte UID.
- All alphabetic hexadecimal characters SHALL be uppercase.
- No separators, spaces, or newlines SHALL be produced.

### 9.2 Card type serial output

- `showCardType(...)` SHALL produce output of the form `Card type: <label>` followed by a newline.

## 10. Error Handling Requirements

### 10.1 Result codes

- All methods that return a result code SHALL use only `MI_OK`, `MI_NOTAGERR`, and `MI_ERR` as defined in section 3.3.

### 10.2 Error propagation

- `request(...)` SHALL return `MI_ERR` on all failure conditions; it is NOT REQUIRED to preserve or propagate `MI_NOTAGERR` to the caller.
- `anticoll(...)` SHALL return `MI_ERR` when BCC verification fails.
- `halt()` is NOT REQUIRED to report or return any success or failure indicator.

### 10.3 No exceptions

- The library SHALL NOT use C++ exception handling.
- The library SHALL NOT perform dynamic allocation.

## 11. Timing Requirements

- A caller SHOULD insert a delay of at least 100 ms between calling `begin(...)` and calling `init()` to allow the reader hardware to stabilize.
- A caller SHOULD insert a delay of at least 1 ms after calling `antennaOn()` or `antennaOff()` before initiating a card exchange.
- The library itself is NOT REQUIRED to enforce these delays internally.
- `toCard(...)` MUST provide a finite timeout for all reader exchanges. The exchange SHALL NOT block indefinitely.
- `calulateCRC(...)` MUST provide a finite timeout for CRC completion.

## 12. Concurrency Requirements

- The library is intended for use in single-threaded Arduino sketches.
- The library is NOT REQUIRED to be thread-safe or interrupt-safe.
- A consumer MUST NOT call library methods concurrently from multiple threads or from within interrupt handlers.

## 13. Memory Requirements

- The library SHALL NOT perform dynamic memory allocation (no `new`, `malloc`, or equivalent).
- Caller-supplied buffers MUST remain valid for the duration of any method call that accepts or returns data through pointers.
- The library is NOT responsible for freeing, validating, or size-checking caller-supplied buffers beyond the requirements stated per method.

## 14. Example Usage

The following pattern illustrates the required call sequence for UID detection:

```cpp
#include "rfid.h"

RFID rfid;
uchar buffer[MAX_LEN];

void setup() {
  Serial.begin(115200);
  rfid.begin(7, 5, 4, 3, 6, 2);
  delay(100);
  rfid.init();
}

void loop() {
  if (rfid.request(PICC_REQIDL, buffer) != MI_OK) {
    return;
  }

  if (rfid.anticoll(buffer) != MI_OK) {
    return;
  }

  rfid.showCardID(buffer);
  Serial.println();
  rfid.halt();
}
```

## 15. API Summary

| Method | Returns | Required precondition |
| --- | --- | --- |
| `begin(...)` | `void` | none |
| `init()` | `void` | `begin(...)` called |
| `reset()` | `void` | `begin(...)` called |
| `antennaOn()` | `void` | `begin(...)` called |
| `antennaOff()` | `void` | `begin(...)` called |
| `writeTo(...)` | `void` | `begin(...)` called |
| `readFrom(...)` | `uchar` | `begin(...)` called |
| `setBitMask(...)` | `void` | `begin(...)` called |
| `clearBitMask(...)` | `void` | `begin(...)` called |
| `request(...)` | `MI_OK` / `MI_ERR` | `init()` called |
| `anticoll(...)` | `MI_OK` / `MI_ERR` | card detected via `request(...)` |
| `showCardID(...)` | `void` | `Serial` initialized |
| `showCardType(...)` | `void` (return unused) | `Serial` initialized |
| `readCardType(...)` | `char*` string literal | — |
| `calulateCRC(...)` | `void` | `init()` called |
| `write(...)` | `MI_OK` / `MI_ERR` | card authenticated externally |
| `halt()` | `void` | card present |

## 16. Conformance

An implementation conforms to this specification if and only if it satisfies all SHALL and MUST requirements defined above, including:

- the API signatures defined for `RFID` and `SWSPI`
- the result code semantics in section 3.3
- the card type mapping table in section 8.3
- the UID output format in section 9.1
- the card type output format in section 9.2
- the receive buffer limit of `MAX_LEN` bytes
- the BCC validation requirement in section 8.4
- the write ACK validation requirement in section 8.5
- the finite-timeout requirement for `toCard(...)` and `calulateCRC(...)`
- the no-dynamic-allocation requirement in section 13