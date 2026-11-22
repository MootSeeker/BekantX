# Hardware

> **Entscheid 2026-11-13:** Controller- und HMI-Platine werden zu **einer** Platine zusammengeführt, der Gehäuse-Style bleibt. Siehe [[Entscheid - Ein PCB]]. Die Abschnitte unten beschreiben den Ist-Stand der beiden bisherigen Platinen.

## Pcb_Controller (KiCad) – die eine Platine
Sheets: `mastersheet` (Root `BekantX.kicad_sch`), `microcontroller`, `powerSupply`, `wifi`, `Connector`, `hmi`.
- **Stand 2026-11-13 (Branch `pcb/merge-hmi-oled`):** HMI ist im Schaltplan integriert. Der Board-zu-Board-Stecker J11 ist entfernt, auf dem Sheet `hmi` sitzen jetzt 6 Tasten (SW3–SW8) mit RC-Filter (100R/100n, Pull-ups 4k7 DNP), das EEPROM 24FC01 (U5, I2C1) und das OLED.
- **Anzeige:** OLED 1.29" 128x64, CH1115, 4-Draht-SPI (EastRising ER-OLED1.29-2W, 16-Pin-FPC). Ersetzt 7-Segment HDSP-433G und Treiber AS1115. Verdrahtet über J3 (16-Pin-FPC, 0.5 mm): interne Ladungspumpe (2× 220 nF), VPP/VCOMH je 4.7 µF, IREF 309k, IM1 an GND (4-Draht-SPI), VDD1/VDD2 an `+3V3`. Datenblätter: `Docs/ER-OLED1.29-2_Datasheet.pdf`, `Docs/CH1115.pdf`, `Docs/ER-CON16HB-1.pdf`. Offene Prüfpunkte siehe [[Offene Punkte]].
- Eine 3.3-V-Rail `+3V3` (vorher zwei unverbundene Netze `+3.3V` und `+3V3`, der STM32 war dadurch unversorgt).
- Schaltplan-Edits per Skript: `tools/sch/sch_edit.py` (siehe [[Toolchain]]).
- **Layout Rev. 1 (2026-11-15, Branch `pcb/layout-4layer`)**: siehe Abschnitt «Layout» unten.

## Layout Rev. 1 (2026-11-15, nach Review und PR-Feedback überarbeitet 2026-11-18)
`Pcb_Controller/BekantX.kicad_pcb`: 145 Bauteile + 6 Bohrungen, 129 × 38 mm mit USB-Nase, 6 Lagen (seit 2026-11-21, vorher 4). Das Board wird von Skripten erzeugt (siehe [[Toolchain]]), nicht von Hand gezeichnet.

