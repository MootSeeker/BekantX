"""Hand fixes after the 6-layer re-route (2026-11-21), with checked coordinates.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_six_fixes.py <in.kicad_pcb> <out.kicad_pcb>

1. +12V: Freerouting laid a B.Cu run along the bottom edge (y 37.319) whose 0.8 mm via ends 0.28 mm from the edge
   (rule 0.3). The run, its via and the end of the F.Cu track on that via move up to y 37.26 (both stay straight);
   the via loses its unused inner-layer rings (it only joins F.Cu and B.Cu) so it keeps 0.2 mm to an In2 track.
2. VCC_SPI: an In2 track runs over pad 1 of C14 (B.Cu) without a via; the grid router took that for a connection.
   A via on the In2 line next to the pad and a short horizontal B.Cu stub from the pad join them.
Every change is checked for clearance (manhattan.Fast with the inner layers); a fix that does not fit aborts.
"""
import math, sys

import pcbnew

from bekantx_layout import MM, P, add_via, unP
from manhattan import Fixer


def main(src, dst):
    b = pcbnew.LoadBoard(str(src))
    fx = Fixer(b)
    cu = fx.cu
    # 1. +12V near the bottom edge
    y0, y1 = 37.319, 37.26
    moved = 0
    items = [t for t in b.GetTracks() if t.GetNetname() == "+12V"]
    via = next((v for v in items if v.GetClass() == "PCB_VIA" and abs(unP(v.GetPosition())[1] - y0) < 0.002), None)
    if via is None:
        sys.exit("+12V via at y 37.319 not found: layout changed")
    vx = unP(via.GetPosition())[0]
    plan = []
    for t in items:
        if t.GetClass() == "PCB_VIA":
            continue
        a, c = unP(t.GetStart()), unP(t.GetEnd())
        na = (a[0], y1) if abs(a[1] - y0) < 0.002 else a
        nc = (c[0], y1) if abs(c[1] - y0) < 0.002 else c
        if na != a or nc != c:
            plan.append((t, na, nc))
    for t, na, nc in plan:
        if not cu.seg_clear(na, nc, pcbnew.ToMM(t.GetWidth()), "+12V", t.GetLayer(), skip=[t, via] + [p[0] for p in plan]):
            sys.exit(f"+12V: moved track {na}-{nc} not clear")
    if not cu.via_clear((vx, y1), pcbnew.ToMM(via.GetWidth(pcbnew.F_Cu)), pcbnew.ToMM(via.GetDrillValue()), "+12V",
                        skip=[via] + [p[0] for p in plan], own_pad_gap=0.05):
        sys.exit("+12V: moved via not clear")
    for t, na, nc in plan:
        t.SetStart(P(*na)); t.SetEnd(P(*nc))
        moved += 1
    via.SetPosition(P(vx, y1))
    # the via connects F.Cu and B.Cu only: without its unused inner rings it keeps the clearance to the In2 track
    via.SetRemoveUnconnected(True)
    print(f"+12V: via and {moved} track ends moved from y {y0} to {y1}, unused inner rings removed")
    # 2. VCC_SPI at C14.1
    pad = next(p for p in b.FindFootprintByReference("C14").Pads() if p.GetNumber() == "1")
    pc = unP(pad.GetPosition())
    if math.dist(pc, (21.75, 21.05)) > 0.01 or pad.GetNetname() != "VCC_SPI":
        sys.exit("C14.1 not where expected: layout changed")
    line = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "VCC_SPI"
            and t.GetLayer() == pcbnew.In2_Cu and abs(unP(t.GetStart())[1] - pc[1]) < 0.002 and abs(unP(t.GetEnd())[1] - pc[1]) < 0.002]
    if not line:
        sys.exit("VCC_SPI In2 line at y 21.05 not found")
    xs = sorted(x for t in line for x in (unP(t.GetStart())[0], unP(t.GetEnd())[0]))
    w = pcbnew.ToMM(line[0].GetWidth())
    # on the line, or up to 0.5 mm beyond its east end (the line is then extended horizontally on In2)
    spots = [(round(pc[0] + sgn * k * 0.05, 3), pc[1]) for k in range(10, 40) for sgn in (1, -1)]
    spots += [(round(xs[-1] + k * 0.05, 3), pc[1]) for k in range(0, 11)]
    for q in sorted(spots, key=lambda q: abs(q[0] - pc[0])):
            if not (xs[0] - 1e-6 <= q[0] <= xs[-1] + 0.5 + 1e-6) or abs(q[0] - pc[0]) < 0.5:
                continue
            ext = (q[0] > xs[-1] + 1e-6)
            if ext and not cu.seg_clear((xs[-1], pc[1]), q, w, "VCC_SPI", pcbnew.In2_Cu):
                continue
            sh = pcbnew.SHAPE_CIRCLE(P(*q), MM(0.25))
            inner_ok = cu._hits(sh, (q[0] - 0.25, q[1] - 0.25, q[0] + 0.25, q[1] + 0.25), "VCC_SPI",
                                [pcbnew.In2_Cu, pcbnew.In3_Cu], set()) is None
            if inner_ok and cu.via_clear(q, 0.5, 0.3, "VCC_SPI", own_pad_gap=0.05) and cu.seg_clear(pc, q, w, "VCC_SPI", pcbnew.B_Cu):
                add_via(b, "VCC_SPI", q, 0.5, 0.3, locked=False)
                if ext:
                    e = pcbnew.PCB_TRACK(b)
                    e.SetStart(P(xs[-1], pc[1])); e.SetEnd(P(*q)); e.SetWidth(MM(w)); e.SetLayer(pcbnew.In2_Cu); e.SetNet(pad.GetNet())
                    b.Add(e)
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(P(*pc)); t.SetEnd(P(*q)); t.SetWidth(MM(w)); t.SetLayer(pcbnew.B_Cu); t.SetNet(pad.GetNet())
                b.Add(t)
                print(f"VCC_SPI: via at {q}, B.Cu stub from C14.1")
                pcbnew.SaveBoard(str(dst), b)
                return
    sys.exit("VCC_SPI: no via spot on the In2 line next to C14.1")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
