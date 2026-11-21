# Renderings for blog posts

Board: `Pcb_Controller/BekantX.kicad_pcb` (6 layers, 2026-11-21). Enclosure: r3 (`CAD/src/bekantx_enclosure.py`).
About 2400 × 1350 px (kicad-cli delivers 2384 × 1320), transparent background (PNG).

| File | Shows | Made with |
|---|---|---|
| `pcb_top.png` | board, front side (keys, OLED connector, LEDs) | kicad-cli |
| `pcb_bottom.png` | board, back side (all other parts) | kicad-cli |
| `pcb_iso_top.png` | board, front side, perspective | kicad-cli |
| `pcb_iso_bottom.png` | board, back side, perspective | kicad-cli |
| `enclosure_front.png` | enclosure closed: case, lid, keypad, display window | VTK |
| `enclosure_back_open.png` | case from the open back with the keypad, no lid | VTK |
| `enclosure_exploded.png` | case, keypad and the lid lifted off | VTK |
| `assembly_closed.png` | board in the closed enclosure, front | kicad-cli |
| `assembly_open.png` | board in the case, lid off | kicad-cli |
| `assembly_exploded.png` | board in the case, lid lifted off | kicad-cli |

The enclosure is a model (not a photo of the printed part). Colours are render defaults, not the print filament.

## Regenerate

```bash
V="$USERPROFILE/.venvs/bekantx-cad/Scripts/python.exe"
"$V" CAD/src/export_board_frame.py build/blog/asm
"$V" CAD/src/export_board_frame.py build/blog/expl --lid-lift=35
"C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/blog_renders.py Docs/bilder --quality=high
"$V" CAD/src/render_enclosure.py Docs/bilder
```

`export_board_frame.py` puts case, lid and keypad into the frame of the board STEP (rotation 180° about x, shift
(64.5, 5.5, 9.6) mm, checked on every run). `blog_renders.py` hangs them as 3D models on a copy of the board and
renders with `kicad-cli pcb render`; the enclosure alone is rendered with VTK because kicad-cli frames the camera
on the board.
