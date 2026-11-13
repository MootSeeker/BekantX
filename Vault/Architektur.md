# Architektur

```
Lokale Bedienung (HMI) ─► Primary (STM32G0B1) ◄─LIN 19200─► BEKANT Motoren
                              ▲ SPI (Primary = Slave)
                              ▼
                     Secondary (ESP32-C3) ◄─Wi-Fi/MQTT─► Home Assistant
```

## Rollen
| | Primary | Secondary |
|---|---|---|
| MCU | STM32G0B1KBU | ESP32-C3 (Dev: ESP32-S2-Saola) |
| Aufgaben | LIN, Motion, Safety, Kalibrierung, Memory, Persistenz, Validierung | Wi-Fi, Provisioning, MQTT, HA-Discovery, LED-Status, Sleep |
| Optional | nein | ja |

## Regeln
- Wer Bewegung beeinflusst, ist autoritativ → Primary.
- Secondary *fragt an*, Primary *entscheidet* (Request-Modell, kein geteilter Authority).
- Stop hat höchste Priorität; lokale Eingabe übersteuert Remote.
- Remote-Motion nur mit **Lease** (Default 500 ms, Keepalive 100 ms); Lease-Ablauf = sicherer Stopp.
- Secondary-Ausfall → Primary bleibt voll nutzbar, danach Resync.

## SPI-Transport
Secondary = Master, Primary = Slave, Mode 0, 1 MHz Start, 4-Draht, **kein IRQ** laut Protokoll-Spec (Poll-basiert). Mailbox-Modell: Request → Poll → Response/Event. CRC-16/CCITT-FALSE, SOF `0xA5`, max. 64 Byte.

> ⚠ Widerspruch: `APPLICATION_PLAN.md` plant eine IRQ-Leitung und ein anderes Frame-Format (2-Byte SOF, Header-CRC). Siehe [[Offene Punkte]].

Details: [[Protokolle]]. Zurück: [[00 Index]]
