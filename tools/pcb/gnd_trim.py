"""NOT USED on the board (the user wants large GND planes, 2026-11-21). Trim the outer GND pours to the copper that needs them (layout rule 2026-11-21: "GND-Flaechen auf Top und
Bottom weiter reduzieren").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/gnd_trim.py <in.kicad_pcb> <out.kicad_pcb>
        [--margin=1.2] [--close=0.8] [--open=0.35] [--min-area=4] [--report]

In2 is a closed GND plane and every GND pad has its own via to it, so the outer pours only add coplanar shielding
next to signals and a little heat spreading. The pour outline of each outer layer becomes
  (copper of other nets on that layer, grown by --margin)
  closed by --close (joins gaps narrower than twice that, so the pour does not fragment),
  opened by --open (drops necks narrower than twice that),
  cut to the board outline, and pieces under --min-area mm2 are dropped.
Everything else (large empty areas) stays bare. A zone stores one outline in the file, so every piece becomes
its own zone ("GND top", "GND top 2", ...), copied from the original; bare patches inside a piece get a rule area. Run before gnd_pour.py (stitching vias, zone fill), after the
last track edit and teardrops.py.
"""
import sys

import pcbnew

sys.stdout.reconfigure(line_buffering=True)

from bekantx_layout import MM
from pcb_geom import OUTER

POURS = {"GND top": pcbnew.F_Cu, "GND bottom": pcbnew.B_Cu}
FREE_AREA = 40.0        # mm2: a piece without GND pad or via inside is kept only from this size (stitching adds vias)
HOLE_MIN = 3.0          # mm2: a bare patch inside a pour piece at least this big becomes a no-pour rule area
ERR = MM(0.01)
STRAT = pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS


def other_copper(board, lay, grow):
    """Copper of every net but GND on layer lay (tracks, pads, vias, teardrop zones), each grown by `grow` mm."""
    ps = pcbnew.SHAPE_POLY_SET()
    n = 0

    def add(item):
        nonlocal n
        s = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(s, lay, MM(grow), ERR, pcbnew.ERROR_OUTSIDE)
        for i in range(s.OutlineCount()):
            ps.AddOutline(s.Outline(i))
            for h in range(s.HoleCount(i)):
                ps.AddHole(s.Hole(i, h))
        n += 1

    for t in board.GetTracks():
        if t.GetNetname() == "GND":
            continue
        if t.GetClass() == "PCB_VIA" or t.GetLayer() == lay:
            add(t)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != "GND" and p.IsOnLayer(lay):
                add(p)
    for z in board.Zones():
        if z.IsTeardropArea() and z.GetNetname() != "GND" and z.IsOnLayer(lay):
            f = z.GetOutline() if hasattr(z, "GetOutline") else z.Outline()
            for i in range(f.OutlineCount()):
                s = pcbnew.SHAPE_POLY_SET()
                s.AddOutline(f.Outline(i))
                s.Inflate(MM(grow), STRAT, ERR)
                for j in range(s.OutlineCount()):
                    ps.AddOutline(s.Outline(j))
    ps.Simplify()
    return ps, n


def area(ps):
    return sum(ps.Outline(i).Area() - sum(ps.Hole(i, h).Area() for h in range(ps.HoleCount(i)))
               for i in range(ps.OutlineCount())) / 1e12


def chain_set(ps, i):
    one = pcbnew.SHAPE_POLY_SET()
    one.AddOutline(ps.Outline(i))
    for h in range(ps.HoleCount(i)):
        one.AddHole(ps.Hole(i, h))
    return one


def main(src, dst, margin=1.2, close=0.8, opening=0.35, min_area=4.0, report=False):
    board = pcbnew.LoadBoard(str(src))
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)
    inner = pcbnew.SHAPE_POLY_SET(outline)
    inner.Deflate(MM(0.3), STRAT, ERR)
    board_area = area(outline)
    for z in [z for z in board.Zones() if z.GetZoneName() in POURS]:
        lay = POURS[z.GetZoneName()]
        name = z.GetZoneName()
        reg, n = other_copper(board, lay, margin)
        reg.Inflate(MM(close), STRAT, ERR)
        reg.Deflate(MM(close), STRAT, ERR)
        reg.BooleanIntersection(inner)
        reg.Deflate(MM(opening), STRAT, ERR)
        reg.Inflate(MM(opening), STRAT, ERR)
        reg.Simplify()
        gnd = [v.GetPosition() for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == "GND"]
        gnd += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads()
                if p.GetNetname() == "GND" and p.IsOnLayer(lay)]
        pieces, dropped, rules = [], 0, 0
        for i in range(reg.OutlineCount()):
            one = chain_set(reg, i)
            a = area(one)
            if a < min_area or (a < FREE_AREA and not any(one.Contains(q) for q in gnd)):
                dropped += 1
                continue
            pieces.append(i)
        total = sum(area(chain_set(reg, i)) for i in pieces)
        print(f"{name}: {n} copper items, pour region {total:.0f} mm2 ({total / board_area * 100:.0f} % of the board), "
              f"{len(pieces)} pieces, {dropped} dropped")
        if report:
            continue
        for k, i in enumerate(pieces):
            zz = z if k == 0 else pcbnew.Cast_to_ZONE(z.Duplicate())
            zz.SetZoneName(name if k == 0 else f"{name} {k + 1}")
            o = zz.Outline()
            o.RemoveAllContours()
            o.AddOutline(reg.Outline(i))
            zz.SetNeedRefill(True)
            if k > 0:
                board.Add(zz)
            for h in range(reg.HoleCount(i)):
                hole = pcbnew.SHAPE_POLY_SET()
                hole.AddOutline(reg.Hole(i, h))
                if abs(hole.Outline(0).Area()) / 1e12 < HOLE_MIN:
                    continue
                ra = pcbnew.ZONE(board)
                ra.SetIsRuleArea(True)
                ra.SetLayer(lay)
                ra.SetDoNotAllowZoneFills(True)
                ra.SetDoNotAllowTracks(False); ra.SetDoNotAllowVias(False)
                ra.SetDoNotAllowPads(False); ra.SetDoNotAllowFootprints(False)
                ra.SetZoneName(f"no GND pour {name} {k + 1}.{h + 1}")
                ro = ra.Outline()
                ro.AddOutline(reg.Hole(i, h))
                board.Add(ra)
                rules += 1
        print(f"  {len(pieces)} zones, {rules} no-pour areas")
    if not report:
        board.BuildConnectivity()
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(str(dst), board)


if __name__ == "__main__":
    kw = {}
    for a in sys.argv[1:]:
        if a.startswith("--margin="):
            kw["margin"] = float(a.split("=")[1])
        elif a.startswith("--close="):
            kw["close"] = float(a.split("=")[1])
        elif a.startswith("--open="):
            kw["opening"] = float(a.split("=")[1])
        elif a.startswith("--min-area="):
            kw["min_area"] = float(a.split("=")[1])
        elif a == "--report":
            kw["report"] = True
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1] if len(pos) > 1 else None, **kw)
