"""Reproducible routing of the BekantX board in two autorouter stages.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_route.py [--work build/bx] [--apply]

1. bekantx_layout.py   board from netlist + enclosure interface, placement, plane vias, locked RF tracks
2. stage 1             Freerouting on the power classes only (short, wide tracks on the empty board), then locked
3. stage 2             Freerouting on everything else (profile tools/pcb/profiles/bekantx.json)
4. touchup_router.py   grid router for the connections that are still open (last resort: tracks on In1)
5. bekantx_finish.py   outer GND pours, stitching vias, stackup; with --apply written to Pcb_Controller/BekantX.kicad_pcb
"""
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = sys.executable
POWER = ["PowerHV", "PowerMid", "LIN"]
OTHERS = ["kicad_default", "Default", "Power", "USB", "RF", "Planes"]


def run(*args):
    r = subprocess.run([PY, *map(str, args)], capture_output=True, text=True)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "image handler" not in l)
    if r.returncode:
        raise SystemExit(out)
    return out


ESCAPE = {"U1": 3.0, "U2": 2.0, "U3": 1.0, "J2": 1.0}     # mm kept free of power tracks around these parts


def add_escape_keepouts(src, dst):
    """Stage 1 routes on an empty board and would run the wide power tracks right along the IC pins.
    Temporary keep-outs (outer layers, tracks and vias) reserve the fan-out area of the signal pins."""
    import pcbnew
    from bekantx_layout import add_rule_area, unP
    b = pcbnew.LoadBoard(str(src))
    for ref, m in ESCAPE.items():
        bb = b.FindFootprintByReference(ref).GetBoundingBox(False)
        x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
        x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        add_rule_area(b, [(x0 - m, y0 - m), (x1 + m, y0 - m), (x1 + m, y1 + m), (x0 - m, y1 + m)], f"tmp escape {ref}",
                      [pcbnew.F_Cu, pcbnew.B_Cu], tracks=True, vias=True, pour=False)
    pcbnew.SaveBoard(str(dst), b)


def lock_tracks(src, dst):
    import pcbnew
    b = pcbnew.LoadBoard(str(src))
    for t in b.GetTracks():
        t.SetLocked(True)
    for z in list(b.Zones()):
        if z.GetZoneName().startswith("tmp escape"):
            b.Remove(z)
    pcbnew.SaveBoard(str(dst), b)
    return len(b.GetTracks())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=str(ROOT / "build" / "bx"))
    ap.add_argument("--apply", action="store_true", help="write the finished board to Pcb_Controller/BekantX.kicad_pcb")
    ap.add_argument("--passes", type=int, default=30)
    ap.add_argument("--manual", help="json with manual touch-ups for the touch-up router (belongs to one routing result)")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    prof = json.loads((HERE / "profiles" / "bekantx.json").read_text(encoding="utf-8"))
    prof["autorouter.max_passes"] = a.passes

    board = work / "placed" / "BekantX.kicad_pcb"
    print(run(HERE / "bekantx_layout.py", "--out", board))

    p1 = dict(prof, **{"autorouter.ignore_net_classes": OTHERS, "autorouter.max_passes": 30, "optimizer.enabled": True})
    (work / "stage1.json").write_text(json.dumps(p1, indent=2), encoding="utf-8")
    s1_in = work / "stage1_in" / "BekantX.kicad_pcb"
    s1_in.parent.mkdir(exist_ok=True)
    s1_in.with_suffix(".kicad_pro").write_text(board.with_suffix(".kicad_pro").read_text(encoding="utf-8"), encoding="utf-8")
    add_escape_keepouts(board, s1_in)
    print(run(HERE / "autoroute.py", "route", s1_in, "--profile", work / "stage1.json", "--out", work / "r1",
              "--keep-tracks", "--timeout", a.timeout))
    s1 = next((work / "r1").rglob("routed.kicad_pcb"))
    locked = work / "stage1" / "BekantX.kicad_pcb"
    locked.parent.mkdir(exist_ok=True)
    (locked.with_suffix(".kicad_pro")).write_text(board.with_suffix(".kicad_pro").read_text(encoding="utf-8"), encoding="utf-8")
    print("stage 1 locked:", lock_tracks(s1, locked), "tracks and vias")

    p2 = dict(prof, **{"autorouter.ignore_net_classes": ["Planes"] + POWER})
    (work / "stage2.json").write_text(json.dumps(p2, indent=2), encoding="utf-8")
    print(run(HERE / "autoroute.py", "route", locked, "--profile", work / "stage2.json", "--out", work / "r2",
              "--keep-tracks", "--timeout", a.timeout))
    s2 = next((work / "r2").rglob("routed.kicad_pcb"))
    # stage 3: what is left gets more tries with cheaper vias; the existing tracks stay (unlocked ones may be ripped up)
    for i, via_cost in enumerate((20,), 3):
        m = json.loads((s2.parent / "metrics.json").read_text(encoding="utf-8"))
        if m.get("unrouted", 1) == 0:
            break
        p3 = dict(p2, **{"scoring.via_costs": via_cost, "autorouter.max_passes": 20})
        (work / f"stage{i}.json").write_text(json.dumps(p3, indent=2), encoding="utf-8")
        src = work / f"stage{i}" / "BekantX.kicad_pcb"
        src.parent.mkdir(exist_ok=True)
        src.write_text(s2.read_text(encoding="utf-8"), encoding="utf-8")
        src.with_suffix(".kicad_pro").write_text(board.with_suffix(".kicad_pro").read_text(encoding="utf-8"), encoding="utf-8")
        print(run(HERE / "autoroute.py", "route", src, "--profile", work / f"stage{i}.json", "--out", work / f"r{i}",
                  "--keep-tracks", "--timeout", a.timeout))
        s2 = next((work / f"r{i}").rglob("routed.kicad_pcb"))
    # stage 4: the grid router closes what is left, first on the outer layers, then also over In1 (+3V3 plane)
    tu = work / "touchup"
    tu.mkdir(exist_ok=True)
    for name in ("a", "b"):
        (tu / f"{name}.kicad_pro").write_text(board.with_suffix(".kicad_pro").read_text(encoding="utf-8"), encoding="utf-8")
    (tu / "touchup_tmp.kicad_pro").write_text(board.with_suffix(".kicad_pro").read_text(encoding="utf-8"), encoding="utf-8")
    print(run(HERE / "touchup_router.py", s2, tu / "a.kicad_pcb", *([f"--manual={a.manual}"] if a.manual else [])))
    print(run(HERE / "touchup_router.py", tu / "a.kicad_pcb", tu / "b.kicad_pcb", "--inner"))
    s2 = tu / "b.kicad_pcb"
    out = ROOT / "Pcb_Controller" / "BekantX.kicad_pcb" if a.apply else work / "final" / "BekantX.kicad_pcb"
    out.parent.mkdir(exist_ok=True)
    if not a.apply:
        (out.with_suffix(".kicad_pro")).write_text(board.with_suffix(".kicad_pro").read_text(encoding="utf-8"), encoding="utf-8")
    print(run(HERE / "bekantx_finish.py", s2, "--out", out))


if __name__ == "__main__":
    main()
