"""Staggered via fan-out of fine-pitch ICs before routing (6-layer board, one track direction per layer, 2026-11-21).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/qfn_fanout.py <in.kicad_pcb> <out.kicad_pcb> U1 U2 U8 [--rows=0.9,1.6,2.3]

Without a fan-out the routers fill the space in front of a 0.5 mm pitch pin row with vias of other nets and the
last pins of a row find no escape (USBST_D_N at U1/U8). Here, for every pad of the given footprints that carries a
signal net and has no track yet: a straight escape on the pad's layer, out of the pin row (direction from the
footprint centre to the pad, snapped to x or y), to a via. Neighbouring pins alternate between the via rows --rows
(distance from the pad centre, mm): first the rows each pin could use are found, then the pins with the fewest
options are placed first (a pin squeezed between a capacitor pad and its neighbours keeps its only row). Every via and escape
keeps all clearances on all layers (manhattan.Fast with the inner layers, NPTH holes). Escapes and vias are LOCKED
so that hv_route.py (which strips unlocked tracks) keeps them; the router then starts from the vias.
Pads of the plane nets (GND, +3V3, VCC: own plane via already), exposed pads and pads that already have copper are
left alone.
"""
import math, sys

import pcbnew

from bekantx_layout import MM, P, add_via, unP
from manhattan import Fixer
from pcb_geom import bbox_mm, net_width, uid

VIA, DRILL = 0.5, 0.3
PLANE = {"GND", "+3V3", "VCC"}


def main(src, dst, refs, rows):
    b = pcbnew.LoadBoard(str(src))
    fx = Fixer(b)
    cu = fx.cu
    inner = [l for l in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu) if b.IsLayerEnabled(l)]
    tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
    done, failed, todo = 0, [], []
    for ref in refs:
        fp = b.FindFootprintByReference(ref)
        fc = unP(fp.GetPosition())
        pads = [p for p in fp.Pads() if p.GetNetname() and p.GetNetname() not in PLANE and not p.HasHole()
                and not p.GetNetname().startswith("unconnected-")]
        sz = lambda p: (pcbnew.ToMM(p.GetSize().x), pcbnew.ToMM(p.GetSize().y))
        # exposed pad = the biggest pad near the centre: skip
        pads = [p for p in pads if math.dist(unP(p.GetPosition()), fc) > 0.8]
        # order along each side so that neighbours alternate rows
        side_of = {}
        for p in pads:
            c = unP(p.GetPosition())
            dx, dy = c[0] - fc[0], c[1] - fc[1]
            side_of[uid(p)] = (1 if dx > 0 else -1, 0) if abs(dx) > abs(dy) else (0, 1 if dy > 0 else -1)
        for p in pads:
            c = unP(p.GetPosition())
            side = side_of[uid(p)]
            if any(t.IsLocked() and t.GetNetname() == p.GetNetname() and (p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd()))
                   for t in tracks):
                continue                      # already has a locked escape (hand-made)
            todo.append((ref, p, c, side))
    # rows each pin could use with the other fan-outs not yet placed; the pins with the fewest options go first,
    # so that a pin squeezed between a capacitor pad and its neighbours keeps its only row
    def try_row(p, c, side, d, apply):
        net = p.GetNetname()
        lay = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) and not p.IsOnLayer(pcbnew.B_Cu) else pcbnew.B_Cu
        w = min(net_width(net), 0.15)        # escape necked to the Default width (0.5 mm pitch)
        q = (round(c[0] + side[0] * d, 3), round(c[1] + side[1] * d, 3))
        if not (fx.hole_ok(c, q, w) and cu.seg_clear(c, q, w, net, lay)):
            return False
        if not cu.via_clear(q, VIA, DRILL, net, own_pad_gap=0.1):
            return False
        shape = pcbnew.SHAPE_CIRCLE(P(*q), MM(VIA / 2))
        if cu._hits(shape, (q[0] - VIA / 2, q[1] - VIA / 2, q[0] + VIA / 2, q[1] + VIA / 2), net, inner, set()) is not None:
            return False
        if apply:
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(P(*c)); t.SetEnd(P(*q)); t.SetWidth(MM(w)); t.SetLayer(lay); t.SetNet(b.FindNet(net))
            t.SetLocked(True)
            b.Add(t)
            cu.add_track(t)
            v = add_via(b, net, q, VIA, DRILL, locked=True)
            it = dict(obj=v, kind="via", net=net, layers=[pcbnew.F_Cu, pcbnew.B_Cu] + inner, box=bbox_mm(v), uid=uid(v))
            cu.items.append(it); cu._reg(it)
            cu.holes.append((q[0], q[1], DRILL / 2, v))
        return True

    opts = [(ref, p, c, side, [d for d in rows if try_row(p, c, side, d, False)]) for ref, p, c, side in todo]
    opts.sort(key=lambda o: len(o[4]))
    for ref, p, c, side, rs in opts:
        if not any(try_row(p, c, side, d, True) for d in rs):
            failed.append(f"{ref}.{p.GetNumber()} {p.GetNetname()}")
        else:
            done += 1
    pcbnew.SaveBoard(str(dst), b)
    print(f"fan-out vias: {done}; no room: {len(failed)} {failed}")


if __name__ == "__main__":
    r = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--rows=")), "0.9,1.6,2.3")
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], pos[2:], [float(x) for x in r.split(",")])
