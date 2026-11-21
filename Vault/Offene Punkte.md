# Offene Punkte

## Inkonsistenzen in den Docs
- [ ] SPI: `inter-controller-protocol.md` (kein IRQ, Frame `0xA5…`) vs. `APPLICATION_PLAN.md` (IRQ-GPIO, anderer Header). Eine kanonische Quelle festlegen → Spec gewinnt, Plan anpassen? Oder IRQ nachrüsten (Sleep-Wake braucht ohnehin Wake-Pin).
- [ ] `architecture.md` nennt HA-Modell (MQTT/native/custom) als offen, Code nutzt MQTT.
- [x] Firmware-`README.md` ersetzt (2026-11-19), war das FTM-Beispiel.
- [ ] Ordnername `Bekanntx` (doppeltes n) in `Firmware/ST/`.

## Hardware
- [x] Ein-PCB-Layout: Umriss, Montage, UI-Positionen aus dem Gehäuse abgeleitet (2026-11-13, `CAD/board_interface.json`), siehe [[Entscheid - Ein PCB]]
- [x] Gehäuse parametrisch neu aufgebaut (Rev. 2, 2026-11-13); offen ist der Probedruck, siehe unten
- [x] ERC-Befunde des Controller-Schaltplans gesichtet (2026-11-13): auf main 43 Meldungen (8 Fehler), im Branch 28 Warnungen und 0 Fehler; 26 davon sind alte Draht-Stummel (< 0.2 mm) an Labels. Das HMI-PCB ist abgelöst.
- [x] Freerouting eingerichtet (Pipeline `tools/pcb/autoroute.py`, siehe [[Toolchain]]); offen: Profil an das Ein-PCB-Layout anpassen und die Netzklassen-Regeln im `.kicad_pro` definieren
- [x] Controller-PCB: Layout Rev. 1 fertig (2026-11-15), siehe unten
- [ ] Pinbelegung final + SPI-Taktlimit validieren
- [ ] LIN-PHY/Pegelanpassung zum Tisch klären
- [x] Gehäuse: CAD-Quelle liegt in `CAD/src/`; Passung zum echten Board folgt nach dem Layout

