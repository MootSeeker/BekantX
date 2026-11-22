# Changelog Vault

- 2026-11-13 – Vault angelegt aus Bestandsaufnahme von Docs, Firmware, KiCad, CubeMX. Stand: ESP-Firmware (Wi-Fi, MQTT, LED) umgesetzt; STM32-Firmware und Controller-PCB-Layout offen.
- 2026-11-13 – Entscheid: ein PCB statt zwei; `CLAUDE.md`, Skills, Subagenten und Hooks unter `.claude/` angelegt.
- 2026-11-13 – Autorouter (Freerouting 2.5.0 + JDK 25) eingerichtet, Pipeline `tools/pcb/autoroute.py` mit Parameter-Sweep, Skill `pcb-design` darauf ausgerichtet.
- 2026-11-13 – Schaltplan analysiert und überarbeitet: HMI in `Pcb_Controller` integriert (Tasten, EEPROM), OLED CH1115 als Anzeige beschlossen (FPC-Beschaltung offen), klare Fehler behoben, Befunde in [[Offene Punkte]].
- 2026-11-13 – Schaltplan-Optimierungen: Schutz am Tisch-Eingang, 3.3-V-Netzteil mit LMR51610, SK6812 an GPIO8, Boot-Taster, NRST-Kondensator, SPI1 im `.ioc` als Slave, Footprints/MPNs gesetzt. Display weiter offen (Datenblatt fehlt).
- 2026-11-13 – OLED verdrahtet (FPC J3, Ladungspumpe, IREF); offene Prüfpunkte zu VDD2 und Stecker in [[Offene Punkte]].
- 2026-11-13 – Review-Befunde eingearbeitet: LIN_TX-Pull-up, SPI-Netze nach ESP-IOMUX, 100 nF an U9, CHIP_EN-RC, `.ioc` (PB5 Open-Drain, Tasten-Pull-ups). Offen bleiben SK6812 an 3.3 V und die ESP-Firmware.
- 2026-11-13 – Gehäuse Rev. 2 parametrisch aufgebaut (build123d), Platinen-Schnittstelle als JSON, Passprüfung gegen Hüllgeometrie bestanden; Probedruck offen.
- 2026-11-14 – Gehäuse Rev. 3 nach dem Probedruck von Rev. 2: Deckel mit Scharnier und Schnapper, Tastenmatte, USB-C bündig (Platine mit Nase), Frontblock 19.5 mm. Offen: C40-Bauhöhe, Probedruck.
- 2026-11-14 – Gehäuse Rev. 3 nach Feedback: Bauhöhe 19.5 mm bestätigt (C40 ersetzen), einheitliche Fasen, M2.5×6-Schrauben, 10 % weniger Material am Gehäuse, Symbole auf den Tasten, Druckhinweise für P1S.
- 2026-11-14 – Gehäuse Rev. 3 gedruckt (PLA, P1S) und freigegeben: passt. r2-Exporte entfernt, PR #4 abgeschlossen. Offen: FPC des OLED, C40-Ersatz, PETG-Druck.

- 2026-11-14 – PCB-Layout Controller begonnen (Branch `pcb/layout-4layer`): Schaltplan-Änderungen (C40 ersetzt, D5 Cree, J10), Platzierungsskripte, zweistufige Freerouting-Pipeline, Nachrouter. Stand: 4 offene Verbindungen, Board noch nicht geschrieben. Details in [[Offene Punkte]].
- 2026-11-15 – PCB-Layout Controller Rev. 1 fertig: 4 Lagen, DRC 0 Fehler / 0 offen / Parität 0, Board-STEP exportiert, Passprüfung gegen Gehäuse Rev. 3 bestanden. Entscheide (Lagen, Regeln 0.15 mm, Via je Plane-Pad) in [[Entscheidungen]], Pipeline und Erkenntnisse in [[Toolchain]].

