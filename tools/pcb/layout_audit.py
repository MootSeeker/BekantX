"""Measure the layout rules of the user feedback on a finished board (read-only).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/layout_audit.py <board.kicad_pcb> [--list]

Reports, on the outer layers:
- track ends in a pad or via of the same net that are not at its centre (offset in mm) or that arrive at an angle
  that is not along a pad axis,
- track segments by direction: horizontal/vertical, 45 degrees, other angles (length in mm),
- area of the outer GND pours and their share of the board.
"""
import collections, math, sys

import pcbnew

from bekantx_layout import unP
from pcb_geom import OUTER

TOL = 0.005          # mm: counts as centred


def seg_class(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n < 1e-6:
        return "zero", 0.0
    ang = math.degrees(math.atan2(abs(dy), abs(dx)))      # 0..90
    if ang < 0.05 or ang > 89.95:
        return "axis", ang
    if abs(ang - 45) < 0.6:
        return "45", ang
    return "other", ang


def main(path, listing=False):
    b = pcbnew.LoadBoard(path)
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for lay in OUTER:
                if p.IsOnLayer(lay):
                    pads.append((p, lay, fp.GetReference()))
    vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
    segs = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() in OUTER]

    # entries: a segment with one end inside a pad/via of its net and the other end outside it
    nodes = [(p, lay, f"{ref}.{p.GetNumber()}", "pad") for p, lay, ref in pads] +             [(v, None, "via", "via") for v in vias]
    entries = []
    for t in segs:
        for e, o in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
            for n, lay, name, kind in nodes:
                if n.GetNetname() != t.GetNetname() or (lay is not None and lay != t.GetLayer()):
                    continue
                if n.HitTest(e) and not n.HitTest(o):
                    c = unP(n.GetPosition())
                    ex, ey = unP(e)
                    ox, oy = unP(o)
                    dx, dy = ox - ex, oy - ey
                    L = math.hypot(dx, dy)
                    if L < 1e-6:
                        continue
                    perp = abs((c[0] - ex) * dy - (c[1] - ey) * dx) / L       # distance centre - line of segment
                    ang = math.degrees(math.atan2(abs(dy), abs(dx)))
                    entries.append((kind, name, t.GetNetname(), t.GetLayer(), (ex, ey), c, perp, ang, L))
    bad_c = [x for x in entries if x[6] > 0.02]
    bad_a = [x for x in entries if x[6] <= 0.02 and 0.05 < x[7] < 89.95]
    print(f"entries (segment crossing the edge of a pad/via of its net): {len(entries)}; "
          f"line misses the centre by > 0.02 mm: {len(bad_c)} (pads {sum(1 for x in bad_c if x[0] == 'pad')}, "
          f"vias {sum(1 for x in bad_c if x[0] == 'via')}); through the centre but diagonal: {len(bad_a)}")
    if listing:
        for k, name, net, lay, e, c, perp, ang, L in sorted(bad_c, key=lambda x: -x[6])[:60]:
            print(f"  miss {k} {name:9s} {net:22s} {b.GetLayerName(lay)} centre ({c[0]:.2f},{c[1]:.2f}) miss {perp:.2f} "
                  f"angle {ang:.0f} len {L:.2f}")

    tot = collections.Counter()
    cnt = collections.Counter()
    odd = []
    for t in segs:
        a, c = unP(t.GetStart()), unP(t.GetEnd())
        k, ang = seg_class(a, c)
        L = math.dist(a, c)
        tot[k] += L
        cnt[k] += 1
        if k == "other":
            odd.append((L, ang, t.GetNetname(), t.GetLayer(), a, c))
    print("segments:", {k: f"{cnt[k]} / {tot[k]:.1f} mm" for k in ("axis", "45", "other", "zero")})
    if listing:
        for L, ang, net, lay, a, c in sorted(odd, reverse=True)[:40]:
            print(f"  other {ang:5.1f} deg {L:5.2f} mm {net:22s} {b.GetLayerName(lay)} ({a[0]:.2f},{a[1]:.2f})-({c[0]:.2f},{c[1]:.2f})")
    long45 = sum(1 for t in segs if seg_class(unP(t.GetStart()), unP(t.GetEnd()))[0] == "45"
                 and math.dist(unP(t.GetStart()), unP(t.GetEnd())) > 1.0)
    print(f"45 degree segments longer than 1 mm: {long45}")

    bb = b.GetBoardEdgesBoundingBox()
    ps = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(ps, True)
    board_area = sum(ps.Outline(i).Area() for i in range(ps.OutlineCount())) / 1e12
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetLayer() not in OUTER or z.IsTeardropArea():
            continue
        lay = z.GetFirstLayer()
        f = z.GetFilledPolysList(lay)
        area = sum(f.Outline(i).Area() for i in range(f.OutlineCount())) / 1e12
        holes = sum(f.Hole(i, h).Area() for i in range(f.OutlineCount()) for h in range(f.HoleCount(i))) / 1e12
        print(f"zone {z.GetZoneName()!r} {b.GetLayerName(lay)} net {z.GetNetname()}: {f.OutlineCount()} pieces, "
              f"{area - holes:.0f} mm2 of {board_area:.0f} mm2 board ({(area - holes) / board_area * 100:.0f} %)")
    td = [z for z in b.Zones() if z.IsTeardropArea()]
    print(f"teardrop zones: {len(td)}; vias: {len(vias)}")


if __name__ == "__main__":
    main(sys.argv[1], "--list" in sys.argv)