## Schaltplan (Stand 2026-11-13, Branch `pcb/merge-hmi-oled`)
Erledigt: HMI integriert, eine Rail `+3V3`, LPUART gekreuzt, CS_N-Pull-up, `FSPI_INT` verdrahtet, Schutz am Tisch-Eingang, neues 3.3-V-Netzteil, adressierbare Status-LED am ESP, Boot-Taster, NRST-Kondensator, Footprints und MPNs. ERC: 0 Fehler, 28 Warnungen (26 alte Draht-Stummel, `SWO`, 1 Lib-Hinweis).
- [x] OLED verdrahtet (J3, Pin-Tabelle aus `Docs/ER-OLED1.29-2_Datasheet.pdf`, Beschaltung nach `Docs/CH1115.pdf`).
- [ ] **OLED-Speisung**: interne Ladungspumpe aus VDD2 = 3.3 V. Der CH1115 erlaubt 3.0–4.75 V (7.4-V-Modus ab 3.0 V), das Panel-Datenblatt nennt VDD2 3.6–4.5 V und VPP 9.5–10.5 V. Folge: geringere Helligkeit; am Prototyp prüfen. Ausweg: VPP extern (ca. 10 V aus der 12-V-Rail), dann C1/C2-Pins und VDD2 offen.
- [ ] **OLED-Stecker**: gezeichnet ist Hirose FH12-16S-0.5SH(55) (0.5 mm, Kontakte unten) mit KiCad-Footprint. Der EastRising-Stecker ER-CON16HB-1 hat ein eigenes Landmuster. Pin-1-Seite und Lage des FPC (Kontakte unten) im Layout prüfen, sonst ist die Belegung gespiegelt.
- [ ] IREF-Widerstand R44 = 309k nach Referenzschaltung ("about 310k"); Helligkeit/Strom am Prototyp einstellen (auch per Kommando 82h intern wählbar).
- [ ] `.ioc` in CubeMX öffnen und die von Hand geänderten Einträge prüfen: SPI2 (TX-only Master), GPIO-Labels, SPI1 als **Slave** mit Hardware-NSS.
- [ ] **ESP-Firmware anpassen**: `LED_GPIO` steht in `Application.cpp` fest auf 10; auf der Platine ist GPIO10 = `FSPI_NCS`, die LED hängt an **GPIO8** (`LED_DIN`). Pin als Kconfig-Option führen.
- [ ] **ASSUMPTION Tisch-Schnittstelle**: J10 (3-Pin-Stiftleiste VDESK/GND/LIN, kein MPN), Eingangsspannung, LIN-Pegel und `VSUP` = +12 V sind nicht am Tisch gemessen. Die Schutzbeschaltung ist für bis 33 V Dauerspannung ausgelegt (TVS SMBJ33CA).
- [ ] PESD1LIN (D7): Ausrichtung (Pin 2 an LIN) aus der Pin-Tabelle abgeleitet, das Applikationsbild im Datenblatt konnte nicht abgerufen werden.
- [ ] Status-LED SK6812MINI (D1) läuft an 3.3 V, das Datenblatt nennt je nach Ausgabe 3.5 bzw. 3.7 V als Minimum (Review: 3.5–5.5 V, VIH 3.4 V). Am Prototyp prüfen oder Typ mit 3.3-V-Freigabe wählen.
- [ ] USB-Speisung: nach D3 liegen ca. 4.5 V am LMR51610 (UVLO steigend max. 4.0 V). Bei schwachem VBUS knapp; am Prototyp prüfen.
- [ ] Antenne AE1: Johanson 2450AT18A100 angenommen (Pin 1 Feed, Pin 2 unbeschaltet). Anpassnetzwerk C8/L2/C9 und Keep-out nach Datenblatt im Layout festlegen und abstimmen.
- [ ] MPNs der Standard-Passiven (Yageo RC, Samsung CL, Murata, TDK) folgen der Serien-Nomenklatur und sind **nicht einzeln** gegen Datenblatt und Lager geprüft. Geprüft sind LMR51610 (Datenblatt in `Docs/datasheets/`), 0468001.NR, EEE-FK1J101P.
- [ ] Ohne MPN: Y1 (40-MHz-Quarz 3225, CL passend zu C10/C11 wählen), D5 (RGB-LED am STM32, auch ohne Footprint; Vorwiderstände jetzt 91R/24R), J10, J2 (nur Footprint).
- [ ] Tasten SW3–SW8: Omron B3F-1000 (THT 6 mm) gesetzt; Gehäuse Rev. 3 rechnet mit 4.3 mm Höhe und der gedruckten Tastenmatte, am Probedruck prüfen.
- [ ] ESP-Link: Serienwiderstand nur auf SCK (R3); ESP32-C3 ohne internes Flash + W25Q32 (Alternative ESP32-C3FH4 spart U3).
- [ ] **Review-Befunde (schematic-reviewer, 2026-11-13, Stand vor dem Display; Urteil: PASS WITH NOTES, 5 Major):**
  - [x] Behoben mit R45 (10k an +3V3); Firmware muss PB6 beim Init hoch setzen. Befund: `LIN_TX` ohne Pull-up: TLIN1027 hat keinen Dominant-Timeout, TXD hat internen Pull-down. Im Reset des STM32 bleibt der Bus dominant. Pull-up ca. 10k an +3V3, PB6 beim Init hoch (bestand schon auf main, sicherheitsrelevant).
  - [ ] SK6812MINI an 3.3 V ausserhalb der Spezifikation (siehe oben).
  - [x] Behoben (`.ioc`: PB5 Open-Drain, Startpegel high; in CubeMX noch nicht geöffnet). Befund: PB5 (`FSPI_INT`) war Push-Pull/low. GPIO9 low beim ESP-Reset = Download-Modus, und SW9 wirkt gegen Push-Pull-high nicht. Auf Open-Drain oder hochohmig stellen.
  - [ ] Firmware: `LED_GPIO` = 10 in `Application.cpp` (eigener Firmware-PR). Erledigt: Hardware-Hinweis zu `FSPI_INT` in `Docs/inter-controller-protocol.md`.
  - [x] Behoben: Netze heissen jetzt `FSPI_MISO` (PA6 ↔ GPIO2/FSPIQ) und `FSPI_MOSI` (PA7 ↔ GPIO7/FSPID) und sind entsprechend verdrahtet. Befund: ESP-IOMUX: `FSPI_DI` (STM MISO) liegt auf GPIO7 (Default MOSI), `FSPI_DO` auf GPIO2 (Default MISO). Geht nur über die GPIO-Matrix; in Kconfig/Protokoll dokumentieren, Netze umbenennen (schon auf main so).
  - [x] U9: C49 (100 nF 100 V) an VIN ergänzt; L4/L20 SRN6045TA-220M: Isat 3.3 A, Irms 2.3 A (Distributor-Angabe) gegen max. 1.95 A Stromgrenze.
  - [ ] USB-only: +12 V regelt nicht, J10 dann nicht an den Tisch; C40 (100 µF) über dem USB-Einschaltstrom-Limit.
  - [ ] TVS SMBJ33CA: spricht an, falls die Tischspannung bei ca. 33 V oder höher liegt; J10-Pinout auf dem Blatt als ASSUMPTION markieren.
  - [x] Kleineres behoben: Felder U5/C28/SW3–SW8, C12 an CHIP_EN auf 1 µF (ca. 5 ms), `.ioc` mit Pull-ups für BTN_x, BOM-Export mit Menge/DNP, ASSUMPTION-Text an J10.
