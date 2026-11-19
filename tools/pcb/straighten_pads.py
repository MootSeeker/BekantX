"""Make every track leave its SMD pad straight (PR #5 feedback: "check all connections if they are straight and
enter the pad right").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/straighten_pads.py <in.kicad_pcb> <out.kicad_pcb>

Rule for a track segment that starts in an SMD pad:
- fine-pitch pads (short side <= 0.35 mm and clearly elongated: QFN, TSSOP, SOT, FPC): the track leaves along the
  long axis of the pad, outwards (away from the part), and bends only 0.25 mm beyond the pad tip;
- all other pads: the first piece is axis-parallel (horizontal or vertical) until 0.25 mm outside the pad.
An off-axis segment is replaced by  pad centre -> exit point -> old far end. Every new piece is checked against all
copper of other nets (pads, tracks, vias, THT) with the net class clearance and against the board edge before it
is applied; a pad entry that cannot be straightened this way is left as it was and reported.
Only coordinates are changed or tracks added (no Remove(): pcbnew proxies break after it).
--nets=NET,NET   work on these nets only (all other copper is an obstacle and stays as it is); used after a
                 partial re-route so that finished areas (USB-C, chamfers) are not touched again
"""
import json, math, sys
from pathlib import Path

import pcbnew

from bekantx_layout import MM, NETCLASSES, P, net_clearance, unP


def net_width(net):
    import fnmatch
    for name, (w, _c, _v, _d, pats) in NETCLASSES.items():
        if any(fnmatch.fnmatchcase(net, p.replace("[", "[[]")) if "*" in p else net == p for p in pats):
            return w
    return NETCLASSES["Default"][0]


def no_acute(path):
    """No joint in the path turns by more than 90 degrees (no acute angle, no fold-back)."""
    for p0, p1, p2 in zip(path, path[1:], path[2:]):
        u, v = (p1[0] - p0[0], p1[1] - p0[1]), (p2[0] - p1[0], p2[1] - p1[1])
        if math.hypot(*u) > 1e-6 and math.hypot(*v) > 1e-6 and u[0] * v[0] + u[1] * v[1] < -1e-9:
            return False
    return True

ROOT = Path(__file__).resolve().parents[2]
ONLY = None          # set of net names (--nets), None = all nets


def mine(net):
    return ONLY is None or net in ONLY
EXIT = 0.25          # mm beyond the pad edge before the track may bend
ANG_TOL = 2.0        # degrees: a segment within this of the wanted direction is fine


def seg_point(p, a, b):
    l2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    u = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / l2))
    return math.hypot(p[0] - a[0] - u * (b[0] - a[0]), p[1] - a[1] - u * (b[1] - a[1]))


def seg_seg(a, b, c, d):
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    if (ccw(a, b, c) > 0) != (ccw(a, b, d) > 0) and (ccw(c, d, a) > 0) != (ccw(c, d, b) > 0):
        return 0.0
    return min(seg_point(a, c, d), seg_point(b, c, d), seg_point(c, a, b), seg_point(d, a, b))


def seg_rect(a, b, r):
    if r[0] <= a[0] <= r[2] and r[1] <= a[1] <= r[3]:
        return 0.0
    corners = [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]
    return min(seg_seg(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


OCT_TOL = 0.5        # degrees: a segment further than this from 0/45/90 degrees is "skewed"
DIRS8 = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 360, 45)]


def _dev(a, b):
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 45
    return min(ang, 45 - ang)


