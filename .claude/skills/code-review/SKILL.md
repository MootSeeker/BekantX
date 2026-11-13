---
name: code-review
description: Review BekantX firmware, scripts and CI changes for correctness, safety, concurrency, protocol conformance and maintainability. Use before a code PR; the code-reviewer subagent follows this skill.
---

# Code review

Read-only. Input: a branch/PR/diff. Use `git diff main...HEAD --stat` first, then read every changed implementation file (not only the diff hunks of tests).

## Checklist
- **Safety**: can any path start or continue desk motion without primary validation, lease, or while a fault is active? Is the failure state "stopped"?
- **Protocol**: framing, CRC (CCITT-FALSE, poly 0x1021, init 0xFFFF), little-endian fields, length limits (≤ 64 B), sequence 0 reserved, duplicate suppression/replay, timeouts (50 ms, one retry), lease timing (default 500 ms, keepalive 100 ms), status/event codes as in the spec.
- **Concurrency**: shared state protected or atomic, queues bounded, no blocking call in an ISR or in the SPI/LIN servicing path, priority inversion, watchdog fed from the right place.
- **Resources**: stack sizes, heap use (no steady-state allocation on the primary), buffer bounds, integer overflow/underflow/sign (positions are s32 in 0.1 mm), string handling.
- **Errors**: every `esp_err_t`/HAL return checked; failure leaves a consistent state; invalid persisted data handled.
- **Security**: no credentials in logs or repo; MQTT/portal input validated; no unbounded input.
- **Config**: pins and topics via Kconfig; consistent with `.ioc`/schematic.
- **Tests**: pure logic covered; the change's edge cases (timeout, duplicate, corrupt frame, reset) are tested or listed as gaps.
- **Maintainability**: naming, size of functions, dead code, comments that explain why, docs updated.

## Report format
```
Verdict: APPROVE | CHANGES REQUESTED
Blockers / Majors / Minors / Nits: <file:line — problem — scenario — fix>
Verified: <read files, ran tests/build> — Not verified: <what, why>
```
Cite `file:line` only for lines you read. Report real defects with a concrete failure scenario; skip style preferences the codebase does not follow.
