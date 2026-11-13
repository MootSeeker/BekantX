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

Neue Einträge hier ergänzen. Zurück: [[00 Index]]
