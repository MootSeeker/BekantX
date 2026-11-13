---
name: test-engineering
description: Plan and write tests for BekantX (host unit tests for protocol and state logic, firmware tests, simulators, hardware bring-up and verification plans mapped to VC-xxx). Use when adding features, before releases, or when defining how a requirement is verified.
---

# Test engineering

## Test levels
1. **Host unit tests** for hardware-independent logic: CRC-16, frame encode/decode, sequence/duplicate cache, lease timer, LIN PID/checksum, motor state decoding, position model, memory slots. Plain C/C++ with a small framework (Unity/Catch2/GoogleTest, pick one and keep it); build with CMake on the PC so no hardware is needed. Put vectors from the specs into tests (e.g. PID of node 0x3D must be 0x7D).
2. **Protocol simulator** (`tools/` Python): emulate the primary over serial/SPI-bridge or in-process to exercise the secondary, and the reverse. Cover timeouts, retries, corrupt CRC, duplicate request, lease expiry, unknown opcode.
3. **Integration on target**: ESP-IDF (Unity on target / `pytest-embedded`), STM32 with a debug UART log.
4. **Hardware bring-up plan**: ordered steps with expected measurements: rails, reset, SWD, clocks, UART, SPI loopback, LIN with a logic analyzer, desk bring-up with limited travel. Each step lists pass criteria and what to record.
5. **System verification**: map every acceptance criterion `VC-001…VC-007` in `Docs/description.md` to a concrete test (who, how, pass criterion, status). Keep the table in `Vault/` (note `Verifikation`).

## Rules
- Tests first for bugs: reproduce, then fix.
- Test the failure paths listed in the specs (SR-xxx) at least as much as the happy path.
- A test that was not run must not be reported as passing. State the command and result you actually ran.
- Deterministic tests only: no real time sleeps in unit tests (inject a clock), no network.
- Safety-relevant behaviour (lease expiry, stop priority, restricted mode) needs a test before the change is considered done.
