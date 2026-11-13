# Firmware ESP32-C3 (Netzwerk-Coprozessor)

ESP-IDF, C++ (dünnes C `main.c` → `Application`). Pfad: `Firmware/ESP32C3/BekantX/`.

## Komponenten (`components/`)
| Komponente | Inhalt | Status |
|---|---|---|
| `bekantx_application` | `Application`, `StatusIndicator`, `wifi/WifiManager`, `WifiCredentialStore` | umgesetzt |
| `bekantx_drivers` | WS2812 (`ws2812_transport`), `LedDriver`, `LedAnimator` (Breath) | umgesetzt |
| `bekantx_libs` | Captive Portal (`portal.html`, HTTP, DNS-Hijack), Library-Registry | umgesetzt |
| `bekantx_mqtt` | `MqttService`, CommandHandler, CredentialStore, StatePublisher, HA-Discovery | umgesetzt (PR #2) |
| `bekantx_utils` | `CppWrapper` C/C++-Bridge | umgesetzt |
| SPI-Slave + Protokoll | – | **fehlt** (Phase 2) |
| Deep Sleep / Power | Kconfig-Defaults vorhanden | Logik offen |

`sdkconfig.defaults`: MQTT `mqtt://homeassistant.local`, Prefix `bekantx`, Device `desk001`, QoS 1, HA-Discovery an, Sleep an (Wake GPIO 9, Level 0).

## Historie
1. FTM-Wi-Fi-Beispiel als Ausgangsbasis (Reste: `README.md` ist noch das FTM-Beispiel → ersetzen)
2. Struktur-Refactor auf C++-Komponenten
3. PR #1: WS2812-LED-Treiber
4. PR #2: WiFi-Manager + MQTT-Service

## Nächste Schritte
Siehe [[Offene Punkte]]: SPI-Slave-Transport nach [[Protokolle]], Lease-/Safety-Filter, Sleep, README bereinigen.

Zurück: [[00 Index]]
