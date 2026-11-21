# Entscheidungen (Decision Log)

| Datum | Entscheidung | Begründung |
|---|---|---|
| früh | Dual-Controller, Primary autoritativ | Safety/Echtzeit von IoT trennen |
| früh | Inter-Controller via **SPI**, Secondary = Master | Primary bleibt autonom; Poll-Modell |
| früh | Remote-Motion nur mit Lease + Keepalive | Sicherer Stopp bei Linkverlust |
| 2026-04 | PCB-Split: Controller + HMI; STM32 + ESP32-C3 | Commit `6e95dbb` |
| 2026-04 | ESP-IDF C++ mit Komponentenstruktur | Wartbarkeit |
| 2026-05 | HA-Anbindung per **MQTT + Discovery** | Implementiert in `bekantx_mqtt`; Architektur-Doc nennt es noch als offen |
| 2026-11-13 | **Ein PCB statt zwei** (Controller + HMI zusammenlegen), Gehäuse-Style bleibt | Siehe [[Entscheid - Ein PCB]] |
| 2026-11-13 | Anzeige: **OLED 1.29" CH1115 (SPI)** ersetzt 7-Segment HDSP-433G + AS1115 | Eine Anzeige für Höhe, Status und Menü; weniger Bauteile und Frontfläche |
| 2026-11-13 | **6 Tasten direkt an STM32-GPIO** statt Key-Scan über AS1115 | Tasten unabhängig vom I2C-Bus direkt am Primary; Preis: alle 32 Pins belegt |
| 2026-11-13 | Eine 3.3-V-Rail `+3V3`, CS_N-Pull-up (R33) auf der Primary-Seite, `FSPI_INT` an PB5 | Fehlerbehebung (STM32 war unversorgt) und AR-007/008: ein fehlender Secondary darf den Primary nicht selektieren |
| 2026-11-13 | 3.3 V direkt aus VCC mit **LMR51610** (synchron, 65 V); 12 V (LV2862) bleibt nur für LIN-VSUP | Kleiner als XL1509-Stufe, weiter Eingangsbereich wegen ungemessener Tischspannung |
| 2026-11-13 | Tisch-Eingang: Sicherung + bidirektionale TVS + Serien-Schottky, LIN mit PESD1LIN | Schutz gegen Verpolung, Überspannung und ESD an der einzigen Schnittstelle nach aussen |
| 2026-11-13 | ESP32-C3 bleibt **diskret** (kein Modul) | Wunsch des Projekts: HF-Design als Lernziel |
| 2026-11-13 | ESP-Status-LED als adressierbare LED (SK6812MINI) an **GPIO8** | Firmware nutzt WS2812-Treiber; GPIO10 ist auf der Platine CS des Inter-Controller-Links |
| 2026-11-13 | Gehäuse Rev. 2: Platine **flach hinter der Front**, Frontblock tiefer (44 mm) und höher (23 mm), Arm bleibt als Befestigung und Kabelraum | Eine starre Platine passt nicht über den 55°-Knick; im alten Frontblock wären nur 129 × 25 mm frei gewesen. Stil und Tastenbild bleiben |
| 2026-11-13 | USB-C in der Seitenwand, Tischkabel am Armende, Status-LEDs hinter ausgedünnter Front | Entscheid des Nutzers; Front bleibt geschlossen, USB von vorne unsichtbar |
| 2026-11-13 | Das Gehäuse gibt Umriss und UI-Positionen der Platine vor (`CAD/board_interface.json`) | Das Layout ist noch leer; so bleibt das Tastenbild des Originals erhalten |
| 2026-11-14 | Gehäuse Rev. 3: Deckel mit **Scharnier am Armende und Schnapper an der Frontwand**, Schrauben nur als Sicherung, Lasche vorne | Probedruck Rev. 2: Deckel gefangen. Das Original rastet am Armende; dort gäbe ein druckbarer Überhang (45°) nur eine flache Haltefläche von ca. 19° zur Bewegung. Vorne reichen 14° Überhang für 40° |
| 2026-11-14 | **Tastenmatte** statt Einzelkappen | Wunsch des Nutzers: ein Druckteil, Kappen fallen nicht heraus |
| 2026-11-14 | USB-C **bündig** in der Seitenwand, Platine mit Nase, seitliches Einschieben | Wunsch des Nutzers: jedes Kabel soll passen, nur die Buchse ist sichtbar |
| 2026-11-14 | Frontblock **19.5 mm** hoch, Rückseite der Platine max. 7.0 mm; **C40 wird ersetzt** | Entscheid des Nutzers (schlanker). Ersatz für C40 (10.2 mm) wird später gewählt |
| 2026-11-14 | Alle Gehäuseschrauben **M2.5×6 Linsenkopf direkt in den Kunststoff** (8 Stück, ein Typ) | Wunsch des Nutzers; ersetzt selbstschneidende 2.2 mm. Alternative: selbstschneidende Schrauben gleicher Grösse |
| 2026-11-14 | Eine einheitliche Fase (3 mm / 45°) statt der ungleichen Fasen des Originals | Wunsch des Nutzers: gleichmässiges, modernes Bild |
| 2026-11-14 | C40 (100 µF, 10.2 mm hoch) ersetzt durch **4 × 22 µF / 63 V** (Panasonic EEE-FK1J220P, 8 × 6.2 mm): C40, C50–C52 | Entscheid des Nutzers: flache Elkos parallel. 88 µF statt 100 µF, max. 6.5 mm hoch bei 7.0 mm Grenze |
| 2026-11-14 | D5 = **Cree CLVBA-FKA** (PLCC4, 1.9 mm), Symbol `LED_RABG` | Pinout laut Datenblatt 1 = Rot, 2 = Anode, 3 = Blau, 4 = Grün; passt zu den Vorwiderständen (91R an Rot). `LED_A` = Rot, `LED_B` = Grün, `LED_C` = Blau |
| 2026-11-14 | OLED-Stecker bleibt **Hirose FH12-16S-0.5SH(55)** | Entscheid des Nutzers |
| 2026-11-14 | Fertiger-Annahme **JLCPCB, 4 Lagen** (JLC04161H-7628) | Entscheid des Nutzers; 6 Lagen waren als Ausweg erlaubt und wurden nicht gebraucht |
| 2026-11-15 | Lagen: F.Cu / In1 `+3V3` / In2 **GND** / B.Cu; fast alle Teile auf B.Cu | Das Gehäuse lässt vorne nur Tasten, Anzeige-Stecker und LEDs zu. GND muss die Nachbarlage von B.Cu sein (HF-Leitung, USB, die meisten Signale) |
| 2026-11-15 | Signalregel **0.15 / 0.15 mm, Via 0.5 / 0.3 mm** statt 0.2 / 0.2 und 0.6 | Mit den gröberen Regeln liessen sich die beiden 0.5-mm-QFNs auf zwei Signallagen nicht vollständig herausrouten. Weiterhin im Standardbereich von JLCPCB |
| 2026-11-15 | Jedes GND- und `+3V3`-SMD-Pad bekommt ein eigenes Via zur Plane | Kurze Rückstrompfade an den Entkopplern und unabhängig von zerschnittenen Aussenflächen |
| 2026-11-15 | Tischstecker J10 **abgewinkelt**, Kabel liegt über der Platine | Rückseite nur 7.5 mm frei; so bleibt alles im Platinenvolumen |
| 2026-11-15 | Bauteil-Bezeichner auf den Fab-Lagen statt im Bestückungsdruck | Die Rückseite ist zu dicht für lesbaren Druck; für die Bestückung wird ein Bestückungsplan exportiert |
| 2026-11-18 | Review-Befunde **lokal umgebaut** statt das ganze Board neu zu routen | Ein neuer Freerouting-Lauf mit der korrigierten Platzierung liess 10 Verbindungen offen, am USB-Mux U8 nicht sauber lösbar. Der Umbau verschiebt nur die 14 betroffenen Bauteile, der Rest bleibt wie geprüft |
| 2026-11-18 | Abstand GND/`+3V3` und USB **0.15 mm** statt 0.2 mm | Ausfahrten neben Entkoppel-Pads; USB nur Full Speed. JLCPCB fertigt 0.09 mm |
| 2026-11-18 | **In1 geteilt**: VCC-Fläche im Leistungsteil, Rest `+3V3`; In2 bleibt durchgehend GND | PR-Feedback des Nutzers (VCC-Leitungen auf B.Cu unübersichtlich). GND muss ungeteilt unter B.Cu bleiben (HF-Leitung, fast alle Signale); `+3V3`-Verbraucher liegen fast alle links |
| 2026-11-18 | 53-V-Netze bleiben bei **0.3 mm** Abstand | IPC-2221B Spalte B4 (mit Lötstopplack) verlangt 0.13 mm für 31–100 V; der Review nannte die unbeschichtete Spalte B2 |
| 2026-11-19 | Bezeichner **doch im Bestückungsdruck** (1.0 mm, wo nötig 0.8 mm), ersetzt den Entscheid vom 2026-11-15 | Wunsch des Nutzers („Beschriftung fehlt“). Automatisch neben das Bauteil gesetzt, nie auf Pads oder fremdem Silk; 7 Teile ohne Platz bleiben auf Fab |
| 2026-11-19 | Speisungs-Pads mit **geradem Stummel zum eigenen Plane-Via**, lange Speisungsbahnen auf den Aussenlagen entfernt; Ausnahme Eingangsschleifen C15–U9 und C25–U20 | Regel des Nutzers (kurze Speisungsleitungen über Planes). Die Schleife Eingangskondensator–VIN–GND bleibt kurz und direkt (Review 2026-11-15) |
| 2026-11-19 | B.Cu-GND vor F.Cu-GND: fünf Netze mit der langen Strecke auf F.Cu | Wunsch des Nutzers (Bottom zerstückelt). B.Cu liegt neben der GND-Plane und trägt fast alle Teile; F.Cu hat dafür mehr Stücke, jedes mit eigenem Via |
| 2026-11-19 | Ecken **2.5 mm** (Nase 0.5 mm), im Gehäuse-Skript als Parameter | Optik; die Gehäusetasche bleibt eckig, die Platine wird nur kleiner. Der Umriss bleibt damit aus einer Quelle |
| 2026-11-19 | Titelblock mit QR-Code zum Repository, Credits mit GitHub-Namen statt vollem Namen | „Wer es gemacht hat“; der GitHub-Name steht ohnehin in der Repo-URL. Voller Name auf Wunsch |
| 2026-11-19 | Lizenzen getrennt: Hardware **CERN-OHL-S-2.0**, Software **GPL-3.0-or-later**, Doku **CC BY-SA 4.0** (vorher GPL-3.0 für alles) | GPL ist eine Software-Lizenz und passt schlecht auf Schaltpläne, Layout und Gehäuse. CERN-OHL-S ist das gleichwertige Copyleft für Hardware, die Absicht der GPL bleibt erhalten. Zuordnung in `LICENSES/README.md` |
| 2026-11-19 | `Pcb_HMI/` und die Original-STLs entfernt, ersetzt den Entscheid «archivieren, nicht löschen» | Wunsch des Nutzers (Repo aufräumen). Archiv ist der Git-Tag `archive/pre-cleanup`; Stil-Referenz ist jetzt das gedruckte Gehäuse r3 |
| 2026-11-21 | Aussen-GND bleibt ganzflächig und möglichst zusammenhängend (Nutzer: grosse GND-Flächen, Bahnen so führen, dass sie wenig zerschneiden; Verkleinern war ein Missverständnis und wurde zurückgenommen). Bahnen rechtwinklig mit 45°-Fasen, Teardrops an Vias | Bahnen im Weg der Fläche zerschneiden sie; In2 bleibt die geschlossene GND-Referenz |

Neue Einträge hier ergänzen. Zurück: [[00 Index]]
