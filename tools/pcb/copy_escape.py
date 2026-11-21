"""Copy the pad escape of some pins from an older layout (6-layer re-route 2026-11-21): where the automatic fan-out
of neighbouring pins takes each other's room (U2.6/U2.7 next to C7, U1.2 between the vias of U1.1/U1.3), the escape
that worked in the 4-layer layout is set first and locked, the fan-out follows around it.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/copy_escape.py <old.kicad_pcb> <in.kicad_pcb> <out.kicad_pcb>
        REF.PIN [REF.PIN ...] [--radius=3.5]

From the pad, the old tracks of the net on the pad's layer are followed until the first via (taken along) or until
--radius mm from the pad centre (there a via is added if one fits). Each piece must keep all clearances in the new
board (manhattan.Fast with the inner layers, NPTH holes), else the pin is reported and skipped. Copies are locked.
"""
import math, sys

import pcbnew

from bekantx_layout import MM, P, add_via, unP
from manhattan import Fixer
from pcb_geom import bbox_mm, uid

VIA, DRILL = 0.5, 0.3


def old_escape(old, ref, pin, radius):
    fp = old.FindFootprintByReference(ref)
    pad = next(p for p in fp.Pads() if p.GetNumber() == pin)
    net, c = pad.GetNetname(), unP(pad.GetPosition())
    lay = pcbnew.B_Cu if pad.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu
    segs = [(unP(t.GetStart()), unP(t.GetEnd()), pcbnew.ToMM(t.GetWidth())) for t in old.GetTracks()
            if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net and t.GetLayer() == lay]
    vias = [unP(v.GetPosition()) for v in old.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == net]
    key = lambda q: (round(q[0], 3), round(q[1], 3))
    front = [q for a, b, _w in segs for q in (a, b) if pad.HitTest(P(*q))]
    seen, out, via, cut = set(), [], None, None
    while front:
        q = front.pop()
        if key(q) in seen:
            continue
        seen.add(key(q))
        if any(math.dist(q, v) < 1e-3 for v in vias) and not pad.HitTest(P(*q)):
            via = q
            continue
        for a, b, w in segs:
            for s, e in ((a, b), (b, a)):
                if math.dist(s, q) < 0.06 and key(e) not in seen:      # ends that nearly meet count as joined
                    if math.dist(e, c) > radius:
                        cut = cut or s
                        continue
                    out.append((s, e, w))
                    front.append(e)
    if via is None and cut is None and out:          # the old track went on without a via: cut at its farthest point
        cut = max((e for _s, e, _w in out), key=lambda q: math.dist(q, c))
    return net, lay, out, via, cut


def main(oldp, src, dst, specs, radius):
    old = pcbnew.LoadBoard(str(oldp))
    esc = {s: old_escape(old, *s.split("."), radius) for s in specs}
    b = pcbnew.LoadBoard(str(src))
    fx = Fixer(b)
    cu = fx.cu
    inner = [l for l in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu) if b.IsLayerEnabled(l)]

    def via_ok(q, net):
        if not cu.via_clear(q, VIA, DRILL, net, own_pad_gap=0.05):
            return False
        sh = pcbnew.SHAPE_CIRCLE(P(*q), MM(VIA / 2))
        return cu._hits(sh, (q[0] - VIA / 2, q[1] - VIA / 2, q[0] + VIA / 2, q[1] + VIA / 2), net, inner, set()) is None

    for spec, (net, lay, segs, via, cut) in esc.items():
        end = via or cut
        if not segs:
            print(f"{spec} ({net}): no old escape")
            continue
        if not all(fx.hole_ok(a, e, w) and cu.seg_clear(a, e, w, net, lay) for a, e, w in segs):
            print(f"{spec} ({net}): old escape collides in the new board")
            continue
        if end is None or not via_ok(end, net):
            print(f"{spec} ({net}): no via at the end {end}")
            continue
        code = b.FindNet(net)
        for a, e, w in segs:
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(P(*a)); t.SetEnd(P(*e)); t.SetWidth(MM(w)); t.SetLayer(lay); t.SetNet(code); t.SetLocked(True)
            b.Add(t)
            cu.add_track(t)
        v = add_via(b, net, end, VIA, DRILL, locked=True)
        it = dict(obj=v, kind="via", net=net, layers=[pcbnew.F_Cu, pcbnew.B_Cu] + inner, box=bbox_mm(v), uid=uid(v))
        cu.items.append(it); cu._reg(it)
        cu.holes.append((end[0], end[1], DRILL / 2, v))
        print(f"{spec} ({net}): {len(segs)} segments, via at ({end[0]:.2f},{end[1]:.2f})")
    pcbnew.SaveBoard(str(dst), b)


if __name__ == "__main__":
    r = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--radius=")), "3.5"))
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], pos[2], pos[3:], r)
