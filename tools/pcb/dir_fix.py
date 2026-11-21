"""Move track pieces that run against the direction of their layer onto a layer of the right direction (user rule
2026-11-21: on every layer either horizontal or vertical tracks, not mixed).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/dir_fix.py <in.kicad_pcb> <out.kicad_pcb>
        [--dirs=F.Cu:V,In2.Cu:H,In3.Cu:V,B.Cu:H] [--escape=1.2]

A piece is a track segment on a routing layer whose direction (H, V or diagonal) is not the one of the layer. Pad
escapes stay: a piece that starts in a pad and is at most --escape mm long. Every other piece keeps its geometry and
moves to the nearest layer of its direction (diagonal pieces are not moved, they are reported); a via of the net is
set at each end that is not already on a via (the neighbours stay on the old layer). If an end lies in an SMD pad,
the piece is split: the first part up to a free via spot (at most --escape mm) stays as the escape, the rest moves.
Every new via and every moved piece keeps all clearances on all layers it touches (pcb_geom with the inner layers,
NPTH hole clearance), else the piece stays and is reported. Locked tracks are not touched.
"""
import collections, math, sys

import pcbnew

from bekantx_layout import MM, P, add_via, unP
from manhattan import Fixer, pt_seg
from pcb_geom import bbox_mm, uid

VIA, DRILL = 0.5, 0.3
CANON = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu, "In3.Cu": pcbnew.In3_Cu,
         "In4.Cu": pcbnew.In4_Cu, "B.Cu": pcbnew.B_Cu}
ORDER = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")      # physical order, for "nearest layer"


def kind(a, b):
    if abs(b[1] - a[1]) < 1e-3:
        return "H"
    if abs(b[0] - a[0]) < 1e-3:
        return "V"
    return "D"


def slide_vias(board, cu, lays, escape, inner_sig, fx, max_jog=1.5):
    """A short jog against the layer direction between a via and the rest of its track: move the via to the far end
    of the jog and extend the via's tracks on the other layers along the jog, where those layers have the jog's
    direction and the tracks are collinear with it. The jog becomes zero length (removed by the caller)."""
    vias = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and not v.IsLocked()]
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and not t.IsLocked()]
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    at = collections.defaultdict(list)                 # rounded point -> [(track, end)]
    key = lambda q: (round(q[0], 3), round(q[1], 3))
    for t in tracks:
        at[key(unP(t.GetStart()))].append((t, "a"))
        at[key(unP(t.GetEnd()))].append((t, "b"))
    n = 0
    for v in vias:
        pv = unP(v.GetPosition())
        net = v.GetNetname()
        here = [(t, e) for t, e in at.get(key(pv), []) if t.GetNetname() == net]
        for t, e in here:
            a, b = unP(t.GetStart()), unP(t.GetEnd())
            q = b if e == "a" else a
            L = math.dist(pv, q)
            k = kind(pv, q)
            if t.GetLayer() not in lays or k == lays[t.GetLayer()] or k == "D" or L > max_jog or L < 1e-3:
                continue
            # the far end must be a plain bend: exactly one other segment of the net on the same layer, no pad, no via
            others_q = [(o, oe) for o, oe in at.get(key(q), []) if o is not t and o.GetNetname() == net]
            if len(others_q) != 1 or others_q[0][0].GetLayer() != t.GetLayer():
                continue
            if any(p.GetNetname() == net and p.HitTest(P(*q)) for p in pads):
                continue
            rest = [(o, oe) for o, oe in here if o is not t]
            ok = bool(rest)
            for o, oe in rest:
                oa, ob = unP(o.GetStart()), unP(o.GetEnd())
                of = ob if oe == "a" else oa
                if lays.get(o.GetLayer()) != k or kind(of, q) != k:
                    ok = False                # the other-layer track must continue straight along the jog
            if not ok or not cu.via_clear(q, pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)), pcbnew.ToMM(v.GetDrillValue()), net,
                                          skip=[v, t] + [o for o, _ in rest], own_pad_gap=0.1):
                continue
            shape = pcbnew.SHAPE_CIRCLE(P(*q), MM(pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)) / 2))
            r = pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)) / 2
            if cu._hits(shape, (q[0] - r, q[1] - r, q[0] + r, q[1] + r), net, inner_sig, {uid(v)} | {uid(o) for o, _ in rest}) is not None:
                continue
            if not all(fx.hole_ok(unP(o.GetStart()) if oe == "b" else unP(o.GetEnd()), q, pcbnew.ToMM(o.GetWidth())) and
                       cu.seg_clear(unP(o.GetStart()) if oe == "b" else unP(o.GetEnd()), q, pcbnew.ToMM(o.GetWidth()), net,
                                    o.GetLayer(), skip=[o, v]) for o, oe in rest):
                continue
            for o, oe in rest:
                cu.drop_track(o)
                (o.SetStart if oe == "a" else o.SetEnd)(P(*q))
                cu.add_track(o)
            cu.drop_track(t)
            t.SetStart(P(*q)); t.SetEnd(P(*q))
            cu.drop_track(v)                  # the via item and its hole move with it
            v.SetPosition(P(*q))
            it = dict(obj=v, kind="via", net=net, layers=[pcbnew.F_Cu, pcbnew.B_Cu] + list(inner_sig), box=bbox_mm(v), uid=uid(v))
            cu.items.append(it); cu._reg(it)
            cu.holes = [h for h in cu.holes if h[3] is not v and uid(h[3]) != uid(v)] + [(q[0], q[1], pcbnew.ToMM(v.GetDrillValue()) / 2, v)]
            n += 1
            break
    return n


