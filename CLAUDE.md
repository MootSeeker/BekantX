# BekantX

Custom controller for the IKEA BEKANT standing desk: electronics (KiCad), firmware (STM32 + ESP32-C3) and an enclosure (CAD).
Dual-controller design: the **primary** controller (STM32G0B1) owns LIN, motion and safety; an **optional secondary** (ESP32-C3) provides Wi-Fi, MQTT and Home Assistant. The desk must work without the secondary.
This is a hardware project first. Part of its purpose is to find out how far AI-assisted PCB and CAD design can go, so be explicit about what was verified and what was not.

## Project memory: `Vault/`

Knowledge lives in the Obsidian vault `Vault/` (Markdown, `[[wikilinks]]`). **Read first at the start of a task:**
`Vault/00 Index.md`, `Vault/Offene Punkte.md`, then `Architektur`, `Hardware`, `Protokolle`, `Entscheidungen`, `Toolchain` as needed.

- The vault holds the **why** (decisions, status, open items), not what the specs in `Docs/` already say. Link instead of duplicating.
- After relevant work update the vault: affected notes, `Entscheidungen.md` for new decisions, `Offene Punkte.md`, `Changelog Vault.md`. Skill: `vault-update`.
- The vault is in the repo: never put secrets (Wi-Fi/MQTT credentials, keys) or personal data into it.
- The vault is written in German; code, commits, skills and hooks are English.

## Repository layout

```
CAD/                         enclosure (STL/STEP; source scripts go to CAD/src)
Docs/                        specs: description.md (requirements), architecture.md, *-protocol.md, datasheets
Firmware/ESP32C3/BekantX     ESP-IDF C++ project (secondary controller)
Firmware/ST/Bekanntx         STM32CubeMX project (primary controller, no code yet)
Pcb_Controller/              KiCad: main board (hierarchical sheets)
Pcb_HMI/                     KiCad: front/HMI board (to be merged into one board, see Vault)
Vault/                       project memory
.claude/                     skills, subagents, hooks
```

## Tools and commands (Windows)

```bash
KICAD="/c/Program Files/KiCad/10.0/bin"
"$KICAD/kicad-cli.exe" pcb drc --format json -o drc.json <file>.kicad_pcb
"$KICAD/kicad-cli.exe" sch erc --format json -o erc.json <root>.kicad_sch   # always the ROOT sheet
"$KICAD/kicad-cli.exe" pcb export step --subst-models -o out.step <file>.kicad_pcb
"$KICAD/kicad-cli.exe" pcb render -o out.png <file>.kicad_pcb
"$KICAD/kicad-cli.exe" sch export pdf -o out.pdf <root>.kicad_sch
"$KICAD/python.exe" script.py                                               # KiCad Python 3.11: pcbnew, skip, kipy
"$USERPROFILE/.venvs/bekantx-cad/Scripts/python.exe" script.py              # Python 3.13: build123d, trimesh
"$KICAD/python.exe" tools/pcb/autoroute.py tune <board>.kicad_pcb --profile balanced   # Freerouting sweep (see skill pcb-design)
idf.py build                                                                # in Firmware/ESP32C3/BekantX (ESP-IDF env)
```

Details and workflow: `Vault/Toolchain.md`. Output of generated artifacts (renders, reports) goes to the scratchpad or `build/` (git-ignored), not into the source tree.

## Guardrails

**Electronics**
- Never assume the desk's electrical interface (LIN voltage, supply, connector pinout). It is **unverified** until measured on the real desk. Mark such parts of a design as `ASSUMPTION` and list them in `Vault/Offene Punkte.md`.
- Pin assignment has a single source of truth: the `.ioc` for the STM32, the Kconfig/sdkconfig for the ESP. Schematic and firmware must agree; change both or neither.
- A schematic or board change is done only when ERC/DRC were run and the result is reported (counts, remaining violations and why they are acceptable). Look at a rendered image or PDF, do not trust the numbers alone.
- Prefer editing KiCad files through `pcbnew` / `kicad-skip` / `kicad-cli` over hand-editing S-expressions. After any scripted edit re-open the file with the API to prove it still loads.
- Do not delete or move existing placed footprints/wires without saying so; the user may have placed them by hand.
- Parts: real MPNs, check availability and footprint against the datasheet in `Docs/` or the vendor datasheet. Never invent part numbers or pinouts; say when unsure.
- Safety-relevant behaviour stays on the primary controller (see `Docs/description.md`, SR-xxx). No design may let the secondary move the desk without the primary's validation.

