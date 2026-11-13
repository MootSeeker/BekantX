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

Neue Einträge hier ergänzen. Zurück: [[00 Index]]