- 2026-11-18 – PCB-Review (PASS WITH NOTES, 3 Major) eingearbeitet: U20-Zelle kompakt, C15 und R41/R42 an U9, C7 am ESP32, Via im Pad entfernt; Abstand GND/+3V3/USB 0.15 mm. DRC 0 Fehler / 0 offen / Parität 0, Passprüfung bestanden. Zwei Review-Punkte begründet abgelehnt (IPC B4, JLC-Via-Restring), siehe [[Offene Punkte]] und [[Entscheidungen]].
- 2026-11-18 – PR-Feedback #5 umgesetzt: In1 geteilt (VCC-Fläche im Leistungsteil), VCC- und überflüssige +3V3-Leitungen entfernt, Treppen geglättet und Pad-Einführungen gerade gezogen. DRC 0 Fehler / 0 offen / Parität 0, Passprüfung bestanden.
- 2026-11-18 – PR-Feedback #5, zweite Runde nach dem Review: Kanten der VCC-Fläche von der USB-Leitung weg, TP10 in die VCC-Fläche verschoben, Vias aus den Pads, alle Segmente auf 0/45/90° (183 → 11 schräg), kleine Versätze teilweise entfernt. DRC 0 Fehler / 0 offen / Parität 0, Passprüfung bestanden.
- 2026-11-18 – PR-Feedback #5, 4. Punkt: VBUS am USB-C-Stecker J1 auf F.Cu, D+/D−/CC1/CC2 gerade auf B.Cu (vorher Umwege), neues Skript `bekantx_usb_rework.py`. DRC 0 Fehler / 0 offen / Parität 0, Passprüfung bestanden.

Zurück: [[00 Index]]
- 2026-11-19 – Layout-Regeln des Nutzers umgesetzt: keine 90°-Ecken, kurze Speisungsstummel zu Plane-Vias, B.Cu-GND 31 → 23 Stücke (5 Netze auf F.Cu neu verlegt), runde Ecken (2.5 mm), Bestückungsdruck mit Referenzen, Labels, QR-Code und Logo. DRC 0 Fehler / 0 offen / Parität 0, Passprüfung bestanden.
- 2026-11-19 – Repo aufgeräumt und präsentiert: README mit Renderings, Lizenzen getrennt (CERN-OHL-S / GPL-3.0 / CC BY-SA), `Pcb_HMI/` und Original-STLs entfernt (Tag `archive/pre-cleanup`), Firmware-README neu.
- 2026-11-21 – Layout-Politur nach Nutzerfeedback (Branch `pcb/layout-polish`): Leiterbahnen durch Pad-/Via-Mitte und möglichst nur waagrecht/senkrecht (`manhattan.py`), Teardrops an Vias (`teardrops.py`), GND-Flächen bleiben ganzflächig (ein Verkleinern war ein Missverständnis, zurückgenommen). DRC 0 Fehler / 0 offen / Parität 0. Rest und Zahlen in [[Offene Punkte]], Werkzeuge in [[Toolchain]].
- 2026-11-21 – Zweite Runde: GND-Flächen aussen weniger zerschnitten (abgeschnittene Inselfläche 946 → 386 mm²) durch Neuverlegen von 4 Netzen und 168 mm langsamer Signale auf In1 (`in1_drop.py`); `+3V3`- und VCC-Fläche bleiben je ein Stück. DRC 0 Fehler / 0 offen / Parität 0.
- 2026-11-21 – Platine auf **6 Lagen** mit einer Leiterbahn-Richtung je Lage (F.Cu/In3 senkrecht, In2/B.Cu waagrecht), neu geroutet (Fanout + Freerouting + Nachrouter). GND aussen: F.Cu 1 Fläche statt 25 Stücke, B.Cu 6 statt 22. DRC 0 Fehler / 0 offen / Parität 0. Entscheid in [[Entscheidungen]], offene Punkte (Stackup-ASSUMPTION, Kosten, Pad-Mitte, Review) in [[Offene Punkte]].
- 2026-11-21 – Alle 90°-Ecken der 6-Lagen-Platine mit 45° gefast (286 → 0), Fasen-Skript auf alle Lagen erweitert. DRC 0 Fehler / 0 offen / Parität 0.
- 2026-11-21 – Reste auf B.Cu nach der Handarbeit des Nutzers bereinigt (Sperren aufgehoben, Mini-Stücke, tote Äste, überlappendes Via). DRC 0 Fehler / 0 offen / Parität 0, nur 2 bekannte Silk-Warnungen.
- 2026-11-21 – Renderings für Blogposts in `Docs/bilder` (Platine, Gehäuse, beides zusammen) mit Skripten zum Neu-Erzeugen, siehe [[Toolchain]].
- 2026-11-22 – Montageanleitung `Docs/Montageanleitung.md` geschrieben (Druck, Tastenmatte, Display, Platine, Tischkabel, Deckel, Tischmontage) mit den Renderings und den Fotos des Probedrucks r3 in `Docs/bilder`. Ungeprüfte Schritte (Tisch-Schnittstelle, FPC Pin 1 und Faltung, Tastenbelegung, PETG) sind markiert; Zusammenbau mit Platine noch nicht gemacht.
