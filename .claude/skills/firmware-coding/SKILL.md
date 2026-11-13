---
name: firmware-coding
description: Write or change BekantX firmware (ESP-IDF C++ for the ESP32-C3 secondary, STM32 C/C++ for the primary). Use for any change under Firmware/, including the SPI/LIN protocol implementations.
---

# Firmware coding

Read first: `Vault/Firmware ESP32-C3.md`, `Vault/Firmware STM32.md`, `Docs/inter-controller-protocol.md`, `Docs/bekant-lin-protocol.md`, `Firmware/ESP32C3/BekantX/APPLICATION_PLAN.md`.

## ESP32-C3 (ESP-IDF)
- Structure: components `bekantx_application`, `bekantx_drivers`, `bekantx_libs`, `bekantx_mqtt`, `bekantx_utils`; thin C `main/main.c`; C++ classes with headers under `include/<module>/`. Follow existing naming and the `CppWrapper` boundary.
- Config via Kconfig (`Kconfig.projbuild`) and `sdkconfig.defaults`, not hard-coded pins or topics. Pins/IRQ/wake come from Kconfig.
- FreeRTOS: no blocking in tasks that serve SPI; bounded queues; ISR only signals a task; check every `esp_err_t`; use `ESP_LOG*` with a module tag; never log credentials.
- NVS for credentials and config; validate on load, fall back to safe defaults.
- Build: `idf.py build` (ESP-IDF environment required; if it is not installed, say the build was **not** run).

## STM32 (primary)
- Pin/peripheral config from `Bekanntx.ioc` (CubeMX). Keep generated code separate from application code (USER CODE sections only, or a separate `App/` layer).
- Hard real-time LIN schedule must not depend on SPI, flash writes or logging. Deterministic loop, watchdog enabled, safe state on reset: motors idle.
- Pure logic (position model, protocol framing/CRC, state machines, lease handling) in hardware-independent modules so they run in host unit tests (`test-engineering`).

## Protocol work
- Change `Docs/inter-controller-protocol.md` first; implement CRC-16/CCITT-FALSE, frame limits (64 bytes), sequence/duplicate handling and lease timeouts exactly as specified. Unknown but well-formed command → `STATUS_UNSUPPORTED`; malformed → drop and count, no side effects.
- LIN constants (node IDs, commands, states) are reverse-engineered and **unverified on the real desk**; keep them in one header with a comment saying so.

## Style
Small functions, explicit error handling, no dynamic allocation in steady state on the primary, `const`/`constexpr`, comments explain why. Match the surrounding code.

## Done when
Builds (or "not built" stated), unit tests for the pure logic pass, pin map consistent with schematic, docs/vault updated, `code-reviewer` reviewed.