- [x] Zweiter Review (Display und Korrekturen, 2026-11-13): PASS WITH NOTES, keine Blocker; alle 16 J3-Pins stimmen mit der Pin-Tabelle überein, die Korrekturen sind in der Netzliste bestätigt.
  - [ ] **Major: FPC-Stecker physisch ungeprüft.** Kein Hirose-FH12-Datenblatt in `Docs/` (Kontaktseite, FPC-Dicke 0.3 mm, Landmuster). Liegt Pin 1 auf der falschen Seite, ist die Belegung gespiegelt und VDD1/VDD2 treffen auf Signalpins. Entweder ER-CON16HB-1 mit eigenem Footprint oder FH12 gegen die Hirose-Zeichnung prüfen; Footprint 1:1 drucken und mit dem echten FPC probestecken.
  - [x] `DISP_RES` (PA9): Pull-down R46 (10k) ergänzt, das Display bleibt im Reset, bis die Firmware den Pin hoch setzt.
  - [ ] PA9/PA10 (UCPD-Dead-Battery): im Referenzhandbuch prüfen und in der Firmware abschalten.
  - [ ] VDD1 und VDD2 hängen gemeinsam an `+3V3`: C43/C44 direkt an J3 platzieren; optional 0R/Ferrit zum Trennen von VDD2 (für externes VPP).
  - [ ] VPP 7.4 V statt 9.5–10.5 V: geringere Helligkeit und Lebensdauer; C47/C48 (X5R) verlieren unter Gleichspannung Kapazität, Welligkeit am Prototyp messen.
  - [ ] SPI2-Takt fürs Display konservativ wählen (CH1115: ca. 4 MHz oder weniger, Tabelle im Datenblatt nachlesen).
  - [ ] Für den Review fehlen in `Docs/`: ESP32-C3-Datenblatt, STM32G0B1-Datenblatt/Referenzhandbuch, Hirose FH12.

## PCB-Layout Controller Rev. 1 (Stand 2026-11-18, Branch `pcb/layout-4layer`)
Fertig geroutet, siehe [[Hardware]] (Abschnitt Layout) und [[Toolchain]] (Pipeline, Erkenntnisse). DRC mit Schaltplan-Parität: 0 Fehler, 0 offen, 0 Paritätsfehler, 2 Warnungen (Bestückungsdruck von J1 an der Platinenkante, harmlos; Entfernen würde J1 von der Bibliothek abweichen lassen). Passprüfung gegen Gehäuse Rev. 3 bestanden.
- [x] Schaltplan angepasst: C40 → C40/C50–C52 (4 × 22 µF / 63 V), D5 = Cree CLVBA-FKA, J10 abgewinkelt, Testpunkte nicht in der Stückliste. ERC unverändert (0 Fehler, 28 alte Warnungen).
- [x] Layout: 0 offene Verbindungen (Stand 2026-11-15 mit Handkorrekturen aus `tools/pcb/bekantx_manual.json`).
- [x] Board-STEP `CAD/BekantX_PCB.step` und Passprüfung (`CAD/src/check_board_fit.py`): 0 mm³ Überschneidung, Einbauweg frei.
- [x] **Review `pcb-reviewer` 2026-11-15: PASS WITH NOTES**, kein Blocker, 3 Major. Behoben 2026-11-18 mit `tools/pcb/bekantx_rework.py` (lokaler Umbau auf dem committeten Stand, Rest des Routings unverändert):
  - [x] Major 1/2: Boot- und Schaltschleife von U20 zu gross (C26 22 mm mit 6 Vias, D20/C25 8–10 mm vom IC) → kompakte Zelle, siehe [[Hardware]].
  - [x] Major 3: C15 ca. 11 mm Leiterbahn vom VIN-Pin von U9 → direkte Leitung, ca. 5 mm. Direkt am Pin geht beim SOT-23-6 nicht (siehe [[Hardware]]).
  - [x] Minor 5: `U9_FB` 15 mm → 4.3 mm, R41/R42 am FB-Pin. Minor 3: C7 an die VDD3P3-Pins. Minor 1: Via im VIN-Pad von U20 entfernt; der Nachrouter setzt keine Vias mehr in SMD-Pads.
  - [x] Minor 6 (53-V-Abstand 0.3 mm, Review verlangte 0.6 mm): **nicht geändert**. IPC-2221B Spalte B4 (Aussenlage mit dauerhafter Polymerbeschichtung = Lötstopplack) nennt 0.13 mm für 31–100 V; 0.6 mm ist die Spalte B2 ohne Beschichtung. Wert aus Sekundärquellen, die Norm selbst lag nicht vor.
  - [x] Minor 7 (Via-Restring 0.1 mm): **nicht geändert**. JLCPCB nennt für Vias Durchmesser = Bohrung + 0.15 mm (0.075 mm Restring); 0.13 mm gilt für Bauteil-Durchkontaktierungen. Beim Bestellen im DFM-Check bestätigen.
  - [ ] Minor 2 (Quarz Y1: XTAL_P 11 mm mit Lagenwechsel, R1 6 mm vom Pin) und Minor 4 (HF-Anpassnetz 9 mm vom Pin, Breite nicht berechnet): offen, am Prototyp beurteilen.
  - [ ] Minor 1 Rest: je 3 × 3 Vias in den Exposed Pads von U1/U2 (gewollt). Beim Bestellen abgedeckt oder gefüllt angeben, sonst fliesst Lot in die Vias.
