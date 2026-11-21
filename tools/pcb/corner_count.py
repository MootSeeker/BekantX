"""Count sharp track corners per layer (read-only): points where exactly two segments of one net meet on one layer,
outside every pad and via, with an inner angle of 90 degrees or less (layout rule: no 90 degree corners, bends only
with 45 degree pieces).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/corner_count.py <board.kicad_pcb> [--list]
"""
import collections, math, sys

import pcbnew

from bekantx_layout import unP

LAYERS = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu)


def corners(b, max_inner=91.0):
    key = lambda q: (round(q[0], 4), round(q[1], 4))
    at = collections.defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetLayer() in LAYERS:
            a, c = unP(t.GetStart()), unP(t.GetEnd())
            if math.dist(a, c) < 1e-6:
                continue
            at[(t.GetNetname(), t.GetLayer(), key(a))].append((a, c))
            at[(t.GetNetname(), t.GetLayer(), key(c))].append((c, a))
    vias = [(unP(v.GetPosition()), pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)) / 2, v.GetNetname())
            for v in b.GetTracks() if v.GetClass() == "PCB_VIA"]
    pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
    out = []
    for (net, lay, k), lst in at.items():
        if len(lst) != 2:
            continue
        p = lst[0][0]
        if any(vn == net and math.dist(p, vp) <= vr + 1e-3 for vp, vr, vn in vias):
            continue
        if any(pd.GetNetname() == net and pd.IsOnLayer(lay) and pd.HitTest(pcbnew.VECTOR2I(*[int(pcbnew.FromMM(v)) for v in (p[0] + 100, p[1] + 80)])) for pd in pads):
            continue
        u = (lst[0][1][0] - p[0], lst[0][1][1] - p[1])
        v = (lst[1][1][0] - p[0], lst[1][1][1] - p[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        ang = math.degrees(math.acos(max(-1, min(1, (u[0] * v[0] + u[1] * v[1]) / lu / lv))))
        if ang <= max_inner:
            out.append((net, lay, p, ang))
    return out


def main(path, listing):
    b = pcbnew.LoadBoard(path)
    cs = corners(b)
    c = collections.Counter(pcbnew.BOARD.GetStandardLayerName(l) for _n, l, _p, _a in cs)
    print(f"corners <= 90 degrees outside pads/vias: {len(cs)} {dict(c)}")
    if listing:
        for n, l, p, a in cs[:60]:
            print(f"  {n:24s} {pcbnew.BOARD.GetStandardLayerName(l)} ({p[0]:.2f},{p[1]:.2f}) {a:.0f} deg")


if __name__ == "__main__":
    main(sys.argv[1], "--list" in sys.argv)
