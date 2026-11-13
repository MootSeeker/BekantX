# Offene Punkte

## Inkonsistenzen in den Docs
- [ ] SPI: `inter-controller-protocol.md` (kein IRQ, Frame `0xA5…`) vs. `APPLICATION_PLAN.md` (IRQ-GPIO, anderer Header). Eine kanonische Quelle festlegen → Spec gewinnt, Plan anpassen? Oder IRQ nachrüsten (Sleep-Wake braucht ohnehin Wake-Pin).
- [ ] `architecture.md` nennt HA-Modell (MQTT/native/custom) als offen, Code nutzt MQTT.
- [ ] Firmware-`README.md` ist noch das FTM-Beispiel.
- [ ] Ordnername `Bekanntx` (doppeltes n) in `Firmware/ST/`.

## Hardware
- [ ] Controller-PCB: Layout (0 Footprints), Schaltplan fertigstellen
- [ ] Pinbelegung final + SPI-Taktlimit validieren
- [ ] LIN-PHY/Pegelanpassung zum Tisch klären
- [ ] Gehäuse: CAD-Quelle (nur STL im Repo), Passung zu PCBs

## Firmware
- [ ] ESP: SPI-Slave-Transport + Protokoll, Lease-/Safety-Filter, Deep Sleep
- [ ] STM32: komplette Firmware (siehe [[Firmware STM32]])
- [ ] LIN-Captures am echten Tisch (Baudrate, Startup, Nodes 1/16/17)
- [ ] Kollisions-Schwellen, Positionsmodell (Rohwerte → 0.1 mm)
- [ ] OTA/Update-Pfad beider Controller
- [ ] MQTT: Auth/TLS-Konzept (NFR-008)

Zurück: [[00 Index]]
