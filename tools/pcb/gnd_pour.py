"""Make the outer GND pours less fragmented and tie every piece to the GND plane (layout rule 2026-11-19: "GND-Plane
ist sehr zerstueckelt, versuchen, das zu verbessern auf dem Bottom").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/gnd_pour.py <in.kicad_pcb> <out.kicad_pcb>

1. Pour clearance of "GND top" / "GND bottom" 0.3 -> 0.2 mm (the net class clearance still counts where it is
   larger, e.g. LIN, PowerHV): the pour reaches into the lanes between bus tracks and joins pieces.
2. Every piece of the outer pours gets stitching vias to In2: one from 1.5 mm2, two from 8 mm2, one more per
   25 mm2. New vias go where they are farthest from the vias already in the piece and keep every clearance.
3. Pieces too small for a via (slivers between pads) are reported; they hang on a pad by its thermal spokes.
Zones are refilled at the start and at the end.
"""
import math, sys

import pcbnew

from bekantx_layout import MM, P, add_via, unP
from pcb_geom import Copper, on_plane, plane_fill

POURS = ("GND bottom", "GND top")
CLEARANCE = 0.2
VIA, DRILL = 0.6, 0.3
STEP = 0.25


def wanted(area):
    if area < 1.5:
        return 0
    return (1 if area < 8 else 2) + int(area // 25)


def pieces(board):
    out = []
    for z in board.Zones():
        if z.GetZoneName() in POURS:
            lay = z.GetFirstLayer()
            f = z.GetFilledPolysList(lay)
            for i in range(f.OutlineCount()):
                ps = pcbnew.SHAPE_POLY_SET()
                ps.AddOutline(f.Outline(i))
                for h in range(f.HoleCount(i)):
                    ps.AddHole(f.Hole(i, h))
                out.append((z.GetZoneName(), lay, ps, f.Outline(i).Area() / 1e12))
    return out


def main(src, dst):
    board = pcbnew.LoadBoard(str(src))
    for z in board.Zones():
        if z.GetZoneName() in POURS:
            z.SetLocalClearance(MM(CLEARANCE))
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    cu = Copper(board)
    gnd_plane = plane_fill(board, "GND")
    gvias = [unP(t.GetPosition()) for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    added, short, slivers = 0, [], 0
    for name, lay, ps, area in sorted(pieces(board), key=lambda r: -r[3]):
        need = wanted(area)
        if need == 0:
            slivers += 1
            continue
        have = [v for v in gvias if ps.Contains(P(*v))]
        if len(have) >= need:
            continue
        bb = ps.BBox()
        x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
        x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        cand = []
        for i in range(int((x1 - x0) / STEP) + 1):
            for j in range(int((y1 - y0) / STEP) + 1):
                q = (x0 + i * STEP, y0 + j * STEP)
                ring = [q] + [(q[0] + (VIA / 2 + 0.05) * math.cos(a), q[1] + (VIA / 2 + 0.05) * math.sin(a))
                              for a in [k * math.pi / 4 for k in range(8)]]
                if all(ps.Contains(P(*r)) for r in ring):
                    cand.append(q)
        n = len(have)
        while n < need and cand:
            ref = have or [((x0 + x1) / 2, (y0 + y1) / 2)]
            cand.sort(key=lambda q: -min(math.dist(q, h) for h in ref))
            for k, q in enumerate(cand):
                if min(math.dist(q, h) for h in ref) < 1.2 and have:
                    cand = []
                    break
                if on_plane(gnd_plane, q, VIA / 2 + 0.1) and cu.via_clear(q, VIA, DRILL, "GND", own_pad_gap=0.1):
                    add_via(board, "GND", q, VIA, DRILL, locked=False)
                    cu.refresh()
                    have.append(q); gvias.append(q)
                    n += 1; added += 1
                    cand = cand[k + 1:]
                    break
            else:
                cand = []
        if n < need:
            c = unP(bb.Centre())
            short.append(f"{name} {area:.1f} mm2 at {c[0]:.1f},{c[1]:.1f}: {n}/{need}")
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(str(dst), board)
    print(f"stitching vias added: {added}; pieces under 1.5 mm2 (no via): {slivers}")
    for s in short:
        print("  short of vias:", s)
    res = {}
    for name, lay, ps, area in pieces(board):
        res.setdefault(name, []).append(area)
    for name, a in res.items():
        print(f"{name}: {len(a)} pieces, main {max(a):.0f} mm2, total {sum(a):.0f} mm2")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
