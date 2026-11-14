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
**Rev. 3 (2026-11-14, Branch `cad/enclosure-single-pcb`):** parametrisch in build123d, Quelle `CAD/src/bekantx_enclosure.py` (alle Masse im Block `Params`). Exporte: `CAD/BekantX_Case_r3`, `BekantX_Lid_r3`, `BekantX_Keypad_r3` (je STEP + STL). Rev. 3 ersetzt Rev. 2; die r2-Exporte liegen noch im Repo und können gelöscht werden. Die alten `BekantX_Case.stl` / `BekantX_Lid.stl` bleiben als Stil-Referenz.

Anlass war der erste Probedruck von Rev. 2: der Deckel liess sich nur mit Gewalt eindrücken und stand am Armende und an den Schrägen über. Ursache war nicht die Toleranz, sondern die Geometrie (Falzwände senkrecht zum Arm, der Deckel war gefangen; der Review hatte das vor dem Druck als Blocker gemeldet).

- **Form wie das Original**: Frontblock mit Tasten und Anzeige, um 55° abgewinkelter Arm unter der Tischplatte. Frontblock 44 mm tief, **19.5 mm hoch** (Original 20, Rev. 2 23). Aussenmasse 140 × 76.7 × 53 mm.
- **Deckel (Scharnier + Schnapper)**: zwei Zungen am Armende greifen in Taschen der Endwand, vorne rastet der Deckel unter zwei Lippen der Frontwand ein. Alle Deckelkanten und Falzwände sind Prismen entlang der Richtung, in der die Vorderkante um das Scharnier schwenkt (ca. 26° zu Z); so kommt der starre Deckel hinein und heraus. Beim Einrasten wird der geknickte Deckel um ca. 0.25 mm gestaucht (Lippe 0.67 mm, Überdeckung 0.40 mm, Haltefläche 40° zur Bewegung, also lösbar). Zwei Schrauben M2.5×6 im Arm sichern (Kopf 1.2 mm versenkt), eine Lasche vorne in der Mitte (16 mm breit, Fase darunter für den Fingernagel) öffnet. Deckeldicke 2.4 mm.
- **Fasen**: eine einheitliche 45°-Fase von 3 mm (Front zu Frontwand, Front zu Seitenwänden, vordere Ecken) und 0.8 mm an den Aussenkanten der Deckelseite. Vorher 3/5, 2/3 und 0.5 mm.
- **Schrauben**: acht gleiche **M2.5×6 Linsenkopf** (ISO 7045 / ISO 14583) direkt in den Kunststoff, 6 für die Platine, 2 für den Deckel; Kernloch 2.25 mm, Durchgang 2.9 mm, Eingriff 4.4 bzw. 4.8 mm. Am Tisch weiterhin Holzschrauben (Loch 4.5 mm).
- **Material**: Gehäuse 49.3 cm³ (vor der Optimierung 54.5): Innenwände des Arms neigen sich unter dem Deckelfalz um 45° nach aussen statt senkrecht zu stehen, Frontwand unter dem Falz 3.8 statt 5 mm.
- **Tastenmatte**: die sechs Kappen hängen an 0.4 mm dicken Armen (zwei Lagen, 2.5 mm breit, ca. 8.5 mm lang) an einem Steg entlang der Frontwand, ein Druckteil. Symbole 0.4 mm vertieft: von vorne gelesen M1 M2 M3 M4, Anzeige, Hoch, Runter (Parameter `button_labels`; die Belegung ist eine Annahme, in den Specs steht keine). Druck mit Steg und Armen auf dem Bett, Kappen nach oben.
- **USB-C bündig**: die Buchse endet 0.2 mm hinter der Wandaussenfläche, die Öffnung ist nur so gross wie die Buchse (+0.3 mm). Dafür hat die Platine eine **Nase** (3.8 × 11 mm) unter der Buchse; Montage: Platine 1.4 mm nach −X versetzt absenken, dann nach +X in die Wandtasche schieben. Über der Tasche ist der Deckelfalz ausgeklinkt, der Deckel hat dort ein Ohr.
- **Platine**: 129 × 38 × 1.6 mm plus USB-Nase, auf 6 Domen (vordere Dome verschoben wegen der Tastenmatte). F.Cu zeigt zur Front, 6 mm Abstand; **Rückseite 7.5 mm frei, Bauteile bis 7.0 mm** (Entscheid 2026-11-14: bleibt so, C40 wird ersetzt, siehe [[Offene Punkte]]).
- **Das Gehäuse gibt die Platine vor** (`CAD/board_interface.json`, vom Skript erzeugt): Umriss mit Nase, Bohrungen, Tasten, OLED, LEDs, USB, Sperrfläche der Tastenmatte, Höhengrenzen.
- **Druck** (Bambu Lab P1S; Prototyp PLA, Endteil PETG): Gehäuse mit der Front auf dem Bett, Deckel mit der Innenseite des Blockteils auf dem Bett, Tastenmatte flach. Keine Stützen. Schichthöhe 0.2 mm (die Arme der Tastenmatte sind genau zwei Lagen).
- **Probedruck (2026-11-14):** Rev. 3 in PLA auf dem P1S gedruckt, passt (Aussage des Nutzers). Die r2-Exporte sind entfernt.
- **Geprüft (rechnerisch)**: 0 mm³ Überschneidung gegen die Hüllgeometrie; Deckel schwenkt ohne Lippen kollisionsfrei um die Zungenspitzen (0.5° bis 6°) und lässt sich danach aus den Taschen ziehen; mit Lippen überschneidet er sich nur zwischen 0.5° und 1.5° (das ist der Schnapper); Platine lässt sich versetzt absenken und einschieben; STL wasserdicht; Renderings und Schnitte gesichtet. **Nicht geprüft**: kein Druck von Rev. 3. Schnappkraft (Schätzung 10 N am Deckel, 15–20 N an der Lasche) und alle Toleranzen sind Rechenwerte; stellbar über `snap_compress`, `snap_retention_deg`, `lid_clearance`.

Zurück: [[00 Index]]
