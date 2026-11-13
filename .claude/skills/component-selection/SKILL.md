---
name: component-selection
description: Choose and verify electronic components (MPN, package, footprint, availability, cost) and maintain the BOM for BekantX. Use before placing a new part in a schematic, when replacing a part, or when preparing the BOM.
---

# Component selection and BOM

## Rules
- **Never invent an MPN, pinout or electrical value.** If you cannot verify it from a datasheet (in `Docs/` or fetched from the vendor), say "unverified" and ask.
- Prefer parts that are: in stock at the target assembler (JLCPCB/LCSC basic or preferred parts first, otherwise Mouser/DigiKey), hand-solderable where practical (0603 or larger passives, no BGA unless necessary), and available in the KiCad standard library (symbol + footprint + 3D model).
- Prefer fewer distinct values/packages. One common 100 nF, one 10 µF, 1 % resistors.
- Check: voltage/temperature ratings with margin (derate caps 50 %), package vs footprint (courtyard, pad geometry), pin 1 orientation, MSL/reflow if relevant.

## Process
1. List the function and constraints (voltage, current, interface, size, cost).
2. Shortlist 2–3 parts, compare in a table (MPN, key specs, package, price, stock, library availability).
3. Pick one and justify in one line. Note the datasheet file/URL.
4. Set symbol fields: `MPN`, `Manufacturer`, `LCSC` (if used), `Datasheet`, `Value`, `Footprint`.
5. Add open verification items (e.g. "LIN transceiver voltage range vs desk bus: unmeasured") to `Vault/Offene Punkte.md`.

## BOM
Export from KiCad: `kicad-cli sch export bom` (root sheet) with fields `Reference,Value,Footprint,MPN,LCSC,Quantity`. Check for missing MPN/footprint, DNP flags (the secondary-controller section stays DNP-able, see `Vault/Entscheidungen.md`).

## Project-specific
- Primary: STM32G0B1KBU (UFQFPN32, see `Firmware/ST/Bekanntx/Bekanntx.ioc`). Secondary: ESP32-C3 module (use a certified module with antenna, keep antenna keep-out).
- Desk-facing parts (LIN PHY, supply, connector) depend on unmeasured desk values: design for a wide input range and mark `ASSUMPTION`.
