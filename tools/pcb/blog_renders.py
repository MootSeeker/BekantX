"""Renderings of the board and the enclosure, alone and together (for blog posts), with kicad-cli pcb render.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/blog_renders.py <out_dir> [--only=name,name] [--quality=high]

Needs the enclosure parts in the board frame first (build123d venv):
  "%USERPROFILE%/.venvs/bekantx-cad/Scripts/python.exe" CAD/src/export_board_frame.py build/blog/asm
  "%USERPROFILE%/.venvs/bekantx-cad/Scripts/python.exe" CAD/src/export_board_frame.py build/blog/expl --lid-lift=35
The parts are hung as 3D models on an extra footprint at the board origin (offset z -1.6: the STEP frame has the
board bottom at z = 0) of a copy of the board. The enclosure alone comes from CAD/src/render_enclosure.py
(VTK): kicad-cli frames the camera on the board and cannot show the enclosure without it. One render at a time (they are heavy).
"""
import shutil, subprocess, sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "Pcb_Controller" / "BekantX.kicad_pcb"
BLOG = ROOT / "build" / "blog"
CLI = "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"
W, H = 2400, 1350

# name: (board variant, models, kicad-cli view options)
VIEWS = {
    "pcb_top": ("board", [], ["--side", "top"]),
    "pcb_bottom": ("board", [], ["--side", "bottom"]),
    "pcb_iso_top": ("board", [], ["--perspective", "--rotate", "-40,0,30", "--zoom", "0.9"]),
    "pcb_iso_bottom": ("board", [], ["--perspective", "--rotate", "140,0,-30", "--zoom", "0.9"]),
    "assembly_closed": ("board", ["asm/case", "asm/lid", "asm/keypad"], ["--perspective", "--rotate", "-55,0,205", "--zoom", "0.8"]),
    "assembly_open": ("board", ["asm/case", "asm/keypad"], ["--perspective", "--rotate", "130,0,-25", "--zoom", "0.8"]),
    "assembly_exploded": ("board", ["expl/case", "expl/lid", "expl/keypad"], ["--perspective", "--rotate", "120,0,-30", "--zoom", "0.6"]),
}


def make_variant(kind, models, dst):
    """Copy of the board with the given enclosure parts as models; kind 'empty' strips the board to a dot."""
    b = pcbnew.LoadBoard(str(BOARD))
    if kind == "empty":
        dead = list(b.GetFootprints()) + list(b.GetTracks()) + list(b.Zones()) + list(b.GetDrawings())
        for x in dead:
            b.Remove(x)
        r = pcbnew.PCB_SHAPE(b)
        r.SetShape(pcbnew.SHAPE_T_RECT)
        r.SetLayer(pcbnew.Edge_Cuts)
        r.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(164.5), pcbnew.FromMM(99.0)))      # inside the cavity, 0.1 mm
        r.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(164.6), pcbnew.FromMM(99.1)))
        b.Add(r)
    if models:
        fp = pcbnew.FOOTPRINT(b)
        fp.SetReference("ENC1")
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100), pcbnew.FromMM(80)))
        fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        for m in models:
            mod = pcbnew.FP_3DMODEL()
            mod.m_Filename = str((BLOG / f"{m}.step").resolve()).replace("\\", "/")
            mod.m_Offset = pcbnew.VECTOR3D(0, 0, -1.6)
            fp.Models().push_back(mod)
        b.Add(fp)
    pcbnew.SaveBoard(str(dst), b)
    shutil.copy(BOARD.with_suffix(".kicad_pro"), dst.with_suffix(".kicad_pro"))
    for f in ("fp-lib-table",):
        shutil.copy(BOARD.parent / f, dst.parent / f)
    if not (dst.parent / "3d").exists():
        shutil.copytree(BOARD.parent / "3d", dst.parent / "3d")


def main(out, only, quality):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = BLOG / "boards"
    work.mkdir(parents=True, exist_ok=True)
    for name, (kind, models, opts) in VIEWS.items():
        if only and name not in only:
            continue
        brd = work / f"{name}.kicad_pcb"
        if kind == "board" and not models:
            brd = BOARD
        else:
            subprocess.run([sys.executable, __file__, "--variant", kind, ",".join(models), str(brd)], check=True,
                           capture_output=True)
        png = out / f"{name}.png"
        r = subprocess.run([CLI, "pcb", "render", "-o", str(png), "-w", str(W), "-h", str(H), "--quality", quality,
                            "--background", "transparent", *opts, str(brd)], capture_output=True, text=True)
        print(f"{name}: {'ok' if png.exists() and r.returncode == 0 else 'FAILED ' + r.stderr[-200:]}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--variant":
        make_variant(sys.argv[2], [m for m in sys.argv[3].split(",") if m], Path(sys.argv[4]))
        sys.exit()
    q = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--quality=")), "high")
    o = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "")
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], set(o.split(",")) - {""}, q)
