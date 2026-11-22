"""Set pad escapes with a via for pads whose escape the routers could not find (dense 0.5 mm pin rows), one after
the other so that neighbouring escapes stagger (6-layer board, one track direction per layer, 2026-11-21).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/escape_vias.py <in.kicad_pcb> <out.kicad_pcb>
        REF.PIN:DIR [REF.PIN:DIR ...] [--ignore=NET,NET] [--lock]

DIR is the way out of the pin row (N, S, E, W, or A = away from the footprint centre). --lock locks the escapes
(hv_route.py keeps locked copper). For every pad, in the given order, the shortest escape is searched:
straight out 0.5..2.5 mm, then sideways or at 45 degrees (up to 2 mm) to a spot where a via of the net fits; all
clearances on all layers (manhattan.Fast with the inner layers, NPTH holes). Nets in --ignore do not count as
obstacles: they must be released and routed again afterwards (touchup_router.py --release=...). The escapes are pad
escapes in the sense of the direction rule (dir_fix.py keeps them). After this: touchup_router.py --hv ... routes the
rest from the new vias. Prints the escapes; a pad without escape is reported and skipped.
"""
import sys

import pcbnew

from bekantx_layout import MM, P, add_via, unP
from manhattan import Fixer
from pcb_geom import bbox_mm, uid

VIA, DRILL = 0.5, 0.3
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


def main(src, dst, specs, ignore, lock=False):
    b = pcbnew.LoadBoard(str(src))
    fx = Fixer(b)
    cu = fx.cu
    from pcb_geom import net_width
    skip = [o for o in b.GetTracks() if o.GetNetname() in ignore]
    inner = [l for l in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu) if b.IsLayerEnabled(l)]
    for spec in specs:
        ref, rest = spec.split(".", 1)
        pin, d = rest.split(":")
        fp = b.FindFootprintByReference(ref)
        pad = next(p for p in fp.Pads() if p.GetNumber() == pin)
        net, c, lay = pad.GetNetname(), unP(pad.GetPosition()), pad.GetLayer() if pad.IsOnLayer(pcbnew.B_Cu) is False else pcbnew.B_Cu
        if pad.IsOnLayer(pcbnew.F_Cu) and not pad.IsOnLayer(pcbnew.B_Cu):
            lay = pcbnew.F_Cu
        w = min(net_width(net), 0.15)        # escape necked to the Default width (0.5 mm pitch)
        if d == "A":                          # automatic: from the footprint centre to the pad, snapped to x or y
            fc = unP(fp.GetPosition())
            dx, dy = c[0] - fc[0], c[1] - fc[1]
            d = ("E" if dx > 0 else "W") if abs(dx) > abs(dy) else ("S" if dy > 0 else "N")
        u = DIRS[d]
        n = (-u[1], u[0])

        def path_ok(pts):
            if not all(fx.hole_ok(pts[k], pts[k + 1], w) and cu.seg_clear(pts[k], pts[k + 1], w, net, lay, skip=skip)
                       for k in range(len(pts) - 1)):
                return False
            q = pts[-1]
            if not cu.via_clear(q, VIA, DRILL, net, skip=skip, own_pad_gap=0.1):
                return False
            shape = pcbnew.SHAPE_CIRCLE(P(*q), MM(VIA / 2))
            return cu._hits(shape, (q[0] - VIA / 2, q[1] - VIA / 2, q[0] + VIA / 2, q[1] + VIA / 2), net, inner,
                            {uid(o) for o in skip}) is None

        cands = []
        for i1 in range(10, 51):
            d1 = i1 * 0.05
            k = (round(c[0] + u[0] * d1, 3), round(c[1] + u[1] * d1, 3))
            cands.append((d1, [c, k]))
            for i2 in range(-40, 41):
                d2 = i2 * 0.05
                if abs(d2) < 0.3:
                    continue
                cands.append((d1 + abs(d2), [c, k, (round(k[0] + n[0] * d2, 3), round(k[1] + n[1] * d2, 3))]))
                q = (round(k[0] + n[0] * d2 + u[0] * abs(d2), 3), round(k[1] + n[1] * d2 + u[1] * abs(d2), 3))
                cands.append((d1 + abs(d2) * 1.414, [c, k, q]))
        cands.sort(key=lambda x: x[0])
        pts = next((p for L, p in cands if L <= 4.0 and path_ok(p)), None)
        if pts is None:
            print(f"{spec} ({net}): no escape found")
            continue
        code = b.FindNet(net)
        for a, e in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(P(*a)); t.SetEnd(P(*e)); t.SetWidth(MM(w)); t.SetLayer(lay); t.SetNet(code)
            t.SetLocked(lock)
            b.Add(t)
            cu.add_track(t)
        v = add_via(b, net, pts[-1], VIA, DRILL, locked=lock)
        it = dict(obj=v, kind="via", net=net, layers=[pcbnew.F_Cu, pcbnew.B_Cu] + inner, box=bbox_mm(v), uid=uid(v))
        cu.items.append(it); cu._reg(it)
        cu.holes.append((pts[-1][0], pts[-1][1], DRILL / 2, v))
        print(f"{spec} ({net}): escape {pts}")
    pcbnew.SaveBoard(str(dst), b)


if __name__ == "__main__":
    ign = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--ignore=")), "")
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], pos[2:], set(ign.split(",")) - {""}, "--lock" in sys.argv)
