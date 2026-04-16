# BekantX Inter-Controller Protocol Specification

## 1. Purpose

This document defines the message-level protocol between the BekantX secondary controller and the BekantX primary controller.

The protocol is designed for the following goals:

- preserve the authority of the primary controller over all desk motion and safety decisions
- support an optional secondary controller without making the desk dependent on it
- provide deterministic request, response, retry, and timeout behavior
- detect corrupted messages and suppress unsafe duplicate command execution
- provide a clean transport boundary for Wi-Fi and Home Assistant integration

## 2. Transport Definition

### 2.1 Physical Interface

The inter-controller interface shall use SPI.

Transport roles:

- secondary controller: SPI master
- primary controller: SPI slave

Rationale:

- the secondary controller is optional and naturally acts as the requester of remote and integration-side operations
- the primary controller remains autonomous and does not depend on the secondary controller clock to run the desk
- the master-driven SPI model fits a poll-based request and status architecture

### 2.2 Electrical and Link Defaults

Unless implementation constraints require otherwise, the protocol assumes:

- 4-wire SPI: SCLK, MOSI, MISO, CS_N
- active-low chip select
- 8-bit word size
- MSB first
- SPI mode 0
- initial clock target: 1 MHz
- higher clock rates may be enabled after signal integrity validation

This specification does not require an interrupt line. Event delivery is poll-based.

## 3. Link Model

### 3.1 Direction and Ownership

The secondary controller initiates all SPI transactions.

The primary controller:

- receives command requests
- validates requests
- executes or rejects requests according to local state and safety rules
- stores the authoritative response
- returns responses and events when the secondary controller polls for them

### 3.2 Message Delivery Model

The protocol uses a mailbox-style request and poll model.

The expected transaction sequence is:

1. The secondary controller sends one request frame.
2. The primary controller validates and queues the corresponding response.
3. The secondary controller polls until it receives a response frame with the matching sequence number.
4. If the primary controller has an event pending, it may return the event before or after the requested response, depending on queue order.

This model avoids requiring the primary controller to compute a complete response during the same SPI transaction in which the request is being received.

## 4. Frame Format

Each SPI application message is encoded as one protocol frame.

### 4.1 Byte Layout

| Offset | Size | Name | Description |
| --- | --- | --- | --- |
| 0 | 1 | SOF | Start-of-frame marker, fixed value `0xA5` |
| 1 | 1 | VERSION | Protocol version, initial value `0x01` |
| 2 | 1 | TYPE | Frame type |
| 3 | 1 | FLAGS | Type-specific flags |
| 4 | 1 | SEQ | Sequence number |
| 5 | 1 | CODE | Command code, status code, or event code |
| 6 | 1 | ARG | Command subtype or echoed command code |
| 7 | 1 | LEN | Payload length in bytes |
| 8..(8+LEN-1) | LEN | PAYLOAD | Type-specific payload |
| 8+LEN | 1 | CRC_LO | CRC-16 low byte |
| 9+LEN | 1 | CRC_HI | CRC-16 high byte |

### 4.2 Maximum Size

- maximum frame size: 64 bytes
- maximum payload size: 54 bytes

Frames larger than 64 bytes are invalid and shall be rejected.

### 4.3 Endianness

All multi-byte integers in payloads shall use little-endian encoding.

### 4.4 Position Units

Position values exposed by the protocol shall use signed 32-bit integers in units of `0.1 mm` relative to the calibrated lower limit.

If calibration is not valid, commands or responses that require absolute position semantics shall return `STATUS_CALIBRATION_REQUIRED`.

## 5. Frame Types

### 5.1 Request Frame

- TYPE: `0x10`
- CODE: command opcode
- ARG: command-specific argument or `0x00`
- SEQ: assigned by the secondary controller

Every request except `POLL` shall use a non-zero sequence number.

### 5.2 Poll Frame

- TYPE: `0x11`
- CODE: `CMD_POLL`
- ARG: `0x00`
- LEN: `0`

The secondary controller uses `POLL` to retrieve the next queued response or event from the primary controller.

### 5.3 Response Frame

- TYPE: `0x20`
- CODE: status code
- ARG: echoed command opcode for which this response was generated
- SEQ: copied from the originating request

### 5.4 Event Frame

- TYPE: `0x30`
- CODE: event code
- ARG: event class or subtype
- SEQ: `0x00`

Events are unsolicited from a logical point of view, but are delivered only when the secondary controller polls.

### 5.5 Idle Frame

- TYPE: `0x40`
- CODE: `STATUS_IDLE`
- ARG: `0x00`
- SEQ: `0x00`
- LEN: `0`

