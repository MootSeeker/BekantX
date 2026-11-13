---
name: schematic-design
description: Design or modify KiCad schematics for BekantX (circuit design, sheet structure, power, MCU, LIN, SPI, HMI, connectors). Use when creating or changing any .kicad_sch file or deciding circuit topology.
---

# Schematic / circuit design

Tools: `Vault/Toolchain.md`. KiCad Python: `C:\Program Files\KiCad\10.0\bin\python.exe` (`skip`, `pcbnew`), `kicad-cli`. Libraries: `C:\Program Files\KiCad\10.0\share\kicad\{symbols,footprints,3dmodels}`.

## Before drawing
1. Requirements and pin budget: `Docs/`, `Firmware/ST/Bekanntx/Bekanntx.ioc` (pin source of truth), `Firmware/ESP32C3/BekantX/sdkconfig.defaults`. Run `component-selection` for new parts.
2. Block diagram first (power tree, signal paths, connectors). Show it to the user for non-trivial changes.
3. Existing structure: root sheet `mastersheet`, sub-sheets `microcontroller`, `powerSupply`, `wifi`, `Connector`, `hmi`. Add to the right sheet; do not restructure without agreement.

## Design rules
- Power: every IC supply pin gets a 100 nF close to it plus bulk per rail; define the power tree with currents; add reverse-polarity and over-voltage protection on the desk-facing input; PWR_FLAG where ERC needs it.
- Reset, boot and programming: BOOT0/EN pull resistors, SWD header (and USB/UART for the ESP) reachable on the board.
- LIN: transceiver with proper pull-up/slave resistor per spec, TVS/ESD, series protection; voltage range **unverified** → `ASSUMPTION` note on the sheet.
- SPI between STM32 (slave) and ESP32-C3 (master): CS_N pull-up so a missing/unpowered secondary cannot select the primary; series resistors (22–47 Ω) on SCLK/MISO/MOSI; optional IRQ/wake line (see `Vault/Offene Punkte.md`). Check ESP32-C3 strapping pins (GPIO2/8/9) before assigning.
- The secondary-controller section must be DNP-able as a block without breaking the primary (AR-007/008): no primary signal may depend on it being populated; isolate shared rails with a link/0 Ω if needed.
- Connectors: ESD on every external pin; pin 1 and orientation marked; mating part named.
- Every symbol: reference designator, value, footprint, MPN. Net names meaningful (`LIN_BUS`, `SPI_SCK`, `+3V3`), global labels for cross-sheet nets, no unnamed critical nets.
- No unconnected pins without an explicit no-connect flag.

## How to edit
- Prefer scripted edits (`skip` for existing symbols/labels/properties; copy the symbol from the KiCad library and instantiate it, including its `lib_symbols` entry, for new parts). Avoid hand-typing S-expressions; if unavoidable, change one thing at a time.
- After each change: `kicad-cli sch erc` on the **root** sheet (the `kicad-check` hook does this after edits and reports the counts), then export a PDF/SVG (`kicad-cli sch export pdf`) and read it visually.
- Existing ERC findings are not yours; do not "fix" them silently. Report the delta.

## Done when
ERC delta is zero for your change, all symbols have footprints/values/MPN, power tree and open assumptions are documented in the vault, and `schematic-reviewer` has reviewed it.