- [x] **Nachprüfung `pcb-reviewer` 2026-11-18: PASS WITH NOTES**, alle drei Major behoben, kein neuer Major; IPC-B4- und JLC-Via-Begründung akzeptiert. Neue Minor:
  - [ ] Eingangsschleife U9 (VIN → C15 → GND) ist mit dem Weg durch die Plane noch ca. 9 mm (vorher ca. 20 mm). Optional: zweites GND-Via an C15 näher bei Pin 2.
  - [ ] Ca. 41 mm überflüssige `+3V3`-Leitungen (vor allem 11 mm auf F.Cu von (103.2, 21.4) nach (92.0, 20.0)), die der Nachrouter zwischen Plane-Vias gelegt hat. Elektrisch harmlos (parallel zur In1-Plane); bei Gelegenheit entfernen und jedem `+3V3`-Pad ein eigenes Via geben.
  - [ ] Ein Via am Pad 2 von D70 (61.8, 16.35, `+12V`) laut Reviewer; mit den Wärme-Vias zusammen abgedeckt bestellen oder verschieben.
- [x] **PR-Feedback #5 (Nutzer, 2026-11-18)**: (1) VCC als Fläche auf einer Innenlage statt Leitungen auf B.Cu, (2) `+3V3` mit unnötigen Lagenwechseln, (3) Leitungen gerade und gerade ins Pad. Umgesetzt mit `tools/pcb/bekantx_power_planes.py`, `touchup_router.py --plane-nets`, `tools/pcb/straighten_pads.py`, siehe [[Hardware]].
  - [x] 4. Punkt des Nutzers (2026-11-18, Bild von J1): VBUS auf F.Cu, D+/D−/CC ohne Umweg auf B.Cu, siehe [[Hardware]]. DRC 0 Fehler / 0 offen / Parität 0, Passprüfung bestanden.
  - [ ] F.Cu-Signale, die auf In1 über die Grenze VCC/`+3V3` laufen, verlieren dort ihre durchgehende Bezugsfläche (In2 GND liegt 1.3 mm tiefer). Für die langsamen Signale unkritisch; USB-Leitungen am Prototyp beobachten. Abstände parallel zur Kante: `USBST_D_N` ≥ 1.0 mm, `USBESP_D_P` 0.75 mm, `LED_DIN` 0.6 mm.
  - [ ] 38 Pad-Einführungen bleiben schräg (Liste im Ausgabeprotokoll von `straighten_pads.py`); gewollt bei J1/J3/U8 und den QFN-Eckpins, 45° an den Tasten-RC-Gliedern.
  - [ ] **Review der zweiten Runde (pcb-reviewer, 2026-11-18): PASS WITH NOTES**, noch offen (Koordinaten Platine-lokal):
    - [ ] Major: F.Cu-Signale über der VCC-Fläche (Bezug VCC statt GND/`+3V3`): `USBST_D_N` ca. 20 mm (x 84–104.6, y 20–22), `USBESP_D_P` ca. 70 %, `LED_DIN` kreuzt die Trennung zweimal (x 80.5 und 95.5 bei y 24.15). Optionen: Paare auf B.Cu (In2 GND als Bezug), VCC-Fläche verkleinern (Arm x 80.5–86.5 / y 24–33.3), oder 100-nF-Stitching-Kondensatoren VCC–`+3V3` an den Kreuzungen (Schaltplanänderung). Entscheid offen.
    - [ ] Major: schräge Reste. VCC-Knoten C15/D4/U9 bei (97.25, 21.7) mit Keil zum Via (98.81, 20.96); BTN_6 bei R37 (70.38, 32.21) schmaler Schlitz zum Via (69.8, 29.4), Via auf (70.38, 29.4) setzen; BTN_6 an U1.3 (57.25–57.4, 30.5–30.8); +12V-Mikrostücke bei (61.6, 15.9–16.35) mit spitzem Knoten; FSPI_MISO an U2.6 (12.9–13.55, 21.45–21.55); Net-(SW2-B) Via (112.15, 29.4) auf die Achse von U8.1 (x 113.15); USBESP_D_P F.Cu (29.1, 29.25)–(49.2, 29.7) 1.3° schräg.
    - [ ] Minor: VCC-Vias am Flächenrand (80.53, 30.05), (92.15, 26.19), (95.6, 7.15): Kante 0.6–1 mm nach aussen oder Vias nach innen.
    - [ ] Minor: zweites VCC-Via an U9 Pin 5 (bei 99.2, 21.62).
    - [ ] Minor: SWDIO-Stummel 0.3 mm hinter dem Via (58.67, 24.35) löschen.
    - [ ] Minor: 0.3/0.35-mm-Leitungen auf 0.25-mm-QFN-Pads (U1 Pin 4/5, U2 Pin 1, 3, 11, 17, 18, 31, 32) auf 0.2 mm einschnüren; Verbreiterungsschritt in `straighten_pads.py` soll Fine-Pitch-Pads auslassen.
    - [ ] Minor: Vias 0.16 mm neben J3-Pads (OLED_C2P, OLED_VPP), DISP_SCK 0.21 mm: Lötstopp-Steg gegen Fertigungsminimum prüfen.
  - [ ] 11 Segmente nicht auf 0/45/90° und 42 kleine Versätze (meist 0.05 mm in den B.Cu-Bussen bei x 50–53 / y 24–27). Kosmetisch, DRC sauber; zum Entfernen Busse als Ganzes verschieben.
  - [ ] D1 (Front-LED, `+3V3`) ist über 5 mm F.Cu an ein Via ausserhalb der VCC-Fläche angebunden (direkt darunter liegen die Pins von U9).
