"""Keep supply tracks over a plane short (layout rule 2026-11-19: "Speisungsleitungen, wenn unten dran eine Plane
ist, moeglichst kurz halten").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/plane_stubs.py <in.kicad_pcb> <out.kicad_pcb>

For the plane nets (GND on In2, VCC on the VCC area of In1, +3V3 on the rest of In1) every SMD pad on an outer
layer should reach a plane via over a short stub. Per net:
1. A graph of the outer-layer copper (pads, track end points, vias; vias join F.Cu and B.Cu). Vias that lie in
   the filled plane of the net are the sources; Dijkstra gives every pad its track length to the plane.
2. A pad farther than MAX_STUB from the plane gets a new via straight out of the pad (axis direction, outward
   first) when via and stub keep every clearance and the via lands in the filled plane.
3. Kept are the shortest pad-to-plane paths and the direct connections listed in KEEP_PAIRS (input loops of the
   buck converters: the input capacitor stays tied straight to the VIN pin). All other tracks of the net on the
   outer layers are removed, then VCC/+3V3 vias that touch nothing any more. GND vias stay (they stitch the pours).
Zones must be filled in the input (the plane test uses the fill). Run bekantx_finish.py (refill) and DRC after.
"""
import heapq, math, sys

import pcbnew

from bekantx_layout import MM, NETCLASSES, P, add_track, add_via, unP
from pcb_geom import Copper, net_width, on_plane, plane_fill

NETS = ("VCC", "+3V3", "GND")
MAX_STUB = 1.5            # mm of track from pad centre to the plane via that count as short
KEEP_PAIRS = [(("C15", "1"), ("U9", "5"), 6.0),      # LMR51610 input loop (C15 = CIN)
              (("C25", "1"), ("U20", "5"), 6.0)]     # LV2862 input loop (C25 = CIN)
GAPS = (0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8)


def via_size(net):
    import fnmatch
    for _n, (_w, _c, vd, vdr, pats) in NETCLASSES.items():
        if any(fnmatch.fnmatchcase(net, p.replace("[", "[[]")) if "*" in p else net == p for p in pats):
            return vd, vdr
    return NETCLASSES["Default"][2], NETCLASSES["Default"][3]


def key(p):
    return (round(p[0], 4), round(p[1], 4))


def build_graph(board, net):
    """Nodes: ('p', id(pad)), ('v', id(via)), ('x', point). Edges carry the segment objects they stand for."""
    pads = [(fp, p) for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == net]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == net]
    segs = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net
            and t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
    adj = {}

    def edge(u, v, length, seg):
        adj.setdefault(u, []).append((v, length, seg))
        adj.setdefault(v, []).append((u, length, seg))

    def node(q, layer):
        vp = P(*q)
        for fp, p in pads:
            if p.IsOnLayer(layer) and p.HitTest(vp):
                return ("p", id(p))
        for v in vias:
            if math.dist(unP(v.GetPosition()), q) <= pcbnew.ToMM(v.GetWidth(layer)) / 2 + 1e-3:
                return ("v", id(v))
        return ("x", key(q), layer)

    for t in segs:
        a, b = unP(t.GetStart()), unP(t.GetEnd())
        edge(node(a, t.GetLayer()), node(b, t.GetLayer()), math.dist(a, b), t)
    # T junctions: an end point on the inside of another segment of the same layer
    from straighten_pads import seg_point
    for t in segs:
        for q in (unP(t.GetStart()), unP(t.GetEnd())):
            n = node(q, t.GetLayer())
            if n[0] != "x":
                continue
            for o in segs:
                if o is t or o.GetLayer() != t.GetLayer():
                    continue
                a, b = unP(o.GetStart()), unP(o.GetEnd())
                if seg_point(q, a, b) < 0.01 and min(math.dist(q, a), math.dist(q, b)) > 0.01:
                    edge(n, node(a, o.GetLayer()), math.dist(q, a), o)
                    edge(n, node(b, o.GetLayer()), math.dist(q, b), o)
    # vias inside a pad (exposed pads with a via array)
    for v in vias:
        for fp, p in pads:
            if p.HitTest(v.GetPosition()):
                edge(("v", id(v)), ("p", id(p)), 0.0, None)
    return pads, vias, segs, adj


