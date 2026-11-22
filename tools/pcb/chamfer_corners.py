"""Replace every track corner of 90 degrees or sharper by a chamfer (layout rule 2026-11-19: "Alle Leiterbahnen,
die eine Kurve machen, duerfen keine 90-Grad-Winkel haben").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/chamfer_corners.py <in.kicad_pcb> <out.kicad_pcb>

A corner is a point where exactly two track segments of one net and layer meet (any copper layer, also the inner
ones of the 6-layer board), outside every pad and via (a
bend inside a pad or under a via is not visible copper). If the inner angle is <= 90 degrees, both legs are cut
back by the same length c and joined by a new segment: a 90 degree corner becomes two 135 degree corners.
c is the largest of CUTS that
- leaves half of a leg whose other end is a corner as well, and keeps a pad exit straight (the cut stops
  PAD_EXIT before the pad edge),
- removes no point where other copper of the net is attached (T junction, via, pad),
- keeps the clearance of the new segment to all copper of other nets and to the board edge.
Only coordinates are changed and segments added (no Remove(): pcbnew proxies break after it).
"""
import math, sys

import pcbnew

from bekantx_layout import MM, P, unP
from pcb_geom import bbox_mm
from manhattan import Fast

CUTS = (1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1, 0.08, 0.06)
PAD_EXIT = 0.15           # mm of straight track left outside a pad edge
MAX_INNER = 91.0          # degrees: corners up to this inner angle are chamfered


def key(p):
    return (round(p[0], 4), round(p[1], 4))


