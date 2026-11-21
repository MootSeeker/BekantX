"""Re-route the bad parts of outer-layer tracks as horizontal/vertical runs with small 45 degree chamfers.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/manhattan.py <in.kicad_pcb> <out.kicad_pcb> [--passes=3] [--nets=A,B]

Layout rules of the user feedback 2026-11-21:
- every track that ends in a pad or via arrives through its centre, straight along the x or y axis,
- no odd angles, no long diagonal runs: 45 degrees only as a short chamfer between two axis-parallel legs.

A *chain* is a run of segments of one net and layer between two nodes (pad, via, junction or open end). A chain is
bad when its first/last segment misses the node centre or is not axis-parallel, when a segment is neither
axis-parallel nor 45 degrees, or when a 45 degree piece is longer than DIAG_MAX or not enclosed by axis legs.
For every bad chain a window of vertices around the bad part (growing until it fits) is replaced by the cheapest
polyline of L/Z shape (axis legs, every 90 degree corner chamfered) that keeps all clearances (pcb_geom, KiCad's
own shapes), starts/ends exactly at the node centres, leaves a pad straight for PAD_EXIT, and joins the kept
neighbours with a turn of at most 45 degrees. Cost = length + vertices + deviation from the old path, so the
tracks stay in their corridors. Nothing is deleted from the board during the run (pcbnew proxies break after
Remove()); dead segments are removed at the very end, then the file is saved.
"""
import collections, math, sys

import pcbnew

from bekantx_layout import MM, P, unP
from pcb_geom import Copper, OUTER, bbox_mm, uid

DIAG_MAX = 1.5          # mm: longest 45 degree piece that still counts as a chamfer
PAD_EXIT = 0.15         # mm of straight track outside a pad edge before the first bend
CUTS = (0.6, 0.4, 0.25, 0.15, 0.08)
MIN_CUT = 0.04
NEAR = 0.12            # mm: gap of ends that count as one vertex
MIN_SEG = 0.05          # no stubs shorter than this
TURN_MAX = 45.01        # degrees at the joint with a kept neighbour
SKIP_NETS = {"Net-(AE1-FEED)", "Net-(U2-LNA_IN)"}     # RF feed: geometry is part of the matching
MAX_TESTS = 160         # candidate polylines tested per window
SQ2 = math.sqrt(2.0)


def key(p):
    return (round(p[0], 3), round(p[1], 3))


