# Toolchain (KiCad + CAD)

Eingerichtet 2026-11-13, damit Claude Leiterplatte und Gehäuse selbst erzeugen und prüfen kann.

## KiCad 10.0.1 (`C:\Program Files\KiCad\10.0\bin`)
- **kicad-cli.exe**: DRC/ERC, Gerber/Drill, STEP/Render, Netlist, BOM, SVG/PDF.
  - `kicad-cli pcb drc -o out.rpt X.kicad_pcb`, `kicad-cli sch erc ...`
  - `kicad-cli pcb export step --subst-models -o X.step X.kicad_pcb`
  - `kicad-cli pcb render -o X.png X.kicad_pcb`
- **KiCad-Python** `C:\Program Files\KiCad\10.0\bin\python.exe` (3.11): enthält `pcbnew`
  (Board lesen/schreiben: Footprints, Tracks, Zonen) und zusätzlich per `--user` installiert:
  - `kicad-skip` (`import skip`): Schaltplan (`.kicad_sch`) programmatisch editieren
  - `kicad-python` (`import kipy`): IPC-API zu laufendem KiCad
- Libraries: `share\kicad\{symbols,footprints,3dmodels}`

## Gehäuse-CAD (Python-venv `%USERPROFILE%\.venvs\bekantx-cad`, Python 3.13)
- `build123d` (parametrisches CAD, STEP/STL-Export), `trimesh` (Mesh-Prüfung), `numpy-stl`
- Aufruf: `%USERPROFILE%\.venvs\bekantx-cad\Scripts\python.exe script.py`
- `cadquery` bewusst **nicht** installiert: bringt inkompatiblen OCP-Kern zu build123d.

## Autorouter (Freerouting 2.5.0)
- Pipeline `tools/pcb/autoroute.py` (mit KiCad-Python): DSN-Export → Freerouting → SES-Import → Zonen neu füllen → Messung (offene Verbindungen, Vias, Länge, DRC-Differenz zur Ausgangslage). Profile in `tools/pcb/profiles/`. `route` für einen Lauf, `tune` für einen parallelen Parameter-Sweep.
- Freerouting als JAR (`%USERPROFILE%\tools\freerouting\freerouting.jar`) mit portablem Temurin-JDK 25 (`%USERPROFILE%\tools\jdk25`). Installiert 2026-11-13, Prüfsummen gegen die Release-Werte verglichen. Die native `freerouting-cli.exe` (GraalVM) bricht beim Routen mit `SerializationConstructorAccessor`-Fehler ab und wurde entfernt.
- Telemetrie abgeschaltet (`-da`, `%APPDATA%\freerouting\freerouting.json`). Der Router prüft beim Start auf Updates (Netzwerkzugriff).
- Erkenntnisse: Kostenparameter nur als ganze Zahlen; `automatic_neckdown=false` verhindert zu dünne Leiterbahnen; Zonen müssen nach dem Import neu gefüllt werden; Einzelne JVM-Abstürze kommen vor (Wiederholung im Skript). Details im Skill `pcb-design`.

## Schaltplan-Edits per Skript
- `tools/sch/sch_edit.py`: editiert `.kicad_sch` auf Textebene (Blöcke klonen/löschen, Symbole, Labels, Drähte setzen), ohne die Datei neu zu serialisieren. Pin-Positionen werden aus `lib_symbols` berechnet; die Transformation ist gegen alle bestehenden Sheets geprüft. Nach jedem Lauf ERC, Netzliste und PDF über `kicad-cli` auf dem Root-Sheet.

## Workflow
1. PCB-Umriss/Bohrungen aus KiCad (`pcbnew` oder `export step`) lesen.
2. Gehäuse in build123d parametrisch modellieren, STEP+STL nach `CAD/` exportieren.
3. Mit `trimesh` Wasserdichtheit/Maße prüfen; PCB-STEP gegen Gehäuse auf Kollision testen.

Hinweis: Das Layout des Controller-PCBs (0 Footprints) ist noch leer. Siehe [[Hardware]], [[Offene Punkte]]. Zurück: [[00 Index]]