- [x] Netzklassen GND/`+3V3` und USB auf 0.15 mm Abstand gesenkt (vorher 0.2). Für USB Full Speed und die Plane-Netze unkritisch; nötig für die Ausfahrten neben Entkoppel-Pads.
- [ ] **Schaltplan-Review nachholen** für die drei Änderungen am Schaltplan (C40-Aufteilung, D5, J10); sie sind bisher nur über ERC, Netzliste und Parität geprüft.
- [ ] **ASSUMPTION USB-C J1** (HRO TYPE-C-31-M-12): Lage der Buchse zur Platinenkante (Gehäusefront 1.5 mm vor dem Ende der Nase) und die Gehäusemasse 8.94 × 7.3 × 3.26 mm stammen aus dem KiCad-Footprint und den Gehäuseparametern, nicht aus dem Datenblatt (nicht abrufbar). Die hinteren Schirm-Pads haben nur 0.3 mm bis zur Kante. Vor der Bestellung gegen das Datenblatt prüfen.
- [ ] **ASSUMPTION OLED-FPC**: Pin 1 liegt auf der Platine bei y = 20.25 (Pin 16 bei 12.75), der Stecker öffnet nach +x, Kontakte unten. Abgeleitet aus der Zeichnung im OLED-Datenblatt (Ansicht von vorn, FPC nach rechts, Pin 1 unten; nach dem Falten zeigen die Kontakte zur Platine). Das Hirose-Datenblatt (Landmuster, FPC-Dicke 0.3 mm) war nicht abrufbar. Der 22-mm-Schwanz reicht gefaltet bis etwa x = 47; der Stecker sitzt bei x = 50. Footprint 1:1 drucken und mit dem echten Display probestecken. Die Anzeige steht für den Betrachter auf dem Kopf (FPC nach links): in der Firmware drehen (CH1115 Segment-Remap/COM-Scan).
- [ ] **Antenne**: Sperrfläche 6.5 × 6.5 mm und Lage nach dem Referenzboard im Johanson-Datenblatt (Rev. 4.0), Anpassnetz C8/L2/C9 mit den Schaltplanwerten. 50-Ω-Breite 0.35 mm ist eine Schätzung für 0.21 mm Prepreg; die GND-Flächen daneben senken die Impedanz zusätzlich. Muss am Prototyp abgestimmt werden (Johanson bietet Tuning an). Die Schraube bei (12.5, 33) sitzt 6 mm neben der Sperrfläche: Kunststoffschraube erwägen.
- [ ] **USB**: Full Speed, die Paare sind nicht gekoppelt und nicht impedanzkontrolliert geführt, Längenunterschied bis 10 mm (unkritisch bei 12 Mbit/s).
- [ ] Freigabe von U20: `Net-(U20-~{SHDN})` 29 mm mit 4 Vias (Gleichspannung, unkritisch).
- [ ] C40-Ersatz: Bauhöhe 6.5 mm max. stammt aus Distributor-Angaben, nicht aus dem Panasonic-Datenblatt.
- [ ] Bezeichner stehen nur auf den Fab-Lagen; für die Handbestückung einen Bestückungsplan (PDF je Seite) und ein interaktives BOM exportieren (Skill `fab-export`). Polaritätsmarken von D1/D5, D3/D4/D20 und der Elkos im Bestückungsplan prüfen.
- [ ] Keine Passermarken (für Handbestückung unnötig, für Bestückung beim Fertiger nachrüsten). Teardrops an Vias seit 2026-11-21 vorhanden.
- [ ] Lagenaufbau JLC04161H-7628 ist aus dem Gedächtnis eingetragen (0.2104 mm Prepreg, 1.065 mm Kern); beim Bestellen mit dem JLCPCB-Formular abgleichen.
- [ ] Reproduzierbarkeit: Der Stand ist «Pipeline 2026-11-15 + `bekantx_manual.json`» und darauf «`bekantx_rework.py` + Nachrouter». Ein neuer Gesamtlauf mit der Platzierung nach dem Review wurde 2026-11-18 versucht: 10 offen nach Freerouting, am USB-Mux U8 auch mit Handkorrekturen nicht sauber lösbar. Die Board-Datei ist das Ergebnis, die Skripte dokumentieren den Weg. `bekantx_manual.json` gehört zum Lauf vom 2026-11-15.
- [ ] `Pcb_Controller/3DxService.log` (3Dconnexion-Treiber) gehört in `.gitignore`.