def classify(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if math.hypot(dx, dy) < 1e-6:
        return "zero", 0.0
    ang = math.degrees(math.atan2(abs(dy), abs(dx)))
    if ang < 0.05 or ang > 89.95:
        return "axis", ang
    if abs(ang - 45) < 0.6:
        return "45", ang
    return "other", ang


def unit(a, b):
    d = math.dist(a, b)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def turn(u, v):
    c = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
    return math.degrees(math.acos(c))


def pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


class Fast(Copper):
    """Copper with a spatial hash for the clearance queries and incremental updates."""
    CELL = 1.5

    def __init__(self, board):
        super().__init__(board)
        self.grid = collections.defaultdict(list)
        for it in self.items:
            it["uid"] = uid(it["obj"])
            self._reg(it)
        self.maxneed = 0.6

    def _cells(self, box):
        c = self.CELL
        for i in range(int(math.floor(box[0] / c)), int(math.floor(box[2] / c)) + 1):
            for j in range(int(math.floor(box[1] / c)), int(math.floor(box[3] / c)) + 1):
                yield (i, j)

    def _reg(self, it):
        for c in self._cells(it["box"]):
            self.grid[c].append(it)

    def add_track(self, t):
        it = dict(obj=t, kind="track", net=t.GetNetname(), layers=[t.GetLayer()], box=bbox_mm(t), uid=uid(t))
        self.items.append(it)
        self._reg(it)
        return it

    def drop_track(self, t):
        u = uid(t)
        for it in [i for i in self.items if i.get("uid") == u]:
            self.items.remove(it)
            for c in self._cells(it["box"]):
                if it in self.grid[c]:
                    self.grid[c].remove(it)

    def _hits(self, shape, box, net, layers, skip, extra=0.0):
        from bekantx_layout import net_clearance
        m = self.maxneed + extra
        seen = set()
        for c in self._cells((box[0] - m, box[1] - m, box[2] + m, box[3] + m)):
            for it in self.grid.get(c, ()):
                k = id(it)
                if k in seen:
                    continue
                seen.add(k)
                if it["uid"] in skip or (it["net"] == net and net):
                    continue
                if not set(layers) & set(it["layers"]):
                    continue
                need = max(net_clearance(net), net_clearance(it["net"])) + extra
                b = it["box"]
                if b[0] - need > box[2] or b[2] + need < box[0] or b[1] - need > box[3] or b[3] + need < box[1]:
                    continue
                for lay in set(layers) & set(it["layers"]):
                    if it["obj"].GetEffectiveShape(lay).Collide(shape, MM(need) - 1000):
                        return it
        return None


class Chain:
    def __init__(self, net, lay, segs, pts, node_s, node_e, locked):
        self.net, self.lay, self.segs, self.pts = net, lay, segs, pts
        self.node_s, self.node_e, self.locked = node_s, node_e, locked
        self.failed = set()


class Fixer:
    def __init__(self, board, only_nets=None):
        self.board = board
        self.cu = Fast(board)
        self.dead = []
        self.only = only_nets
        self.stats = collections.Counter()
        self.ok_diag = set()                 # uids of 45 degree runs kept on purpose (no Manhattan path fits)
        self.node_cache = {}
        self.npth = []                       # drilled holes without copper: tracks keep the hole clearance
        for fp in board.GetFootprints():
            for pd in fp.Pads():
                if pd.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    x, y = unP(pd.GetPosition())
                    self.npth.append((x, y, pcbnew.ToMM(max(pd.GetDrillSize().x, pd.GetDrillSize().y)) / 2))
        self.nodes_by_net = collections.defaultdict(list)
        for it in self.cu.items:
            if it["kind"] in ("pad", "via"):
                self.nodes_by_net[it["net"]].append(it)

    def hole_ok(self, a, b, w):
        for x, y, r in self.npth:
            if pt_seg((x, y), a, b) < r + w / 2 + 0.25 + 0.01:
                return False
        return True

    # ---------------------------------------------------------------- nodes
    def node_at(self, pt, net, lay):
        best = None
        for it in self.nodes_by_net.get(net, ()):
            if lay not in it["layers"]:
                continue
            bx = it["box"]
            if pt[0] < bx[0] or pt[0] > bx[2] or pt[1] < bx[1] or pt[1] > bx[3]:
                continue
            if it["obj"].HitTest(P(*pt)):
                if it["kind"] == "via":
                    return it
                if best is None:
                    best = it
        return best

    @staticmethod
    def centre(node):
        return unP(node["obj"].GetPosition())

    def exit_len(self, node, d):
        """Distance from the node centre to its edge along the unit vector d, plus PAD_EXIT."""
        c = self.centre(node)
        o = node["obj"]
        t = 0.0
        while t < 4.0 and o.HitTest(P(c[0] + d[0] * t, c[1] + d[1] * t)):
            t += 0.01
        return t + PAD_EXIT

    # ---------------------------------------------------------------- chains
    def build_chains(self):
        groups = collections.defaultdict(list)
        for t in self.board.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetLayer() not in OUTER or uid(t) in {uid(d) for d in self.dead}:
                continue
            a, b = unP(t.GetStart()), unP(t.GetEnd())
            if math.dist(a, b) < 1e-6:
                continue
            groups[(t.GetNetname(), t.GetLayer())].append(dict(obj=t, a=a, b=b, w=pcbnew.ToMM(t.GetWidth())))
        chains = []
        for (net, lay), segs in groups.items():
            if net in SKIP_NETS or (self.only and net not in self.only):
                continue
            vmap = collections.defaultdict(list)
            for s in segs:
                vmap[key(s["a"])].append((s, "a"))
                vmap[key(s["b"])].append((s, "b"))
            frozen = set()
            for k, lst in vmap.items():                   # T junction on the inside of a segment: freeze that segment
                if len(lst) != 1 and len(lst) < 3:
                    continue
                p = lst[0][0][lst[0][1]]
                for s in segs:
                    if s is lst[0][0] or key(s["a"]) == k or key(s["b"]) == k:
                        continue
                    if pt_seg(p, s["a"], s["b"]) < 0.002:
                        frozen.add(id(s))
            for k, lst in list(vmap.items()):
                if len(lst) == 1:
                    p = lst[0][0][lst[0][1]]
                    for s in segs:
                        if s is not lst[0][0] and pt_seg(p, s["a"], s["b"]) < 0.002 and key(s["a"]) != k and key(s["b"]) != k:
                            frozen.add(id(s))
            nodeinfo = {}

            def nd(k):
                if k not in nodeinfo:
                    nodeinfo[k] = self.node_at(k, net, lay) if True else None
                return nodeinfo[k]

            def boundary(k):
                return nd(k) is not None or len(vmap[k]) != 2

            visited = set()
            for s in segs:
                if id(s) in visited:
                    continue
                # walk to one boundary, then along the chain
                cur, end = s, "a"
                seen = {id(cur)}
                while True:
                    k = key(cur[end])
                    if boundary(k):
                        break
                    nxt = [x for x in vmap[k] if x[0] is not cur]
                    if not nxt or id(nxt[0][0]) in seen:
                        break
                    cur, e2 = nxt[0]
                    seen.add(id(cur))
                    end = "b" if e2 == "a" else "a"
                # cur has its boundary vertex at `end`; walk the other way
                order = []
                pts = [cur[end]]
                node = cur
                e_in = end
                chain_frozen = False
                while True:
                    order.append(node)
                    e_out = "b" if e_in == "a" else "a"
                    pts.append(node[e_out])
                    visited.add(id(node))
                    if id(node) in frozen:
                        chain_frozen = True
                    k = key(node[e_out])
                    if boundary(k):
                        break
                    nxt = [x for x in vmap[k] if x[0] is not node]
                    if not nxt:
                        break
                    node, e_in = nxt[0]
                    if id(node) in visited:
                        chain_frozen = True
                        break
                if chain_frozen or len(order) == 0:
                    continue
                ns, ne = nd(key(pts[0])), nd(key(pts[-1]))
                if ns is not None and ne is not None and ns is ne and len(order) == 1:
                    continue
                if len(order) == 1 and ns is None and ne is None:
                    pass
                locked = any(sg["obj"].IsLocked() for sg in order)
                chains.append(Chain(net, lay, [sg["obj"] for sg in order], [tuple(p) for p in pts], ns, ne, locked))
                chains[-1].w = [sg["w"] for sg in order]
        return chains

    # ---------------------------------------------------------------- badness
    def bad_segments(self, ch):
        n = len(ch.segs)
        out = []
        for k in range(n):
            if k in ch.failed:
                continue
            a, b = ch.pts[k], ch.pts[k + 1]
            cls, ang = classify(a, b)
            L = math.dist(a, b)
            bad = False
            for end, node, other in ((0, ch.node_s, b), (n - 1, ch.node_e, a)):
                pass
            if k == 0 and ch.node_s is not None:
                bad |= self.entry_bad(ch.node_s, a, b, cls)
            if k == n - 1 and ch.node_e is not None:
                bad |= self.entry_bad(ch.node_e, b, a, cls)
            if cls == "other":
                bad = True
            elif cls == "45":
                pa = classify(ch.pts[k - 1], a)[0] if k > 0 else "axis"
                nb = classify(b, ch.pts[k + 2])[0] if k < n - 1 else "axis"
                if (k == 0 and ch.node_s is not None) or (k == n - 1 and ch.node_e is not None):
                    bad = True                           # a 45 degree piece right at a pad or via
                if (L > DIAG_MAX or pa != "axis" or nb != "axis") and uid(ch.segs[k]) not in self.ok_diag:
                    bad = True
            if bad:
                out.append(k)
        return out

    def entry_bad(self, node, e, o, cls):
        """Segment e->o leaves the node at e: must be axis-parallel and its line must pass through the node centre."""
        c = self.centre(node)
        if node["obj"].HitTest(P(*o)):
            return False
        dx, dy = o[0] - e[0], o[1] - e[1]
        L = math.hypot(dx, dy)
        perp = abs((c[0] - e[0]) * dy - (c[1] - e[1]) * dx) / L
        return perp > 0.02 or cls != "axis"

    # ---------------------------------------------------------------- candidates
    def polyline(self, pts, c_all, m_start, m_end):
        """Chamfer every corner of an axis-parallel polyline; None when a leg is too short."""
        pts = [pts[0]] + [p for i, p in enumerate(pts[1:], 1) if math.dist(p, pts[i - 1]) > 1e-6]
        # drop collinear vertices
        k = 1
        while k < len(pts) - 1:
            u, v = unit(pts[k - 1], pts[k]), unit(pts[k], pts[k + 1])
            if abs(u[0] * v[0] + u[1] * v[1]) > 0.9999 and u[0] * v[0] + u[1] * v[1] > 0:
                del pts[k]
            else:
                k += 1
        n = len(pts)
        if n < 2:
            return None
        L = [math.dist(pts[k], pts[k + 1]) for k in range(n - 1)]
        for k in range(n - 2):
            u, v = unit(pts[k], pts[k + 1]), unit(pts[k + 1], pts[k + 2])
            if abs(u[0] * v[0] + u[1] * v[1]) > 0.001:
                return None                          # not a 90 degree corner (U turn): reject
        avail = []
        for k in range(n - 1):
            a = L[k] - (m_start if k == 0 else 0.0) - (m_end if k == n - 2 else 0.0)
            avail.append(a)
        if min(avail) < 0:
            return None
        cuts = {}
        for v in range(1, n - 1):
            cl = avail[v - 1] / (2.0 if v - 1 >= 1 else 1.0)
            cr = avail[v] / (2.0 if v + 1 <= n - 2 else 1.0)
            c = min(c_all, cl, cr)
            if c < MIN_CUT:
                return None
            cuts[v] = c
        out = [pts[0]]
        for v in range(1, n - 1):
            u, w = unit(pts[v - 1], pts[v]), unit(pts[v], pts[v + 1])
            q1 = (pts[v][0] - u[0] * cuts[v], pts[v][1] - u[1] * cuts[v])
            q2 = (pts[v][0] + w[0] * cuts[v], pts[v][1] + w[1] * cuts[v])
            out += [q1, q2]
        out.append(pts[-1])
        res = [out[0]]
        for p in out[1:]:
            if math.dist(p, res[-1]) > 1e-6:
                res.append(p)
        k = 1
        while k < len(res) - 1:                       # two consumed chamfers leave collinear 45 degree pieces
            u, v = unit(res[k - 1], res[k]), unit(res[k], res[k + 1])
            if u[0] * v[0] + u[1] * v[1] > 0.9999:
                del res[k]
            else:
                k += 1
        if any(math.dist(res[k], res[k + 1]) < MIN_SEG for k in range(len(res) - 1)):
            return None
        return res

    def dev(self, new, old):
        tot, cnt = 0.0, 0
        for i in range(len(new) - 1):
            a, b = new[i], new[i + 1]
            L = math.dist(a, b)
            m = max(1, int(L / 0.4))
            for s in range(m + 1):
                q = (a[0] + (b[0] - a[0]) * s / m, a[1] + (b[1] - a[1]) * s / m)
                tot += min(pt_seg(q, old[j], old[j + 1]) for j in range(len(old) - 1))
                cnt += 1
        return tot / max(cnt, 1)

    @staticmethod
    def fallback_shapes(P0, Q0, m_s, m_e):
        """Axis leg - 45 degree run - axis leg shapes (HDH, VDV, HDV, VDH) for windows where no L/Z shape fits."""
        dx, dy = Q0[0] - P0[0], Q0[1] - P0[1]
        sx = 1.0 if dx >= 0 else -1.0
        sy = 1.0 if dy >= 0 else -1.0
        ax, ay = abs(dx), abs(dy)
        out = []
        step = 0.1
        if ax > 1e-3 and ay > 1e-3:
            a = m_s
            while a <= ax - ay - m_e + 1e-9:                          # H, D, H
                p1 = (P0[0] + sx * a, P0[1])
                p2 = (p1[0] + sx * ay, Q0[1])
                out.append([P0, p1, p2, Q0])
                a += step
            a = m_s
            while a <= ay - ax - m_e + 1e-9:                          # V, D, V
                p1 = (P0[0], P0[1] + sy * a)
                p2 = (Q0[0], p1[1] + sy * ax)
                out.append([P0, p1, p2, Q0])
                a += step
            a = m_s
            while a < ax - 1e-6:                                      # H, D, V (diag ends on the x of Q)
                k = ax - a
                if ay - k >= m_e:
                    out.append([P0, (P0[0] + sx * a, P0[1]), (Q0[0], P0[1] + sy * k), Q0])
                a += step
            a = m_s
            while a < ay - 1e-6:                                      # V, D, H
                k = ay - a
                if ax - k >= m_e:
                    out.append([P0, (P0[0], P0[1] + sy * a), (P0[0] + sx * k, Q0[1]), Q0])
                a += step
        res = []
        for pl in out:
            pl = [pl[0]] + [p for k, p in enumerate(pl[1:], 1) if math.dist(p, pl[k - 1]) > 1e-6]
            if len(pl) >= 3 and all(math.dist(pl[k], pl[k + 1]) >= MIN_SEG for k in range(len(pl) - 1)):
                res.append(pl)
        return res

    def try_window(self, ch, i, j, fallback=False):
        n = len(ch.segs)
        P0 = self.centre(ch.node_s) if (i == 0 and ch.node_s is not None) else ch.pts[i]
        Q0 = self.centre(ch.node_e) if (j == n and ch.node_e is not None) else ch.pts[j]
        old = [P0] + list(ch.pts[i + 1:j]) + [Q0]
        u_prev = unit(ch.pts[i - 1], ch.pts[i]) if i > 0 else None
        u_next = unit(ch.pts[j], ch.pts[j + 1]) if j < n else None
        node_p = ch.node_s if (i == 0 and ch.node_s is not None) else None
        node_q = ch.node_e if (j == n and ch.node_e is not None) else None
        dx, dy = Q0[0] - P0[0], Q0[1] - P0[1]
        ax, ay = abs(dx) < 1e-3, abs(dy) < 1e-3
        xs = {round(p[0], 3) for p in old}
        ys = {round(p[1], 3) for p in old}
        lox, hix = min(P0[0], Q0[0]) - 1.5, max(P0[0], Q0[0]) + 1.5
        loy, hiy = min(P0[1], Q0[1]) - 1.5, max(P0[1], Q0[1]) + 1.5
        g = math.ceil(lox / 0.25) * 0.25
        while g <= hix:
            xs.add(round(g, 3)); g += 0.25
        g = math.ceil(loy / 0.25) * 0.25
        while g <= hiy:
            ys.add(round(g, 3)); g += 0.25
        for d in (-0.2, -0.1, 0.1, 0.2):
            for p in old[1:-1]:
                xs.add(round(p[0] + d, 3)); ys.add(round(p[1] + d, 3))
        shapes = []
        if ax or ay:
            shapes.append([P0, Q0])
        if not ax and not ay:
            shapes.append([P0, (Q0[0], P0[1]), Q0])
            shapes.append([P0, (P0[0], Q0[1]), Q0])
        for xm in xs:
            if abs(xm - P0[0]) > 1e-3 and abs(xm - Q0[0]) > 1e-3 and not ay:
                shapes.append([P0, (xm, P0[1]), (xm, Q0[1]), Q0])
        for ym in ys:
            if abs(ym - P0[1]) > 1e-3 and abs(ym - Q0[1]) > 1e-3 and not ax:
                shapes.append([P0, (P0[0], ym), (Q0[0], ym), Q0])
        w_all = max(ch.w[i:j])
        w_first, w_last = ch.w[i], ch.w[j - 1]
        cands = []
        if fallback:
            m_s = self.exit_len(node_p, unit(P0, (P0[0] + (1 if dx >= 0 else -1), P0[1]))) if node_p else 0.0
            for pl in self.fallback_shapes(P0, Q0, 0.0 if not node_p else 0.25, 0.0 if not node_q else 0.25):
                d0, d1 = unit(pl[0], pl[1]), unit(pl[-2], pl[-1])
                if u_prev is not None and turn(u_prev, d0) > TURN_MAX:
                    continue
                if u_next is not None and turn(d1, u_next) > TURN_MAX:
                    continue
                ms = self.exit_len(node_p, d0) if node_p else 0.0
                me = self.exit_len(node_q, (-d1[0], -d1[1])) if node_q else 0.0
                if math.dist(pl[0], pl[1]) < ms or math.dist(pl[-2], pl[-1]) < me:
                    continue
                length = sum(math.dist(pl[k], pl[k + 1]) for k in range(len(pl) - 1))
                diag = sum(math.dist(pl[k], pl[k + 1]) for k in range(len(pl) - 1) if classify(pl[k], pl[k + 1])[0] == "45")
                cands.append((length + 0.3 * len(pl) + 0.6 * self.dev(pl, old) + 2.0 + 0.3 * diag, pl))
            shapes = []
        for sh in shapes:
            d0 = unit(sh[0], sh[1])
            d1 = unit(sh[-2], sh[-1])
            if u_prev is not None and turn(u_prev, d0) > TURN_MAX:
                continue
            if u_next is not None and turn(d1, u_next) > TURN_MAX:
                continue
            m_s = self.exit_len(node_p, d0) if node_p else 0.0
            m_e = self.exit_len(node_q, (-d1[0], -d1[1])) if node_q else 0.0
            if node_p and (m_s > 0 and len(sh) == 2 and False):
                continue
            for c_all in (CUTS if len(sh) > 2 else (0.0,)):
                pl = self.polyline(sh, c_all, m_s, m_e) if len(sh) > 2 else sh
                if pl is None:
                    continue
                length = sum(math.dist(pl[k], pl[k + 1]) for k in range(len(pl) - 1))
                cost = length + 0.3 * len(pl) + 0.6 * self.dev(pl, old)
                if node_p:                       # leaving a long pad across its short side looks odd
                    o = node_p["obj"]
                    if node_p["kind"] == "pad":
                        sz = o.GetSize()
                        if sz.x != sz.y:
                            along_x = abs(d0[0]) > 0.5
                            if (sz.x > sz.y) != along_x:
                                cost += 0.8
                cands.append((cost, pl))
        cands.sort(key=lambda x: x[0])
        skip = list(ch.segs[i:j])
        for cost, pl in cands[:MAX_TESTS]:
            ok = True
            ws = []
            for k in range(len(pl) - 1):
                w = w_all
                if k == 0:
                    w = w_first
                if k == len(pl) - 2:
                    w = min(w, w_last) if k == 0 else w_last
                ws.append(w)
            for k in range(len(pl) - 1):
                if k == 0 and False:
                    pass
                if not self.hole_ok(pl[k], pl[k + 1], ws[k]) or                         not self.cu.seg_clear(pl[k], pl[k + 1], ws[k], ch.net, ch.lay, skip=skip):
                    ok = False
                    break
            if ok:
                return pl, ws
        return None

    # ---------------------------------------------------------------- apply
    def apply(self, ch, i, j, pl, ws, fallback=False):
        board = self.board
        old = ch.segs[i:j]
        new_objs = []
        for k in range(len(pl) - 1):
            if k < len(old):
                t = old[k]
                self.cu.drop_track(t)
            else:
                t = pcbnew.PCB_TRACK(board)
                t.SetLayer(ch.lay)
                t.SetNet(board.FindNet(ch.net))
                board.Add(t)
                if ch.locked:
                    t.SetLocked(True)
            t.SetStart(P(*pl[k])); t.SetEnd(P(*pl[k + 1])); t.SetWidth(MM(ws[k]))
            new_objs.append(t)
        for t in old[len(pl) - 1:]:
            self.cu.drop_track(t)
            t.SetStart(P(*pl[0])); t.SetEnd(P(*pl[0]))
            self.dead.append(t)
        for t in new_objs:
            self.cu.add_track(t)
            self.ok_diag.discard(uid(t))
        if fallback:
            for t, k in zip(new_objs, range(len(pl) - 1)):
                if classify(pl[k], pl[k + 1])[0] == "45" and math.dist(pl[k], pl[k + 1]) > DIAG_MAX:
                    self.ok_diag.add(uid(t))
        ch.segs[i:j] = new_objs
        ch.pts[i:j + 1] = pl
        ch.w[i:j] = ws
        # keep ch.failed meaningful: indices moved, reset
        ch.failed = set()

    def fix_chain(self, ch):
        done = 0
        guard = 0
        seen = {tuple(ch.pts)}
        while guard < 12:
            guard += 1
            bad = self.bad_segments(ch)
            if not bad:
                break
            n = len(ch.segs)
            k0 = bad[0]
            k1 = k0
            while k1 + 1 in bad:
                k1 += 1
            fixed = False
            for fb in (False, True):
                for g in range(1, n + 1):
                    i, j = max(0, k0 - g), min(n, k1 + 1 + g)
                    res = self.try_window(ch, i, j, fb)
                    if res:
                        sig = tuple(ch.pts[:i] + res[0] + ch.pts[j + 1:])
                        if sig in seen:
                            continue
                        seen.add(sig)
                        self.apply(ch, i, j, *res, fallback=fb)
                        done += 1
                        fixed = True
                        break
                    if i == 0 and j == n:
                        break
                if fixed:
                    break
            if not fixed:
                for k in range(k0, k1 + 1):
                    ch.failed.add(k)
        return done

    def snap_near_joins(self):
        """Track ends of one net and layer that nearly meet (gap under NEAR) and touch no pad or via are moved to the
        midpoint, so the two segments form one clean vertex instead of a kink (KiCad joined them by overlap)."""
        groups = collections.defaultdict(list)
        for t in self.board.GetTracks():
            if t.GetClass() == "PCB_TRACK" and t.GetLayer() in OUTER and t.GetNetname() not in SKIP_NETS:
                groups[(t.GetNetname(), t.GetLayer())].append(t)
        moved = 0
        for (net, lay), ts in groups.items():
            ends = [(t, e, unP(t.GetStart() if e == "a" else t.GetEnd())) for t in ts for e in ("a", "b")]
            for x in range(len(ends)):
                for y in range(x + 1, len(ends)):
                    t1, e1, p1 = ends[x]
                    t2, e2, p2 = ends[y]
                    d = math.dist(p1, p2)
                    if t1 is t2 or d < 1e-3 or d > NEAR:
                        continue
                    if self.node_at(p1, net, lay) or self.node_at(p2, net, lay):
                        continue
                    mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                    ok = True
                    for t, e in ((t1, e1), (t2, e2)):
                        a = unP(t.GetStart()); b = unP(t.GetEnd())
                        na, nb = (mid, b) if e == "a" else (a, mid)
                        if math.dist(na, nb) < 1e-3 or not self.hole_ok(na, nb, pcbnew.ToMM(t.GetWidth())) or                                 not self.cu.seg_clear(na, nb, pcbnew.ToMM(t.GetWidth()), net, lay, skip=[t]):
                            ok = False
                    if not ok:
                        continue
                    for t, e in ((t1, e1), (t2, e2)):
                        self.cu.drop_track(t)
                        (t.SetStart if e == "a" else t.SetEnd)(P(*mid))
                        self.cu.add_track(t)
                    ends[x] = (t1, e1, mid); ends[y] = (t2, e2, mid)
                    moved += 1
        print(f"near joins snapped to one vertex: {moved}")

    def run(self, passes=3):
        self.snap_near_joins()
        for ps in range(passes):
            chains = self.build_chains()
            todo = [c for c in chains if self.bad_segments(c)]
            todo.sort(key=lambda c: -sum(math.dist(c.pts[k], c.pts[k + 1]) for k in range(len(c.segs))))
            nfix = 0
            for ch in todo:
                nfix += self.fix_chain(ch)
            left = sum(1 for c in chains if self.bad_segments(c))
            print(f"pass {ps + 1}: chains {len(chains)}, bad {len(todo)}, windows replaced {nfix}, still bad {left}")
            if nfix == 0:
                break

    def finish(self, dst):
        for t in self.dead:
            self.board.Remove(t)
        pcbnew.SaveBoard(str(dst), self.board)


def main(src, dst, passes=3, only=None):
    board = pcbnew.LoadBoard(str(src))
    fx = Fixer(board, only)
    fx.run(passes)
    fx.finish(dst)
    print("saved", dst, "dead segments removed:", len(fx.dead))


if __name__ == "__main__":
    passes, only = 3, None
    for a in sys.argv[1:]:
        if a.startswith("--passes="):
            passes = int(a.split("=")[1])
        if a.startswith("--nets="):
            only = set(a.split("=")[1].split(","))
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], passes, only)
