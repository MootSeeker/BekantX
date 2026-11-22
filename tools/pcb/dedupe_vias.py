"""Merge vias of one net that sit closer than the hole-to-hole distance (the grid router sometimes sets a plane via
next to an existing one; DRC: hole_to_hole).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/dedupe_vias.py <in.kicad_pcb> <out.kicad_pcb>

For every such pair the via with more attached track ends (locked first) stays; the track ends on the other via
move onto the kept one when the moved segment keeps all clearances (manhattan.Fast with the inner layers), then the
other via is removed. Pairs that cannot be merged are reported. Removal happens at the very end.
"""
import math, sys

import pcbnew

from bekantx_layout import P, unP
from manhattan import Fixer
from pcb_geom import uid

MIN_HOLE_GAP = 0.25


def main(src, dst):
    b = pcbnew.LoadBoard(str(src))
    fx = Fixer(b)
    cu = fx.cu
    vias = [v for v in b.GetTracks() if v.GetClass() == "PCB_VIA"]
    tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
    dead, merged, left = set(), 0, []

    def ends_at(v):
        return [(t, e) for t in tracks for e, q in (("a", t.GetStart()), ("b", t.GetEnd()))
                if t.GetNetname() == v.GetNetname() and v.HitTest(q)]

    for i, v in enumerate(vias):
        if uid(v) in dead:
            continue
        pv = unP(v.GetPosition())
        for w in vias[i + 1:]:
            if uid(w) in dead or w.GetNetname() != v.GetNetname():
                continue
            pw = unP(w.GetPosition())
            gap = math.dist(pv, pw) - (pcbnew.ToMM(v.GetDrillValue()) + pcbnew.ToMM(w.GetDrillValue())) / 2
            if gap >= MIN_HOLE_GAP:
                continue
            ev, ew = ends_at(v), ends_at(w)
            keep, drop, ed = (v, w, ew) if (v.IsLocked(), len(ev)) >= (w.IsLocked(), len(ew)) else (w, v, ev)
            pk = unP(keep.GetPosition())
            ok = True
            for t, e in ed:
                other = unP(t.GetEnd()) if e == "a" else unP(t.GetStart())
                if not cu.seg_clear(other, pk, pcbnew.ToMM(t.GetWidth()), t.GetNetname(), t.GetLayer(), skip=[t, drop, keep]):
                    ok = False
            if not ok or drop.IsLocked():
                left.append((v.GetNetname(), pv, pw))
                continue
            for t, e in ed:
                cu.drop_track(t)
                (t.SetStart if e == "a" else t.SetEnd)(P(*pk))
                cu.add_track(t)
            dead.add(uid(drop))
            merged += 1
            if drop is v:
                break
    for v in vias:
        if uid(v) in dead:
            b.Remove(v)
    pcbnew.SaveBoard(str(dst), b)
    print(f"vias merged: {merged}; left: {len(left)}")
    for n, a, c in left:
        print(f"  {n} ({a[0]:.2f},{a[1]:.2f}) / ({c[0]:.2f},{c[1]:.2f})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
