---
name: architecture-design
description: Design or evaluate BekantX system, firmware and interface architecture (controller split, SPI/LIN protocols, module boundaries, state ownership, safety). Use when a feature touches more than one component, an interface changes, or before starting a new subsystem.
---

# Architecture design

Read first: `Docs/description.md` (requirements AR/FR/SR/NFR/IF), `Docs/architecture.md`, the two protocol specs, `Vault/Architektur.md`, `Vault/Entscheidungen.md`.

## Process
1. State the problem and the requirement IDs it serves (AR-xxx, FR-xxx, SR-xxx). No requirement → say so and propose one.
2. Check the invariants, which no design may break:
   - the primary controller owns all desk movement and safety; the secondary only *requests*;
   - the desk works with the secondary absent, reset or hung (AR-002/003, SR-002);
   - stop has top priority; remote motion needs a lease; lease expiry stops motion;
   - uncertain state → stop / reject / restricted mode (SR-007).
3. Assign state ownership for every new piece of state (who is authoritative, who caches).
4. Define the interface before the implementation: message, units (0.1 mm, s32, little-endian), error codes, timeouts, versioning. Update `Docs/inter-controller-protocol.md` first.
5. Give 2–3 options with trade-offs only when the choice is real; otherwise give a recommendation.
6. Failure analysis: for each new function list what happens on power loss, reset of either controller, link loss, corrupt frame, duplicate frame.
7. Record the decision in `Vault/Entscheidungen.md` (what, why, date) and open items in `Vault/Offene Punkte.md`.

## Output
Short design note: context → decision → interface → failure behaviour → impact on schematic/pins/firmware/enclosure → open questions.

## Review checklist (when asked to review an architecture)
- Any path where the secondary or the network can cause motion without primary validation?
- Single source of truth for each value (pin map, protocol constants, limits)?
- Timing: anything on the LIN schedule that depends on Wi-Fi, flash writes or blocking calls?
- Is the protocol versioned and are unknown commands answered with `STATUS_UNSUPPORTED`?
- Hardware consequences (extra pins, IRQ/wake line, connector) named?
