# IKEA BEKANT LIN Protocol

## 1. Purpose

This document describes the reverse-engineered LIN protocol behavior used by the IKEA BEKANT desk, based on public reverse-engineering work and observed controller implementations.

It is not an official IKEA specification. It is a working engineering document intended to capture the current understanding of:

- the LIN bus structure used by the desk
- the known runtime node map
- the startup and diagnostic sequence
- the payload formats used during normal operation
- the command and state values observed on the bus

## 2. Status and Confidence

This document is derived primarily from the public reverse-engineered implementations in `mgkoenig/lyft` and `mgkoenig/lyft_mk2`.

Confidence levels:

- high confidence: node IDs, frame direction model, checksum handling, startup payload patterns, runtime payload size, command values, and state values explicitly present in code
- medium confidence: semantic meaning of several startup diagnostic messages and the role of some non-motor runtime nodes
- lower confidence: exact meaning of every startup byte and compatibility across all desk revisions

Where the meaning of a frame is inferred rather than explicitly proven, that is stated clearly.

## 3. LIN Bus Characteristics

The BEKANT desk uses a standard LIN-style master-slave serial bus.

Observed characteristics from the public implementations:

- sync field: `0x55`
- diagnostic request node ID: `0x3C` (60)
- diagnostic response node ID: `0x3D` (61)
- diagnostic response PID after parity: `0x7D`
- classic checksum is used for diagnostic frames
- enhanced checksum is used for normal runtime frames

The earlier LYFT implementation explicitly documents the bus as `19200 baud`, with a LIN break length greater than 13 bit times. BekantX should treat `19200 baud` as the current working assumption unless desk-specific measurements indicate otherwise.

## 4. LIN Frame Model

### 4.1 Generic LIN Layout

A normal LIN transaction follows the standard pattern:

1. break field
2. sync field `0x55`
3. protected identifier `PID`
4. zero or more data bytes
5. checksum byte

For a read transaction, the master sends only the break, sync, and protected identifier, and the selected slave returns the payload and checksum.

### 4.2 Protected Identifier

The public implementations calculate the protected identifier with the standard LIN parity bits:

$$
p_0 = ID_0 \oplus ID_1 \oplus ID_2 \oplus ID_4
$$

$$
p_1 = \neg(ID_1 \oplus ID_3 \oplus ID_4 \oplus ID_5)
$$

$$
PID = ID \;|\; ((p_0 \;|\; (p_1 \ll 1)) \ll 6)
$$

This yields the expected diagnostic response PID `0x7D` for node ID `0x3D`.

### 4.3 Checksum Rules

Two checksum variants are used:

- classic checksum: sum over data bytes only, inverted at the end
- enhanced checksum: sum over PID and data bytes, inverted at the end

Observed rule in the reverse-engineered implementations:

- diagnostic traffic on `0x3C/0x3D` uses classic checksum
- runtime traffic uses enhanced checksum

## 5. Known Node Map

The following runtime node IDs are explicitly present in the reverse-engineered controller code.

| Node ID | Role | Confidence | Notes |
| --- | --- | --- | --- |
| `1` | auxiliary runtime node | medium | polled during the runtime burst; response is not currently interpreted in the public code |
| `8` | left motor | high | returns current position and motor state |
| `9` | right motor | high | returns current position and motor state |
| `16` | auxiliary runtime node | medium | polled several times during the runtime burst; payload currently ignored |
| `17` | heartbeat or synchronization node | medium | receives `00 00 00` once per cycle |
| `18` | master command node | high | receives the active movement command payload |
| `0x3C` | diagnostic transmit | high | startup and discovery requests |
| `0x3D` | diagnostic receive | high | startup and discovery responses |

The exact desk-internal role of nodes `1`, `16`, and `17` is not fully decoded, but their presence and polling order are consistent across the public implementations.

## 6. Runtime Payload Format

### 6.1 Runtime Payload Length

The newer reverse-engineered implementation treats the BEKANT runtime payload length as `3` data bytes per normal operation packet, excluding the checksum.

### 6.2 Motor Status Response

When node `8` or `9` is read, the returned data is interpreted as:

| Byte | Meaning |
| --- | --- |
| `0` | position low byte |
| `1` | position high byte |
| `2` | motor state |

The position is reconstructed as:

$$
position = (byte_1 \ll 8) | byte_0
$$

### 6.3 Master Command Payload

The command sent to node `18` is interpreted as:

| Byte | Meaning |
| --- | --- |
| `0` | target or reference position low byte |
| `1` | target or reference position high byte |
| `2` | motor instruction |

