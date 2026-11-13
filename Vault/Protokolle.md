# Protokolle

## LIN (Primary ↔ Tisch) – reverse-engineered
Quelle: mgkoenig/lyft + lyft_mk2. Voll: `Docs/bekant-lin-protocol.md`.
- 19200 Baud (Annahme), Sync `0x55`, Diagnose 0x3C/0x3D mit **classic**, Laufzeit mit **enhanced** Checksum
- Nodes: 8 = Motor links, 9 = Motor rechts, 17 = Heartbeat (`00 00 00`), 18 = Kommando, 1/16 = Hilfsnodes
- Payload 3 Byte: Pos lo, Pos hi, State/Command
- Kommandos: `0x86` Up, `0x85` Down, `0x87` Slow, `0x84` Stop, `0xFC` Idle, `0xC4/0xBD/0xBC` Kalibrierung, `0x80–0x82` Limit
- States: `0x00` Idle, `0x02` Moving, `0x62` Blocked, `0x65` Error u. a.
- Position: Rohschritte ca. 162–6537, nicht cm → eigenes Umrechnungsmodell nötig
- **Noch nicht am eigenen Tisch verifiziert** (Logic-Analyzer-Captures fehlen)

## SPI (Secondary ↔ Primary) – eigenes Protokoll v1
Voll: `Docs/inter-controller-protocol.md`.
- Frame: `A5 | ver | type | flags | seq | code | arg | len | payload | crc16(LE)`
- Typen: Request `0x10`, Poll `0x11`, Response `0x20`, Event `0x30`, Idle `0x40`
- Positionen: s32 in 0.1 mm relativ zur unteren Kalibriergrenze
- Lease: `ACQUIRE/KEEPALIVE/RELEASE` (0x10–0x12), Move/Stop/MoveTo/Calibrate (0x20–0x25), Memory (0x30–0x34), Management (0x01–0x06)
- Timeouts: Request 50 ms, 1 Retry mit gleicher SEQ, Duplikat → gecachte Response
- Noch offen: Capability-/Fault-Bits, max. SPI-Takt

Zurück: [[00 Index]], [[Architektur]]
