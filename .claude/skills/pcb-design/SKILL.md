---
name: pcb-design
description: Lay out BekantX PCBs in KiCad with the Freerouting autorouter as the main routing tool - set up design rules, constraints and router parameters, tune them by measured parameter sweeps until the result needs only small manual touch-ups, then verify with DRC and the enclosure fit. Use when editing any .kicad_pcb, routing a board, or tuning router settings.
---

# PCB design (autorouter-first)

The goal is not "run the autorouter once". The goal is a **tuned, reproducible router setup** (rules + constraints + parameters) that produces a board needing only small manual touch-ups. Spend the effort on the setup and on measuring, not on hand-routing.

## Tools (all local, see `Vault/Toolchain.md`)
- Pipeline: `"C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/autoroute.py route|tune <board.kicad_pcb> [options]`
  Exports DSN (`pcbnew`) → Freerouting → imports SES → refills zones → measures (unrouted, vias, length, DRC **delta vs. baseline**) → writes `build/route/<run>/{routed.kicad_pcb,metrics.json}` and `best.json`. Never modifies the source board; `--apply` writes `<board>_routed.kicad_pcb` next to it.
- Freerouting 2.5.0: `%USERPROFILE%\tools\freerouting\freerouting.jar`, run with portable JDK 25 in `%USERPROFILE%\tools\jdk25`. (The native `freerouting-cli.exe` is broken for routing, do not use it.) Telemetry is disabled (`-da`, settings file).
- Profiles: `tools/pcb/profiles/*.json` (router parameters, keys are relative to `--router.`). Per board, save the tuned profile as `tools/pcb/profiles/<board>.json` and commit it.
- Reviews: `kicad-cli pcb drc`, `pcb render`, `pcb-reviewer` agent.

## Workflow

### 1. Preconditions (stop if not met)
Schematic ERC reviewed; netlist updated into the board; every footprint has correct pads; **placement is final enough** (the router never moves parts; a bad placement cannot be tuned away); board outline, mounting holes and keep-outs from the enclosure parameters; GND/power zones drawn (they become plane nets); antenna keep-out as a rule area.

### 2. Rules first (this is where most "autorouter DRC errors" come from)
- In `.kicad_pro` define net classes: `Default`, `Power` (width from current), `LIN`, `USB` (90 Ω pair), with clearance/track/via values the **fab can build** (JLCPCB 2-layer: use ≥ 0.15 mm trace/space, 0.3 mm drill, 0.6 mm via; prefer looser). Set board minimums (`min_track_width`, `min_via_diameter`, `min_hole_clearance`, copper-to-edge).
- Check what the router actually received: `grep -nE "resolution|\(rule|\(width|\(clearance|\(class" build/route/<run>/in.dsn`. Values must match the net classes. KiCad custom rules (`.kicad_dru`) are lost in the DSN; pass them with the profile key `"_rules": "<file>.kicad_dru"`.
- Zone clearance is **not** known to the router: DRC only reads true after zones are refilled (the pipeline does this). If you route manually in pcbnew, refill zones before judging DRC.

### 3. Constraints
- Hand-route only what the router cannot know: USB pair, LIN, power entry. Lock those tracks (`track.SetLocked(True)`); `route` keeps locked tracks (strip happens only for unlocked ones).
- Use net classes to steer: `ignore_net_classes` in the profile skips classes you routed by hand (comma list or array), e.g. `"autorouter.ignore_net_classes": ["USB"]`.
- Plane nets: GND (and rails with pours) via `"plane_nets": ["GND"]` if not auto-detected; keep `scoring.plane_via_costs` low so pads drop into planes with short vias.

### 4. Baseline run, then measure
`route <board> --profile balanced` → read the table: `unrouted`, `drc_new` (errors the router introduced), `vias`, `len_mm`, and `drc_new_by_type` in `metrics.json`. Open the render and look at it.

### 5. Tune by sweeps, not by guessing
`tune <board> --profile balanced --via-costs 15 30 60 100 --ripup-costs 50 100 200 --jobs 6` (≈ 40 s for a small board; runs are independent copies). Rank is: unrouted → new DRC errors → vias → length. Then **narrow**: re-run a finer grid around the best cell, then vary the next knobs one group at a time:

| Symptom | Likely cause | Try |
| --- | --- | --- |
| `unrouted > 0` | router gives up, vias too costly, too few passes | lower `scoring.via_costs`, raise `autorouter.max_passes`, raise or lower `start_ripup_costs`; if still open: change **placement** or add a layer, not more passes |
| `track_width` errors, tracks thinner than the net class | automatic neckdown | `"automatic_neckdown": false` (already in the profiles) |
| `clearance` errors to zones | stale fills | refill zones (pipeline does); else rules mismatch in `in.dsn` |
| `clearance`/`hole_clearance` at pads | DSN rules smaller than board rules | fix net class values, re-export |
| `starved_thermal` | zone connection/thermal-relief settings, not the router | adjust zone thermal gap/spoke or pad zone connection in KiCad |
| too many vias | via cost too low | raise `scoring.via_costs`, `plane_via_costs` stays low |
| long, wiggly traces | optimizer stops early | lower `optimizer.improvement_threshold` (1.0 → 0.5), more `optimizer.max_passes` |
| results identical across runs | parameter not applied | read `build/route/<run>/freerouting.out` for `Failed to apply CLI router setting` |

Freerouting 2.5.0 facts (verified): valid keys include `autorouter.max_passes`, `autorouter.ignore_net_classes`, `scoring.via_costs`, `scoring.plane_via_costs`, `scoring.start_ripup_costs` (**integers only**), `automatic_neckdown`, `optimizer.enabled|improvement_threshold|max_passes`, `fanout.enabled`, `trace_pull_tight_accuracy`, `allowed_via_types`, `plane_nets`, `max_threads`. Not available in 2.5.0 despite newer docs: `item_order_seed`, `stagnation_pass_limit`, `priority_net_classes`, `plane_as_priority`. Check unknown keys in the run's `freerouting.out` warnings before trusting a sweep.

### 6. Apply and finish by hand (small things only)
`tune ... --apply` (or `route ... --apply`) → `<board>_routed.kicad_pcb`. Compare against the source, open in KiCad, then do only: ratsnest leftovers, length tuning, teardrops, stitching vias, silkscreen, test points. If the manual list grows long, go back to step 2/3/5 and improve the setup instead.

### 7. Verify and record
- Full DRC with schematic parity (`kicad-check` hook / `kicad-cli pcb drc --schematic-parity --refill-zones`): zero errors, zero unconnected. Render top/bottom and view.
- Fit check against the enclosure with `mechanical-cad`.
- `pcb-reviewer` agent before the PR.
- Save the winning profile as `tools/pcb/profiles/<board>.json`; note rules, profile, final metrics and what remained manual in `Vault/Hardware.md` (skill `vault-update`).

## Rules
- The source board is never overwritten by the pipeline. Experiments stay in `build/` (git-ignored).
- Pre-existing DRC findings are not yours; report the delta (the pipeline already does).
- Report honestly: tuned result with numbers (unrouted, new DRC errors, vias, length, runs tried) and what was not verified (signal integrity, EMC, thermal, real fab rules).
- If a run dies (JVM crash, timeout), say so; the script retries once and records `jvm_crash.log` in the run folder.
