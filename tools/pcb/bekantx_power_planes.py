"""Split In1 into a VCC area and the +3V3 plane, and remove the VCC and redundant +3V3 tracks (PR #5 feedback).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_power_planes.py <in.kicad_pcb> <out.kicad_pcb>

Feedback on PR #5 (2026-11-18): the VCC tracks on B.Cu are a mess, use part of an inner plane for VCC; +3V3 is
already the In1 plane, but the touch-up router had laid +3V3 tracks between plane vias, which look like extra
layer changes.

- In1: VCC zone (priority 1) over the power area where all 17 VCC pads are; the +3V3 plane (priority 0) flows
  around it along the top and right board edge and stays one piece. In2 stays a solid GND plane.
  The VCC area leaves out the +3V3 pads next to it (C42, D1, R35) and has a +3V3 tongue for the via of D5.
- All VCC tracks are removed except the two short, hand-placed input-loop tracks (U20 pin 5 - C25,
  C15 - U9 pin 5), which are placed again. Every VCC pad gets a via into the VCC area, the larger pads two.
- All unlocked +3V3 tracks and vias (laid by the touch-up router) are removed; +3V3 pads that are left without
  a plane connection get their own via.
Afterwards: touch-up router for what is still open, bekantx_finish.py, DRC.
"""
import json, math, subprocess, sys
from pathlib import Path

import pcbnew

from bekantx_layout import P, add_track, add_zone, drop_plane_vias, unP
from bekantx_rework import dangling, inside

ROOT = Path(__file__).resolve().parents[2]

# VCC area on In1, board coordinates (x right, y down), clockwise
# - the notch at x 96.4..98.6 lets a 2.2 mm +3V3 tongue reach the via of the front LED D5 (its pad 2 is enclosed
#   on F.Cu by the tracks of the other two cathodes; the via between the pads is the only way out)
# - the lower edges keep at least 1 mm from the F.Cu track of USBST_D_N (y 22.0 for x 93..105, y 24.1 for
#   x 107..119), so that it crosses the split only at right angles (review 2026-11-18, Major)
VCC_AREA = [(84.0, 7.0), (96.4, 7.0), (96.4, 10.4), (98.6, 10.4), (98.6, 7.0), (121.0, 7.0), (121.0, 23.0),
            (108.5, 23.0), (108.5, 21.0), (104.6, 21.0), (104.6, 23.3), (95.5, 23.3), (95.5, 26.3), (86.5, 26.3),
            (86.5, 33.3), (80.5, 33.3), (80.5, 24.0), (84.0, 24.0)]
# test point TP10 (VCC) moves into the VCC area (move_test_point): at its old place it needed a notch that the USB
# track crossed
BIG_VCC_PADS = {("D4", "1"), ("D3", "1"), ("C40", "1"), ("C50", "1"), ("C51", "1"), ("C52", "1"),
                ("C24", "1"), ("C25", "1"), ("C15", "1")}


def in_poly(p, poly):
    """Point in polygon (even-odd)."""
    x, y = p
    c = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def move_test_point(board, items, ref):
    """Move a VCC test point on B.Cu to the free spot inside the VCC area that is closest to D3 (the USB side of
    the input). Free: courtyard 0.15 mm from other B courtyards and THT pads, pad (r 0.5) 0.3 mm from copper
    of other nets, 1.2 mm inside the area for its via."""
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        return
    pos = unP(fp.GetPosition())
    bb = fp.GetCourtyard(pcbnew.B_CrtYd).BBox()
    cx0, cy0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
    cx1, cy1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
    hx, hy = (cx1 - cx0) / 2 + 0.15, (cy1 - cy0) / 2 + 0.15
    boxes = []
    for o in board.GetFootprints():
        if o.GetReference() == ref:
            continue
        if o.IsFlipped():
            b2 = o.GetCourtyard(pcbnew.B_CrtYd).BBox()
            if b2.GetWidth() > 0:
                boxes.append(unP(pcbnew.VECTOR2I(b2.GetLeft(), b2.GetTop())) + unP(pcbnew.VECTOR2I(b2.GetRight(), b2.GetBottom())))
        for p in o.Pads():
            if p.HasHole():
                b2 = p.GetBoundingBox()
                boxes.append(unP(pcbnew.VECTOR2I(b2.GetLeft(), b2.GetTop())) + unP(pcbnew.VECTOR2I(b2.GetRight(), b2.GetBottom())))
    copper = [it for it in items if it["net"] != "VCC" and (it["kind"] == "v" or it["layer"] == pcbnew.B_Cu)]

    def free(x, y):
        if not in_poly((x, y), VCC_AREA) or any(not in_poly((x + dx, y + dy), VCC_AREA)
                                                for dx, dy in ((1.2, 0), (-1.2, 0), (0, 1.2), (0, -1.2))):
            return False
        if any(x - hx < b[2] and b[0] < x + hx and y - hy < b[3] and b[1] < y + hy for b in boxes):
            return False
        for it in copper:
            if it["kind"] == "v":
                if math.dist((x, y), it["p"]) < 0.5 + it["r"] + 0.3:
                    return False
            else:
                ax, ay = it["a"]
                bx, by = it["b"]
                l2 = (bx - ax) ** 2 + (by - ay) ** 2
                u = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / l2))
                if math.hypot(x - ax - u * (bx - ax), y - ay - u * (by - ay)) < 0.5 + it["w"] / 2 + 0.3:
                    return False
        return True

    target = (114.0, 19.0)
    spots = [(108.5 + i * 0.25, 8.0 + j * 0.25) for i in range(51) for j in range(57)]
    spots.sort(key=lambda q: math.dist(q, target))
    for x, y in spots:
        if free(x, y):
            dx, dy = x - (cx0 + cx1) / 2, y - (cy0 + cy1) / 2
            fp.SetPosition(P(pos[0] + dx, pos[1] + dy))
            print(f"{ref} moved from {pos[0]:.2f}, {pos[1]:.2f} to {pos[0] + dx:.2f}, {pos[1] + dy:.2f}")
            return
    print(f"{ref}: no free spot in the VCC area, left where it is")