def octilinear(board, segs, vias, vobjs, pads, clear, plane_ok, pad_at):
    """6. Every segment on a 0/45/90 degree direction (PR #5 feedback: connections straight).
    a) a plane via fed by a single skewed stub moves onto the nearest 0/45/90 ray from the stub's other end
       (axis-parallel if that end is a pad), within 0.35 mm of where it was;
    b) any other skewed segment becomes a dogleg (one axis-parallel and one 45 degree leg, or an L) between its
       unchanged end points; a leg that touches a pad is axis-parallel (along the outward axis for fine pitch).
    Everything is checked like the other steps: clearance to foreign copper, no acute joint with the neighbours,
    the plane side of In1 for moved vias, rule areas that forbid vias, hole-to-hole distance."""
    keepouts = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    near = lambda u, v: math.dist(u, v) < 0.01

    def attached(p, net):
        return [s for s in segs if s["net"] == net and (near(s["a"], p) or near(s["b"], p))]

    def neighbours(s, p):
        """Far points of the other segments of the same net and layer that meet s at p."""
        return [o["b"] if near(o["a"], p) else o["a"] for o in segs
                if o is not s and o["net"] == s["net"] and o["lay"] == s["lay"] and (near(o["a"], p) or near(o["b"], p))]

    def leg_dirs(p, s):
        """Allowed directions of a leg that starts at p: None = any of the eight."""
        pd = pad_at(p, s["net"], s["lay"])
        if pd is None:
            return None
        if pd["fine"]:
            return [pd["out"], (-pd["out"][0], -pd["out"][1])]
        return [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)]

    def dir_ok(p, q, dirs):
        if dirs is None or math.dist(p, q) < 1e-6:
            return True
        u = ((q[0] - p[0]) / math.dist(p, q), (q[1] - p[1]) / math.dist(p, q))
        return any(abs(u[0] - d[0]) < 1e-3 and abs(u[1] - d[1]) < 1e-3 for d in dirs)

    def path_ok(s, path):
        pts = [p for k, p in enumerate(path) if k == 0 or math.dist(p, path[k - 1]) > 1e-6]
        if len(pts) < 2 or not dir_ok(pts[0], pts[1], leg_dirs(pts[0], s)) or \
                not dir_ok(pts[-1], pts[-2], leg_dirs(pts[-1], s)):
            return False
        for na in neighbours(s, pts[0]) or [None]:
            for nb in neighbours(s, pts[-1]) or [None]:
                full = ([na] if na else []) + pts + ([nb] if nb else [])
                if not no_acute(full):
                    return False
        return all(clear(p0, p1, s["w"], s["net"], s["lay"], s) for p0, p1 in zip(pts, pts[1:]))

    vobj_at = {(vo.GetNetname(), round(unP(vo.GetPosition())[0], 3), round(unP(vo.GetPosition())[1], 3)): vo for vo in vobjs}
    moved = doglegs = 0
    left = []
    for s in sorted([s for s in segs if math.dist(s["a"], s["b"]) > 0.05 and _dev(s["a"], s["b"]) > OCT_TOL and mine(s["net"])],
                    key=lambda s: math.dist(s["a"], s["b"])):
        done = False
        # a) movable stub via
        for vend in ("a", "b"):
            v = s[vend]
            vo = vobj_at.get((s["net"], round(v[0], 3), round(v[1], 3)))
            if vo is None or s["net"] not in ("GND", "+3V3", "VCC") or len(attached(v, s["net"])) != 1:
                continue
            q = s["b" if vend == "a" else "a"]
            rv = pcbnew.ToMM(vo.GetWidth(pcbnew.F_Cu)) / 2
            dirs = leg_dirs(q, s) or DIRS8
            L = math.dist(q, v)
            cands = []
            for d in dirs:
                for k in range(-7, 8):
                    t = L + 0.05 * k
                    if t > 0.3:
                        c = (q[0] + d[0] * t, q[1] + d[1] * t)
                        if math.dist(c, v) <= 0.35:
                            cands.append(c)
            cands.sort(key=lambda c: math.dist(c, v))
            for c in cands:
                if not plane_ok(s["net"], c) or any(not plane_ok(s["net"], (c[0] + dx, c[1] + dy))
                                                     for dx, dy in ((0.6, 0), (-0.6, 0), (0, 0.6), (0, -0.6))):
                    continue
                if any(z.Outline().Contains(P(*c)) for z in keepouts):
                    continue
                own = [pd for pd in pads if pd["net"] == s["net"] and not pd["tht"]]
                if any(seg_rect(c, c, pd["rect"]) < rv + 0.1 - 1e-4 for pd in own):
                    continue                   # ring into a pad of its own net (solder wicking)
                if any(w["p"] is not v and math.dist(w["p"], c) < 0.55 and not near(w["p"], v) for w in vias):
                    continue                   # hole to hole
                if not all(clear(c, c, 2 * rv, s["net"], lay, s) for lay in (pcbnew.F_Cu, pcbnew.B_Cu)):
                    continue
                tmp = dict(s)
                tmp[vend] = c
                if not path_ok(s, [tmp["a"], tmp["b"]]):
                    continue
                vo.SetPosition(P(*c))
                (s["obj"].SetStart if vend == "a" else s["obj"].SetEnd)(P(*c))
                s[vend] = c
                for w in vias:
                    if w["net"] == s["net"] and near(w["p"], v):
                        w["p"] = c
                moved += 1
                done = True
                break
            if done:
                break
        if done:
            continue
        # b) dogleg between the unchanged end points
        a, b = s["a"], s["b"]
        dx, dy = b[0] - a[0], b[1] - a[1]
        sx, sy = math.copysign(1, dx), math.copysign(1, dy)
        m = min(abs(dx), abs(dy))
        if abs(dx) >= abs(dy):
            ks = [(b[0] - sx * m, a[1]), (a[0] + sx * m, b[1])]
        else:
            ks = [(a[0], b[1] - sy * m), (b[0], a[1] + sy * m)]
        paths = [[a, k, b] for k in ks] + [[a, (b[0], a[1]), b], [a, (a[0], b[1]), b]]
        # Z shapes: axis-parallel, 45 degrees, axis-parallel, with the diagonal at several places along the way
        rest = abs(abs(dx) - abs(dy))
        for f in (0.5, 0.3, 0.7, 0.15, 0.85):
            t = rest * f
            if abs(dx) >= abs(dy):
                k1 = (a[0] + sx * t, a[1])
                k2 = (k1[0] + sx * m, b[1])
            else:
                k1 = (a[0], a[1] + sy * t)
                k2 = (b[0], k1[1] + sy * m)
            paths.append([a, k1, k2, b])
        for path in paths:
            if path_ok(s, path):
                t = s["obj"]
                pts = [p for k, p in enumerate(path) if k == 0 or math.dist(p, path[k - 1]) > 1e-6]
                t.SetEnd(P(*pts[1]))
                s["b"] = pts[1]
                for p0, p1 in zip(pts[1:], pts[2:]):
                    n = pcbnew.PCB_TRACK(board)
                    n.SetStart(P(*p0)); n.SetEnd(P(*p1)); n.SetWidth(t.GetWidth()); n.SetLayer(t.GetLayer())
                    n.SetNet(t.GetNet()); n.SetLocked(t.IsLocked())
                    board.Add(n)
                    segs.append(dict(a=p0, b=p1, w=s["w"], net=s["net"], lay=s["lay"], obj=n))
                doglegs += 1
                done = True
                break
        if not done:
            left.append(f"{s['net']} {a[0]:.2f},{a[1]:.2f}->{b[0]:.2f},{b[1]:.2f} ({_dev(a, b):.0f} deg)")
    print(f"octilinear: {moved} stub vias moved, {doglegs} doglegs, {len(left)} skewed segments left: {left}")


