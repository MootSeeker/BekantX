---
name: schematic-review
description: Review a BekantX KiCad schematic for electrical correctness, datasheet conformance and completeness. Use before a schematic PR or when asked to check a circuit; the schematic-reviewer subagent follows this skill.
---

# Schematic review

Read-only. Inputs: the root `.kicad_sch` (or a diff), the datasheets in `Docs/`, `Vault/Offene Punkte.md`.

## Steps
1. Run `kicad-cli sch erc --format json --severity-all` on the root sheet. Separate **pre-existing** findings (compare with `git stash`/`git show main:<file>` result) from ones introduced by the change.
2. Export a PDF/SVG and view it. Review sheet by sheet.
3. Netlist check: `kicad-cli sch export netlist` and verify critical nets pin by pin against datasheets (supply, reset/boot, SPI, LIN, programming).
4. Walk the checklist below. For each finding give severity, location (sheet + reference/net), evidence, and a concrete fix.

## Checklist
- **Power**: every supply pin connected, decoupling per pin, rail current budget vs regulator rating, regulator input/output caps per datasheet, protection (reverse polarity, OV, ESD), PWR_FLAGs, sequencing.
- **MCU**: boot/strapping pins in safe state, reset circuit, clock source/load caps, unused pins handled, pin functions match `.ioc` / sdkconfig.
- **Interfaces**: SPI roles (STM32 slave, ESP master) and direction of each line; CS_N pull-up; level compatibility (3.3 V everywhere?); LIN transceiver wiring/termination; USB D+/D- with ESD and series resistors; I2C pull-ups once.
- **Safety**: nothing lets the secondary drive the desk bus; behaviour with the secondary unpowered/DNP (floating inputs? back-powering through SPI pins?).
- **Completeness**: footprint, value, MPN on every part; polarity/orientation notes; test points on rails and key signals; programming header; connector pinouts documented.
- **Assumptions**: unverified desk interface items are labelled and tracked.

## Report format
```
Verdict: PASS | PASS WITH NOTES | FAIL
ERC: <new errors/warnings> (pre-existing: <n>)
Blockers:  1. <sheet/ref> — <problem> — <evidence> — <fix>
Majors / Minors / Nits: ...
Verified against: <datasheets, files>   Not verified: <what you could not check>
```
Never claim a pin or value is correct without having checked the datasheet in this session; say "not verified".
