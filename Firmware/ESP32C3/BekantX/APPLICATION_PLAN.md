# BekantX Network Coprocessor - Application Planning

## 1. Product Vision
Build a robust ESP-IDF C++ network coprocessor for a standing desk controller, developed first on ESP32-S2-Saola and then migrated to ESP32-C3 production hardware, that:
- Manages Wi-Fi connectivity with easy provisioning and recovery.
- Bridges cloud/home automation commands (MQTT) to the main desk CPU.
- Exposes a reliable SPI slave protocol to the master CPU.
- Provides clear local status feedback through onboard RGB LED behavior.
- Enters low-power mode when idle or disconnected for longer periods.

## 2. Core Requirements (Requested Scope)

### 2.1 Smart Wi-Fi Manager
Goal: Behavior similar to lightweight WiFi manager libraries (auto-connect, captive portal fallback, stored credentials).

Planned behavior:
- Try stored Wi-Fi credentials on boot.
- If connect fails, open provisioning mode (SoftAP + captive portal or serial fallback).
- Persist credentials securely in NVS.
- Support reconnect policy with backoff.
- Report Wi-Fi state changes to master CPU via SPI events.

### 2.2 MQTT Client (Smart Home Commands)
Goal: Receive smart-home commands and forward valid actions to master CPU.

Planned behavior:
- MQTT over TLS (if broker supports it) or configurable plain TCP for development.
- Subscribe to command topics (desk up/down/stop/preset/etc.).
- Validate and map inbound payloads to internal command IDs.
- Push commands into SPI outbound queue to master CPU.
- Publish telemetry/state (online/offline, desk state mirror, errors).

### 2.3 SPI Slave + IRQ to Master CPU
Goal: ESP acts as SPI slave command coprocessor.

Planned behavior:
- Implement framed protocol with version, type, length, seq, crc.
- Support command/response and async event messages.
- Use IRQ GPIO line to notify master about queued inbound MQTT commands/events.
- Handle retries, timeout, sequence checks, and malformed frames.
- Maintain bounded queues to avoid memory pressure.

### 2.4 RGB LED Controller (Saola Board)
Goal: Use onboard RGB LED as status and diagnostic indicator.

Planned behavior:
- Boot sequence animation.
- Wi-Fi state indication (connecting, provisioning, connected, error).
- MQTT state indication (connected, disconnected, auth fail).
- SPI traffic/error pulse patterns.
- Optional low-brightness night mode and disable flag via config.

### 2.5 Low Power Management
Goal: Minimize power usage when the coprocessor is not actively needed.

Planned behavior:
- Keep normal active mode while SPI traffic or MQTT activity is present.
- Enter deep sleep after configurable idle timeout when Wi-Fi is disconnected and no critical pending work exists.
- Support wake-up sources based on hardware design (RTC timer and/or external GPIO from master CPU).
- On wake-up, perform fast restore: load config, reconnect Wi-Fi, restore MQTT session, and resync state with master.
- Expose sleep/wake reasons and counters in diagnostics.

### 2.6 Target Transition Strategy (ESP32-S2-Saola -> ESP32-C3)
Goal: Keep development smooth on S2-Saola while reducing migration risk to C3.

Planned behavior:
- Build with target-aware abstraction for board pins and peripheral differences.
- Keep SPI, LED, and wake GPIO mapping in Kconfig (not hardcoded).
- Validate every milestone on both targets where practical.
- Avoid target-specific assumptions in protocol and application logic.
- Freeze a migration checklist before final hardware switch.

## 3. Recommended Software Architecture

## 3.1 Module Layout
- app/
  - AppController (startup orchestration + main state machine)
- wifi/
  - WifiManager (provisioning, connection, events)
- mqtt/
  - MqttService (broker session, subscriptions, publish)
- spi/
  - SpiSlaveTransport (driver, IRQ signaling, queues)
  - SpiProtocol (framing, parser, serializer, CRC)
- led/
  - LedController (patterns + state mapping)
- config/
  - ConfigStore (NVS-backed config and credentials)
- platform/
  - TargetConfig (board/target abstraction for S2 vs C3 pin and feature differences)
- diagnostics/
  - HealthMonitor, counters, watchdog integration

## 3.2 Runtime Model
- Event-driven architecture with FreeRTOS tasks:
  - TaskWifi
  - TaskMqtt
  - TaskSpi
  - TaskLed
  - TaskAppSupervisor
- Use an internal event bus (queue) to decouple modules.
- Keep ISR paths minimal: signal work to task context only.

## 3.3 Power State Model
- States: Active, Idle, DeepSleep.
- Transition to DeepSleep only when:
  - Wi-Fi is disconnected beyond timeout, or device has no active workload.
  - SPI queues are empty and no critical command is pending.
- Wake triggers:
  - RTC timer for periodic reconnect attempts.
  - External wake pin from main CPU (recommended for deterministic wake-on-demand).
- After wake, publish boot/wake reason and re-advertise readiness to master CPU.