def _line_x(p, q, r, s):
    """Intersection of the lines p-q and r-s, or None when they are parallel."""
    d = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])
    if abs(d) < 1e-9:
        return None
    t = ((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0])) / d
    return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))


def remove_jogs(segs, vias, dead, clear, pad_at, max_len=0.4):
    """7. A short cross piece J (<= max_len) between two parallel runs S1, S2 of one net is a jog. If the far end
    of S1 is a free bend (only S0 and S1 meet there, no pad, no via), that bend slides along S0 until S1 lies on
    the line of S2:  Z -S0- A -S1- a -J- c -S2- B  becomes  Z - A' - B  (same directions, two pieces fewer).
    Otherwise the same from the S2 side. Parallel lines of a bus usually jog together by the same offset and sit
    at minimum spacing, so jogs with the same offset vector next to each other are moved as one group."""
    near = lambda u, v: math.dist(u, v) < 0.01
    via_pts = [(v["net"], v["p"]) for v in vias]

    def meet(p, net, lay):
        return [s for s in segs if s["net"] == net and s["lay"] == lay and (near(s["a"], p) or near(s["b"], p))]

    def free(p, net, lay):
        return len(meet(p, net, lay)) == 2 and pad_at(p, net, lay) is None and \
            not any(n == net and near(q, p) for n, q in via_pts)

    other = lambda s, p: s["b"] if near(s["a"], p) else s["a"]
    unit = lambda p, q: ((q[0] - p[0]) / math.dist(p, q), (q[1] - p[1]) / math.dist(p, q))

    def jogs():
        out = []
        for j in segs:
            if not 1e-6 < math.dist(j["a"], j["b"]) <= max_len or not mine(j["net"]):
                continue
            net, lay, a, c = j["net"], j["lay"], j["a"], j["b"]
            if not (free(a, net, lay) and free(c, net, lay)):
                continue
            s1 = [s for s in meet(a, net, lay) if s is not j][0]
            s2 = [s for s in meet(c, net, lay) if s is not j][0]
            A, B = other(s1, a), other(s2, c)
            if math.dist(A, a) < 1e-6 or math.dist(c, B) < 1e-6:
                continue
            u1, u2 = unit(A, a), unit(c, B)
            if u1[0] * u2[0] + u1[1] * u2[1] >= 0.999:
                out.append((j, s1, s2, A, B, u1))
        return out

    def plan(jg, side):
        """Geometry of one jog removal: ([(seg, end key, new point)], [segments to drop]) or None."""
        j, s1, s2, A, B, u1 = jg
        net, lay, a, c = j["net"], j["lay"], j["a"], j["b"]
        run, far_end, keep, keep_old = (s1, A, s2, c) if side == 0 else (s2, B, s1, a)
        if not free(far_end, net, lay):
            return None
        s0 = [s for s in meet(far_end, net, lay) if s is not run][0]
        Z = other(s0, far_end)
        Ap = _line_x(Z, far_end, keep["a"], keep["b"])
        if Ap is None or math.dist(Z, Ap) < 0.05 or math.dist(Ap, far_end) > 0.6:
            return None
        if (Ap[0] - Z[0]) * (far_end[0] - Z[0]) + (Ap[1] - Z[1]) * (far_end[1] - Z[1]) <= 0:
            return None
        end = other(keep, keep_old)
        if math.dist(Ap, end) < 0.05 or not no_acute([Z, Ap, end] if side == 0 else [end, Ap, Z]):
            return None
        d_new = unit(Ap, end) if side == 0 else unit(end, Ap)
        if d_new[0] * u1[0] + d_new[1] * u1[1] < 0.999:
            return None
        ups = [(s0, "a" if near(s0["a"], far_end) else "b", Ap), (keep, "a" if near(keep["a"], keep_old) else "b", Ap)]
        return ups, [run, j]

    def attempt(plans):
        """Apply the plans to the geometry, keep them if every changed segment is clear, otherwise undo."""
        drops = [s for _u, d in plans for s in d]
        if len({id(s) for s in drops}) != len(drops):
            return False
        old = [(s, k, s[k]) for u, _d in plans for s, k, _p in u]
        for u, _d in plans:
            for s, k, p in u:
                s[k] = p
        for s in drops:
            segs.remove(s)
        ok = all(clear(s["a"], s["b"], s["w"], s["net"], s["lay"], s) for u, _d in plans for s, _k, _p in u)
        if ok:
            for u, _d in plans:
                for s, k, p in u:
                    (s["obj"].SetStart if k == "a" else s["obj"].SetEnd)(P(*p))
            dead.extend(s["obj"] for s in drops)
        else:
            for s, k, p in reversed(old):
                s[k] = p
            segs.extend(drops)
        return ok

    fixed = 0
    changed = True
    while changed:
        changed = False
        # single jogs first, then groups of jogs with the same offset vector within 3 mm of each other
        for jg in jogs():
            if jg[0] not in segs:
                continue
            for side in (0, 1):
                pl = plan(jg, side)
                if pl and attempt([pl]):
                    fixed += 1
                    changed = True
                    break
        if changed:
            continue
        js = jogs()
        vec = lambda jg: (jg[0]["b"][0] - jg[0]["a"][0], jg[0]["b"][1] - jg[0]["a"][1])
        mid = lambda jg: ((jg[0]["a"][0] + jg[0]["b"][0]) / 2, (jg[0]["a"][1] + jg[0]["b"][1]) / 2)
        for g0 in js:
            group = [g for g in js if g[0]["lay"] == g0[0]["lay"] and math.dist(mid(g), mid(g0)) < 3.0 and
                     (math.dist(vec(g), vec(g0)) < 0.005 or math.dist(vec(g), (-vec(g0)[0], -vec(g0)[1])) < 0.005)]
            if len(group) < 2 or any(g[0] not in segs for g in group):
                continue
            for side in (0, 1):
                pls = [plan(g, side) for g in group]
                if all(pls) and attempt(pls):
                    fixed += len(group)
                    changed = True
                    break
            if changed:
                break
    print(f"jogs removed: {fixed}")


