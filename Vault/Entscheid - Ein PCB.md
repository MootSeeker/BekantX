# Entscheid: ein PCB statt zwei

**Datum:** 2026-11-13 · **Status:** beschlossen, Umsetzung offen

## Entscheid
Die bisherigen Platinen `Pcb_Controller` (STM32 + ESP32-C3, LIN, Power) und `Pcb_HMI` (OLED, 7-Segment, Tasten) werden zu **einer einzigen Platine** zusammengeführt. Der **Gehäuse-Style bleibt** (Optik, Proportionen und Aufteilung von `CAD/BekantX_Case.stl` und `BekantX_Lid.stl`). Das Gehäuse wird parametrisch neu aufgebaut und an die neue Platine angepasst.

## Warum
Die Aufteilung in zwei Platinen war nötig, weil das passende Gehäuse von Hand nicht konstruierbar war (Platine hinten, Bedienteil vorne). Mit KI-gestütztem CAD (build123d) und Platinen-Daten aus KiCad fällt diese Einschränkung weg. Eine Platine spart Board-Verbindung (Stecker/Kabel), Kosten, Montage und Fehlerquellen.

## Auswirkungen
- Architektur bleibt: Primary (STM32) und Secondary (ESP32-C3) sind weiter getrennte Controller. Nur die Platinenzahl ändert sich.
- **Anforderungen AR-007/AR-008** (Primary unabhängig bestück- und testbar, IoT-Teil entfernbar) bleiben bindend: der ESP32-C3-Block muss als Ganzes unbestückt (DNP) möglich sein, ohne den Primary zu beeinträchtigen. Gemeinsame Rails und SPI-Leitungen entsprechend entkoppeln (CS_N-Pull-up, keine Rückspeisung).
- Die HMI-Elemente (OLED, 7-Segment HDSP-433G, Tasten, LED) bestimmen die Platinenform und die Position im Gehäuse. Mögliche Form: eine Platine mit Bedienbereich an der Frontkante; Höhe der Bauteile gegen Deckel prüfen.
- Bestehende Schaltpläne (`hmi.kicad_sch` im Controller-Projekt und `Pcb_HMI/BekantX_HMI.kicad_sch`) sind die Grundlage; `Pcb_HMI` wird nach der Zusammenführung archiviert, nicht gelöscht.
- Pin-Zuordnung: `.ioc` bleibt Quelle der Wahrheit; durch den Wegfall des Board-zu-Board-Steckers werden I2C/Tasten-Pins direkt verdrahtet.

## Vorgehen
1. Gehäuse-Parameter aus den STL-Dateien auslesen (Aussenmasse ca. 140 × 64 × 53 mm) und als build123d-Skript nachbauen.
2. Schaltplan zusammenführen (Skill `schematic-design`), Review (`schematic-reviewer`).
3. Layout (`pcb-design`), Review (`pcb-reviewer`), Passprüfung gegen Gehäuse (`mechanical-cad`, `cad-reviewer`).
4. Fertigungsdaten (`fab-export`).

Verlinkt: [[Hardware]], [[Architektur]], [[Entscheidungen]], [[Offene Punkte]]. Zurück: [[00 Index]]
