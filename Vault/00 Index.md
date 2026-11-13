# BekantX Vault – Index

Wissensbasis (Obsidian-kompatibel, `[[Wikilinks]]`) für das Projekt **BekantX**: eine eigene Steuerung für den IKEA BEKANT Stehtisch (Custom-Elektronik, Firmware, Gehäuse).

Die normativen Specs bleiben in `Docs/`. Der Vault fasst zusammen, hält Entscheidungen und Status fest und wird laufend gepflegt.

## Navigation
- [[Projektüberblick]] – Vision, Ziele, Scope
- [[Architektur]] – Dual-Controller, Verantwortlichkeiten
- [[Hardware]] – PCBs, MCUs, Gehäuse
- [[Firmware ESP32-C3]] – Netzwerk-Coprozessor (Stand der Umsetzung)
- [[Firmware STM32]] – Primary Controller (noch offen)
- [[Protokolle]] – LIN (Tisch) und SPI (Inter-Controller)
- [[Toolchain]] – KiCad-CLI/Python, build123d für Gehäuse
- [[Entscheidungen]] – Decision Log
  - [[Entscheid - Ein PCB]]
- [[Offene Punkte]] – Backlog / Risiken
- [[Changelog Vault]]

## Specs im Repo
- `Docs/description.md` – Requirements (AR/FR/SR/NFR/IF/VC)
- `Docs/architecture.md`
- `Docs/inter-controller-protocol.md`
- `Docs/bekant-lin-protocol.md`
- `Firmware/ESP32C3/BekantX/APPLICATION_PLAN.md`

## Repo-Struktur
```
CAD/            Gehäuse (Case, Lid als STL)
Docs/           Specs, Datenblätter ESP32-S2, drawio
Firmware/ESP32C3/BekantX   ESP-IDF C++ Projekt (IoT-Coprozessor)
Firmware/ST/Bekanntx       STM32CubeMX (.ioc), noch kein Code
Pcb_Controller/ KiCad: Hauptplatine (STM32 + ESP32-C3, LIN, Power)
Pcb_HMI/        KiCad: Bedienplatine (OLED, 7-Segment HDSP-433G)
```
