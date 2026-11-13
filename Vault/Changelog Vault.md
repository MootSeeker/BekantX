# Changelog Vault

- 2026-11-13 – Vault angelegt aus Bestandsaufnahme von Docs, Firmware, KiCad, CubeMX. Stand: ESP-Firmware (Wi-Fi, MQTT, LED) umgesetzt; STM32-Firmware und Controller-PCB-Layout offen.
- 2026-11-13 – Entscheid: ein PCB statt zwei; `CLAUDE.md`, Skills, Subagenten und Hooks unter `.claude/` angelegt.
- 2026-11-13 – Autorouter (Freerouting 2.5.0 + JDK 25) eingerichtet, Pipeline `tools/pcb/autoroute.py` mit Parameter-Sweep, Skill `pcb-design` darauf ausgerichtet.
- 2026-11-13 – Schaltplan analysiert und überarbeitet: HMI in `Pcb_Controller` integriert (Tasten, EEPROM), OLED CH1115 als Anzeige beschlossen (FPC-Beschaltung offen), klare Fehler behoben, Befunde in [[Offene Punkte]].
- 2026-11-13 – Schaltplan-Optimierungen: Schutz am Tisch-Eingang, 3.3-V-Netzteil mit LMR51610, SK6812 an GPIO8, Boot-Taster, NRST-Kondensator, SPI1 im `.ioc` als Slave, Footprints/MPNs gesetzt. Display weiter offen (Datenblatt fehlt).
- 2026-11-13 – OLED verdrahtet (FPC J3, Ladungspumpe, IREF); offene Prüfpunkte zu VDD2 und Stecker in [[Offene Punkte]].
- 2026-11-13 – Review-Befunde eingearbeitet: LIN_TX-Pull-up, SPI-Netze nach ESP-IOMUX, 100 nF an U9, CHIP_EN-RC, `.ioc` (PB5 Open-Drain, Tasten-Pull-ups). Offen bleiben SK6812 an 3.3 V und die ESP-Firmware.

Zurück: [[00 Index]]