def dijkstra(adj, sources):
    dist, prev = {s: 0.0 for s in sources}, {}
    h = [(0.0, i, s) for i, s in enumerate(sources)]
    heapq.heapify(h)
    cnt = len(h)
    while h:
        d, _i, u = heapq.heappop(h)
        if d > dist.get(u, 1e9):
            continue
        for v, l, seg in adj.get(u, []):
            nd = d + l
            if nd < dist.get(v, 1e9) - 1e-9:
                dist[v], prev[v] = nd, (u, seg)
                cnt += 1
                heapq.heappush(h, (nd, cnt, v))
    return dist, prev


def path_segs(prev, n):
    out = []
    while n in prev:
        n, seg = prev[n]
        if seg is not None:
            out.append(seg)
    return out


def sharp_corner(path):
    """The path (segments in order) bends by 90 degrees or more at a point outside pads and vias."""
    for s, t in zip(path, path[1:]):
        a, b, c, d = unP(s.GetStart()), unP(s.GetEnd()), unP(t.GetStart()), unP(t.GetEnd())
        for p, q1 in ((a, b), (b, a)):
            for r, q2 in ((c, d), (d, c)):
                if math.dist(p, r) < 1e-3 and s.GetLayer() == t.GetLayer():
                    u, v = (q1[0] - p[0], q1[1] - p[1]), (q2[0] - p[0], q2[1] - p[1])
                    lu, lv = math.hypot(*u), math.hypot(*v)
                    if lu > 1e-6 and lv > 1e-6 and (u[0] * v[0] + u[1] * v[1]) / lu / lv > -0.017:
                        return True
    return False


def try_via(board, cu, net, fp, pad, fill):
    """A via straight out of the pad, outward first. Returns the via position or None."""
    c = unP(pad.GetPosition())
    x0, y0, x1, y1 = (lambda bb: unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())) + unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom())))(pad.GetBoundingBox())
    hx, hy = (x1 - x0) / 2, (y1 - y0) / 2
    fc = unP(fp.GetPosition())
    dx, dy = c[0] - fc[0], c[1] - fc[1]
    if abs(dx) >= abs(dy):
        order = [(math.copysign(1, dx or 1), 0), (0, -1), (0, 1), (-math.copysign(1, dx or 1), 0)]
    else:
        order = [(0, math.copysign(1, dy or 1)), (-1, 0), (1, 0), (0, -math.copysign(1, dy or 1))]
    if len(fp.Pads()) > 2:
        order = order[:3]                     # never under the body of a multi-pin part
    dia, drill = via_size(net)
    layer = pcbnew.B_Cu if pad.IsOnLayer(pcbnew.B_Cu) and not pad.HasHole() else pcbnew.F_Cu
    for gap in GAPS:
        for ux, uy in order:
            ext = hx if ux else hy
            q = (c[0] + ux * (ext + gap + dia / 2), c[1] + uy * (ext + gap + dia / 2))
            w = min(net_width(net), 2 * (hy if ux else hx))
            if not on_plane(fill, q, dia / 2 + 0.1):
                continue
            if not cu.via_clear(q, dia, drill, net):
                continue
            if not cu.seg_clear(c, q, w, net, layer):
                continue
            add_track(board, net, [c, q], w, layer, locked=False)
            add_via(board, net, q, dia, drill, locked=False)
            cu.refresh()
            return q
    return None