## Gehäuse Rev. 3 (Stand 2026-11-14, Branch `cad/enclosure-single-pcb`)
Rev. 2 wurde gedruckt: der Deckel passte nicht (gefangen, wie vom Review vorhergesagt). Rev. 3 ersetzt Rev. 2, siehe [[Hardware]].
- [x] Blocker aus dem Review von Rev. 2 (Deckel gefangen) und die Überhänge im Arm: behoben durch Scharnier am Armende, Schnapper vorne und Wände entlang der Schwenkrichtung; Bewegungsweg im Skript nachgerechnet.
- [x] Minor aus dem Review von Rev. 2: Senkung Deckelschraube 4.8, Kabelbinder-Schlitze 3.2 mm, Sturz über dem Kabelfenster 1.6 mm, OLED-Fenster 0.3 mm kleiner als die Sichtfläche, Parameter `end_wall` entfernt.
- [x] Review `cad-reviewer` 2026-11-14: **PASS WITH NOTES**, kein Blocker für den Probedruck. Bestätigt an STEP/STL: 0 mm³ Überschneidung, Deckel lässt sich starr aufsetzen und abnehmen (frei ab 5°, Herausziehen 2.5 mm ab 6°), Überhänge über 45° von ca. 1000 auf 87 mm², alle Parameter ±10 % regenerieren. Nach dem Review geändert: Wand vor der USB-Nase 1.2 mm und 0.3 mm Luft beim Absenken, Kappen-Durchmesser 9.8 (0.4 mm Spiel), Deckel-Export liegt auf Z = 0.
  - [ ] Major: der Schnapper braucht ca. 0.3 mm elastische Stauchung des Deckels; ±0.15 mm Druckfehler machen ihn sehr lose oder zu stramm, Elefantenfuss an der Deckelnase erhöht die Überdeckung. Am Probedruck messen, dann `snap_compress` / `snap_gap` nachstellen. Geschlossen hat der Deckel 0.2 mm Spiel, die Schrauben halten ihn fest.
  - [ ] Minor: dünne tragende Stellen (Dach der Zungentaschen 1.15 mm, Wand hinter der Tasche 1.8 mm, Wand vor USB 1.2 mm); Taschenenden 55° Überhang auf 1 mm; Brücke über der USB-Öffnung 9.5 mm; Arme der Tastenmatte nur bei 0.2 mm Schichthöhe zwei Lagen; Schraubenlänge der Deckelschrauben nicht festgelegt; einzelne feste Zahlen im Skript; `lid_t` unter ca. 2.3 und `arm_angle` +10 % brauchen Nacharbeit am Schnapper bzw. Entnahmeweg.
- [x] Entscheid Bauhöhe (Nutzer, 2026-11-14): der Frontblock bleibt 19.5 mm hoch.
- [x] **C40 ersetzt** (2026-11-14: 4 × EEE-FK1J220P), Tischstecker J10 abgewinkelt.
- [x] **Probedruck Rev. 3** (2026-11-14, Nutzer, Bambu P1S, PLA): gedruckt, **passt**. Das ist die Aussage des Nutzers; Schnappkraft, Klick, Tastenmatte, USB-Passung und Schraubengriff wurden nicht einzeln protokolliert. Der PETG-Druck des Endteils steht noch aus (zäher: Schnapper und Kernloch dort prüfen).
- [ ] Major aus dem Review von Rev. 2, **weiter offen**: FPC des OLED nicht berücksichtigt (Faltung zwischen Glaskante und SW5, Stecker unter dem Glas); als Sperrflächen aufnehmen, Glas/Flansch verschieben.
- [x] Änderungen nach dem ersten Review von Rev. 3 (einheitliche Fasen, M2.5×6-Schrauben, Entlastung der Armwände, dünnere Frontwand, Symbole auf den Tasten): der zweite Review des `cad-reviewer` wurde **nicht abgeschlossen** (Agent vorzeitig gestoppt, kein Befund). Stattdessen gilt der Probedruck des Nutzers als Freigabe (PASS, Entscheid des Nutzers 2026-11-14); Prüfungen im Skript: 0 mm³ Überschneidung.
- [ ] **Schrauben M2.5×6 direkt in Kunststoff**: im PLA-Probedruck passend (Aussage des Nutzers). Kernloch 2.25 mm für PETG am Endteil bestätigen (Dom 5.5 mm, Wand 1.6 mm).
- [ ] **ASSUMPTION Tastenbelegung**: M1–M4 links, Hoch/Runter rechts der Anzeige; mit der Firmware (`BTN_1`…`BTN_6`) abgleichen.
- [ ] **ASSUMPTION USB-C**: Buchse HRO TYPE-C-31-M-12 (8.94 × 7.35 × 3.26 mm) und der Überstand von 1.5 mm über die Kante der Platinen-Nase sind nicht gegen Datenblatt und Footprint geprüft. Davon hängt ab, ob die Buchse wirklich bündig sitzt.
- [ ] **ASSUMPTION Tischkabel**: Durchmesser (5 mm) und Stecker sind nicht gemessen; Austritt 9 × 5 mm lässt ein 3-poliges 2.54-mm-Gehäuse durch.
- [ ] Taster B3F-1000 (Höhe 4.3 mm) gegen das Datenblatt prüfen; das Mass stammt nicht aus `Docs/`.
- [ ] OLED-Befestigung: Glas in der Tasche kleben (dünnes doppelseitiges Band) oder Schaumstoff zwischen Glas und Platine.
- [x] (2026-11-15 im Layout umgesetzt) Layout: `CAD/board_interface.json` (r3) übernehmen: Umriss 129 × 38 **mit USB-Nase**, 6 Bohrungen (vordere Reihe verschoben), Tasten, J3 unter dem Display, J1 auf B.Cu am Ende der Nase, D5/D1 unter den Lichtschächten, Sperrfläche Tastenmatte. Nichts darf an der +X-Kante über den Umriss ragen (Platine wird seitlich eingeschoben). D5 hat noch keinen Footprint.
- [x] Nach dem Layout: Board-STEP exportiert, Passprüfung gegen das echte Board bestanden (2026-11-15).
- [x] r2-Exporte (`CAD/BekantX_*_r2.*`) aus dem Repo entfernt (2026-11-14, nach dem passenden Druck von Rev. 3; bleiben in der Git-Historie).