## 4. Protocol Planning (SPI)
Define v1 protocol before full implementation.

Frame proposal:
- SOF (2 bytes)
- Version (1 byte)
- MsgType (1 byte)
- Sequence (2 bytes)
- PayloadLength (2 bytes)
- Flags (1 byte)
- HeaderCRC (2 bytes)
- Payload (0..N)
- PayloadCRC (2 bytes)

Message groups:
- CMD_* (from master)
- RSP_* (to master)
- EVT_* (async from coprocessor, e.g. MQTT command arrived)

Required behavior:
- ACK/NACK policy
- Retry policy
- Duplicate sequence handling
- Error codes and diagnostics counters

## 5. Config and Kconfig Plan
Add project-level configuration options for:
- Wi-Fi provisioning enable/disable and timeout.
- MQTT broker URI, port, TLS mode, topic root, QoS.
- SPI pins, queue depth, max payload, IRQ GPIO.
- LED mode, brightness cap, pattern set.
- Power policy: idle timeout, deep sleep enable flag, wake interval, wake pin.
- Target profile selection (S2-Saola dev profile vs C3 production profile).
- Logging verbosity per module.

## 6. Security and Reliability Baseline
Minimum baseline:
- Store credentials in NVS and avoid plain logging of secrets.
- MQTT auth via username/password or certs.
- Enable watchdog and recoverable restart paths.
- Last Will and Testament for MQTT online state.
- Brownout-safe startup and queue bounds.

## 7. Development Phases

### Phase 0 - Foundation
- Convert project baseline from example app to product skeleton.
- Create C++ module structure and CMake wiring.
- Add Kconfig options + sdkconfig.defaults cleanup.
- Add target abstraction and board profile configs for S2-Saola and C3.
- Implement unified logging tags and error policy.

### Phase 1 - Connectivity
- Implement WifiManager with provisioning fallback.
- Implement MqttService connect/subscribe/publish loop.
- Add event model between Wi-Fi and MQTT modules.

### Phase 2 - SPI Bridge
- Implement SPI slave transport and protocol parser.
- Add IRQ signaling and queueing for MQTT->CPU events.
- Implement command/response handlers and timeout handling.

### Phase 3 - UX + Diagnostics
- Implement LED states/patterns.
- Add health metrics (uptime, reconnect count, queue drops).
- Add command to dump diagnostics over SPI or serial log.

### Phase 3.5 - Power Optimization
- Implement idle detection and deep sleep transitions.
- Implement wake flow and post-wake reinitialization ordering.
- Validate no command loss across sleep/wake edges.
- Measure and document active/idle/sleep current consumption.

### Phase 4 - Hardening
- Fault injection and soak tests.
- Reconnect storm handling.
- Payload fuzz tests for protocol parser.
- Optional OTA update support.

## 8. Additional Ideas (Recommended)
For a standing desk network coprocessor, these are high-value additions:

1. Local command deduplication window
Ignore repeated identical MQTT commands within a short window to avoid jittery desk behavior.

2. Safety command filter
Enforce command policy (for example, prevent long continuous move without periodic keepalive).

3. Offline command strategy
When MQTT disconnects, define strict policy: discard, keep last, or bounded queue replay.

4. Device shadow/state reconciliation
Maintain desired vs reported state topics so smart-home UI remains consistent.

5. Home Assistant discovery support
Optional MQTT discovery payloads for easier integration.

6. Manufacturing/service mode
Expose firmware version, Wi-Fi RSSI, broker state, SPI stats, reset reason.

7. Protocol simulator for desktop tests
Small host tool to emulate master CPU SPI transactions during firmware development.

8. OTA update readiness
Even if postponed, reserve architecture hooks and partition strategy early.

9. Offline-safe wake strategy
Let master CPU wake the network coprocessor via dedicated pin before sending critical commands.

## 9. Open Decisions Needed Before Implementation
- SPI electrical contract: max clock, mode, CS timing, IRQ active level.
- Protocol ownership: who defines canonical command IDs (ESP team vs master CPU team).
- MQTT topic schema and payload format (JSON vs compact binary).
- Security profile: TLS required in production?
- Provisioning UX: captive portal only, BLE assist, or serial fallback?
- LED policy: strictly status-only or user-customizable behavior?
- Deep sleep policy: exact idle criteria, timeout values, and allowed wake sources.
- S2 -> C3 migration deltas: final pin map, peripheral differences, and test coverage expectations.

## 10. Definition of Ready
Implementation should start when all checks below are satisfied:
- [ ] Protocol v1 drafted and reviewed by both firmware sides.
- [ ] SPI pin map + IRQ behavior frozen.
- [ ] MQTT topic contract documented.
- [ ] Wi-Fi provisioning flow agreed.
- [ ] C++ project skeleton merged and builds cleanly.
- [ ] Deep sleep and wake behavior specified with measurable criteria.
- [ ] Dual-target build and smoke test validated (S2-Saola dev and C3 production target).
- [ ] Basic integration test plan created (Wi-Fi, MQTT, SPI, LED).
