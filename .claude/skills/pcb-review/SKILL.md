---
name: pcb-review
description: Review a BekantX KiCad PCB layout for DRC, manufacturability, signal/power integrity, EMC and mechanical fit. Use before a PCB PR or fab export; the pcb-reviewer subagent follows this skill.
---

# PCB review

Read-only. Inputs: `.kicad_pcb`, `.kicad_pro` (rules), the schematic, enclosure parameters in `CAD/`.

## Steps
1. `kicad-cli pcb drc --format json --severity-all --schematic-parity`; split pre-existing vs new. Unconnected items and parity errors are blockers.
2. Render front/back (`kicad-cli pcb render --side top|bottom`) and inspect; export STEP for the fit check.
3. Query the board with `pcbnew` for facts (track widths per net class, via sizes, clearances, courtyard overlaps, copper-to-edge distance, ref-des text sizes).
4. Walk the checklist; give severity, location (coordinates/ref/net), evidence, fix.

## Checklist
- **Manufacturing** (assembler rules for the chosen fab): min trace/space, drill, annular ring, copper-to-edge, solder-mask slivers, silk over pads, fiducials, panelisation need, part orientation consistency, polarised parts marked, thermal reliefs on hand-solder pads, tombstone-prone 0402 asymmetry.
- **Power**: trace widths vs current, regulator thermal copper, input protection placement, decoupling distance to pins, return paths.
- **Signals**: SPI short/grouped, no splits under fast signals, USB pair impedance/length match, LIN protected and away from switching, crystal guard.
- **EMC/ESD**: antenna keep-out honoured (no copper, parts, or traces), ESD parts at connectors, stitching around the board edge, loop areas small.
- **Safety**: creepage/clearance on the desk-voltage side per the actual voltage; mounting holes and screws vs copper.
- **Mechanical**: outline matches the enclosure parameters; hole positions; connector/button/display/LED alignment with enclosure openings; component heights vs lid.
- **Documentation**: board name/revision, pin 1 markers, test point labels, assembly notes.

## Report format
```
Verdict: PASS | PASS WITH NOTES | FAIL
DRC: <new> (pre-existing: <n>)   Unconnected: <n>   Parity: <n>
Blockers / Majors / Minors / Nits: <location — problem — evidence — fix>
Verified: <what, how>    Not verified: <what, why>
```
Do not claim signal-integrity or EMC performance as verified: only layout-rule conformance can be checked here.