def main(src, dst):
    board = pcbnew.LoadBoard(str(src))
    cu = Copper(board)
    remove = []
    for net in NETS:
        fill = plane_fill(board, net)
        pads, vias, segs, adj = build_graph(board, net)
        grounded = [("v", id(v)) for v in vias if fill is not None and fill.Contains(v.GetPosition())]
        grounded += [("p", id(p)) for fp, p in pads if p.HasHole() and fill is not None and fill.Contains(p.GetPosition())]
        dist, prev = dijkstra(adj, grounded)
        added, failed, forced = 0, [], {}
        for fp, p in pads:
            if p.HasHole() or ("p", id(p)) not in adj:
                continue                      # THT pads reach the plane themselves; untracked pads use the pour
            n = ("p", id(p))
            far = dist.get(n, 1e9) > MAX_STUB
            bent = n in dist and sharp_corner(path_segs(prev, n))
            if far or bent:
                q = try_via(board, cu, net, fp, p, fill)
                if q:
                    added += 1
                    forced[(fp.GetReference(), p.GetNumber())] = q
                elif far:
                    failed.append(f"{fp.GetReference()}.{p.GetNumber()}({dist.get(('p', id(p)), float('inf')):.1f})")
        # new graph with the new vias and stubs
        pads, vias, segs, adj = build_graph(board, net)
        grounded = [("v", id(v)) for v in vias if fill is not None and fill.Contains(v.GetPosition())]
        grounded += [("p", id(p)) for fp, p in pads if p.HasHole() and fill is not None and fill.Contains(p.GetPosition())]
        dist, prev = dijkstra(adj, grounded)
        keep = set()
        for fp, p in pads:
            n = ("p", id(p))
            q = forced.get((fp.GetReference(), p.GetNumber()))
            if q is not None:                  # the new straight stub replaces the old (long or bent) path
                vn = [("v", id(v)) for v in vias if math.dist(unP(v.GetPosition()), q) < 1e-3]
                d2, prev2 = dijkstra(adj, [n])
                if vn and vn[0] in d2:
                    keep.update(id(s) for s in path_segs(prev2, vn[0]))
                    continue
            if n in dist:
                keep.update(id(s) for s in path_segs(prev, n))
        byref = {(fp.GetReference(), p.GetNumber()): p for fp, p in pads}
        for (ra, rb, lmax) in KEEP_PAIRS:
            if ra in byref and rb in byref:
                d2, prev2 = dijkstra(adj, [("p", id(byref[ra]))])
                n = ("p", id(byref[rb]))
                if d2.get(n, 1e9) <= lmax:
                    keep.update(id(s) for s in path_segs(prev2, n))
                else:
                    print(f"  {ra}-{rb}: no direct track of <= {lmax} mm ({d2.get(n, float('inf')):.1f})")
        gone = [s for s in segs if id(s) not in keep]
        length = sum(pcbnew.ToMM(s.GetLength()) for s in gone)
        remove += gone
        # vias that touch nothing after the removal (only VCC/+3V3; GND vias stitch the pours)
        dead_v = []
        if net != "GND":
            kept = [s for s in segs if id(s) in keep]
            for v in vias:
                vp = unP(v.GetPosition())
                r = pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)) / 2
                touch = any(min(math.dist(vp, unP(s.GetStart())), math.dist(vp, unP(s.GetEnd()))) <= r + 1e-3 for s in kept)
                touch = touch or any(p.HitTest(v.GetPosition()) for fp, p in pads)
                touch = touch or any(math.dist(vp, unP(s.GetStart())) <= r + 1e-3 or math.dist(vp, unP(s.GetEnd())) <= r + 1e-3
                                     for s in board.GetTracks() if s.GetClass() == "PCB_TRACK" and s.GetNetname() == net
                                     and s.GetLayer() in (pcbnew.In1_Cu, pcbnew.In2_Cu))
                if not touch:
                    dead_v.append(v)
        remove += dead_v
        print(f"{net}: {added} new plane vias, {len(gone)} track segments removed ({length:.1f} mm), "
              f"{len(dead_v)} loose vias removed; pads still far from the plane: {failed or 'none'}")
    for o in remove:                           # removals last: pcbnew proxies break after Remove()
        board.Remove(o)
    pcbnew.SaveBoard(str(dst), board)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