def main(src, dst):
    board = pcbnew.LoadBoard(str(src))
    cu = Fast(board)                       # clearance model with the inner layers (6-layer board)
    outer = tuple(l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu)
                  if board.IsLayerEnabled(l))
    segs = [dict(obj=t, a=unP(t.GetStart()), b=unP(t.GetEnd()), w=pcbnew.ToMM(t.GetWidth()), net=t.GetNetname(),
                 lay=t.GetLayer()) for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() in outer]
    vias = [(unP(t.GetPosition()), pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, t.GetNetname())
            for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    pads = [(p, fp.GetReference()) for fp in board.GetFootprints() for p in fp.Pads()]

    def pad_hit(q, net, lay, acc=0.0):
        vq = P(*q)
        return [p for p, _r in pads if p.GetNetname() == net and p.IsOnLayer(lay) and p.HitTest(vq, MM(acc))]

    def at_index():
        idx = {}
        for s in segs:
            for e in ("a", "b"):
                idx.setdefault((s["net"], s["lay"], key(s[e])), []).append((s, e))
        return idx

    def inner_angle(p, q1, q2):
        u, v = (q1[0] - p[0], q1[1] - p[1]), (q2[0] - p[0], q2[1] - p[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-6 or lv < 1e-6:
            return 180.0
        return math.degrees(math.acos(max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / lu / lv))))

    def is_corner(net, lay, p, idx):
        lst = idx.get((net, lay, key(p)), [])
        if len(lst) != 2 or lst[0][0] is lst[1][0]:
            return None
        if any(math.dist(p, vp) <= vr + 1e-3 and vn == net for vp, vr, vn in vias):
            return None
        if pad_hit(p, net, lay):
            return None
        (s1, e1), (s2, e2) = lst
        f1 = s1["b"] if e1 == "a" else s1["a"]
        f2 = s2["b"] if e2 == "a" else s2["a"]
        if inner_angle(p, f1, f2) > MAX_INNER:
            return None
        return (s1, e1, f1), (s2, e2, f2)

    idx = at_index()
    corners = []
    for (net, lay, k), lst in idx.items():
        p = lst[0][0][lst[0][1]]
        c = is_corner(net, lay, p, idx)
        if c:
            corners.append((net, lay, p, c))
    corner_keys = {(n, l, key(p)) for n, l, p, _c in corners}
    print(f"corners <= {MAX_INNER:.0f} deg outside pads and vias: {len(corners)}")

    def leg_limit(net, lay, p, far, length, into_pad):
        lim = length / 2 if (net, lay, key(far)) in corner_keys else length
        hit = pad_hit(far, net, lay)
        if hit and into_pad:                   # pass 2: the cut may reach into the pad (not past its centre)
            return min(lim, length - 0.01)
        if hit:                                # keep the pad exit straight
            ux, uy = (far[0] - p[0]) / length, (far[1] - p[1]) / length
            t = 0.0
            while t < length and not pad_hit((p[0] + ux * t, p[1] + uy * t), net, lay, PAD_EXIT):
                t += 0.01
            lim = min(lim, t)
        return lim

    def cut_free(net, lay, p, q, skip, own_pad=None):
        """Nothing else of the net is attached between corner p and the new end q."""
        for s in segs:
            if s in skip or s["net"] != net or s["lay"] != lay:
                continue
            for e in (s["a"], s["b"]):
                from straighten_pads import seg_point
                if seg_point(e, p, q) < 0.01:
                    return False
        for vp, vr, vn in vias:
            if vn == net:
                from straighten_pads import seg_point
                if seg_point(vp, p, q) < vr + 0.01:
                    return False
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            hit = pad_hit((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t), net, lay)
            if any(own_pad is None or h.GetParentFootprint().GetReference() + h.GetNumber() != own_pad for h in hit):
                return False
        return True

    done = 0

    def padname(q, net, lay):
        h = pad_hit(q, net, lay)
        return h[0].GetParentFootprint().GetReference() + h[0].GetNumber() if h else None

    def chamfer(net, lay, p, s1, e1, s2, e2, into_pad):
        nonlocal done
        # the legs may have been shortened at their other end by an earlier chamfer: use current geometry
        if key(s1[e1]) != key(p) or key(s2[e2]) != key(p):
            return "moved"
        f1 = s1["b"] if e1 == "a" else s1["a"]
        f2 = s2["b"] if e2 == "a" else s2["a"]
        l1, l2 = math.dist(p, f1), math.dist(p, f2)
        lim = min(leg_limit(net, lay, p, f1, l1, into_pad), leg_limit(net, lay, p, f2, l2, into_pad))
        o1, o2 = (padname(f1, net, lay), padname(f2, net, lay)) if into_pad else (None, None)
        u1 = ((f1[0] - p[0]) / l1, (f1[1] - p[1]) / l1)
        u2 = ((f2[0] - p[0]) / l2, (f2[1] - p[1]) / l2)
        w = min(s1["w"], s2["w"])
        ok = False
        for c in CUTS:
            if c > lim + 1e-6:
                continue
            q1 = (p[0] + u1[0] * c, p[1] + u1[1] * c)
            q2 = (p[0] + u2[0] * c, p[1] + u2[1] * c)
            if not (cut_free(net, lay, p, q1, (s1, s2), o1) and cut_free(net, lay, p, q2, (s1, s2), o2)):
                continue
            if not cu.seg_clear(q1, q2, max(s1["w"], s2["w"]), net, lay):
                if w == max(s1["w"], s2["w"]) or not cu.seg_clear(q1, q2, w, net, lay):
                    continue
            else:
                w = max(s1["w"], s2["w"])
            ok = True
            break
        if not ok:
            return f"no room (limit {lim:.2f} mm)"
        for s, e, q in ((s1, e1, q1), (s2, e2, q2)):
            s[e] = q
            (s["obj"].SetStart if e == "a" else s["obj"].SetEnd)(P(*q))
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*q1)); t.SetEnd(P(*q2)); t.SetWidth(MM(w)); t.SetLayer(lay)
        t.SetNet(board.FindNet(net))
        board.Add(t)
        segs.append(dict(obj=t, a=q1, b=q2, w=w, net=net, lay=lay))
        cu.add_track(t)
        done += 1
        return None

    # pass 0: Z jogs (two corners joined by a short middle segment, the outer legs parallel and pointing in
    # opposite directions): the middle segment becomes one 45 degree piece of the same offset
    corners_left, jogs = [], 0
    by_pos = {(n, l, key(p)): c for n, l, p, c in corners}
    used = set()
    for net, lay, p, ((s1, e1, f1), (s2, e2, f2)) in corners:
        if (net, lay, key(p)) in used:
            continue
        for sm, em, fm, so, eo, fo in ((s1, e1, f1, s2, e2, f2), (s2, e2, f2, s1, e1, f1)):
            other = by_pos.get((net, lay, key(fm)))
            if other is None or (net, lay, key(fm)) in used or math.dist(p, fm) > 0.3:
                continue
            (t1, g1, h1), (t2, g2, h2) = other
            tb, gb, hb = (t2, g2, h2) if t1 is sm else (t1, g1, h1)
            if tb is sm or tb is so:
                continue
            d = math.dist(p, fm)
            lo, lb = math.dist(p, fo), math.dist(fm, hb)
            uo = ((fo[0] - p[0]) / lo, (fo[1] - p[1]) / lo)
            ub = ((hb[0] - fm[0]) / lb, (hb[1] - fm[1]) / lb)
            if uo[0] * ub[0] + uo[1] * ub[1] > -0.999 or min(lo, lb) < d / 2 + 0.05:
                continue                       # not a Z (the outer legs must be antiparallel) or legs too short
            q1 = (p[0] + uo[0] * d / 2, p[1] + uo[1] * d / 2)
            q2 = (fm[0] + ub[0] * d / 2, fm[1] + ub[1] * d / 2)
            if not cu.seg_clear(q1, q2, sm["w"], net, lay):
                continue
            for s, e, q in ((so, eo, q1), (tb, gb, q2)):
                s[e] = q
                (s["obj"].SetStart if e == "a" else s["obj"].SetEnd)(P(*q))
            sm["a"], sm["b"] = q1, q2
            sm["obj"].SetStart(P(*q1)); sm["obj"].SetEnd(P(*q2))
            used.update({(net, lay, key(p)), (net, lay, key(fm))})
            jogs += 1
            break
    print(f"Z jogs turned into one 45 degree piece: {jogs}")
    corners = [c for c in corners if (c[0], c[1], key(c[2])) not in used]

    left = []
    for net, lay, p, ((s1, e1, _f1), (s2, e2, _f2)) in corners:
        if chamfer(net, lay, p, s1, e1, s2, e2, False):
            left.append((net, lay, p, s1, e1, s2, e2))
    n1 = done
    # pass 2: corners right at a pad exit; the chamfer starts inside the pad, the track leaves the pad at 45 deg
    skipped = []
    for net, lay, p, s1, e1, s2, e2 in left:
        why = chamfer(net, lay, p, s1, e1, s2, e2, True)
        if why:
            skipped.append((net, lay, p, why))
    print(f"chamfered: {n1} + {done - n1} from inside a pad, left: {len(skipped)}")
    for net, lay, p, why in skipped:
        print(f"  {net} at {p[0]:.2f}, {p[1]:.2f} ({board.GetLayerName(lay)}): {why}")
    pcbnew.SaveBoard(str(dst), board)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