def phase1(src, dst):
    """Remove on a Python copy first (pcbnew proxies break after board.Remove())."""
    board = pcbnew.LoadBoard(str(src))
    objs = list(board.GetTracks())
    items = []
    for t in objs:
        if t.GetClass() == "PCB_VIA":
            items.append(dict(kind="v", net=t.GetNetname(), layer=None, p=unP(t.GetPosition()),
                              r=pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, locked=t.IsLocked()))
        else:
            items.append(dict(kind="t", net=t.GetNetname(), layer=t.GetLayer(), a=unP(t.GetStart()), b=unP(t.GetEnd()),
                              w=pcbnew.ToMM(t.GetWidth()), locked=t.IsLocked()))
    move_test_point(board, items, "TP10")
    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            lay = {pcbnew.F_Cu, pcbnew.B_Cu} if p.HasHole() else {pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu}
            pads.append(((x0, y0, x1, y1), p.GetNetname(), lay))
    gone = {i for i, it in enumerate(items)
            if it["net"] == "VCC" or (it["net"] == "+3V3" and not it["locked"])}
    # +3V3 vias inside the VCC area would no longer reach the +3V3 plane: remove them with the stubs ending there
    dead_vias = [it["p"] for it in items if it["kind"] == "v" and it["net"] == "+3V3" and in_poly(it["p"], VCC_AREA)]
    for i, it in enumerate(items):
        if it["net"] != "+3V3":
            continue
        pts = [it["p"]] if it["kind"] == "v" else [it["a"], it["b"]]
        if any(math.dist(q, v) < 0.35 for q in pts for v in dead_vias):
            gone.add(i)
    print("+3V3 vias inside the VCC area:", len(dead_vias))
    n0 = len(gone)
    gone = dangling(items, pads, gone)
    print(f"removed: {n0} VCC / unlocked +3V3 tracks and vias, {len(gone) - n0} dangling")
    for i in sorted(gone):
        board.Remove(objs[i])
    tmp = Path(dst).with_name("planes_phase1.kicad_pcb")
    pcbnew.SaveBoard(str(tmp), board)
    raise SystemExit(subprocess.run([sys.executable, __file__, "--phase2", str(tmp), str(dst)]).returncode)


