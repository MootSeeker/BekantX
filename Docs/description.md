# BekantX Requirements Specification

## 1. Purpose

BekantX is an engineering project to develop a custom controller platform for the IKEA BEKANT desk. The purpose of this document is to define the initial system requirements for the first implementation of the platform.

This specification focuses on the controller architecture, core desk-control functionality, safety-related behavior, and the optional IoT extension path. It is intended to guide hardware design, firmware development, integration work, and later validation.

## 2. Background

The project is inspired by [LYFT mk2](https://github.com/mgkoenig/lyft_mk2), which demonstrates that the IKEA BEKANT desk can be controlled through a split architecture with a dedicated low-level desk controller and a higher-level ESP32-based interface controller. BekantX adopts the same high-level architectural idea, but aims for a cleaner hardware implementation and a more explicit separation between critical control logic and optional IoT functionality.

Unlike a consumer product brief, this document treats BekantX as a technical development effort. The central design principle is that all desk-critical behavior must remain on the primary controller, while connected features are isolated behind an optional secondary controller.

## 3. Scope

The initial scope of BekantX includes:

- a primary desk controller responsible for protocol handling, movement control, calibration, limits, and safety-related behavior
- support for memory positions
- support for collision or obstruction detection
- an optional ESP-based secondary controller for IoT functionality only
- a Wi-Fi API intended for integration with Home Assistant
- diagnostics and status reporting required for development and integration

The initial scope does not require cloud services, vendor-specific mobile applications, or dependency on the optional IoT controller for basic desk operation.

## 4. System Overview

BekantX shall use a dual-controller architecture.

The primary controller shall be the authoritative control unit for all desk-related functions. It shall manage communication with the desk, execute movement commands, track position-related state, enforce limits, handle calibration, and react to faults.

The secondary controller shall be optional. Its purpose shall be limited to IoT and integration features such as Wi-Fi connectivity, Home Assistant integration, telemetry forwarding, and remote command transport. The system shall remain operational as a desk controller when the secondary controller is absent, unpowered, disconnected, or malfunctioning.

## 5. Goals

The main goals of BekantX are:

- improve the hardware implementation compared to the available open reference
- keep real-time desk control independent from optional network services
- add features not available in the original desk controller
- create a maintainable foundation for future extension and experimentation
- provide a practical path for Home Assistant integration through a local Wi-Fi API

## 6. Non-Goals

The following items are out of scope for the first requirements baseline:

- mandatory cloud connectivity
- dependency on a smartphone app for normal operation
- support for desk models other than IKEA BEKANT unless explicitly validated later
- replacement of the primary control path by the IoT controller
- safety claims that require formal certification unless such certification is defined in a later project phase

## 7. Architectural Requirements

### 7.1 Controller Separation

- AR-001: The system shall be split into a primary desk controller and an optional secondary IoT controller.
- AR-002: The primary desk controller shall remain fully functional without the secondary controller.
- AR-003: Failure, reboot, or removal of the secondary controller shall not prevent local desk control or leave the desk in an unsafe active movement state.
- AR-004: The primary controller shall own all timing-critical communication with the desk.
- AR-005: The secondary controller shall not directly control the desk bus unless explicitly routed through the primary controller interface.

### 7.2 Modularity

- AR-006: The interface between the two controllers shall be clearly defined and versionable.
- AR-007: The hardware design shall allow the primary controller to be assembled and tested independently of the secondary controller.
- AR-008: Optional IoT functionality shall be removable without redesigning the core desk controller.

## 8. Functional Requirements

### 8.1 Core Desk Control

- FR-001: The primary controller shall communicate with the IKEA BEKANT desk electronics and execute movement commands.
- FR-002: The primary controller shall support moving the desk upward, downward, and stopping motion.
- FR-003: The primary controller shall manage startup, initialization, and desk-ready state handling.
- FR-004: The primary controller shall detect and track relevant desk state, including current movement state and available limit information where technically possible.
- FR-005: The primary controller shall prevent invalid movement commands when the desk is not in a ready state.

### 8.2 Calibration and Limits

- FR-006: The system shall support a calibration procedure if required by the desk protocol or position model.
- FR-007: The controller shall maintain knowledge of the desk's usable movement range.
- FR-008: The controller shall prevent commanded motion beyond known or inferred safe limits.
- FR-009: If valid position information is unavailable, the controller shall enter a restricted or degraded mode rather than continue with unrestricted automatic movement.

### 8.3 Memory Positions

- FR-010: The system shall support configurable memory positions for common desk heights.
- FR-011: The number of stored memory positions shall be configurable in firmware or system configuration.
- FR-012: A user or integrating system shall be able to store, overwrite, recall, and delete memory positions.
- FR-013: Invoking a memory position shall cause the desk to move automatically toward the stored target height.
- FR-014: Automatic motion to a memory position shall stop when the target is reached, a stop command is issued, an obstruction is detected, or a fault condition occurs.

### 8.4 Collision and Obstruction Detection

- FR-015: The system shall include a mechanism for detecting probable collision or obstruction events during powered motion.
- FR-016: Collision detection may be based on one or more indicators such as motor behavior, position drift, timing anomalies, current-related observations, or protocol-visible fault conditions.
- FR-017: On detection of a probable collision or obstruction, the controller shall stop desk motion immediately.
- FR-018: The controller shall record that a collision or obstruction event occurred and expose this information through diagnostics.
- FR-019: The detection strategy shall be configurable and tunable during development.

### 8.5 Local Operation

- FR-020: The system shall support local desk operation without requiring Wi-Fi, Home Assistant, or the optional IoT controller.
- FR-021: A local stop path shall always be available when the primary controller is operating normally.
- FR-022: Local operation shall have priority over optional remote automation when both are active simultaneously.

### 8.6 Optional IoT Controller

- FR-023: The secondary controller shall provide optional network and integration features only.
- FR-024: The secondary controller shall communicate with the primary controller through a defined command and status interface.
- FR-025: Loss of communication between controllers shall not cause uncontrolled desk behavior.
- FR-026: If the secondary controller becomes unavailable, any remote move request in progress shall terminate safely.

### 8.7 Wi-Fi API and Home Assistant Integration

- FR-027: The optional IoT controller shall expose a local Wi-Fi API for external integration.
- FR-028: The primary intended integration target shall be Home Assistant.
- FR-029: The API shall support reading desk state, current position if available, target position if applicable, motion state, fault state, and memory position configuration relevant to automation.
- FR-030: The API shall support commands for move up, move down, stop, and recall memory positions.
- FR-031: The API should support setting or updating memory positions, subject to implementation constraints.
- FR-032: The API shall be designed so that Home Assistant integration can be implemented without cloud dependencies.
- FR-033: Remote commands received through the Wi-Fi API shall be validated by the primary controller before execution.

### 8.8 Diagnostics and Telemetry

- FR-034: The system shall expose diagnostic information useful during development and maintenance.
- FR-035: Diagnostic data shall include controller status, communication health, recent fault conditions, and collision-related events where available.
- FR-036: The system should support telemetry outputs suitable for debugging and integration testing.
- FR-037: Diagnostic functionality shall not compromise the deterministic behavior of the primary control loop.

### 8.9 Persistence and Configuration

- FR-038: Configuration data required for normal operation shall persist across power cycles.
- FR-039: Persisted data may include memory positions, calibration data, configuration values, and selected thresholds.
- FR-040: The system shall detect invalid persisted configuration and fall back to a safe default or recovery path.

## 9. Safety and Fault Handling Requirements

- SR-001: Safety-related desk behavior shall be handled by the primary controller.
- SR-002: Optional network functionality shall never be required to stop desk movement.
- SR-003: Any detected controller communication failure that affects safe automatic motion shall result in a safe stop or a transition to a restricted mode.
- SR-004: The system shall reject malformed, incomplete, or unsupported remote commands.
- SR-005: Automatic movement shall be interruptible by a stop command at any time during normal operation.
- SR-006: Fault states shall be latched or recorded long enough to support diagnosis after the event.
- SR-007: The system shall prefer stopping motion over continuing movement when internal state confidence is insufficient.

## 10. Non-Functional Requirements

### 10.1 Reliability

- NFR-001: The primary controller shall be designed for predictable behavior under normal operation and foreseeable fault conditions.
- NFR-002: Optional IoT features shall degrade gracefully and shall not compromise core desk functionality.

### 10.2 Maintainability

- NFR-003: Hardware and firmware boundaries shall be documented clearly enough to support future redesign and extension.
- NFR-004: The primary and secondary controller firmware shall be independently testable.
- NFR-005: The design should favor simple, inspectable interfaces over tightly coupled implementation shortcuts.

### 10.3 Performance and Determinism

- NFR-006: Timing-critical desk communication shall not depend on Wi-Fi stack timing, network latency, or Home Assistant availability.
- NFR-007: Remote integration latency is acceptable only if it does not interfere with safe and deterministic local control.

### 10.4 Security

- NFR-008: The Wi-Fi API shall be designed for local-network use and should include a basic authentication or access-control strategy before general deployment.
- NFR-009: The system shall not require internet connectivity for core operation.

### 10.5 Serviceability

- NFR-010: The design should support firmware updates and recovery procedures for both controllers.
- NFR-011: The design should provide a practical method for observing internal state during bring-up and debugging.

## 11. External Interface Requirements

### 11.1 Desk Interface

- IF-001: The primary controller shall implement the physical and logical interface required to communicate with the BEKANT desk system.
- IF-002: The desk-facing interface shall be electrically compatible with the target desk hardware.

### 11.2 Inter-Controller Interface

- IF-003: The communication link between primary and secondary controller shall have a documented command set, framing, and error-handling strategy.
- IF-004: The inter-controller interface shall support status queries, movement commands, stop commands, memory position operations, and diagnostic access.

### 11.3 User and Integration Interface

- IF-005: The system shall provide a local control path independent of Home Assistant.
- IF-006: The optional Wi-Fi API shall be suitable for integration by Home Assistant through a local network.

## 12. Assumptions and Constraints

- AC-001: The first implementation targets the IKEA BEKANT desk family and may need validation for specific desk revisions.
- AC-002: Some desk-internal signals and protocol details may need to be inferred through reverse engineering and testing.
- AC-003: Collision detection in the first version may be heuristic rather than based on certified safety sensing.
- AC-004: Exact hardware choices for the primary controller are not fixed by this document.
- AC-005: The use of an ESP-class device for the optional IoT controller is a current project direction, but the key requirement is optional Wi-Fi integration rather than a specific chip family.

## 13. Verification and Acceptance Criteria

- VC-001: The primary controller shall be able to initialize and operate the desk without the optional IoT controller present.
- VC-002: The system shall successfully execute local move up, move down, and stop commands.
- VC-003: Memory positions shall be stored, recalled, and executed repeatably within the tolerance defined during implementation.
- VC-004: A simulated or real obstruction event shall cause movement to stop and produce a diagnostic record.
- VC-005: Disconnecting or resetting the optional IoT controller during normal operation shall not leave the desk moving uncontrolled.
- VC-006: Home Assistant integration shall be able to read desk state and send basic control commands through the Wi-Fi API.
- VC-007: Invalid or malformed remote commands shall be rejected without unsafe side effects.

## 14. Open Items

The following items remain open and should be refined in later revisions:

- the exact physical user interface on the local controller
- the exact production pin assignment and validated SPI operating limits
- the exact data model and transport format of the Wi-Fi API
- quantitative thresholds and validation strategy for collision detection
- acceptable target tolerance for position recall and repeatability
- preferred firmware update path for both controllers

## 15. Summary

BekantX is defined as a dual-controller desk-control platform with a strict separation between core real-time desk control and optional IoT functionality. The primary controller is the safety-relevant and timing-critical part of the system. The optional secondary controller adds Wi-Fi-based integration, with Home Assistant as the primary target. The resulting system is intended to remain functional, maintainable, and safe even when optional connected features are absent or unavailable.