The primary controller returns an idle frame when no queued response or event is available.

## 6. CRC and Integrity Protection

### 6.1 CRC Definition

The checksum shall be `CRC-16/CCITT-FALSE` with the following parameters:

- polynomial: `0x1021`
- initial value: `0xFFFF`
- refin: `false`
- refout: `false`
- xorout: `0x0000`

The CRC shall be calculated over all bytes from `SOF` through the final payload byte. The CRC bytes themselves are excluded from the calculation.

### 6.2 CRC Error Handling

If the primary controller detects an invalid CRC on a received request frame:

- it shall discard the frame
- it shall not execute the request
- it shall increment a transport error counter
- it may enqueue a transport error event

If the secondary controller detects an invalid CRC on a received frame:

- it shall discard the frame
- it shall continue polling until timeout
- it may retry the last request according to the retry rules

## 7. Sequence Numbers and Duplicate Suppression

### 7.1 Sequence Number Rules

- the secondary controller owns the sequence number space
- sequence numbers are 8-bit values
- `0x00` is reserved for events and idle frames
- requests shall use sequence numbers `0x01` through `0xFF`

### 7.2 Duplicate Handling

The primary controller shall cache the last successfully processed request and response for each active remote lease.

If it receives the same sequence number again for the same lease and the request payload matches the previously accepted request, it shall:

- not execute the command a second time
- replay the cached response instead

This rule prevents duplicate motion commands after timeout-driven retransmission.

## 8. Remote Control Lease Model

Motion-capable remote commands shall require an active remote-control lease.

Commands requiring a valid lease:

- `MOVE_UP`
- `MOVE_DOWN`
- `STOP`
- `MOVE_TO_POSITION`
- `MEMORY_RECALL`
- `CALIBRATE_START`

### 8.1 Lease Principles

- only one secondary-side lease may be active at a time
- lease ownership is enforced by the primary controller
- lease expiration shall stop any remote-initiated motion safely
- local user commands may preempt remote motion at any time

### 8.2 Lease Timing

- default lease timeout: `500 ms`
- minimum allowed lease timeout request: `100 ms`
- maximum allowed lease timeout request: `1000 ms`
- recommended keepalive period: `100 ms`
- hard lease-expiry stop threshold: `500 ms` after the last accepted keepalive unless a different granted timeout is returned by the primary controller

## 9. Status Codes

### 9.1 Normal Status Codes

| Code | Name | Meaning |
| --- | --- | --- |
| `0x00` | `STATUS_OK` | Request completed successfully |
| `0x01` | `STATUS_ACCEPTED` | Request accepted and execution started |
| `0x02` | `STATUS_PENDING` | Request accepted but result not yet final |
| `0x03` | `STATUS_IDLE` | No response or event pending |
| `0x04` | `STATUS_REPLAYED` | Cached response replayed for duplicate request |

### 9.2 Error Status Codes

| Code | Name | Meaning |
| --- | --- | --- |
| `0x10` | `STATUS_INVALID_OPCODE` | Unknown command |
| `0x11` | `STATUS_INVALID_LENGTH` | Payload length invalid |
| `0x12` | `STATUS_INVALID_STATE` | Command not allowed in current state |
| `0x13` | `STATUS_ACCESS_DENIED` | Command denied by policy or ownership rules |
| `0x14` | `STATUS_BUSY` | Controller temporarily busy |
| `0x15` | `STATUS_RANGE_ERROR` | Numeric value out of range |
| `0x16` | `STATUS_UNSUPPORTED` | Command recognized but not implemented |
| `0x17` | `STATUS_SAFETY_REJECTED` | Command blocked for safety reasons |
| `0x18` | `STATUS_FAULT_ACTIVE` | Active fault prevents execution |
| `0x19` | `STATUS_LEASE_REQUIRED` | Command requires valid lease |
| `0x1A` | `STATUS_LEASE_EXPIRED` | Lease expired |
| `0x1B` | `STATUS_CALIBRATION_REQUIRED` | Calibration required |
| `0x1C` | `STATUS_NOT_FOUND` | Requested resource does not exist |
| `0x1D` | `STATUS_PROTOCOL_ERROR` | Framing or protocol rule violation |

## 10. Event Codes

