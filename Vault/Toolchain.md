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
- Gehäuse bauen: `...\python.exe CAD/src/bekantx_enclosure.py` (baut, prüft die Passung, exportiert STEP/STL nach `CAD/` und schreibt `CAD/board_interface.json`; bricht bei einer Überschneidung ab).
- Im venv fehlen `matplotlib`, `shapely` und `networkx`: `trimesh`-Schnitte als Pfad (`section().discrete`, `to_planar`) gehen nicht, `trimesh.intersections.mesh_plane` schon. Bilder lassen sich mit dem mitinstallierten `vtk` offscreen rendern.
- `cadquery` bewusst **nicht** installiert: bringt inkompatiblen OCP-Kern zu build123d.

## Autorouter (Freerouting 2.5.0)
- Pipeline `tools/pcb/autoroute.py` (mit KiCad-Python): DSN-Export → Freerouting → SES-Import → Zonen neu füllen → Messung (offene Verbindungen, Vias, Länge, DRC-Differenz zur Ausgangslage). Profile in `tools/pcb/profiles/`. `route` für einen Lauf, `tune` für einen parallelen Parameter-Sweep.
- Freerouting als JAR (`%USERPROFILE%\tools\freerouting\freerouting.jar`) mit portablem Temurin-JDK 25 (`%USERPROFILE%\tools\jdk25`). Installiert 2026-11-13, Prüfsummen gegen die Release-Werte verglichen. Die native `freerouting-cli.exe` (GraalVM) bricht beim Routen mit `SerializationConstructorAccessor`-Fehler ab und wurde entfernt.
- Telemetrie abgeschaltet (`-da`, `%APPDATA%\freerouting\freerouting.json`). Der Router prüft beim Start auf Updates (Netzwerkzugriff).
- Erkenntnisse: Kostenparameter nur als ganze Zahlen; `automatic_neckdown=false` verhindert zu dünne Leiterbahnen; Zonen müssen nach dem Import neu gefüllt werden; Einzelne JVM-Abstürze kommen vor (Wiederholung im Skript). Details im Skill `pcb-design`.

## Layout-Pipeline für das Controller-Board (2026-11-15)
Alle Skripte in `tools/pcb/`, Aufruf mit KiCad-Python. Ausgaben nach `build/` (git-ignoriert).
1. `bekantx_layout.py` + `bekantx_placement.py`: leeres 4-Lagen-Board, Netzklassen ins `.kicad_pro`, Umriss/Bohrungen/Sperrflächen aus `CAD/board_interface.json`, Footprints und Netze aus der Netzliste (`kicad-cli sch export netlist`), Platzierung (grosse Teile fest, Kleinteile per Greedy-Placer neben ihre Pads), Via je Plane-Pad, HF-Leitung von Hand (gesperrt).
2. `bekantx_route.py`: Stufe 1 Freerouting nur für die Leistungsklassen auf dem leeren Board (danach gesperrt; temporäre Sperrflächen um U1/U2/U3/J2 halten deren Fluchtraum frei), Stufe 2 alle Signale, Stufe 3 ein Nachversuch, dann `touchup_router.py`, dann `bekantx_finish.py`.
3. `touchup_router.py`: Raster-Router (A*, 0.05 mm) für die letzten offenen Verbindungen; mit `--manual=tools/pcb/bekantx_manual.json` zuerst Handkorrekturen (Netze/Vias freigeben, kurze Leitungsstücke und Vias setzen).
4. `bekantx_finish.py`: GND-Flächen aussen, Regel «keine Leiterbahn auf In2», Stitching-Vias, Lagenaufbau, 3D-Modelle, Beschriftung; schreibt `Pcb_Controller/BekantX.kicad_pcb`.
5. `board_view.py`: Kontrollbild je Seite (Pads, Leiterbahnen, offene Verbindungen aus dem DRC-Report), Koordinaten wie in `board_interface.json`.

Das Board Rev. 1 ist: Lauf mit 0.15-mm-Regeln (4 offen nach Freerouting) + `bekantx_manual.json` + Nachrouter. Die Handkorrekturen gehören zu genau diesem Freerouting-Ergebnis; nach einem neuen Lauf die offenen Verbindungen neu ansehen.

