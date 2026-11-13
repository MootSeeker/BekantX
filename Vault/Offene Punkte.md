# Offene Punkte

## Inkonsistenzen in den Docs
- [ ] SPI: `inter-controller-protocol.md` (kein IRQ, Frame `0xA5…`) vs. `APPLICATION_PLAN.md` (IRQ-GPIO, anderer Header). Eine kanonische Quelle festlegen → Spec gewinnt, Plan anpassen? Oder IRQ nachrüsten (Sleep-Wake braucht ohnehin Wake-Pin).
- [ ] `architecture.md` nennt HA-Modell (MQTT/native/custom) als offen, Code nutzt MQTT.
- [ ] Firmware-`README.md` ist noch das FTM-Beispiel.
- [ ] Ordnername `Bekanntx` (doppeltes n) in `Firmware/ST/`.

## Hardware
- [x] Ein-PCB-Layout: Umriss, Montage, UI-Positionen aus dem Gehäuse abgeleitet (2026-11-13, `CAD/board_interface.json`), siehe [[Entscheid - Ein PCB]]
- [x] Gehäuse parametrisch neu aufgebaut (Rev. 2, 2026-11-13); offen ist der Probedruck, siehe unten
- [x] ERC-Befunde des Controller-Schaltplans gesichtet (2026-11-13): auf main 43 Meldungen (8 Fehler), im Branch 28 Warnungen und 0 Fehler; 26 davon sind alte Draht-Stummel (< 0.2 mm) an Labels. Das HMI-PCB ist abgelöst.
- [x] Freerouting eingerichtet (Pipeline `tools/pcb/autoroute.py`, siehe [[Toolchain]]); offen: Profil an das Ein-PCB-Layout anpassen und die Netzklassen-Regeln im `.kicad_pro` definieren
- [ ] Controller-PCB: Layout (0 Footprints), Schaltplan fertigstellen
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
- [ ] Tasten SW3–SW8: Omron B3F-1000 (THT 6 mm) gesetzt; Gehäuse Rev. 2 rechnet mit 4.3 mm Höhe und gedruckten Kappen, am Probedruck prüfen.
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

## Gehäuse Rev. 2 (Stand 2026-11-13, Branch `cad/enclosure-single-pcb`)
- [x] Gehäuse parametrisch neu aufgebaut (`CAD/src/bekantx_enclosure.py`), Platinen-Schnittstelle in `CAD/board_interface.json`. Siehe [[Hardware]].
- [ ] **Review `cad-reviewer` 2026-11-13: FAIL (1 Blocker), Stand im Repo ist noch NICHT korrigiert, so nicht drucken.**
  - [ ] **Blocker: Deckel ist gefangen.** Als starres Teil lässt er sich weder aufsetzen noch abnehmen (Zungen brauchen 1.3 mm Weg in +Y, der Falz im Arm samt Verjüngung und Endwand sperrt). Geplante Korrektur: Falz, Deckelkante und Hohlraum im Arm als Wände parallel zu Z (statt senkrecht zum Arm), damit der Deckel um die Zungen aufschwenkt; danach den Bewegungsweg rechnerisch prüfen.
  - [ ] Major: FPC des OLED nicht berücksichtigt (Faltung zwischen Glaskante und SW5, Stecker ER-CON16HB-1 unter dem Glas); als Sperrflächen in Hüllgeometrie und `board_interface.json` aufnehmen, Glas/Flansch verschieben.
  - [ ] Major: Überhänge im Arm (Endwand innen ca. 440 mm², Verjüngung je ca. 290 mm², 55° bzw. 49.5° zur Senkrechten) bei Druck mit der Front nach unten; entfällt mit den Z-parallelen Wänden.
  - [ ] Minor: Senkung Deckelschraube 4.2 < Kopf 4.4; Kabelbinder-Schlitze 2.0 mm zu schmal (3 oder mehr); Sturz über dem Kabelfenster und Dach der Zungentaschen nur 1.0 mm; USB-Anschlag 0.5 mm vor der Buchse; OLED-Fenster gleich gross wie die Sichtfläche (kleiner machen); `wall` > 5.1 bricht den Offset; Parameter `end_wall` wirkt nicht auf den Hohlraum; einzelne feste Zahlen im Skript.
  - Bestätigt vom Review: 0 mm³ Überschneidung (an den STEP-Dateien nachgerechnet), STL wasserdicht, `board_interface.json` stimmt mit der Geometrie überein, Parameter-Variation ±10 % regeneriert.
- [ ] **Probedruck** von Gehäuse, Deckel und Tastenkappen: Passungen (Deckelfalz 0.25 mm, Kappen 0.3 mm radial), Zungen, Durchscheinen der LED-Fenster. Alle Toleranzen sind Schätzwerte.
- [ ] **ASSUMPTION Tischkabel**: Durchmesser (5 mm) und Stecker sind nicht gemessen; Austritt 9 × 6 mm lässt ein 3-poliges 2.54-mm-Gehäuse durch.
- [ ] Taster B3F-1000 (Höhe 4.3 mm) und USB-Buchse HRO TYPE-C-31-M-12 (8.94 × 7.35 × 3.26 mm) gegen die Datenblätter prüfen; beide Masse stammen nicht aus `Docs/`.
- [ ] OLED-Befestigung: Glas in der Tasche kleben (dünnes doppelseitiges Band) oder Schaumstoff zwischen Glas und Platine; Lage des FPC-Abgangs am echten Display prüfen.
- [ ] Layout: `CAD/board_interface.json` übernehmen (Umriss 129 × 38, 6 Bohrungen, Tasten, J3 unter dem Display, J1 auf B.Cu an der +X-Kante, D5/D1 unter den Lichtschächten). D5 hat noch keinen Footprint.
- [ ] Bauhöhen: Vorderseite 6 mm (an der hinteren Kante weniger, siehe JSON), Rückseite 11.4 mm. C40 (10.2 mm) passt mit 1.2 mm Luft.
- [ ] Nach dem Layout: Board-STEP exportieren und die Passprüfung gegen das echte Board wiederholen.

## Firmware
- [ ] ESP: SPI-Slave-Transport + Protokoll, Lease-/Safety-Filter, Deep Sleep
- [ ] STM32: komplette Firmware (siehe [[Firmware STM32]])
- [ ] LIN-Captures am echten Tisch (Baudrate, Startup, Nodes 1/16/17)
- [ ] Kollisions-Schwellen, Positionsmodell (Rohwerte → 0.1 mm)
- [ ] OTA/Update-Pfad beider Controller
- [ ] MQTT: Auth/TLS-Konzept (NFR-008)

Zurück: [[00 Index]]