| Code | Name | Meaning |
| --- | --- | --- |
| `0x20` | `EVT_FAULT_RAISED` | New fault became active |
| `0x21` | `EVT_FAULT_CLEARED` | Fault state cleared |
| `0x22` | `EVT_COLLISION_DETECTED` | Collision or obstruction event detected |
| `0x23` | `EVT_MOTION_COMPLETE` | Automatic motion completed |
| `0x24` | `EVT_MOTION_ABORTED` | Automatic motion aborted |
| `0x25` | `EVT_LEASE_EXPIRED` | Remote-control lease expired |
| `0x26` | `EVT_TRANSPORT_ERROR` | CRC or frame-level transport error observed |
| `0x27` | `EVT_STATE_CHANGED` | Relevant desk state changed |

## 11. Command Set

### 11.1 Management Commands

#### `CMD_PING` (`0x01`)

Request payload:

- `u32 nonce`

Response payload:

- `u32 nonce`

Purpose:

- link test
- startup synchronization

#### `CMD_GET_PROTOCOL_INFO` (`0x02`)

Request payload: none

Response payload:

- `u8 protocol_version_major`
- `u8 protocol_version_minor`
- `u8 max_frame_size`
- `u8 capabilities_bitmap_0`
- `u8 capabilities_bitmap_1`
- `u8 reserved[2]`

#### `CMD_GET_STATUS_SUMMARY` (`0x03`)

Request payload: none

Response payload:

- `u8 system_state`
- `u8 motion_state`
- `u8 calibration_state`
- `u8 limit_flags`
- `u16 fault_flags`
- `u16 event_counter`
- `s32 current_position_0_1mm`
- `s32 target_position_0_1mm`

#### `CMD_GET_EXTENDED_STATUS` (`0x04`)

Request payload: none

Response payload:

- `s32 lower_limit_0_1mm`
- `s32 upper_limit_0_1mm`
- `u16 supply_mv`
- `u16 transport_error_count`
- `u16 last_fault_code`
- `u16 status_flags`

#### `CMD_GET_FAULTS` (`0x05`)

Request payload: none

Response payload:

- `u16 active_fault_flags`
- `u16 latched_fault_flags`
- `u16 last_fault_code`
- `u16 last_event_code`

#### `CMD_CLEAR_FAULTS` (`0x06`)

Request payload:

- `u16 clear_mask`

Response payload:

- `u16 remaining_latched_fault_flags`

### 11.2 Lease Commands

#### `CMD_ACQUIRE_LEASE` (`0x10`)

Request payload:

- `u16 requested_timeout_ms`
- `u32 client_nonce`

Response payload:

- `u16 lease_id`
- `u16 granted_timeout_ms`
- `u32 client_nonce`

#### `CMD_KEEPALIVE` (`0x11`)

Request payload:

- `u16 lease_id`

Response payload:

- `u16 lease_id`
- `u16 remaining_timeout_ms`

#### `CMD_RELEASE_LEASE` (`0x12`)

Request payload:

- `u16 lease_id`

Response payload:

- `u16 lease_id`

### 11.3 Control Commands

#### `CMD_MOVE_UP` (`0x20`)

Request payload:

- `u16 lease_id`

Response payload:

- `u8 accepted_motion_source`

Notes:

- command remains active until stop, release, safety condition, local override, or lease expiry

#### `CMD_MOVE_DOWN` (`0x21`)

Request payload:

- `u16 lease_id`

Response payload:

- `u8 accepted_motion_source`

#### `CMD_STOP` (`0x22`)

Request payload:

- `u16 lease_id`
- `u8 reason_code`

Response payload:

- `u8 stop_state`

Notes:

- `STOP` has highest remote priority
- the primary controller shall acknowledge `STOP` even if motion is already stopped

#### `CMD_MOVE_TO_POSITION` (`0x23`)

Request payload:

- `u16 lease_id`
- `s32 target_position_0_1mm`

Response payload:

- `s32 accepted_target_position_0_1mm`

Notes:

- returns `STATUS_ACCEPTED` when movement starts
- final completion is observed through status polling or `EVT_MOTION_COMPLETE`

#### `CMD_GET_POSITION` (`0x24`)

Request payload: none

Response payload:

- `s32 current_position_0_1mm`
- `s32 target_position_0_1mm`
- `u8 position_valid`
- `u8 moving`

#### `CMD_CALIBRATE_START` (`0x25`)

Request payload:

- `u16 lease_id`
- `u8 mode`

Response payload:

- `u8 calibration_state`

### 11.4 Memory Commands

#### `CMD_MEMORY_LIST` (`0x30`)

Request payload: none

Response payload:

- `u8 slot_count`
- `u8 valid_bitmap`
- `u8 reserved[2]`

#### `CMD_MEMORY_READ` (`0x31`)

Request payload:

- `u8 slot_index`

Response payload:

- `u8 slot_index`
- `u8 valid`
- `u16 reserved`
- `s32 stored_position_0_1mm`

