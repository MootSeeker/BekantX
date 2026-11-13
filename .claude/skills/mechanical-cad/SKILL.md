---
name: mechanical-cad
description: Design the BekantX enclosure (case, lid, mounts, openings) as parametric build123d code and export STEP/STL, fitted to the PCB. Use when creating or changing anything in CAD/ or when the board outline or connector positions change.
---

# Mechanical CAD (build123d)

Python: `%USERPROFILE%\.venvs\bekantx-cad\Scripts\python.exe` (build123d, trimesh, numpy-stl). Source scripts live in `CAD/src/`, exports in `CAD/` (`*.step` **and** `*.stl`).

## Principles
- Millimetres, one `params` block at the top of the script: every dimension named (wall, clearance, board size, hole positions, screw sizes). No magic numbers in geometry code.
- **Keep the existing enclosure style**: take outer shape, split line, proportions and details from `CAD/BekantX_Case.stl` / `BekantX_Lid.stl` (inspect with `trimesh`: bounds ≈ 140 × 64 × 53 mm). Recreate it parametrically, then adapt to the single PCB.
- The board is an input, not a guess: read outline, mounting holes, connector and component positions/heights from the board (`pcbnew` via KiCad Python, or the STEP from `kicad-cli pcb export step`). Write them into a small JSON that the CAD script reads.
- Design for FDM printing (PLA/PETG): wall ≥ 2 mm, 0.2–0.3 mm clearance for fits, no unsupported overhangs > 45° (or add chamfers), screw bosses with heat-set inserts or self-tapping holes (M2.5/M3, hole = 0.9 × thread dia for self-tapping), snap/screw lid, bridging-friendly.
- Functional openings: connector cut-outs with 0.3 mm margin, display window and button/LED holes aligned to board coordinates, cable strain relief, ventilation if needed, label/mounting to the desk (mounting method is a Vault open point).

## Process
1. Collect inputs (board JSON, connectors, display, mount points). List assumptions.
2. Model case and lid in separate bodies with the same origin as the board origin.
3. Export STEP + STL. Run checks (`cad-review` list): watertight, bounding box, min wall.
4. Fit check: import the board STEP, boolean-intersect with case/lid solids (volume must be ~0), check clearance to walls and lid.
5. Render a view (matplotlib/trimesh to PNG) and look at it. Report numbers: outer size, wall, clearances, interference volume.
6. Update `Vault/Hardware.md` with the parameters and open items.

## Rules
- Never overwrite the existing STL files silently; write new versions with a revision suffix and say which replaces which.
- Say what was not verified (no physical print yet, tolerances are estimates).
- Done when the fit check passes and `cad-reviewer` reviewed.