- **Lagen** (seit 2026-11-21 sechs, 1.6 mm, ASSUMPTION Aufbau nach JLCPCB JLC06161H-2116, siehe [[Offene Punkte]]): F.Cu Signale **senkrecht** (Tasten, OLED-Stecker J3, LEDs D1/D5) / In1 `+3V3`-Plane und VCC-Fläche (keine Signale) / In2 Signale **waagrecht** / In3 Signale **senkrecht** / In4 GND-Plane (direkt unter B.Cu) / B.Cu Signale **waagrecht** (alle übrigen Teile, Pad-Ausfahrten, Speisungsbahnen). Eine Richtung je Lage (Nutzer), damit die GND-Flächen aussen zusammenhängen: F.Cu jetzt 1 Fläche (vorher 25 Stücke), B.Cu 6 (vorher 22). Teardrops an Vias auf allen Lagen.
- **Bestückung**: Vorderseite nur, was das Gehäuse dort verlangt (22 Footprints inkl. Bohrungen); Rückseite alles andere, höchstes Teil 6.3 mm (Elkos) bei 7.0 mm Grenze.
- **Netzklassen** (`BekantX.kicad_pro`): Default 0.15/0.15 mm, Via 0.5/0.3; `+3.3VA`/`VCC_SPI` 0.3; `+12V`/`VBUS` 0.4; Hochvolt (`VDESK`, `VIN`, `VCC`, Schaltknoten, bis 53 V an der TVS) 0.5 mm mit 0.3 mm Abstand; LIN 0.3/0.3; USB 0.25/0.15 (Full Speed); GND/`+3V3` 0.15 mm Abstand; HF 0.35 mm.
- **Planes**: jedes SMD-Pad an GND und `+3V3` hat ein eigenes Via, die Exposed Pads von U1/U2 je 3 × 3 Vias. Beide Innenlagen tragen keine Leiterbahn.
- **VCC-Fläche auf In1** (PR-Feedback 2026-11-18): rechter Teil von In1 (ca. x 80.5–121, y 7–33, Polygon in `tools/pcb/bekantx_power_planes.py`) ist VCC (Priorität über der `+3V3`-Plane). Alle 17 VCC-Pads haben ein Via hinein (die grossen zwei), die VCC-Leitungen auf B.Cu sind bis auf die zwei kurzen Eingangsleitungen an U20 und U9 weg (104 → 60 mm, der Rest sind Stummel vom Pad zum Via, bei den Elkos grösstenteils im Pad). Die `+3V3`-Plane fliesst oben und rechts um die VCC-Fläche herum und bleibt ein Stück; eine 2.2 mm breite `+3V3`-Zunge reicht zum Via der Front-LED D5 (ihr Pad ist auf F.Cu von zwei Kathodenleitungen eingeschlossen). VIN (vor D4) bleibt eine Leitung. Die Kanten der VCC-Fläche halten mindestens 1 mm Abstand zur parallelen F.Cu-Leitung `USBST_D_N` (kreuzt die Trennung nur rechtwinklig), `USBESP_D_P` läuft 9 mm über der VCC-Fläche mit 0.75 mm zur Kante (> 3 × 0.21 mm Abstand F.Cu–In1). Testpunkt **TP10 (VCC) verschoben** von (113.25, 28.75) nach (115.25, 16.50) in die VCC-Fläche: an der alten Stelle brauchte er eine Ausbuchtung, die die USB-Leitung kreuzte.
- **Leitungsführung** (PR-Feedback): Treppen aus Rasterstücken zu geraden Strecken geglättet (50 Ketten, 555 → 185 Segmente), Pad-Einführungen gerade: Fine-Pitch-Pads entlang der Längsachse bis 0.25 mm hinter die Spitze, andere achsparallel; 19 Vias, deren Ring ins eigene Pad reichte, nach aussen geschoben; 82 Leitungen auf Netzklassenbreite verbreitert, 59 doppelte Segmente entfernt. Danach alle Segmente auf 0/45/90°: 183 schräge Segmente → 11 (18 Stummel-Vias auf den Strahl geschoben, 154 Knicke/Z-Formen), 9 kleine Versätze entfernt. Übrig: 38 schräge Pad-Einführungen (absichtlich nach innen bei J3, Vias unter U8; Eckpins der QFNs; 45°-Abgänge an den RC-Gliedern der Tasten), 11 schräge Segmente (eingeklemmt) und 42 Versätze von 0.02–0.4 mm, die meisten 0.05 mm in den B.Cu-Bussen bei x 50–53 / y 24–27 (zum Entfernen müssten ganze Busse verschoben werden).
- **Blöcke**: ESP32-C3 links (zwischen den Pin-Reihen von SW3/SW4), Chip-Antenne in der Ecke x 0–6.5 / y 31.5–38 mit kupferfreier Zone auf allen Lagen und Masse-Vias am Rand, Anpassnetz C8/L2/C9 an der Antenne, 50-Ω-Leitung 9 mm. STM32 in der Mitte mit 3 mm freiem Ring. Tischstecker J10 abgewinkelt, Stifte und Kabelgehäuse liegen über der Platine (Sperrfläche); Sicherung, TVS und C28 direkt am VDESK-Stift. 12-V- und 3.3-V-Regler rechts davon, vier Eingangs-Elkos entlang der Vorderkante, USB ganz rechts.
- **Regler (nach dem Review)**: U20 (12 V) als kompakte Zelle: C25 direkt über VIN, C26 zwischen CB und SW (Boot-Leitung 2.0 mm, vorher 21.7 mm mit 6 Vias), D20 direkt am SW-Pin, L20 daneben; Schaltknoten 9.6 mm ohne Via (vorher 22.4 mm mit 2 Vias). U9 (3.3 V): C15 links neben U9 mit direkter VIN-Leitung über Pin 4 auf den Zulauf von Pin 5 (ca. 5 mm, vorher ca. 11 mm), GND-Vias von C15 und Pin 2 2.4 mm auseinander; R41/R42 direkt am FB-Pin (`U9_FB` 4.3 mm, vorher 15.4 mm). Näher geht es beim SOT-23-6 nicht: VIN und GND sind die Mittelpins gegenüberliegender Reihen, SHDN und FB liegen auf der Seite von C15 dazwischen. C7 liegt jetzt ca. 2 mm vor den VDD3P3-Pins des ESP32-C3.
- **USB-C J1** (PR-Feedback, 4. Punkt: „VBUS in eine andere Lage, damit D+/D− direkt geführt werden können“): VBUS läuft in der Nähe des Steckers auf **F.Cu** (0.4-mm-Schiene bei x 125.3 von Via zu Via an den beiden VBUS-Padgruppen, Abzweige zu U4 Pin 5 und zu C35; 4 Vias 0.5/0.3), auf B.Cu nur noch die kurzen Stummel. D+ und D− laufen auf B.Cu gerade von B6/B7 zu U4 Pin 6/4 und treten mittig ins Pad ein (45°-Versatz 0.25 mm davor). A7–B7 (D−) sind vor den Pad-Enden verbunden (x 125.5), A6–B6 (D+) hinter den Pad-Enden (x 127.65), so dass sich nichts kreuzt. CC1/CC2 gehen als gerade L-Stücke zu R13/R12. Vorher: D+ 25 mm Schleife um den Stecker, D− mit zwei Vias auf F.Cu, CC1/CC2 mit F.Cu-Sprüngen (58 Leitungen/Vias entfernt). Skript `tools/pcb/bekantx_usb_rework.py`.
- **Layout-Regeln des Nutzers (2026-11-19)**, umgesetzt mit Skripten (Reihenfolge in [[Toolchain]]):
  - Keine Ecke mit 90° oder spitzer: 101 freie 90°-Ecken gefast (45°-Fase 0.06–1.0 mm, wo eine Ecke direkt am Pad lag, beginnt die Fase im Pad), 3 Knäuel aus 0.05-mm-Stücken von Hand bereinigt. Übrig sind nur Knicke, die ganz unter einem Pad oder Via liegen.
  - Leiterbahnen mindestens 5 mil (0.127 mm): die schmalste ist 0.15 mm (Regel `min_track_width` 0.15 mm, strenger als verlangt).
  - Speisungsleitungen über einer Plane kurz: jedes VCC-/`+3V3`-/GND-Pad hat einen geraden Stummel zu einem eigenen Plane-Via; lange Speisungsbahnen auf den Aussenlagen entfernt (VCC 59.5 → 31.3 mm, `+3V3` 73.6 → 64.0 mm, GND 110.8 → 93.5 mm), 34 neue Plane-Vias. Bewusst direkt verbunden bleiben die Eingangsschleifen C15–U9.5 und C25–U20.5.
  - GND-Fläche auf B.Cu weniger zerstückelt: Flächenabstand 0.3 → 0.2 mm (Netzklassen-Abstand gilt weiter, wo er grösser ist), fünf lange B.Cu-Züge (`FSPI_NCS`, `BTN_1`, `LIN_RX`, `BTN_5`, `DISP_RES`) mit der langen Strecke auf F.Cu neu verlegt, jedes Flächenstück ab 1.5 mm² mit eigenem Stitching-Via. B.Cu: 31 → 23 Stücke, Hauptstück 2393 → 2683 mm². Preis: die F.Cu-Fläche hat jetzt 25 statt 15 Stücke (Hauptstück 3552 → 3140 mm²). `U0RXD`, `U0TXD`, `FSPI_CLK`, `FSPI_MISO`, `BTN_2` liessen sich am Westrand von U1 nicht neu verlegen (zu eng) und bilden weiter das 228-mm²-Stück unten links.
  - Ecken gerundet: 2.5 mm aussen, 0.5 mm an der USB-Nase (aussen und innen); Parameter `pcb_corner_r`, `pcb_tab_corner_r` im Gehäuse-Skript, von dort in `CAD/board_interface.json`.
  - Bestückungsdruck: Referenzen auf Silk (138 von 145 platziert, 1.0 mm hoch, 13 mit 0.8 mm, Strich 0.15 mm), Funktionslabels (Testpunkte mit Signalname, USB-C, SWD, OLED, RST, BOOT, USB SEL, DESK), Titelblock vorne links mit QR-Code zum Repository, Tisch-Logo, Name, Revision, Credits (1.0 mm), sowie `JLCJLCJLCJLC` auf B.Cu für die JLC-Auftragsnummer. Keinen Platz gefunden haben C15, C49, C16, R22, R27, R36 und das Label von TP9 (bleiben auf Fab).