**Mechanical**
- Units are millimetres. The enclosure is parametric (`build123d`), every dimension a named parameter; the PCB outline and mounting holes come from the board (`pcbnew`/STEP), not typed by hand.
- Keep the existing enclosure style (`CAD/BekantX_Case.stl`, `BekantX_Lid.stl`). Export STEP **and** STL; check wall thickness, tolerances (printer clearance), and PCB-vs-enclosure collision before calling a part done.

**Firmware**
- ESP-IDF C++ in components (`bekantx_*`), thin C `main`. No blocking calls in tasks that serve SPI; bounded queues; no secrets in logs.
- Protocol changes start in `Docs/inter-controller-protocol.md`, then both firmwares. Bump the protocol version on breaking changes.

**Language**: code, comments, commits, issues, skills and hooks in English; vault in German (Swiss spelling, no ß).

## Git rules

1. **Never commit or push directly to `main`.** One branch per topic → pull request. A hook enforces this.
2. Branch names: `feature/<topic>`, `fix/<topic>`, `chore/<topic>`, `docs/<topic>`, `pcb/<topic>`, `cad/<topic>`.
3. Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`); scopes such as `pcb`, `sch`, `cad`, `esp`, `stm`, `vault`.
4. One PR = one topic. No unrelated files along the way.
5. Merge only after the user's explicit OK and green CI. Do not wait for CI: after the push say that CI is running and continue or stop; the user reports the result. Check once with `gh pr checks` when asked to merge.
6. No force-push, no `--no-verify`, no bypassing hooks or signing, no history rewriting without asking.
7. Issues always get labels (`gh label list` first). Use the issue forms in `.github/ISSUE_TEMPLATE/` when they exist.
8. After merge: delete the branch, `git fetch --prune`.
9. Update the vault when an issue or PR is finished.
10. Never commit secrets (Wi-Fi/MQTT credentials, tokens, `sdkconfig` with credentials). KiCad backup and lock files stay out of git (see `.gitignore`).
11. AI attribution lines (`Co-Authored-By`, "Generated with") in commits and PRs are fine for this repo.

## Workflow

Roles are skills (load on demand) plus a few read-only reviewer subagents (independent review without author bias).

| Task | Skill | Review |
| --- | --- | --- |
| Architecture / interfaces | `architecture-design` | `architecture-design` checklist |
| Schematic | `schematic-design`, `component-selection` | `schematic-reviewer` agent (`schematic-review`) |
| PCB layout (Freerouting-first, tuned by sweeps) | `pcb-design` | `pcb-reviewer` agent (`pcb-review`) |
| Enclosure | `mechanical-cad` | `cad-reviewer` agent (`cad-review`) |
| Firmware | `firmware-coding` | `code-reviewer` agent (`code-review`) |
| Tests | `test-engineering` | |
| CI/CD | `cicd-engineering` | |
| Manufacturing files | `fab-export` | `pcb-reviewer` |
| Vault | `vault-update` | |

Order for a hardware change: architecture/requirements → schematic (+ review) → PCB (+ review) → enclosure fit check → fab export. Never skip the review step for schematic and PCB; run the reviewer subagent before opening the PR and pass its findings on unchanged.

Hooks (`.claude/hooks/`): `guard-bash.mjs` enforces the git rules; `kicad-check.mjs` runs ERC/DRC after edits to KiCad files and reports the result back.