This payload format is the core runtime control mechanism.

### 6.4 Heartbeat Payload

At the beginning of the runtime burst, node `17` receives:

```text
00 00 00
```

Its exact semantic meaning is not fully decoded, but it behaves like a heartbeat, keepalive, or cycle synchronization write.

## 7. Observed Runtime Schedule

The `lyft_mk2` desk controller uses a repeating burst schedule that looks like this at the application level:

| Step | Action |
| --- | --- |
| `0` | write heartbeat `00 00 00` to node `17` |
| `1` | read node `8` |
| `2` | consume node `8` response, then read node `9` |
| `3` | consume node `9` response, then read node `16` |
| `4` | discard node `16` response, update current desk position, then read node `16` again |
| `5` | discard response, evaluate motor error conditions, then read node `16` again |
| `6..8` | continue dummy reads from node `16` |
| `9` | build next motor command, then read node `1` |
| `10` | discard node `1` response, then write command payload to node `18` |
| `11` | end of active transaction window |

The public code continues counting beyond step `11`, but no further active bus traffic is defined there. This suggests an intentional idle gap before the burst restarts.

## 8. Startup and Discovery Protocol

The startup phase uses diagnostic traffic over nodes `0x3C` and `0x3D` with `8` data bytes per diagnostic payload.

### 8.1 Startup Phases

The observed high-level startup state machine is:

1. announcement phase
2. preprocessing phase
3. node scan phase
4. node parameter read phase
5. node identifier write phase
6. postprocessing phase
7. switch to runtime operation

### 8.2 Startup Announcement

Observed diagnostic announcement payload:

```text
FF 07 FF FF FF FF FF FF
```

This frame is sent twice at startup before preprocessing begins.

### 8.3 Startup Preprocessing

Observed preprocessing payloads:

```text
FF 01 07 FF FF FF FF FF
D0 02 07 FF FF FF FF FF
```

The exact semantics are not fully known, but they appear to prime the desk for the scan sequence.

### 8.4 Node Scan

Observed scan request format:

```text
[node] 02 [identifier] [nodeFound] FF FF FF FF
```

Where:

- `node` iterates through the startup scan range
- `identifier` is the temporary logical identifier being assigned or probed
- `nodeFound` is initialized as `0xFF` and later cleared when a node responds

The public startup code scans node counters `0..7` and uses a rotating logical identifier that begins at `0x07`, then wraps to `0x00` and increments.

This behavior strongly suggests that the startup sequence uses temporary or discovery-oriented node numbering that is distinct from the fixed runtime node IDs `8` and `9`.

### 8.5 Register Reads

Observed register-read request format:

```text
[node] 06 [register] 00 FF FF FF FF
```

Known registers:

| Register | Meaning | Confidence |
| --- | --- | --- |
| `0x09` | motor property or status byte | medium-high |
| `0x0A` | lower limit high byte | high |
| `0x0B` | lower limit low byte | high |
| `0x0C` | upper limit high byte | high |
| `0x0D` | upper limit low byte | high |

During startup, the controller reads these registers in order and reconstructs the usable range for each discovered motor.

### 8.6 Identifier Write

Observed identifier-write request format:

```text
[node] 04 [identifier] 00 FF FF FF FF
```

The exact semantics appear to be: write a logical identifier back to the discovered node and wait for an acknowledgment whose first data byte is `0xFF`.

### 8.7 Startup Postprocessing

Observed postprocessing payloads:

```text
D0 01 07 [nodeFound] FF FF FF FF
D0 02 07 [nodeFound] FF FF FF FF
```

If no node was found, the public code restarts the scan. If valid nodes were discovered, their properties and limits are copied into the runtime motor structures and the desk enters runtime operation.

## 9. Known Motor Commands

The following command byte values are explicitly present in the public reverse-engineered code.

| Value | Name | Meaning |
| --- | --- | --- |
| `0xFC` | `MOTOR_CMD_IDLE` | no movement |
| `0xC4` | `MOTOR_CMD_ANNOUNCEMENT` | announce upcoming movement or calibration phase |
| `0xBD` | `MOTOR_CMD_CALIBRATION` | calibration movement |
| `0xBC` | `MOTOR_CMD_CALIBRATION_STOP` | finish calibration |
| `0x86` | `MOTOR_CMD_MOVE_UP` | move desk upward |
| `0x85` | `MOTOR_CMD_MOVE_DOWN` | move desk downward |
| `0x87` | `MOTOR_CMD_MOVE_SLOW` | final slow approach to target |
| `0x84` | `MOTOR_CMD_MOVE_STOP` | controlled stop |
| `0x80` | `MOTOR_CMD_LIMIT_START` | attempt to move beyond a limit |
| `0x82` | `MOTOR_CMD_LIMIT_HIGH` | upper limit indication |
| `0x81` | `MOTOR_CMD_LIMIT_LOW` | lower limit indication |

