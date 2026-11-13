---
name: fab-export
description: Generate manufacturing files for a BekantX PCB (Gerbers, drill, BOM, pick-and-place, STEP, PDF) with kicad-cli and check them before ordering. Use when preparing a PCB order or a release.
---

# Fabrication export

Pre-checks: DRC clean (zero errors, zero unconnected, parity ok), ERC reviewed, `pcb-reviewer` verdict PASS, BOM has MPN/LCSC for every populated part, version/date silkscreen updated.

## Commands (from the board folder, `kicad-cli` from `C:\Program Files\KiCad\10.0\bin`)
```
kicad-cli pcb export gerbers --output out/gerbers/ <board>.kicad_pcb
kicad-cli pcb export drill   --output out/gerbers/ <board>.kicad_pcb
kicad-cli pcb export pos     --format csv --units mm --side both -o out/cpl.csv <board>.kicad_pcb
kicad-cli sch export bom     -o out/bom.csv <root>.kicad_sch
kicad-cli sch export pdf     -o out/schematic.pdf <root>.kicad_sch
kicad-cli pcb export step    --subst-models -o out/board.step <board>.kicad_pcb
```
Use the layer list and options required by the chosen assembler (JLCPCB: map reference/rotation conventions in the CPL; check the fab's current guidelines before ordering).

## Verify the output
- Load the Gerbers in a viewer (render with `kicad-cli` or another Gerber viewer if installed) and look at every layer; check outline, drills, mask openings, paste.
- Cross-check BOM count vs CPL count vs placed footprints; DNP parts excluded consistently.
- Output goes to `build/` (git-ignored) or a release asset, never committed to the source tree.
- Ordering and payment are the user's action; never place an order.
