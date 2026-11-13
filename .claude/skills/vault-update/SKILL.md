---
name: vault-update
description: Keep the BekantX Obsidian vault (Vault/) current after relevant work: decisions, status, open items, changelog. Use at the end of any task that changes design, hardware, firmware, tooling or decisions.
---

# Vault update

The vault is the project memory (German, Swiss spelling, `[[wikilinks]]`). It records the **why** and the current status; it links to `Docs/` and the code instead of copying them.

## Steps
1. Decide which notes are affected: `Architektur`, `Hardware`, `Firmware ESP32-C3`, `Firmware STM32`, `Protokolle`, `Toolchain`, `Entscheidungen`, `Offene Punkte`.
2. New decision → row in `Entscheidungen.md` (date, decision, reason). Superseded decisions are marked, not deleted.
3. Done items → tick or remove in `Offene Punkte.md`; add newly discovered open items, assumptions and risks (e.g. unmeasured desk values).
4. Add one line to `Changelog Vault.md` with the date.
5. Keep `00 Index.md` links valid when notes are added or renamed.
6. Never add secrets or personal data (the vault is in the repo).
7. If the work revealed a doc inconsistency (`Docs/`), either fix the doc or record it in `Offene Punkte.md`.