## 10. Known Motor States

The following motor state values are explicitly present in the public reverse-engineered code.

| Value | Name | Meaning |
| --- | --- | --- |
| `0x00` | `MOTOR_STATE_IDLE` | idle |
| `0x01` | `MOTOR_STATE_CALIBRATED` | calibration finished |
| `0x02` | `MOTOR_STATE_MOVING` | moving |
| `0x03` | `MOTOR_STATE_MOVING_SLOW` | slow movement near target |
| `0x04` | `MOTOR_STATE_CALIBRATING` | calibration in progress |
| `0xA5` | `MOTOR_STATE_LIMIT_A` | inferred limit-related state |
| `0x25` | `MOTOR_STATE_LIMIT_B` | inferred limit-related state |
| `0x62` | `MOTOR_STATE_BLOCKED` | blocked or collision-like error state |
| `0x65` | `MOTOR_STATE_ERROR` | general motor error |

The exact distinction between `0xA5` and `0x25` is not fully decoded, but both are treated as special limit-related conditions in the public implementations.

## 11. Position Model

The desk reports a numeric position rather than a direct height in centimeters.

Observed characteristics from the earlier LYFT project:

- the motor step values appear to lie roughly in the range `162` to `6537`
- these values represent actuator position, not a user-facing height unit
- user-facing height must be derived from a separate conversion model

For BekantX, these raw position values should be treated as the authoritative desk coordinate system on the LIN side.

## 12. Safety-Relevant Observations

The public implementations reveal several behavior patterns that matter for controller design:

- both motor positions are polled each cycle and compared for drift
- blocked motor states trigger a rescue sequence rather than continuing normal motion
- movement slows down near the target before a final stop command is issued
- calibration is an explicit command sequence rather than an implicit side effect
- loss of valid motor data is counted per motor and affects how the controller chooses a trusted position reference

These observations are relevant for BekantX because they show that the desk protocol is not just a simple direct up/down interface. It exposes enough state to implement range management, drift monitoring, and blocked-motion handling.

## 13. Example Transactions

### 13.1 Runtime Read of Left Motor

Application-level intent:

1. master sends LIN break
2. master sends sync `0x55`
3. master sends protected identifier for node `8`
4. left motor replies with `position_lo`, `position_hi`, `state`, and enhanced checksum

### 13.2 Runtime Command Write

Application-level intent:

1. master sends LIN break
2. master sends sync `0x55`
3. master sends protected identifier for node `18`
4. master sends `position_lo`, `position_hi`, `command`
5. master sends enhanced checksum

### 13.3 Diagnostic Read of Register `0x09`

Observed data payload:

```text
[node] 06 09 00 FF FF FF FF
```

This is sent to diagnostic transmit node `0x3C`, and the desk responds via diagnostic receive node `0x3D` with an `8`-byte diagnostic payload protected by classic checksum.

## 14. Open Questions

The following points are not fully resolved yet:

- exact meaning of the announcement, preprocessing, and postprocessing diagnostic payloads
- exact desk-internal role of runtime nodes `1`, `16`, and `17`
- full semantic meaning of the startup scan fields `identifier` and `nodeFound`
- whether all IKEA BEKANT revisions use exactly the same startup behavior
- whether additional undocumented state codes exist beyond those already observed

## 15. Practical Guidance for BekantX

Until direct captures from the target desk are available, BekantX should treat the following as the current working model:

- use a standard LIN physical layer and protected-identifier calculation
- assume `19200 baud` unless measurements show otherwise
- use classic checksum for diagnostic traffic on `0x3C/0x3D`
- use enhanced checksum for normal runtime traffic
- model runtime traffic around nodes `8`, `9`, `17`, and `18`
- treat startup as a diagnostic discovery-and-parameter-read phase rather than a fixed blind sequence only
- keep controller logic tolerant to unknown auxiliary-node behavior

## 16. Source Basis

This document is based on public reverse-engineering work in:

- `mgkoenig/lyft`
- `mgkoenig/lyft_mk2`

Further refinement should be based on direct logic-analyzer captures from the target desk and validation against the specific BEKANT hardware revision used by BekantX.