def unplaned_pads(board, net, via_ok):
    """(ref, pad number) of the SMD pads of `net` whose copper (pads, tracks, vias, by touching geometry) has no via
    for which via_ok(x, y) is true, i.e. no via that reaches the plane of the net."""
    nodes = []                                          # (kind, geometry, key)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net:
                bb = p.GetBoundingBox()
                r = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())) + unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
                nodes.append(("p", r, (fp.GetReference(), p.GetNumber()), p.HasHole()))
    for t in board.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.GetClass() == "PCB_VIA":
            nodes.append(("v", unP(t.GetPosition()) + (pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2,), None, True))
        else:
            nodes.append(("t", unP(t.GetStart()) + unP(t.GetEnd()) + (pcbnew.ToMM(t.GetWidth()) / 2,), None, False))
    par = list(range(len(nodes)))
    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    def pts(n):
        k, g = n[0], n[1]
        if k == "p":
            return [((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)]
        if k == "v":
            return [g[:2]]
        return [g[:2], g[2:4]]
    def touch(a, b):
        for q in pts(a):
            k, g = b[0], b[1]
            if k == "p" and inside(q, (g[0] - 0.01, g[1] - 0.01, g[2] + 0.01, g[3] + 0.01)):
                return True
            if k == "v" and math.dist(q, g[:2]) <= g[2]:
                return True
            if k == "t":
                ax, ay, bx, by = g[:4]
                l2 = (bx - ax) ** 2 + (by - ay) ** 2
                u = 0 if l2 == 0 else max(0, min(1, ((q[0] - ax) * (bx - ax) + (q[1] - ay) * (by - ay)) / l2))
                if math.hypot(q[0] - ax - u * (bx - ax), q[1] - ay - u * (by - ay)) <= 0.01:
                    return True
        return False
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if touch(nodes[i], nodes[j]) or touch(nodes[j], nodes[i]):
                par[find(i)] = find(j)
    good = {find(i) for i, n in enumerate(nodes) if n[0] == "v" and via_ok(*n[1][:2])}
    # a through-hole pad reaches the plane by itself
    good |= {find(i) for i, n in enumerate(nodes) if n[0] == "p" and n[3]}
    return {n[2] for i, n in enumerate(nodes) if n[0] == "p" and not n[3] and find(i) not in good}


def phase2(src, dst):
    iface = json.loads((ROOT / "CAD" / "board_interface.json").read_text(encoding="utf-8"))
    board = pcbnew.LoadBoard(str(src))
    pad = lambda r, num: unP([p for p in board.FindFootprintByReference(r).Pads() if p.GetNumber() == str(num)][0].GetPosition())

    # VCC area on In1 above the +3V3 plane
    z = add_zone(board, "VCC", pcbnew.In1_Cu, VCC_AREA, "VCC area", prio=1, solid=True)

    # the two short input-loop tracks (as in bekantx_rework.py)
    B = pcbnew.B_Cu
    vin, c25v = pad("U20", 5), pad("C25", 1)
    add_track(board, "VCC", [vin, (vin[0], c25v[1] + 0.9), c25v], 0.5, B)
    c15v, u9vin = pad("C15", 1), pad("U9", 5)
    add_track(board, "VCC", [(c15v[0] + 0.35, c15v[1] - 0.3), (c15v[0] + 1.0, u9vin[1] - 1.24),
                             (u9vin[0], u9vin[1] - 1.24), u9vin], 0.5, B)

    # one via per VCC pad inside the area, a second one on the larger pads
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for x, y in VCC_AREA:
        poly.Append(P(x, y).x, P(x, y).y)
    # U20 pin 5 gets no via of its own: it is tied to C25 by the input-loop track, and C25 has two (a via there
    # would sit in the pad, review 2026-11-18)
    vcc_refs = {fp.GetReference() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == "VCC"} - {"U20"}
    in_area = lambda x, y: in_poly((x, y), VCC_AREA)
    n1, f1 = drop_plane_vias(board, iface, nets=("VCC",), only=tuple(vcc_refs), via=0.6, drill=0.3, clearance=0.3,
                             allowed=in_area)
    big = {(r, n) for r, n in BIG_VCC_PADS}
    n2, f2 = drop_plane_vias(board, iface, nets=("VCC",), only=tuple(r for r, _ in big), pads_only=big,
                             via=0.6, drill=0.3, clearance=0.3, share=False, allowed=in_area)
    print(f"VCC vias: {n1} + {n2} extra, failed: {f1 + f2}")
    # C72 (decoupling of U1 pin 4) straight onto C73, which has its plane via: no second via, no V of stubs
    c72, c73 = pad("C72", 1), pad("C73", 1)
    add_track(board, "+3V3", [c72, (c73[0], c72[1])], 0.3, B)
    # +3V3 pads that lost their plane via (it was a router via, or it lies in the VCC area now)
    outside = lambda x, y: not in_poly((x, y), VCC_AREA)
    lost = unplaned_pads(board, "+3V3", outside)
    n3, f3 = drop_plane_vias(board, iface, nets=("+3V3",), only=tuple(r for r, _ in lost), pads_only=lost,
                             share=True, allowed=outside)          # share a +3V3 via next to the pad if there is one
    lost_vcc = unplaned_pads(board, "VCC", lambda x, y: in_poly((x, y), VCC_AREA))
    n4, f4 = drop_plane_vias(board, iface, nets=("VCC",), only=tuple(r for r, _ in lost_vcc), pads_only=lost_vcc,
                             share=False, allowed=lambda x, y: in_poly((x, y), VCC_AREA), clearance=0.3)
    print(f"+3V3 pads without plane via: {sorted(lost)} -> {n3} vias, failed {f3}; "
          f"VCC: {sorted(lost_vcc)} -> {n4} vias, failed {f4}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(dst), board)
    print("saved", dst)


if __name__ == "__main__":
    if sys.argv[1] == "--phase2":
        phase2(sys.argv[2], sys.argv[3])
    else:
        phase1(sys.argv[1], sys.argv[2])