- **Zahlen**: 1296 Leiterbahnsegmente (F.Cu 1.15 m, B.Cu 1.27 m), 459 Vias (0.5/0.3 und 0.6/0.3). Jede Innenlagen-Fläche (VCC, `+3V3`, GND) ist ein zusammenhängendes Stück. DRC mit Schaltplan-Parität: 0 Fehler, 0 offene Verbindungen, 0 Paritätsfehler, 2 Warnungen (Bestückungsdruck des J1-Footprints an der Platinenkante). ERC unverändert 0 Fehler / 28 alte Warnungen.
- **Gehäuse**: `CAD/BekantX_PCB.step` (Ursprung = Platinenecke), Passprüfung `CAD/src/check_board_fit.py` gegen Rev. 3: 0 mm³ Überschneidung mit Gehäuse, Deckel, Tastenmatte und OLED-Glas, Einbauweg (absenken, einschieben) frei. Für J1, SW2, D1, D5 und AE1 gibt es keine Bibliotheks-3D-Modelle; sie haben Hüllkörper aus `CAD/src/make_pcb_models.py` (`Pcb_Controller/3d/`).
- **Nicht geprüft**: Signalintegrität, EMV, Erwärmung, HF-Anpassung (Antenne muss am Prototyp abgestimmt werden), reale Fertigungsregeln beim Bestellen. USB ist Full Speed und nicht als gekoppeltes Paar geführt (Längen: ESP 103/106 mm, STM 60/70 mm). Bezeichner stehen auf den Fab-Lagen, nicht im Bestückungsdruck (zu dicht).
- Offene Punkte und Review-Befunde: [[Offene Punkte]].

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
Frühere Bedienplatine (AS1115 + HDSP-433G, 6 Tasten über Key-Scan, EEPROM). Tasten und EEPROM sind in `Pcb_Controller` übernommen, 7-Segment und AS1115 entfallen. Am 2026-11-19 auf Wunsch des Nutzers aus dem Repo entfernt; der letzte Stand liegt im Git-Tag `archive/pre-cleanup`.

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
**Rev. 3 (2026-11-14, Branch `cad/enclosure-single-pcb`):** parametrisch in build123d, Quelle `CAD/src/bekantx_enclosure.py` (alle Masse im Block `Params`). Exporte: `CAD/BekantX_Case_r3`, `BekantX_Lid_r3`, `BekantX_Keypad_r3` (je STEP + STL). Rev. 3 ersetzt Rev. 2 und ist die Stil-Referenz. Die alten `BekantX_Case.stl` / `BekantX_Lid.stl` sind seit 2026-11-19 nur noch im Git-Tag `archive/pre-cleanup`.

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