def main(src, dst):
    iface = json.loads((ROOT / "CAD" / "board_interface.json").read_text(encoding="utf-8"))
    W, H = iface["board"]["width"], iface["board"]["depth"]
    board = pcbnew.LoadBoard(str(src))

    pads = []                                    # (rect, net, layers, is_fine, outward unit vector, fp centre)
    for fp in board.GetFootprints():
        fc = unP(fp.GetPosition())
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            if p.HasHole():
                lay = {pcbnew.F_Cu, pcbnew.B_Cu}
            else:
                lay = {pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu}
            w, h = x1 - x0, y1 - y0
            fine = min(w, h) <= 0.35 and max(w, h) > 1.5 * min(w, h) and not p.HasHole()
            c = ((x0 + x1) / 2, (y0 + y1) / 2)
            if w > h:
                out = (1.0, 0.0) if c[0] >= fc[0] else (-1.0, 0.0)
            else:
                out = (0.0, 1.0) if c[1] >= fc[1] else (0.0, -1.0)
            pads.append(dict(rect=(x0, y0, x1, y1), net=p.GetNetname(), lay=lay, fine=fine, out=out, c=c,
                             tht=p.HasHole(), ref=fp.GetReference(), num=p.GetNumber()))
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [dict(p=unP(t.GetPosition()), r=pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, net=t.GetNetname())
            for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    segs = [dict(a=unP(t.GetStart()), b=unP(t.GetEnd()), w=pcbnew.ToMM(t.GetWidth()), net=t.GetNetname(),
                 lay=t.GetLayer(), obj=t) for t in tracks]

    def clear(a, b, w, net, lay, skip):
        """Segment a-b (width w, net, layer) keeps the rule distance to all copper of other nets."""
        r = w / 2
        if min(a[0], b[0]) < 0.3 + r or min(a[1], b[1]) < 0.3 + r or max(a[1], b[1]) > H - 0.3 - r:
            return False
        if max(a[0], b[0]) > W - 0.3 - r and not (20.8 <= min(a[1], b[1]) and max(a[1], b[1]) <= 31.2):
            return False
        for pd in pads:
            if pd["net"] == net or lay not in pd["lay"]:
                continue
            need = max(net_clearance(net), net_clearance(pd["net"]))
            if pd["tht"] and not pd["net"]:
                need = max(need, 0.25)         # NPTH: board hole clearance (min_hole_clearance)
            if seg_rect(a, b, pd["rect"]) < r + need - 1e-4:
                return False
        for v in vias:
            if v["net"] != net and seg_point(v["p"], a, b) < r + v["r"] + max(net_clearance(net), net_clearance(v["net"])) - 1e-4:
                return False
        for s in segs:
            if s is skip or s["net"] == net or s["lay"] != lay:
                continue
            if seg_seg(a, b, s["a"], s["b"]) < r + s["w"] / 2 + max(net_clearance(net), net_clearance(s["net"])) - 1e-4:
                return False
        return True

    try:
        from bekantx_power_planes import VCC_AREA, in_poly
    except ImportError:
        VCC_AREA, in_poly = None, None

    def plane_ok(net, q):
        """A moved via must still land on the plane of its net (In1 is split into VCC and +3V3)."""
        if VCC_AREA is None:
            return True
        if net == "VCC":
            return in_poly(q, VCC_AREA)
        if net == "+3V3":
            return not in_poly(q, VCC_AREA)
        return True

    def pad_at(q, net, lay):
        for pd in pads:
            r = pd["rect"]
            if pd["net"] == net and lay in pd["lay"] and not pd["tht"] and r[0] - 1e-3 <= q[0] <= r[2] + 1e-3 and r[1] - 1e-3 <= q[1] <= r[3] + 1e-3:
                return pd
        return None

    # 1. smooth chains: consecutive segments of one net, layer and width, joined at vertices that touch nothing else
    #    (no pad, no via, no third segment), are replaced by the fewest straight pieces that keep the clearance.
    #    This removes the 0.05 mm staircases of the earlier touch-up router runs.
    key = lambda p: (round(p[0], 4), round(p[1], 4))
    at = {}
    for s in segs:
        for p in (s["a"], s["b"]):
            at.setdefault((s["net"], s["lay"], key(p)), []).append(s)
    via_at = {(v["net"], key(v["p"])) for v in vias}

    def interior(s, p):
        lst = at.get((s["net"], s["lay"], key(p)), [])
        if len(lst) != 2 or lst[0]["w"] != lst[1]["w"] or (s["net"], key(p)) in via_at:
            return False
        if pad_at(p, s["net"], s["lay"]) is not None:
            return False
        return not any(o not in lst and o["net"] == s["net"] and o["lay"] == s["lay"] and seg_point(p, o["a"], o["b"]) < 0.01
                       for o in segs)

    dead, seen, n_chain, n_before, n_after = [], set(), 0, 0, 0
    for s0 in list(segs):
        if id(s0) in seen or not mine(s0["net"]):
            continue
        # walk to one end of the chain, then collect it in order
        s, p = s0, s0["a"]
        while interior(s, p):
            nxt = [o for o in at[(s["net"], s["lay"], key(p))] if o is not s][0]
            if nxt is s0:
                break                          # a closed loop: leave it
            p = nxt["b"] if key(nxt["a"]) == key(p) else nxt["a"]
            s = nxt
        chain, pts = [s], [p, s["b"] if key(s["a"]) == key(p) else s["a"]]
        while interior(s, pts[-1]):
            nxt = [o for o in at[(s["net"], s["lay"], key(pts[-1]))] if o is not s][0]
            if nxt in chain:
                break
            pts.append(nxt["b"] if key(nxt["a"]) == key(pts[-1]) else nxt["a"])
            chain.append(nxt)
            s = nxt
        for c in chain:
            seen.add(id(c))
        if len(chain) < 3:
            continue
        net, lay, w = chain[0]["net"], chain[0]["lay"], chain[0]["w"]
        out, i = [pts[0]], 0
        while i < len(pts) - 1:
            j = i + 1
            while j + 1 < len(pts) and clear(pts[i], pts[j + 1], w, net, lay, None):
                j += 1
            out.append(pts[j])
            i = j
        if len(out) >= len(pts):
            continue
        locked = any(c["obj"].IsLocked() for c in chain)
        ref = chain[0]["obj"]
        for p0, p1 in zip(out, out[1:]):
            n = pcbnew.PCB_TRACK(board)
            n.SetStart(P(*p0)); n.SetEnd(P(*p1)); n.SetWidth(ref.GetWidth()); n.SetLayer(ref.GetLayer())
            n.SetNet(ref.GetNet()); n.SetLocked(locked)
            board.Add(n)
            segs.append(dict(a=p0, b=p1, w=w, net=net, lay=lay, obj=n))
        for c in chain:
            segs.remove(c)
            dead.append(c["obj"])
        n_chain += 1
        n_before += len(chain)
        n_after += len(out) - 1
    print(f"chains smoothed: {n_chain}, {n_before} segments -> {n_after}")

    fixed, kept, ok = 0, [], 0
    for s in list(segs):
        if not mine(s["net"]):
            continue
        for end in ("a", "b"):
            q, other = s[end], s["b" if end == "a" else "a"]
            pd = pad_at(q, s["net"], s["lay"])
            if pd is None or pad_at(other, s["net"], s["lay"]) is pd:
                continue                       # not in a pad, or a short piece inside the same pad
            if math.dist(q, pd["c"]) > 0.05:
                # the segment starts inside the pad but not at its centre: fine if a straight piece of the same
                # net runs from the centre to here and q is at the pad edge (usual QFN fan-out: bend at the tip)
                cq = (q[0] - pd["c"][0], q[1] - pd["c"][1])
                axis_ok = abs(cq[0]) < 0.02 or abs(cq[1]) < 0.02
                near = lambda u, v: math.dist(u, v) < 0.02
                feed = any(o is not s and o["net"] == s["net"] and o["lay"] == s["lay"] and
                           ((near(o["a"], q) and near(o["b"], pd["c"])) or (near(o["b"], q) and near(o["a"], pd["c"])))
                           for o in segs)
                if axis_ok and feed:
                    ok += 1
                    continue
            dx, dy = other[0] - q[0], other[1] - q[1]
            ln = math.hypot(dx, dy)
            if ln < 1e-6:
                continue
            ang = math.degrees(math.atan2(dy, dx))
            if pd["fine"]:
                wanted = [pd["out"]]
            else:
                wanted = sorted([(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)],
                                key=lambda d: -(d[0] * dx + d[1] * dy))
            want_ang = math.degrees(math.atan2(wanted[0][1], wanted[0][0]))
            if abs((ang - want_ang + 180) % 360 - 180) <= ANG_TOL:
                ok += 1
                continue                       # already straight in the wanted direction
            r = pd["rect"]
            c = pd["c"]
            done = False
            def candidates():
                """Paths pad centre -> exit -> ... -> far end: straight on, then an L or a 45 degree bend."""
                for d in wanted:
                    half = (r[2] - r[0]) / 2 if d[0] else (r[3] - r[1]) / 2
                    for ex in (EXIT, 0.15, 0.4, 0.6):
                        e = (c[0] + d[0] * (half + ex), c[1] + d[1] * (half + ex))
                        if (e[0] - other[0]) * d[0] + (e[1] - other[1]) * d[1] > 0 and not pd["fine"]:
                            continue           # the exit would overshoot the far end
                        yield [c, e, other]
                        yield [c, e, (e[0], other[1]), other] if d[0] else [c, e, (other[0], e[1]), other]
                        # 45 degree: continue along d, then diagonally onto the far end
                        rx, ry = other[0] - e[0], other[1] - e[1]
                        along = (rx * d[0] + ry * d[1]) - abs(ry * d[0] - rx * d[1])
                        if along > 0:
                            k = (e[0] + d[0] * along, e[1] + d[1] * along)
                            yield [c, e, k, other]

            for path in candidates():
                pts = [p for k, p in enumerate(path) if k == 0 or math.dist(p, path[k - 1]) > 1e-6]
                if no_acute(pts) and \
                        all(clear(p0, p1, s["w"], s["net"], s["lay"], s) for p0, p1 in zip(pts, pts[1:])):
                    t = s["obj"]
                    # the existing segment becomes the last piece, new segments for the pieces before it
                    if end == "a":
                        t.SetStart(P(*path[-2]))
                        s["a"] = path[-2]
                    else:
                        t.SetEnd(P(*path[-2]))
                        s["b"] = path[-2]
                    for p0, p1 in zip(path[:-2], path[1:-1]):
                        if math.dist(p0, p1) < 1e-6:
                            continue
                        n = pcbnew.PCB_TRACK(board)
                        n.SetStart(P(*p0)); n.SetEnd(P(*p1)); n.SetWidth(t.GetWidth()); n.SetLayer(t.GetLayer())
                        n.SetNet(t.GetNet()); n.SetLocked(t.IsLocked())
                        board.Add(n)
                        segs.append(dict(a=p0, b=p1, w=s["w"], net=s["net"], lay=s["lay"], obj=n))
                    fixed += 1
                    done = True
                    break
            if not done:
                dev = abs((ang - want_ang + 180) % 360 - 180)
                kept.append(f"{pd['ref']}.{pd['num']} ({s['net']}, {dev:.0f} deg)")
    # 3. vias whose ring reaches into a pad of their own net (solder wicking) move outwards, with their tracks
    vobjs = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    moved = 0
    for vo in vobjs:
        p = unP(vo.GetPosition())
        rv = pcbnew.ToMM(vo.GetWidth(pcbnew.F_Cu)) / 2
        net = vo.GetNetname()
        if not mine(net):
            continue
        for pd in pads:
            r = pd["rect"]
            if pd["net"] != net or pd["tht"]:
                continue
            if r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]:
                break                          # a via inside the pad (thermal vias of an exposed pad): leave it
            nx, ny = min(max(p[0], r[0]), r[2]), min(max(p[1], r[1]), r[3])
            d = math.hypot(p[0] - nx, p[1] - ny)
            if d >= rv + 0.1 - 1e-4:
                continue
            ux, uy = (p[0] - nx) / d, (p[1] - ny) / d
            q = (p[0] + ux * (rv + 0.1 - d), p[1] + uy * (rv + 0.1 - d))
            attached = [s for s in segs if s["net"] == net and (math.dist(s["a"], p) < 0.01 or math.dist(s["b"], p) < 0.01)]
            ok_v = plane_ok(net, q) and all(clear(q, q, 2 * rv, net, lay, None) for lay in (pcbnew.F_Cu, pcbnew.B_Cu))
            ok_v = ok_v and all(clear(q if math.dist(s["a"], p) < 0.01 else s["a"],
                                      q if math.dist(s["b"], p) < 0.01 else s["b"], s["w"], net, s["lay"], s)
                                for s in attached)
            ok_v = ok_v and not any(o is not vo and math.dist(unP(o.GetPosition()), q) < rv + 0.25 + 0.15 for o in vobjs
                                    if o.GetNetname() != net)
            if ok_v:
                vo.SetPosition(P(*q))
                for s in attached:
                    if math.dist(s["a"], p) < 0.01:
                        s["obj"].SetStart(P(*q)); s["a"] = q
                    else:
                        s["obj"].SetEnd(P(*q)); s["b"] = q
                for v in vias:
                    if v["net"] == net and math.dist(v["p"], p) < 0.01:
                        v["p"] = q
                moved += 1
            break
    # 4. tracks narrower than their net class get the class width where it fits
    widened = 0
    for s in segs:
        cw = net_width(s["net"])
        if mine(s["net"]) and s["w"] < cw - 1e-6 and clear(s["a"], s["b"], cw, s["net"], s["lay"], s):
            s["obj"].SetWidth(MM(cw))
            s["w"] = cw
            widened += 1
    # 5. a segment lying completely on another, wider or equal segment of the same net and layer is removed
    dup = 0
    for s in list(segs):
        if not mine(s["net"]):
            continue
        for o in segs:
            if o is s or o["net"] != s["net"] or o["lay"] != s["lay"] or o["w"] < s["w"] - 1e-6:
                continue
            if seg_point(s["a"], o["a"], o["b"]) < 0.005 and seg_point(s["b"], o["a"], o["b"]) < 0.005 and \
                    not (math.dist(s["a"], o["a"]) < 1e-4 and math.dist(s["b"], o["b"]) < 1e-4 and id(s) < id(o)):
                segs.remove(s)
                dead.append(s["obj"])
                dup += 1
                break
    print(f"vias moved off pads: {moved}, tracks widened to class width: {widened}, duplicate segments removed: {dup}")
    octilinear(board, segs, vias, vobjs, pads, clear, plane_ok, pad_at)
    remove_jogs(segs, vias, dead, clear, pad_at)
    for o in dead:                           # removals last: pcbnew proxies break after Remove()
        board.Remove(o)
    pcbnew.SaveBoard(str(dst), board)
    print(f"pad entries: {ok} straight, {fixed} straightened, {len(kept)} left as they are: {kept}")


if __name__ == "__main__":
    nets = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--nets=")), "")
    if nets:
        ONLY = set(nets.split(","))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], args[1])
