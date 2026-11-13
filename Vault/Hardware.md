# Hardware

> **Entscheid 2026-11-13:** Controller- und HMI-Platine werden zu **einer** Platine zusammengeführt, der Gehäuse-Style bleibt. Siehe [[Entscheid - Ein PCB]]. Die Abschnitte unten beschreiben den Ist-Stand der beiden bisherigen Platinen.

## Pcb_Controller (KiCad) – die eine Platine
Sheets: `mastersheet` (Root `BekantX.kicad_sch`), `microcontroller`, `powerSupply`, `wifi`, `Connector`, `hmi`.
- **Stand 2026-11-13 (Branch `pcb/merge-hmi-oled`):** HMI ist im Schaltplan integriert. Der Board-zu-Board-Stecker J11 ist entfernt, auf dem Sheet `hmi` sitzen jetzt 6 Tasten (SW3–SW8) mit RC-Filter (100R/100n, Pull-ups 4k7 DNP), das EEPROM 24FC01 (U5, I2C1) und das OLED.
- **Anzeige:** OLED 1.29" 128x64, CH1115, 4-Draht-SPI (EastRising ER-OLED1.29-2W, 16-Pin-FPC). Ersetzt 7-Segment HDSP-433G und Treiber AS1115. Verdrahtet über J3 (16-Pin-FPC, 0.5 mm): interne Ladungspumpe (2× 220 nF), VPP/VCOMH je 4.7 µF, IREF 309k, IM1 an GND (4-Draht-SPI), VDD1/VDD2 an `+3V3`. Datenblätter: `Docs/ER-OLED1.29-2_Datasheet.pdf`, `Docs/CH1115.pdf`, `Docs/ER-CON16HB-1.pdf`. Offene Prüfpunkte siehe [[Offene Punkte]].
- Eine 3.3-V-Rail `+3V3` (vorher zwei unverbundene Netze `+3.3V` und `+3V3`, der STM32 war dadurch unversorgt).
- Der `.kicad_pcb` enthält weiterhin **0 Footprints** (Layout noch nicht begonnen).
- Schaltplan-Edits per Skript: `tools/sch/sch_edit.py` (siehe [[Toolchain]]).

## Speisung und Schutz (Stand 2026-11-13)
```
J10 VDESK -> F1 (1 A träge, 63 V) -> VIN -> D4 (B160) --+-- VCC -> U9  LMR51610 -> +3V3 (1 A)
                         TVS D6 SMBJ33CA auf VIN         |       -> U20 LV2862   -> +12V (nur LIN VSUP)
USB VBUS ----------------------------> D3 (B160) --------+
```
- Verpolschutz und ODER-Verknüpfung über die Schottky-Dioden D4/D3. TVS klemmt bei ca. 53 V, alle Teile an VCC sind für >= 60 V gewählt (Kondensatoren 100 V bzw. 63 V).
- 3.3 V: LMR51610XDBVR (4–65 V, synchron, 400 kHz, SOT-23-6, pin-kompatibel zum LV2862), 22 µH, 69.8k/22.1k → 3.33 V. Ersetzt XL1509 + 68 µH + THT-Diode.
- LIN: ESD-Diode PESD1LIN (D7) am Stecker, Master-Pull-up 1 k (1206) über D70, 1 nF.
- ESP-Teil bleibt bewusst ein diskretes Chip-Design (kein Modul). Status-LED: SK6812MINI an GPIO8, Boot-Taster SW9 an GPIO9 (über 1 k), Reset SW1.
- Bauteildaten: Footprint, MPN und Hersteller sind als Felder im Schaltplan gesetzt; BOM-Export über `kicad-cli sch export bom`.

## Pcb_HMI (KiCad) – abgelöst
Frühere Bedienplatine (AS1115 + HDSP-433G, 6 Tasten über Key-Scan, EEPROM). Tasten und EEPROM sind in `Pcb_Controller` übernommen, 7-Segment und AS1115 entfallen. Das Projekt bleibt als Referenz im Repo (archivieren, nicht löschen).

## STM32 (Primary)
CubeMX `Firmware/ST/Bekanntx/Bekanntx.ioc`: **STM32G0B1KBUx**, alle 32 Pins sind belegt (keine Reserve).