## Firmware
- [ ] ESP: SPI-Slave-Transport + Protokoll, Lease-/Safety-Filter, Deep Sleep
- [ ] STM32: komplette Firmware (siehe [[Firmware STM32]])
- [ ] LIN-Captures am echten Tisch (Baudrate, Startup, Nodes 1/16/17)
- [ ] Kollisions-Schwellen, Positionsmodell (Rohwerte → 0.1 mm)
- [ ] OTA/Update-Pfad beider Controller
- [ ] MQTT: Auth/TLS-Konzept (NFR-008)

Zurück: [[00 Index]]
- [x] **Layout-Regeln des Nutzers (2026-11-19)**: keine 90°-Ecken, ≥ 5 mil, kurze Speisungsleitungen über Planes, B.Cu-GND weniger zerstückelt, runde Ecken, Bestückungsdruck mit Logo. Umgesetzt, siehe [[Hardware]]. DRC mit Parität 0 Fehler / 0 offen / 0 Parität, 2 bekannte Warnungen; Passprüfung bestanden.
  - [ ] F.Cu-GND-Fläche ist durch die Neuverlegung stärker geteilt (15 → 25 Stücke); jedes Stück ab 1.5 mm² hat ein Via. Prüfen, ob das so passt.
  - [ ] Weitere lange B.Cu-Züge (`U0RXD`, `U0TXD`, `FSPI_CLK`, `FSPI_MISO`, `BTN_2`) teilen B.Cu unten links weiter; neu verlegen ginge nur mit Umplatzieren um U1 oder mit Freerouting.
  - [ ] 7 Referenzen ohne Platz auf dem Silk (C15, C49, C16, R22, R27, R36, Label TP9); bei Bedarf von Hand setzen.
  - [ ] Credits im Titelblock nennen den GitHub-Namen (MootSeeker), nicht den vollen Namen; bei Wunsch ändern in `tools/pcb/bekantx_silk.py`.
  - [x] **Review `pcb-reviewer` 2026-11-19: PASS WITH NOTES**, kein Blocker. Behoben: 45°-Spitze bei `FSPI_MISO` an U2 (12.9, 21.45) samt zwei Null-Segmenten; Bohrloch des GND-Vias an U9 Pin 2 lag in der Lötstopp-Öffnung (Via 0.13 mm nach unten, ganz frei geht nicht: `USBESP_D_P` läuft darunter auf F.Cu); Titelblock-Zeilen auf 1.0 mm.
    - [ ] Minor: 12 Referenzen und kleine Labels mit 0.8 mm bei 0.15 mm Strich (JLC empfiehlt ca. 1 mm); bewusst so, sonst fehlen sie ganz.
    - [ ] Minor: ca. 60 Plane-Vias 0.1 mm neben SMD-Pads (gleiches Netz, Vias gedeckt/tented); beim Bestellen Tenting bestätigen. Thermal-Vias in den EPs von U1/U2 abgedeckt oder gefüllt bestellen (schon bekannt).
    - [ ] Hinweis: `BTN_5` läuft 11 mm auf F.Cu über der VCC-Fläche (Bezug VCC). Langsames Tastensignal mit RC, unkritisch; gehört zum offenen Punkt «F.Cu-Signale über der VCC-Fläche».
    - Nicht geprüft: Signalintegrität, EMV, ob der QR-Code scannt, Silk-Qualität in der echten Fertigung.
