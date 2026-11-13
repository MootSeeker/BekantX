---
name: cicd-engineering
description: Design and maintain GitHub Actions CI/CD for BekantX (KiCad ERC/DRC, fab/CAD artifacts, ESP-IDF build, host unit tests, release packaging). Use when adding or changing anything in .github/ or defining what must be green before merge.
---

# CI/CD engineering

Workflows live in `.github/workflows/`. Keep jobs small, cached and independent; path filters so a docs change does not rebuild firmware.

## Jobs to provide
1. **kicad-checks** (paths: `Pcb_*/**`): container `kicad/kicad:10.0` (check the tag exists) → `kicad-cli sch erc` and `pcb drc --schematic-parity` with `--exit-code-violations`, upload JSON reports and a rendered PNG/PDF as artifacts. Start with a baseline: record current violation counts, fail only on **new** violations until the board is clean.
2. **fab-artifacts** (on tag/release): Gerbers, drill, BOM, CPL, STEP, schematic PDF zipped as release assets (`fab-export` skill).
3. **firmware-esp** (paths: `Firmware/ESP32C3/**`): `espressif/idf` container, `idf.py build` for `esp32c3`, cache `~/.espressif` and managed components; upload `.bin`.
4. **firmware-stm32** (when code exists): `arm-none-eabi-gcc` build; host unit tests via CMake/ctest.
5. **host-tests**: protocol/state unit tests + `node --test .claude/hooks/*.test.mjs`.
6. **cad** (paths: `CAD/**`): run the build123d scripts, check watertight/bounds with `trimesh`, upload STEP/STL.
7. **docs/links**: markdown link check for `Docs/` and `Vault/`.
8. **release**: version from tag; changelog; attach artifacts.

## Rules
- Pin action versions by tag or SHA, minimal `permissions:` per workflow, no secrets in logs, no secrets needed for PR builds from forks.
- Required checks for merge: the jobs relevant to the changed paths. Do not weaken or skip a check to get green; fix the cause.
- Do not poll CI from a session (see CLAUDE.md git rule 5). After pushing, say that CI runs.
- Local reproduction commands go in each job's comments so a failure can be reproduced on the Windows machine.
- Document the pipeline in `Vault/` (note `CI-CD`) and keep it in step with the workflows.
