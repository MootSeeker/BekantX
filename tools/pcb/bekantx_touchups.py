"""Hand touch-ups after chamfer_corners.py: three spots where routers left knots of 0.05 mm pieces that no rule-based
step can clean up (2026-11-19).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_touchups.py <in.kicad_pcb> <out.kicad_pcb>

Every edit names the exact segments (net, layer, end points) it expects and stops if they are not there, so a
changed layout is never edited blindly.
1. USBESP_D_P at U8 pin 3: two B.Cu pieces form a small loop next to the via (the via is reached anyway): removed.
2. LINBUS at D7: a T junction followed by a 0.04 mm step and a 90 degree turn: the branch to D7 starts at the T.
3. +3.3VA at U2 pins 2/3: the branch from pin 2 met the path from pin 3 at a 90 degree corner 0.05 mm before the
   path turned: the turn starts at the meeting point now (a clean three-way junction).

With --late (after the partial re-route, before bekantx_silk.py; review 2026-11-19):
4. Zero-length segments are removed (all nets).
5. FSPI_MISO at U2: the horizontal piece ran 0.05 mm past the start of the diagonal (a 45 degree spike): it ends
   where the diagonal starts.
6. The hole of the GND via of U9 pin 2 lay in the pad's mask opening (solder wicking): the via moves down until
   the hole is outside the opening (a full 0.1 mm gap does not fit, USBESP_D_P runs below on F.Cu).
"""
import math, sys

import pcbnew

from bekantx_layout import P, unP

TOL = 0.005


def find(board, net, layer, a, b):
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() != net or t.GetLayer() != layer:
            continue
        s, e = unP(t.GetStart()), unP(t.GetEnd())
        if (math.dist(s, a) < TOL and math.dist(e, b) < TOL) or (math.dist(s, b) < TOL and math.dist(e, a) < TOL):
            return t
    raise SystemExit(f"touch-up: segment {net} {a} - {b} not found; the layout changed, check the spot by hand")


def move(t, old, new):
    if math.dist(unP(t.GetStart()), old) < TOL:
        t.SetStart(P(*new))
    else:
        t.SetEnd(P(*new))


def late(src, dst):
    from pcb_geom import Copper
    board = pcbnew.LoadBoard(str(src))
    B = pcbnew.B_Cu
    dead = [tr for tr in board.GetTracks() if tr.GetClass() == "PCB_TRACK" and pcbnew.ToMM(tr.GetLength()) < 0.001]
    h = find(board, "FSPI_MISO", B, (12.61, 21.45), (12.95, 21.45))
    move(h, (12.95, 21.45), (12.9, 21.45))
    pad = board.FindFootprintByReference("U9").FindPadByNumber("2")
    old = (100.5, 25.94)
    via = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == "GND"
           and math.dist(unP(v.GetPosition()), old) < TOL]
    if not via:
        raise SystemExit("touch-up: GND via of U9 pin 2 not found")
    via = via[0]
    r = pcbnew.ToMM(via.GetWidth(pcbnew.F_Cu)) / 2
    edge = unP(pad.GetPosition())[1] + pcbnew.ToMM(pad.GetBoundingBox().GetHeight()) / 2
    cu = Copper(board)
    new = None
    # A whole via 0.1 mm below the pad does not fit (USBESP_D_P runs on F.Cu right below, R42 below that). The via
    # moves down until its hole lies outside the solder mask opening of the pad (pad edge + 0.05 mm expansion
    # + 0.02 mm): the ring still touches the pad (same net), but no solder can run into the hole.
    drill = pcbnew.ToMM(via.GetDrillValue())
    lo = edge + 0.05 + 0.02 + drill / 2
    for k in range(12, -1, -1):
        q = (old[0], round(lo + 0.01 * k, 3))
        if cu.via_clear(q, 2 * r, drill, "GND", skip=[via], own_pad_gap=None):
            new = q
            break
    if new is None:
        raise SystemExit("touch-up: no room for the U9 pin 2 via below the pad")
    stubs = [tr for tr in board.GetTracks() if tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == "GND"
             and min(math.dist(unP(tr.GetStart()), old), math.dist(unP(tr.GetEnd()), old)) < TOL]
    for tr in stubs:
        if not cu.seg_clear(unP(tr.GetStart()) if math.dist(unP(tr.GetEnd()), old) < TOL else new,
                            new if math.dist(unP(tr.GetEnd()), old) < TOL else unP(tr.GetEnd()),
                            pcbnew.ToMM(tr.GetWidth()), "GND", tr.GetLayer()):
            raise SystemExit("touch-up: the stub to the U9 pin 2 via would violate a clearance")
        move(tr, old, new)
    via.SetPosition(P(*new))
    for tr in dead:                            # removals last: pcbnew proxies break after Remove()
        board.Remove(tr)
    pcbnew.SaveBoard(str(dst), board)
    print(f"late touch-ups: {len(dead)} zero-length segments removed, FSPI_MISO spike, U9.2 via {old} -> {new}")


def main(src, dst):
    board = pcbnew.LoadBoard(str(src))
    B = pcbnew.B_Cu
    dead = []
    # 1. loop next to the via of USBESP_D_P
    dead.append(find(board, "USBESP_D_P", B, (111.85, 25.65), (112.0, 25.65)))
    dead.append(find(board, "USBESP_D_P", B, (112.0, 25.65), (112.0, 25.6)))
    # 2. LINBUS branch to D7 pin 2
    step = find(board, "LINBUS", B, (66.753, 14.996), (66.797, 14.996))
    tee = min((unP(step.GetStart()), unP(step.GetEnd())), key=lambda q: q[0])     # exact, not the rounded value
    dead.append(step)
    v = find(board, "LINBUS", B, (66.797, 14.996), (66.797, 15.546))
    d = find(board, "LINBUS", B, (66.797, 15.546), (67.25, 16.0))
    knee = (tee[0], 16.0 - (67.25 - tee[0]))
    move(v, (66.797, 14.996), tee)
    move(v, (66.797, 15.546), knee)
    move(d, (66.797, 15.546), knee)
    # 3. +3.3VA at U2 pins 2/3
    diag = find(board, "+3.3VA", B, (12.95, 23.05), (12.6, 22.7))
    up = find(board, "+3.3VA", B, (12.6, 22.7), (12.6, 22.5))
    move(diag, (12.95, 23.05), (12.9, 23.05))
    move(diag, (12.6, 22.7), (12.6, 22.75))
    move(up, (12.6, 22.7), (12.6, 22.75))
    for t in dead:                             # removals last: pcbnew proxies break after Remove()
        board.Remove(t)
    pcbnew.SaveBoard(str(dst), board)
    print(f"touch-ups: 3 spots, {len(dead)} segments removed")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    (late if "--late" in sys.argv else main)(a[0], a[1])