#### `CMD_MEMORY_WRITE` (`0x32`)

Request payload:

- `u8 slot_index`
- `u8 mode`
- `u16 reserved`
- `s32 stored_position_0_1mm`

Response payload:

- `u8 slot_index`
- `u8 valid`

#### `CMD_MEMORY_DELETE` (`0x33`)

Request payload:

- `u8 slot_index`

Response payload:

- `u8 slot_index`
- `u8 valid`

#### `CMD_MEMORY_RECALL` (`0x34`)

Request payload:

- `u16 lease_id`
- `u8 slot_index`

Response payload:

- `u8 slot_index`
- `s32 accepted_target_position_0_1mm`

## 12. Timeouts and Retry Rules

### 12.1 Polling Intervals

- recommended poll interval after sending a request: `5 ms`
- recommended idle background poll interval when connected: `50 ms`

### 12.2 Response Deadlines

- `PING`, `GET_PROTOCOL_INFO`, `GET_STATUS_SUMMARY`, `GET_POSITION`, `GET_FAULTS`: response shall be available within `10 ms`
- `ACQUIRE_LEASE`, `KEEPALIVE`, `RELEASE_LEASE`, `STOP`: response shall be available within `20 ms`
- `MOVE_UP`, `MOVE_DOWN`, `MOVE_TO_POSITION`, `MEMORY_RECALL`, `CALIBRATE_START`: accept or reject response shall be available within `20 ms`
- if a command launches a longer operation, the primary controller shall return `STATUS_ACCEPTED` rather than blocking until completion

### 12.3 Request Timeout

The secondary controller shall consider a request timed out if no matching response frame is received within `50 ms` of the initial request transmission.

### 12.4 Retries

On timeout, the secondary controller may retransmit the same request once using the same sequence number.

If the retry also times out:

- the secondary controller shall mark the link degraded
- any active remote-control lease shall be considered at risk
- no further motion commands shall be issued until the link is revalidated

### 12.5 Stop Behavior on Link Loss

If a remote-initiated move is active and the lease expires because keepalives are no longer received, the primary controller shall stop motion safely.

## 13. Fault and State Flags

The exact bit assignments may be finalized later, but the protocol shall reserve bitfields for:

- motion state
- calibration validity
- upper-limit reached
- lower-limit reached
- remote control active
- local override active
- collision or obstruction active
- transport error observed
- active desk fault

## 14. Expected Secondary Controller Behavior

The secondary controller shall:

- acquire a lease before sending motion-capable commands
- continue sending keepalives while remote motion authority is required
- treat `STATUS_ACCEPTED` as acknowledgment of command start, not completion
- poll for final state after any automatic motion command
- never assume cached state is authoritative over primary-controller state
- stop issuing motion requests if the link is degraded or lease state is uncertain

## 15. Expected Primary Controller Behavior

The primary controller shall:

- validate every received command against state, safety rules, and lease ownership
- reject malformed or unauthorized commands without side effects
- cache enough response data to support duplicate suppression and replay
- maintain authoritative motion and safety state independent of the secondary controller
- prioritize safe stop behavior over protocol convenience

## 16. Example Request Flow

### 16.1 Move to Stored Memory Position

1. Secondary sends `CMD_ACQUIRE_LEASE`.
2. Primary returns lease grant with `lease_id`.
3. Secondary sends `CMD_MEMORY_RECALL` with `lease_id` and slot index.
4. Primary returns `STATUS_ACCEPTED` if movement can begin.
5. Secondary polls `CMD_GET_STATUS_SUMMARY` or receives `EVT_MOTION_COMPLETE` through polling.
6. Secondary sends `CMD_RELEASE_LEASE` when remote control session ends.

### 16.2 Recovering from Timeout

1. Secondary sends `CMD_MOVE_TO_POSITION` with sequence `0x44`.
2. No response is received within `50 ms`.
3. Secondary retransmits the same frame with sequence `0x44`.
4. Primary detects it as a duplicate and replays the cached response without reissuing motion.

## 17. Versioning Rules

- breaking frame-layout changes require a protocol major-version change
- new commands may be added without changing the frame layout
- unsupported but well-formed commands shall return `STATUS_UNSUPPORTED`
- both controllers shall validate the reported protocol version during startup

## 18. Open Protocol Details

The following details may still be refined during implementation without changing the overall protocol model:

- exact capability bitmap assignments
- exact bit definitions for fault and status flags
- final numeric values for system-state enumerations
- validated maximum SPI clock rate on production hardware
- whether event queue depth should exceed one frame