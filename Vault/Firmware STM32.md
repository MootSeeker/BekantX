# Firmware STM32 (Primary Controller)

Status: **nur CubeMX-Konfiguration** (`Firmware/ST/Bekanntx/Bekanntx.ioc`, STM32G0B1KBUx), kein Quellcode.

## Zu implementieren (aus Specs)
- LIN-Master (19200 Baud, Break/Sync/PID, klassisch/enhanced Checksum) → [[Protokolle]]
- Startup/Discovery (Diagnose 0x3C/0x3D), Laufzeit-Burst-Schedule (Nodes 17, 8, 9, 16, 1, 18)
- Motion-State-Machine, Limits, Kalibrierung, Memory-Slots, Kollisionsheuristik (Zustand `0x62` Blocked, Drift L/R)
- SPI-Slave-Mailbox, Lease-Verwaltung, Duplikat-Cache
- Persistenz (Flash/EEPROM) mit Validierung/Fallback (FR-040)
- HMI: OLED (I2C), 7-Segment, Taster

Zurück: [[00 Index]], [[Architektur]]