- [x] **Repo-Auftritt (2026-11-19, Branch `chore/github-presentation`)**: README mit Bildern, GitHub-Beschreibung und Topics, Lizenzen getrennt (siehe [[Entscheidungen]]), `Pcb_HMI/` und Original-STLs entfernt (Tag `archive/pre-cleanup`), `.vscode/` der Firmware nicht mehr versioniert (lokale Pfade, Ziel ESP32-S2), `.gitignore` um Obsidian-Workspace und venvs ergänzt.
  - [ ] Hersteller-Datenblätter in `Docs/` (PDF) sind fremdes Urheberrecht im öffentlichen Repo. Prüfen, ob sie bleiben dürfen, oder durch Links ersetzen.
- [x] **Layout-Politur (Nutzer, 2026-11-21, Branch `pcb/layout-polish`)**: Leiterbahnen gerade durch die Mitte von Pad/Via, nur waagrecht/senkrecht, weniger GND-Fläche, Teardrops an Vias. Umgesetzt mit `tools/pcb/layout_polish.py` (siehe [[Toolchain]]). DRC mit Parität 0 Fehler / 0 offen / 0 Parität, 2 bekannte Warnungen. Gemessen mit `layout_audit.py` (vorher → nachher): Einführungen, die die Mitte verfehlen 125 → 35; Segmente mit krummem Winkel 48 → 6; 45°-Stücke über 1 mm 166 → 97; 370 Teardrops. GND-Flächen bleiben ganzflächig (76 % / 62 % der Platine gefüllt, Hauptfläche 85 % / 87 % davon). Ein erster Versuch, die Flächen zu verkleinern, war ein Missverständnis und ist zurückgenommen.
  - [ ] **Noch schräg**: dichte Bündel an U1/U2 (QFN-Ausfahrten, Bündel nach unten links); dort fand der Router keinen Achsenweg, weil +3V3-Vias und Nachbarbahnen im Weg liegen. Pad-Austritt ist dort meist gerade, der Mittelteil bleibt 45°. Weiter ginge nur mit Verschieben der Plane-Vias oder einem neuen Lauf.
  - [ ] 35 Einführungen verfehlen die Mitte noch (23 Pads, 12 Vias), 23 laufen schräg durch die Mitte; 49 Vias ohne Teardrop (Bahn trifft die Via-Mitte nicht), 44 mit zu kurzem ersten Stück.
  - [ ] `USBST_D_P` (F.Cu, 36 mm) und `Net-(D5-BK)` (32 mm) laufen 0.4–0.5° schräg (Nachbarbahn zu nah für einen Versatz). Optisch gerade.
  - [ ] **GND-Flächen zerschnitten**: F.Cu 25 Teilflächen (24 Inseln, grösste 98 mm²), B.Cu 22 (21 Inseln, grösste 163 mm²); alle Inseln haben Stitching-Vias zu In2. Ursache der grössten Inseln: lange Bahnen, die zusammen mit anderem Kupfer eine geschlossene Schleife bilden. B.Cu 163 mm²: Bündel `U0RXD`/`U0TXD`/`FSPI_CLK` von U2 läuft unten herum (y ≈ 37) und wieder hoch (x ≈ 36); F.Cu: SPI-Bahnen `FSPI_NCS`, `/WiFi/SPI_*`, USB-Paare. Neu verlegen getestet (2026-11-21, `touchup_router.py --opencost` = neue Bahnen kleben am Kupfer, `plane_opt.py` = Netz für Netz neu verlegen, annehmen nur bei weniger Inselfläche, vollständig verbunden und DRC sauber): `U0RXD`, `U0TXD`, `FSPI_NCS`, `/WiFi/SPI_NCS`, `DISP_CS`, `USBST_D_P`, `BTN_4`, `BTN_5` lassen sich nicht neu verlegen (Kapazität am Westrand von U1, mehrere Netze gleichzeitig kippen hin und her). Nur `FSPI_CLK` allein schliesst die 163-mm²-Insel auf B.Cu, bringt aber eine neue 104-mm²-Insel auf F.Cu. Mit `USBST_D_N`/`USBESP_D_N` zusammen sinkt die Inselfläche von 946 auf 844 mm² (−11 %), dafür 85 Segmente mit krummem Winkel (A*-Pfade, der Begradiger schafft sie nicht), 1 offene Verbindung und USB-Datenleitungen auf neuen Wegen. **Nicht übernommen**; die Platine hat weiter den Stand vor dem Versuch. Geht nur mit Umplatzieren um U1/U2 oder neuem Routing (Freerouting) mit Zielfunktion «wenig Zerschneidung».
  - [ ] Teardrops sind Zonen im Dateitext (kein KiCad-Generator per Skript); in KiCad «Teardrops neu erzeugen» würde sie ersetzen, `teardrops.py` setzt sie nach jeder Bahnänderung neu.
  - [ ] `pcb-reviewer` für diese Politur noch nicht gelaufen (vor dem PR nachholen); Passprüfung Gehäuse nicht neu gelaufen (Umriss und Bauteile unverändert).
