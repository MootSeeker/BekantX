# Hardware

> **Entscheid 2026-11-13:** Controller- und HMI-Platine werden zu **einer** Platine zusammengeführt, der Gehäuse-Style bleibt. Siehe [[Entscheid - Ein PCB]]. Die Abschnitte unten beschreiben den Ist-Stand der beiden bisherigen Platinen.

## Pcb_Controller (KiCad)
Hauptplatine, aufgeteilt in Sheets: `mastersheet`, `microcontroller`, `powerSupply`, `wifi`, `Connector`, `hmi`.
- Der `.kicad_pcb` enthält aktuell **0 Footprints** (Layout noch nicht begonnen; Schaltplan in Arbeit, letzte Änderung Sep).
- Commit `6e95dbb`: Projekt in zwei PCBs gesplittet; Controller nutzt STM32 + ESP32-C3 als Netzwerk-Modul.

## Pcb_HMI (KiCad)
Bedienplatine mit OLED-Display und 7-Segment-Anzeige HDSP-433G (eigene Lib in `Pcb_HMI/HDSP-433G/`). ~22 Footprints platziert. `PCB.step` für 3D/Gehäuse.

## STM32 (Primary)
CubeMX `Firmware/ST/Bekanntx/Bekanntx.ioc`: **STM32G0B1KBUx**
- SPI1 (NSS/SCK/MISO/MOSI auf PA4–PA7) → Inter-Controller-Link
- USART1 (PB6/PB7) → vermutlich LIN-PHY
- LPUART1 (PA2/PA3) → Debug/Service
- I2C1 (PB8/PB9) → OLED
- TIM2 CH1–3 (PA15, PB3, PC6) → z. B. Anzeige/Taster/PWM (zu klären)
- USB Device CDC (PA11/PA12), SWD
- GPIO/EXTI: PA8, PB0, PB1, PB2 (Taster/IRQ, zu klären)

## ESP32-C3 (Secondary)
Dev auf ESP32-S2-Saola (Datenblätter in `Docs/`), Zielhardware ESP32-C3. Wake-GPIO per Kconfig = GPIO 9, WS2812 als Status-LED.

## Gehäuse
`CAD/BekantX_Case.stl`, `CAD/BekantX_Lid.stl` (nur STL, keine Quelldatei im Repo).

Zurück: [[00 Index]]