| Pin | Funktion | Netz |
|---|---|---|
| PA0 / PA10 | SPI2 SCK / MOSI (nur TX) | `DISP_SCK` / `DISP_MOSI` |
| PA1 / PA8 / PA9 | GPIO out | `DISP_CS` / `DISP_DC` / `DISP_RES` |
| PA2 / PA3 | LPUART1 TX / RX | `U0RXD` / `U0TXD` (gekreuzt zum ESP-UART0) |
| PA4–PA7 | SPI1 Slave: NSS/SCK/MISO/MOSI | `FSPI_NCS` / `FSPI_CLK` / `FSPI_MISO` / `FSPI_MOSI` (ESP: GPIO10 / 6 / 2 / 7, FSPI-IOMUX) |
| PB5 | GPIO out (Open-Drain empfohlen) | `FSPI_INT` → ESP GPIO9 |
| PB1, PB0, PB2, PB4, PC14, PC15 | GPIO in | `BTN_1` … `BTN_6` |
| PB6 / PB7 | USART1 | `LIN_TX` (Pull-up R45) / `LIN_RX` |
| PB8 / PB9 | I2C1 | `HMI_I2C_SCL` / `HMI_I2C_SDA` (EEPROM) |
| PA15, PB3, PC6 | TIM2 CH1–3 | RGB-LED D5 |
| PA11 / PA12, PA13 / PA14 | USB, SWD | |

Hinweise für die Firmware (nicht verifiziert): PA8/PA9/PA10 liegen im UCPD-Umfeld des G0 (Dead-Battery-Pull-downs über `SYSCFG` abschalten); PC14/PC15 sind schwache Pins, deshalb nur Tasteneingänge. `FSPI_INT` hängt am ESP-Strapping-Pin GPIO9 (Pull-up R6): der STM32 darf die Leitung während eines ESP-Resets nicht tief ziehen. Die SPI2- und GPIO-Einträge im `.ioc` sind von Hand ergänzt und noch nicht in CubeMX geöffnet worden.

## ESP32-C3 (Secondary)
Dev auf ESP32-S2-Saola (Datenblätter in `Docs/`), Zielhardware ESP32-C3. Wake-GPIO per Kconfig = GPIO 9, WS2812 als Status-LED.

## Gehäuse
**Rev. 2 (2026-11-13, Branch `cad/enclosure-single-pcb`):** parametrisch in build123d, Quelle `CAD/src/bekantx_enclosure.py` (alle Masse im Block `Params`). Exporte: `CAD/BekantX_Case_r2`, `BekantX_Lid_r2`, `BekantX_ButtonCap_r2` (je STEP + STL). Die alten `BekantX_Case.stl` / `BekantX_Lid.stl` bleiben als Stil-Referenz und sind **nicht** ersetzt, solange r2 nicht gedruckt und geprüft ist.

- **Form wie das Original**: Frontblock mit Tasten und Anzeige, um 55° abgewinkelter Arm zur Befestigung unter der Tischplatte, Deckel mit Knick in einem Falz. Der Frontblock ist tiefer (44 statt 31.5 mm) und höher (23 statt 20 mm), damit die eine Platine hineinpasst. Aussenmasse 140 × 76.7 × 53 mm (alt 140 × 64.1 × 53).
- **Platine**: 129 × 38 × 1.6 mm, liegt flach hinter der Front auf 6 Domen (selbstschneidende Schrauben 2.2 mm, Vorbohrung 1.9 wie im Original). Die Seite mit Tasten und OLED-Stecker (F.Cu) zeigt zur Front, 6 mm Abstand; Rückseite 11.4 mm frei (C40 braucht 10.2). Der Arm enthält nur noch Kabel und Zugentlastung.
- **Das Gehäuse gibt die Platine vor**, weil das Layout noch leer ist: Umriss, Bohrungen, Tasten, OLED, LEDs, USB und Höhengrenzen stehen in `CAD/board_interface.json` (vom Skript erzeugt, Board-Koordinaten wie in KiCad auf F.Cu gesehen). Sobald ein Layout existiert, dreht sich die Richtung um: Board-STEP als Eingang für die Passprüfung.
- **Bedienfeld**: Tastenbild des Originals (6 Löcher 10.6 mm, Raster 15 mm) mit gedruckten Kappen (Flansch hinter der Front, B3F-1000). OLED-Glas von innen in eine Tasche geklebt, Fenster = Sichtfläche 30.4 × 15.7 mm, FPC geht Richtung +X ab. Zwei Status-LEDs (D5, D1) scheinen durch die auf 0.6 mm ausgedünnte Front, je mit Lichtschacht.
- **Anschlüsse**: USB-C in der Seitenwand (+X), Buchse auf der Platinenrückseite, 1.5 mm über die Platinenkante. Tischkabel verlässt das Gehäuse am Armende (Fenster 9 × 6 mm), Kabelbinder-Schlitze im Armboden.
- **Deckel**: zwei Zungen vorne, zwei Schrauben am Armende. Befestigung am Tisch über zwei Laschen (Holzschrauben, Loch 4.5 mm).
- **Geprüft**: Skript-Passprüfung gegen eine Hüllgeometrie (Platine, Taster, Kappen, OLED, USB, 10.2-mm-Schicht über der ganzen Rückseite): 0 mm³ Überschneidung; alle STL wasserdicht; Renderings gesichtet. **Nicht geprüft**: kein Probedruck, kein echtes Board-STEP, Masse von Taster und USB-Buchse nicht gegen Datenblatt. Details in [[Offene Punkte]].

Zurück: [[00 Index]]
