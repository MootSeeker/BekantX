---
name: cad-review
description: Review BekantX enclosure CAD (build123d scripts and STEP/STL) for fit, printability and parametrics. Use before a CAD PR or print; the cad-reviewer subagent follows this skill.
---

# CAD review

Read-only. Inputs: `CAD/src/*.py`, exported STEP/STL, board STEP, board JSON.

## Checks (with the build123d venv: `%USERPROFILE%\.venvs\bekantx-cad\Scripts\python.exe`)
1. **Mesh integrity** (`trimesh`): watertight, no degenerate faces, positive volume, bounds vs expected outer size.
2. **Fit**: load the board STEP and case/lid; interference volume ≈ 0; min distance board↔walls; component height vs lid clearance; connector/display/button/LED openings aligned with their board coordinates (report offsets in mm).
3. **Printability**: min wall ≥ 2 mm (sample via ray casting/section slices), overhangs > 45° without support or chamfer, first-layer flat faces, bridge lengths, hole diameters vs screw/insert specs, lid-case clearance 0.2–0.3 mm.
4. **Parametrics**: all dimensions from the `params` block; changing one param regenerates a valid solid (try a ±10 % change on 2–3 parameters).
5. **Assembly**: screw access, lid removal, cable routing, strain relief, desk mounting.
6. **Consistency**: STEP and STL match; revision naming; existing files not overwritten.

## Report format
```
Verdict: PASS | PASS WITH NOTES | FAIL
Numbers: outer size, min wall, interference volume, clearances, opening offsets
Blockers / Majors / Minors / Nits: <part — problem — measurement — fix>
Verified: <how>    Not verified: <e.g. physical print, material shrinkage>
```
