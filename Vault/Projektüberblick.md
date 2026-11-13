# Projektüberblick

**Ziel:** Optimierte Tischsteuerung für den IKEA BEKANT mit eigener Elektronik, Firmware und Gehäuse. Inspiration: [LYFT mk2](https://github.com/mgkoenig/lyft_mk2) – gleiche Grundidee (LIN-Controller + ESP), aber sauberere Hardware und klare Trennung kritisch/optional.

## Kernprinzip
Alles Tisch-Kritische (LIN, Bewegung, Limits, Kollision, Memory) liegt auf dem **Primary Controller**. Wi-Fi/Home Assistant liegt auf einem **optionalen Secondary Controller**. Der Tisch muss ohne diesen voll funktionieren (AR-002/003, SR-002).

## Scope v1
- Auf/Ab/Stop, Memory-Positionen, Kalibrierung, Limits
- Kollisions-/Hinderniserkennung (heuristisch, keine Zertifizierung)
- Wi-Fi-API → Home Assistant (lokal, ohne Cloud)
- Diagnose/Telemetrie, Persistenz

## Nicht-Ziele
Cloud-Pflicht, Smartphone-App-Pflicht, andere Tischmodelle, formale Safety-Zertifizierung.

Siehe [[Architektur]], [[Offene Punkte]]. Zurück: [[00 Index]]
