"""Two hand fixes for relics left by the scripted 6-layer routing (2026-11-21), with checked coordinates.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_relic_fixes.py <in.kicad_pcb> <out.kicad_pcb>

1. BTN_5 at U1.2: the copied old escape left a dead branch (59.15,30.65)-(59.15,30.81)-(59.29,30.95)-(59.70,30.95)
   (doubled first piece, its via already gone); the real route runs past it. The branch is removed.
2. +3.3VA at U2.2/U2.3: three tracks met only by overlapping a via that joins nothing on another layer. Their ends
   now meet at the via centre (11.95, 23.55) and the via goes. The new pieces lie inside the old via copper.
3. BTN_5 in front of its via at (60.84, 30.39): a knot of five short pieces (a dead end, a 90 degree corner) becomes
   one 45 degree piece and the straight run to the via (clearance checked).
Coordinates are board mm; the script aborts if the geometry is not as expected.
"""
import math, sys

import pcbnew

from bekantx_layout import P, unP


def seg_is(t, a, b, tol=0.003):
    s, e = unP(t.GetStart()), unP(t.GetEnd())
    return (math.dist(s, a) < tol and math.dist(e, b) < tol) or (math.dist(s, b) < tol and math.dist(e, a) < tol)


def main(src, dst):
    brd = pcbnew.LoadBoard(str(src))
    tracks = [t for t in brd.GetTracks() if t.GetClass() == "PCB_TRACK"]
    dead = []
    # 1. BTN_5 branch
    branch = [((59.15, 30.65), (59.15, 30.81)), ((59.15, 30.81), (59.29, 30.95)), ((59.29, 30.95), (59.7, 30.95))]
    for a, b in branch:
        hit = [t for t in tracks if t.GetNetname() == "BTN_5" and seg_is(t, a, b)]
        if not hit:
            sys.exit(f"BTN_5 piece {a}-{b} not found: layout changed")
        dead += hit
    # 2. +3.3VA junction
    c = (11.95, 23.55)
    via = next((v for v in brd.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == "+3.3VA"
                and math.dist(unP(v.GetPosition()), c) < 0.003), None)
    vert = next((t for t in tracks if t.GetNetname() == "+3.3VA" and seg_is(t, (11.95, 23.35), (11.95, 23.15))), None)
    l1 = next((t for t in tracks if t.GetNetname() == "+3.3VA" and seg_is(t, (10.95, 23.65), (11.75, 23.65))), None)
    if not (via and vert and l1):
        sys.exit("+3.3VA junction not as expected: layout changed")
    vert.SetStart(P(11.95, 23.05)); vert.SetEnd(P(*c))          # from the centre line of the 0.3 mm track to the centre
    l1.SetStart(P(10.95, 23.65)); l1.SetEnd(P(11.85, 23.65))   # then 45 degrees into the centre (no 90 degree corner)
    t = pcbnew.PCB_TRACK(brd)
    t.SetStart(P(11.85, 23.65)); t.SetEnd(P(*c)); t.SetWidth(l1.GetWidth()); t.SetLayer(l1.GetLayer()); t.SetNet(l1.GetNet())
    brd.Add(t)
    dead.append(via)
    # 3. BTN_5: the knot of short pieces in front of the via (one dead end, one 90 degree corner) becomes one
    #    45 degree piece and the straight run to the via
    knot = [((59.123, 30.629), (59.15, 30.629)), ((59.15, 30.629), (59.15, 30.65)), ((59.15, 30.594), (59.15, 30.629)),
            ((59.35, 30.394), (59.15, 30.594)), ((59.35, 30.394), (60.841, 30.394))]
    pieces = []
    for a, b in knot:
        hit = [t for t in tracks if t.GetNetname() == "BTN_5" and seg_is(t, a, b) and t not in dead]
        if not hit:
            sys.exit(f"BTN_5 piece {a}-{b} not found: layout changed")
        pieces.append(hit[0])
    from manhattan import Fixer
    cu = Fixer(brd).cu
    w = pcbnew.ToMM(pieces[0].GetWidth())
    q = (59.358, 30.394)
    for a, b in (((59.123, 30.629), q), (q, (60.841, 30.394))):
        if not cu.seg_clear(a, b, w, "BTN_5", pcbnew.B_Cu, skip=pieces):
            sys.exit(f"BTN_5 new piece {a}-{b} not clear")
    pieces[0].SetStart(P(59.123, 30.629)); pieces[0].SetEnd(P(*q))
    pieces[4].SetStart(P(*q)); pieces[4].SetEnd(P(60.841, 30.394))
    dead += pieces[1:4]
    for x in dead:
        brd.Remove(x)
    pcbnew.SaveBoard(str(dst), brd)
    print(f"BTN_5: {len(dead) - 1} dead branch pieces removed; +3.3VA: ends joined at {c}, via removed")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