def main(src, dst, dirs, escape):
    board = pcbnew.LoadBoard(str(src))
    fx = Fixer(board)
    cu = fx.cu
    lays = {CANON[k]: v for k, v in dirs.items()}
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    vias = {(round(unP(v.GetPosition())[0], 3), round(unP(v.GetPosition())[1], 3), v.GetNetname())
            for v in board.GetTracks() if v.GetClass() == "PCB_VIA"}
    inner_sig = [CANON[k] for k in dirs if k not in ("F.Cu", "B.Cu")]

    def pad_at(q, net, lay):
        return next((p for p in pads if p.GetNetname() == net and p.IsOnLayer(lay) and p.HitTest(P(*q))), None)

    def via_ok(q, net, skip):
        if not cu.via_clear(q, VIA, DRILL, net, skip=skip, own_pad_gap=0.1):
            return False
        shape = pcbnew.SHAPE_CIRCLE(P(*q), MM(VIA / 2))
        box = (q[0] - VIA / 2, q[1] - VIA / 2, q[0] + VIA / 2, q[1] + VIA / 2)
        return cu._hits(shape, box, net, inner_sig, {uid(o) for o in skip}) is None

    def targets(lay, k):
        i = ORDER.index(pcbnew.BOARD.GetStandardLayerName(lay))
        cand = [CANON[n] for n in ORDER if dirs.get(n) == k]
        return sorted(cand, key=lambda l: (l in (pcbnew.F_Cu, pcbnew.B_Cu), abs(ORDER.index(pcbnew.BOARD.GetStandardLayerName(l)) - i)))

    slid = slide_vias(board, cu, lays, escape, inner_sig, fx)
    segs = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() in lays and not t.IsLocked()
            and math.dist(unP(t.GetStart()), unP(t.GetEnd())) > 1e-6]
    todo = []
    for t in segs:
        a, b = unP(t.GetStart()), unP(t.GetEnd())
        k = kind(a, b)
        if k != lays[t.GetLayer()]:
            todo.append((math.dist(a, b), t, a, b, k))
    todo.sort(key=lambda x: -x[0])
    stats = collections.Counter()
    left = []
    for L, t, a, b, k in todo:
        net, lay, w = t.GetNetname(), t.GetLayer(), pcbnew.ToMM(t.GetWidth())
        pa, pb = pad_at(a, net, lay), pad_at(b, net, lay)
        if (pa or pb) and L <= escape:
            stats["escape kept"] += 1
            continue
        if k == "D":
            left.append((net, lay, a, b, "diagonal"))
            continue
        # ends of the moved part: the segment ends, or a split point next to an SMD pad
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)

        def end_point(p0, sgn, pad):
            if not pad or pad.HasHole():
                return p0, False
            s = 0.3
            while s <= min(escape, L / 2):
                q = (p0[0] + sgn * u[0] * s, p0[1] + sgn * u[1] * s)
                if not pad.HitTest(P(*q)) and via_ok(q, net, [t]):
                    return q, True
                s += 0.05
            return None, False

        qa, split_a = end_point(a, 1, pa)
        qb, split_b = end_point(b, -1, pb)
        if qa is None or qb is None or math.dist(qa, qb) < 0.3:
            left.append((net, lay, a, b, "no via next to the pad"))
            continue
        need = [q for q, sp in ((qa, split_a), (qb, split_b))
                if (round(q[0], 3), round(q[1], 3), net) not in vias]
        if not all(via_ok(q, net, [t]) for q in need):
            left.append((net, lay, a, b, "no room for a via"))
            continue
        moved = False
        for tl in targets(lay, k):
            if fx.hole_ok(qa, qb, w) and cu.seg_clear(qa, qb, w, net, tl, skip=[t]):
                # apply: keep escape stubs on the old layer, the middle on tl
                cu.drop_track(t)
                stubs = []
                if split_a:
                    stubs.append((a, qa))
                if split_b:
                    stubs.append((qb, b))
                t.SetStart(P(*qa)); t.SetEnd(P(*qb)); t.SetLayer(tl)
                cu.add_track(t)
                for p0, p1 in stubs:
                    n = pcbnew.PCB_TRACK(board)
                    n.SetStart(P(*p0)); n.SetEnd(P(*p1)); n.SetWidth(t.GetWidth()); n.SetLayer(lay); n.SetNet(t.GetNet())
                    board.Add(n)
                    cu.add_track(n)
                for q in need:
                    v = add_via(board, net, q, VIA, DRILL, locked=False)
                    vias.add((round(q[0], 3), round(q[1], 3), net))
                    it = dict(obj=v, kind="via", net=net, layers=[pcbnew.F_Cu, pcbnew.B_Cu] + inner_sig, box=bbox_mm(v), uid=uid(v))
                    cu.items.append(it); cu._reg(it)
                    x, y = q
                    cu.holes.append((x, y, DRILL / 2, v))
                stats[f"moved to {pcbnew.BOARD.GetStandardLayerName(tl)}"] += 1
                moved = True
                break
        if not moved:
            left.append((net, lay, a, b, "no room on a layer of that direction"))
    for t in [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and math.dist(unP(t.GetStart()), unP(t.GetEnd())) < 1e-6]:
        board.Remove(t)                       # the jogs emptied by slide_vias (removed last: proxies break after Remove)
    pcbnew.SaveBoard(str(dst), board)
    print(f"vias slid onto the line (short jog moved to a layer of its direction): {slid}")
    print(f"pieces against the layer direction: {len(todo)}; {dict(stats)}; left {len(left)}")
    for net, lay, a, b, why in sorted(left, key=lambda x: -math.dist(x[2], x[3]))[:40]:
        print(f"  {net:24s} {pcbnew.BOARD.GetStandardLayerName(lay)} {math.dist(a, b):5.2f} mm "
              f"({a[0]:.2f},{a[1]:.2f})-({b[0]:.2f},{b[1]:.2f}): {why}")


if __name__ == "__main__":
    d = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--dirs=")), "F.Cu:V,In2.Cu:H,In3.Cu:V,B.Cu:H")
    e = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--escape=")), "1.2"))
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], dict(x.split(":") for x in d.split(",")), e)