**Erkenntnisse (gemessen, offene Verbindungen nach der Signal-Stufe):**
- Netzklassen-Breite über 0.3 mm kommt nicht aus 0.5-mm-Pitch-Pads heraus (`automatic_neckdown=false`): erster Lauf 60 offen.
- Sperrfläche «keine Leiterbahn» auf den Innenlagen: Freerouting setzt dann **kein einziges Via**. Stattdessen `plane_as_obstacle=true` (keine Leiterbahn auf Plane-Lagen, Vias gehen).
- Freeroutings Fanout-Stufe und die Plane-Anbindung von SMD-Pads sind unzuverlässig (Pads bleiben unverbunden). Lösung: eigenes Via je Pad vor dem Routen, Plane-Netze als Klasse `Planes` ignorieren.
- GND-Flächen auf den Aussenlagen erst nach dem Routen giessen (der Router hält sie sonst für Planes).
- SES-Import scheitert kommentarlos, wenn ein Footprint keine Bibliotheks-ID hat (Bohrungen): Footprint `BekantX:MountingHole_2.9mm_NPTH` in `Pcb_Controller/BekantX.pretty`.
- Leistungsnetze zuerst und sperren: sonst bleiben die breiten 53-V-Leitungen offen (16 Verbindungen an `VCC`).
- Default 0.2/0.2 mm mit 0.6-mm-Vias: 13 bis 23 offen in sieben Läufen. Default **0.15/0.15 mm mit 0.5-mm-Vias: 4 offen**. Das war der entscheidende Schritt.
- Schlechter als freie Pins: gesperrte Ausfahrt-Stummel an den QFN-Pins (23), Fan-out-Vias an jedem zweiten Pin (30), In1 als gemischte Signallage (9 Signale offen und 1.1 m Leiterbahn auf der `+3V3`-Lage).
- Rip-up im eigenen Nachrouter konvergiert nicht (reisst mehr auf, als er schliesst); gezieltes Freigeben einzelner Netze von Hand funktioniert.
- Mehrere `LoadBoard` in einem pcbnew-Prozess sind unzuverlässig; nach dem Entfernen von Objekten in einem neuen Prozess weiterarbeiten.
- Der DRC fand einen Kurzschluss, den ich beim Handsetzen eines Vias übersehen hatte (Via auf dem Pad von L4): jede Handkorrektur per DRC prüfen, nicht per Augenschein.

**Umbau nach dem Review (2026-11-18):** `tools/pcb/bekantx_rework.py <routed> <out>` verschiebt einzelne Bauteile auf einem fertig gerouteten Board, entfernt die Leitungen an ihren alten Pads und die, die jetzt im Weg liegen, räumt lose Enden auf, setzt Plane-Vias und von Hand definierte kurze Leitungen (Schaltschleife U20, VIN von C15) und überlässt den Rest dem Nachrouter. Danach `bekantx_finish.py`.
- pcbnew: Nach einem `board.Remove()` liefern `GetTracks()`, `GetFootprints()` und sogar `GetStart()` unbrauchbare `SwigPyObject`. Deshalb alles auf einer Python-Kopie der Geometrie entscheiden, am Schluss in einem Zug entfernen, speichern und in einem neuen Prozess weitermachen.
- Nachrouter `touchup_router.py` (Stand 2026-11-18): sucht vom ganzen zusammenhängenden Kupfer des Start- und Zielpunkts aus (nur Rasterpunkte 0.02 mm innerhalb des Kupfers, sonst gelten 0.05 mm nahe Stücke als verbunden), glättet Treppen zu geraden Strecken (die freien Rasterzellen enthalten Abstand plus halben Rasterschritt, deshalb bleibt eine gerade Strecke regelkonform), setzt keine Vias in SMD-Pads. Aufreissen (`--rip`) nur eine Runde.
- `bekantx_finish.py` setzt Stitching-Vias nur dort, wo im Umkreis eines halben Rasters (2.5 mm) noch keines liegt; ein zweiter Lauf auf einem fertigen Board verdoppelt sie sonst.

## Schaltplan-Edits per Skript
- `tools/sch/sch_edit.py`: editiert `.kicad_sch` auf Textebene (Blöcke klonen/löschen, Symbole, Labels, Drähte setzen), ohne die Datei neu zu serialisieren. Pin-Positionen werden aus `lib_symbols` berechnet; die Transformation ist gegen alle bestehenden Sheets geprüft. Nach jedem Lauf ERC, Netzliste und PDF über `kicad-cli` auf dem Root-Sheet.

## Workflow
1. PCB-Umriss/Bohrungen aus KiCad (`pcbnew` oder `export step`) lesen.
2. Gehäuse in build123d parametrisch modellieren, STEP+STL nach `CAD/` exportieren.
3. Mit `trimesh` Wasserdichtheit/Maße prüfen; PCB-STEP gegen Gehäuse auf Kollision testen.

4. Board-STEP: `kicad-cli pcb export step --subst-models --user-origin 100x80mm --no-dnp -o CAD/BekantX_PCB.step Pcb_Controller/BekantX.kicad_pcb`, dann `CAD/src/check_board_fit.py` (venv `bekantx-cad`) für die Passprüfung gegen das Gehäuse.

Siehe [[Hardware]], [[Offene Punkte]]. Zurück: [[00 Index]]
