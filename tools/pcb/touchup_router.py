"""Close the connections the autorouter left open with a small grid router (A*, two layers, vias).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/touchup_router.py <in.kicad_pcb> <out.kicad_pcb> [--grid=0.05]

For every open connection of the DRC report (kicad-cli) a path is searched on F.Cu/B.Cu that keeps the
clearance and width of the net class to all copper of other nets, the board edge, holes and keep-outs.
Obstacles are rasterised conservatively (pads as their bounding boxes, half a grid step extra), so a path
that is found is DRC clean; a connection that finds no path is reported and stays open.
--rip    in the first round a blocked connection may cross unlocked tracks of other nets; those segments
         are removed and routed again in the following rounds, which do not rip up any more (ripping in
         every round does not converge: it tears up more than it closes)
--inner  In1 (the +3V3 plane) may be used as a third layer, at a high cost
--release=NET,NET        remove the unlocked routing of these nets first (they are routed again)
--release-vias=X/Y,X/Y   remove the vias at these board positions first (mm, also locked ones)
--first=NET,NET          route the open connections of these nets before all others
--plane-nets=NET,NET     for these nets a via into their filled inner-layer plane also closes a connection
--manual=FILE            json with release_nets, release_vias, tracks, vias and first (see bekantx_manual.json)
--opencost=X --openr=R   cost factor X for track cells farther than R mm (0.7) from any copper: new tracks hug
                         existing copper and cut the outer GND pours less (default 1 = off)
--bcost=X                cost factor of a track step on B.Cu (default 1); > 1 keeps long runs on F.Cu so that
                         the GND pour on B.Cu stays in one piece (B.Cu then only connects the pads)
The tracks are not locked.
"""
import heapq, json, math, re, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import pcbnew

from bekantx_layout import KICAD_BIN, NETCLASSES, ORIGIN, P, ROOT, net_clearance, unP

VIA_D, VIA_DRILL, VIA_COST = 0.5, 0.3, 40.0   # a via costs as much as 2 mm of track (fewer layer changes)
LAYER = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu, "I": pcbnew.In1_Cu}
INNER_COST = 4.0        # a track on In1 cuts the +3V3 plane: only where nothing else works
RIP_COST = 8.0          # per grid cell inside the clearance area of a track that would have to be ripped up
B_COST = 1.0            # cost factor of B.Cu (--bcost)
OPEN_COST = 1.0         # cost factor of cells farther than OPEN_R from any copper (--opencost): runs hug existing copper
OPEN_R = 0.7            # mm (--openr), so a new track cuts the outer GND pours as little as possible


def net_width(net):
    import fnmatch
    for name, (w, _c, _v, _d, pats) in NETCLASSES.items():
        if any(fnmatch.fnmatchcase(net, p.replace("[", "[[]")) if "*" in p else net == p for p in pats):
            return w
    return NETCLASSES["Default"][0]


def touchup_width(net):
    """Width used here: the class width, but at most 0.25 mm so that a track can leave a 0.5 mm pitch pad."""
    w = net_width(net)
    return w if w >= 0.4 else min(w, 0.2)


def open_connections(board_path):
    with tempfile.TemporaryDirectory() as d:
        rep = Path(d) / "drc.json"
        subprocess.run([str(KICAD_BIN / "kicad-cli.exe"), "pcb", "drc", "--format", "json", "--severity-all",
                        "-o", str(rep), str(board_path)], capture_output=True)
        data = json.loads(rep.read_text(encoding="utf-8"))
    out = []
    for u in data.get("unconnected_items", []):
        a, b = u["items"][:2]
        net = re.search(r"\[([^\]]+)\]", a["description"]).group(1)
        out.append((net, (a["pos"]["x"], a["pos"]["y"]), (b["pos"]["x"], b["pos"]["y"])))
    return out


class Grid:
    def __init__(self, board, iface, g, layers="FB", plane_nets=()):
        self.b, self.g, self.layers = board, g, layers
        # filled plane copper of the given nets on the inner layers (zones must be filled)
        self.plane_nets = {}
        for z in board.Zones():
            if z.GetIsRuleArea() or z.GetNetname() not in plane_nets:
                continue
            for lay in (pcbnew.In1_Cu, pcbnew.In2_Cu):
                if z.IsOnLayer(lay):
                    self.plane_nets.setdefault(z.GetNetname(), []).append(z.GetFilledPolysList(lay))
        self.W, self.H = iface["board"]["width"] + 4.0, iface["board"]["depth"]
        self.nx, self.ny = int(self.W / g) + 1, int(self.H / g) + 1
        self.iface = iface
        self.xs = np.arange(self.nx) * g
        self.ys = np.arange(self.ny) * g

    def collect(self):
        """All copper as primitives: (kind, geometry, net, layers) with layers a subset of 'FB'."""
        prim = []
        for fp in self.b.GetFootprints():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
                x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
                lay = "A" if pad.HasHole() else ("B" if pad.IsOnLayer(pcbnew.B_Cu) else "F")
                prim.append(("rect", (x0, y0, x1, y1), pad.GetNetname(), lay, None))
        for t in self.b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                x, y = unP(t.GetPosition())
                prim.append(("circle", (x, y, pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2), t.GetNetname(), "A", None))
            elif t.GetLayer() in LAYER.values():
                prim.append(("seg", unP(t.GetStart()) + unP(t.GetEnd()) + (pcbnew.ToMM(t.GetWidth()) / 2,),
                             t.GetNetname(), [k for k, v in LAYER.items() if v == t.GetLayer()][0],
                             None if t.IsLocked() else t))
        return prim

    def window(self, x0, y0, x1, y1):
        i0, i1 = max(0, int(x0 / self.g)), min(self.nx, int(x1 / self.g) + 2)
        j0, j1 = max(0, int(y0 / self.g)), min(self.ny, int(y1 / self.g) + 2)
        return i0, i1, j0, j1

    def dist(self, kind, geo, i0, i1, j0, j1):
        X, Y = np.meshgrid(self.xs[i0:i1], self.ys[j0:j1], indexing="ij")
        if kind == "rect":
            dx = np.maximum(np.maximum(geo[0] - X, X - geo[2]), 0)
            dy = np.maximum(np.maximum(geo[1] - Y, Y - geo[3]), 0)
            return np.hypot(dx, dy)
        if kind == "circle":
            return np.hypot(X - geo[0], Y - geo[1]) - geo[2]
        ax, ay, bx, by, r = geo
        l2 = (bx - ax) ** 2 + (by - ay) ** 2
        u = np.zeros_like(X) if l2 == 0 else np.clip(((X - ax) * (bx - ax) + (Y - ay) * (by - ay)) / l2, 0, 1)
        return np.hypot(X - ax - u * (bx - ax), Y - ay - u * (by - ay)) - r

    def maps(self, prim, net, width, rip=False):
        """blocked[layer][i, j] for a track centre, viablock[i, j] for a via centre, own[layer] = own copper."""
        g = self.g
        L = self.layers
        on = lambda lay: L if lay == "A" else [l for l in L if l == lay]
        blocked = {l: np.zeros((self.nx, self.ny), bool) for l in L}
        own = {l: np.zeros((self.nx, self.ny), bool) for l in L}
        soft = {l: np.zeros((self.nx, self.ny), bool) for l in L}      # blocked only by tracks that may be ripped up
        # On copper of the own net (inside a pad between its neighbours) the conservative margin is too much,
        # but a new track there can still come too close to other nets: `exact` holds the real rule.
        exact = {l: np.zeros((self.nx, self.ny), bool) for l in L}
        viablock = np.zeros((self.nx, self.ny), bool)
        ownvia = np.zeros((self.nx, self.ny), bool)                    # inside a via or THT pad of the own net
        core = {l: np.zeros((self.nx, self.ny), bool) for l in self.layers}   # well inside own copper
        iface = self.iface
        Wb, Hb = iface["board"]["width"], iface["board"]["depth"]
        tab = [q for q in iface["board"]["outline"] if q[0] > Wb]
        ty0, ty1, tx = min(q[1] for q in tab), max(q[1] for q in tab), max(q[0] for q in tab)
        X, Y = np.meshgrid(self.xs, self.ys, indexing="ij")
        for m, target in ((0.3 + width / 2 + g / 2, None), (0.3 + VIA_D / 2 + g / 2, viablock)):
            out = (Y < m) | (Y > Hb - m) | (X < m) | (X > np.where((Y > ty0 + m) & (Y < ty1 - m), tx, Wb) - m)
            if target is None:
                for l in L:
                    blocked[l] |= out
            else:
                target |= out
        for h in iface["mounting_holes"]:
            d = np.hypot(X - h["x"], Y - h["y"])
            for l in L:
                blocked[l] |= d < h["drill"] / 2 + 0.3 + width / 2 + g / 2
            viablock |= d < h["drill"] / 2 + 0.5 + VIA_D / 2 + g / 2
        for z in self.b.Zones():
            if z.GetIsRuleArea() and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()) and z.IsOnLayer(pcbnew.B_Cu):
                bb = z.GetBoundingBox()
                x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
                x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
                i0, i1, j0, j1 = self.window(x0 - 1, y0 - 1, x1 + 1, y1 + 1)       # the whole box, conservatively
                for l in L:
                    blocked[l][i0:i1, j0:j1] = True
                viablock[i0:i1, j0:j1] = True
        for kind, geo, n, lay, obj in prim:
            if kind == "rect":
                bx = geo
            elif kind == "circle":
                bx = (geo[0] - geo[2], geo[1] - geo[2], geo[0] + geo[2], geo[1] + geo[2])
            else:
                bx = (min(geo[0], geo[2]) - geo[4], min(geo[1], geo[3]) - geo[4], max(geo[0], geo[2]) + geo[4], max(geo[1], geo[3]) + geo[4])
            if n == net:
                i0, i1, j0, j1 = self.window(*bx)
                d = self.dist(kind, geo, i0, i1, j0, j1)
                for l in on(lay):
                    own[l][i0:i1, j0:j1] |= d <= 0
                    core[l][i0:i1, j0:j1] |= d <= -0.02
                if lay == "A":
                    ownvia[i0:i1, j0:j1] |= d <= -0.1                  # well inside: the layer change is already there
                elif kind == "rect":
                    viablock[i0:i1, j0:j1] |= d < VIA_D / 2 + 0.05     # no via in or touching an SMD pad (review)
                continue
            cl = max(net_clearance(net), net_clearance(n)) + g / 2 + 0.04
            mt, mv = cl + width / 2, cl + VIA_D / 2
            i0, i1, j0, j1 = self.window(bx[0] - mv, bx[1] - mv, bx[2] + mv, bx[3] + mv)
            d = self.dist(kind, geo, i0, i1, j0, j1)
            for l in on(lay):
                exact[l][i0:i1, j0:j1] |= d < max(net_clearance(net), net_clearance(n)) + 0.02 + width / 2
                if rip and obj is not None:
                    soft[l][i0:i1, j0:j1] |= d < mt
                else:
                    blocked[l][i0:i1, j0:j1] |= d < mt
            viablock[i0:i1, j0:j1] |= d < mv
            if kind == "rect" and lay == "A":                  # hole to hole
                viablock[i0:i1, j0:j1] |= d < 0.5 + VIA_D / 2
        # vias of the own net: keep the hole distance
        for kind, geo, n, lay, _obj in prim:
            if n == net and kind == "circle":
                i0, i1, j0, j1 = self.window(geo[0] - 1.5, geo[1] - 1.5, geo[0] + 1.5, geo[1] + 1.5)
                d = self.dist(kind, geo, i0, i1, j0, j1)
                viablock[i0:i1, j0:j1] |= (d < 0.5 + VIA_DRILL / 2) & (d > 0)
        for l in L:
            soft[l] &= ~blocked[l] & ~own[l]
        self.ownvia = ownvia
        # connectivity uses only cells 0.02 mm inside the copper: two items closer than a grid step must not
        # look connected (they are not, the DRC still reports them open)
        self.core = core
        self.exact = exact
        return blocked, viablock, own, soft

    def plane_mask(self, net, c0, viablock, radius=12.0):
        """Cells (within `radius` mm of c0) where a via of `net` can stand and lands well inside the filled plane
        of that net on an inner layer (all of its pad plus 0.1 mm inside the fill)."""
        g = self.g
        mask = np.zeros((self.nx, self.ny), bool)
        polys = self.plane_nets[net]
        n = int(radius / g)
        r = VIA_D / 2 + 0.1
        offs = [(0, 0), (r, 0), (-r, 0), (0, r), (0, -r)]
        for i in range(max(0, c0[0] - n), min(self.nx, c0[0] + n + 1), 2):      # every second cell is enough
            for j in range(max(0, c0[1] - n), min(self.ny, c0[1] + n + 1), 2):
                if viablock[i, j]:
                    continue
                x, y = i * g, j * g
                if all(any(ps.Contains(P(x + dx, y + dy)) for ps in polys) for dx, dy in offs):
                    mask[i, j] = True
        return mask

    def route(self, prim, net, a, b, rip=False):
        g = self.g
        width = touchup_width(net)
        blocked, viablock, own, soft = self.maps(prim, net, width, rip)
        cell = lambda p: (int(round(p[0] / g)), int(round(p[1] / g)))
        ca, cb = cell(a), cell(b)
        lay_at = lambda c: [l for l in "FB" if own[l][c]] or ["B", "F"]
        L = self.layers
        lcost = {l: (INNER_COST if l == "I" else B_COST if l == "B" else 1.0) for l in L}
        openc = {}
        if OPEN_COST > 1.0:                   # cells without copper (blocked area) within OPEN_R: free space, dearer
            r = max(1, int(round(OPEN_R / g)))
            for l in L:
                nearb = blocked[l].copy()
                for _ in range(r):
                    m = nearb.copy()
                    m[1:, :] |= nearb[:-1, :]; m[:-1, :] |= nearb[1:, :]
                    m[:, 1:] |= nearb[:, :-1]; m[:, :-1] |= nearb[:, 1:]
                    nearb = m
                openc[l] = np.where(nearb, 1.0, OPEN_COST)
        # own copper may be walked on freely; free the area right at the end points (inside the own pad)
        free = {l: ~blocked[l] | (own[l] & ~self.exact[l]) for l in L}
        for c in (ca, cb):                    # the end points themselves are existing copper
            for l in L:
                if own[l][c]:
                    free[l][c] = True

        def flood(c0):
            """All grid nodes of the own copper connected to c0 (tracks, pads, vias of the item at c0).
            The search starts from / ends on any of them: existing own copper may run closer to other nets
            than a new track would be allowed to, so walking on it is not possible."""
            core = self.core
            seen = set((c0, l) for l in L if core[l][c0])
            stack = list(seen)
            while stack and len(seen) < 400000:
                (i, j), l = stack.pop()
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nn = ((i + di, j + dj), l)
                    if nn not in seen and 0 <= i + di < self.nx and 0 <= j + dj < self.ny and core[l][i + di, j + dj]:
                        seen.add(nn)
                        stack.append(nn)
                if self.ownvia[i, j]:
                    for ol in L:
                        if ((i, j), ol) not in seen and core[ol][i, j]:
                            seen.add(((i, j), ol))
                            stack.append(((i, j), ol))
            return seen

        self._free = free
        # plane nets: a via that lands in the filled plane of the net (In1/In2) is a goal as well
        plane_ok = self.plane_mask(net, ca, viablock) if self.plane_nets and net in self.plane_nets else None
        src = flood(ca) or {(ca, l) for l in lay_at(ca)}
        dst = flood(cb) or {(cb, l) for l in lay_at(cb)}
        if plane_ok is not None:
            # route from the end that is not on the plane yet; if this one is, let the caller try the other way
            polys = self.plane_nets[net]
            on_plane = lambda c: any(ps.Contains(P(c[0] * g, c[1] * g)) for ps in polys)
            if any(self.ownvia[c] and on_plane(c) for c, _l in src):
                return None
        starts = list(src)
        dst_cells = np.array([c for c, _l in dst])
        for c, l in dst:                      # the goal copper must be enterable
            free[l][c] = True
        S2 = math.sqrt(2)
        moves = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, S2), (1, -1, S2), (-1, 1, S2), (-1, -1, S2)]
        # admissible heuristic: distance to the nearest goal cell (subsampled for large goal sets)
        hc = dst_cells if len(dst_cells) <= 2000 else dst_cells[:: max(1, len(dst_cells) // 2000)]
        h = lambda c: float(np.min(np.hypot(hc[:, 0] - c[0], hc[:, 1] - c[1]))) * (1.0 if len(hc) == len(dst_cells) else 0.0)
        if plane_ok is not None:
            h = lambda c: 0.0                 # the nearest plane via is the goal: plain Dijkstra
        best, prev, pq = {}, {}, []
        for s in starts:
            best[s] = 0.0
            heapq.heappush(pq, (h(s[0]), 0.0, s))
        end = None
        while pq:
            _f, cost, node = heapq.heappop(pq)
            if cost > best.get(node, 1e18):
                continue
            (i, j), l = node
            if node in dst:
                end = node
                break
            if plane_ok is not None and plane_ok[i, j] and node not in src:
                end = node
                break
            for di, dj, c in moves:
                ni, nj = i + di, j + dj
                if not (0 <= ni < self.nx and 0 <= nj < self.ny) or not free[l][ni, nj]:
                    continue
                if di and dj and not (free[l][ni, j] and free[l][i, nj]):
                    continue
                nn, nc = ((ni, nj), l), cost + c * (0.3 if own[l][ni, nj] else lcost[l] * (openc[l][ni, nj] if openc else 1.0)) + (RIP_COST if soft[l][ni, nj] else 0.0)
                if nc < best.get(nn, 1e18):
                    best[nn], prev[nn] = nc, node
                    heapq.heappush(pq, (nc + h((ni, nj)), nc, nn))
            if not viablock[i, j] or self.ownvia[i, j]:
                for ol in L:
                    if ol != l and free[ol][i, j] and not soft[ol][i, j] and not soft[l][i, j]:
                        nn, nc = ((i, j), ol), cost + (1.0 if self.ownvia[i, j] else VIA_COST)
                        if nc < best.get(nn, 1e18):
                            best[nn], prev[nn] = nc, node
                            heapq.heappush(pq, (nc + h((i, j)), nc, nn))
        if end is None:
            return None
        path = [end]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()
        if plane_ok is not None and end not in dst:      # finish with a via into the plane
            path.append((end[0], "F" if end[1] != "F" else "B"))
        # tracks of other nets whose clearance area the path crosses: they are ripped up by the caller
        ripped = []
        cells = {l: np.array([[c[0] * g, c[1] * g] for c, pl in path if pl == l and soft[l][c]]) for l in L}
        if any(len(v) for v in cells.values()):
            for kind, geo, n, lay, obj in prim:
                if obj is None or n == net or kind != "seg" or not len(cells.get(lay, ())):
                    continue
                pts = cells[lay]
                ax, ay, bx, by, r = geo
                l2 = (bx - ax) ** 2 + (by - ay) ** 2
                u = np.zeros(len(pts)) if l2 == 0 else np.clip(((pts[:, 0] - ax) * (bx - ax) + (pts[:, 1] - ay) * (by - ay)) / l2, 0, 1)
                d = np.hypot(pts[:, 0] - ax - u * (bx - ax), pts[:, 1] - ay - u * (by - ay)) - r
                if (d < max(net_clearance(net), net_clearance(n)) + g / 2 + 0.01 + width / 2).any():
                    ripped.append(obj)
        # the path starts and ends on existing own copper; the given end points are only used when the
        # path begins / ends exactly there
        a_eff = a if path[0][0] == ca else None
        b_eff = b if path[-1][0] == cb else None
        return path, width, ripped, a_eff, b_eff

    def commit(self, net, path, width, a, b):
        g = self.g
        code = self.b.FindNet(net)
        pts, cur = [], None
        segs, vias = [], []
        run = [path[0]]
        for node in path[1:]:
            if node[1] != run[-1][1]:
                segs.append(run)
                vias.append(node[0])
                run = [node]
            else:
                run.append(node)
        segs.append(run)
        free = getattr(self, "_free", None)

        def clear(l, p, q):
            """Straight segment p-q (mm) runs only through free grid cells (sampled every g/4)."""
            n = max(1, int(math.dist(p, q) / (g / 4)))
            for i in range(n + 1):
                x, y = p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n
                if not free[l][int(round(x / g)), int(round(y / g))]:
                    return False
            return True

        for k, run in enumerate(segs):
            layer = LAYER[run[0][1]]
            pts = [(c[0] * g, c[1] * g) for c, _l in run]
            if free is not None and len(pts) > 2:
                # string pulling: replace the grid staircase by the longest straight segments that stay in free
                # cells. Free cells already include the clearance plus half a grid step, so a straight segment
                # between them keeps the rule distance (nearest cell centre within g/sqrt(2) < g/2 + 0.04).
                l = run[0][1]
                out, i = [pts[0]], 0
                while i < len(pts) - 1:
                    j = i + 1
                    while j + 1 < len(pts) and clear(l, pts[i], pts[j + 1]):
                        j += 1
                    out.append(pts[j])
                    i = j
                pts = out
            if k == 0 and a is not None:
                pts.insert(0, a)
            if k == len(segs) - 1 and b is not None:
                pts.append(b)
            simp = [pts[0]]                           # drop collinear points
            for q in pts[1:]:
                if len(simp) >= 2:
                    (x0, y0), (x1, y1) = simp[-2], simp[-1]
                    if abs((x1 - x0) * (q[1] - y1) - (y1 - y0) * (q[0] - x1)) < 1e-9:
                        simp[-1] = q
                        continue
                simp.append(q)
            for p0, p1 in zip(simp, simp[1:]):
                if math.dist(p0, p1) < 1e-6:
                    continue
                t = pcbnew.PCB_TRACK(self.b)
                t.SetStart(P(*p0)); t.SetEnd(P(*p1)); t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(layer); t.SetNet(code)
                self.b.Add(t)
        for c in vias:
            if self.ownvia[c]:
                continue                      # the path changes layer in an existing via or THT pad of the net
            v = pcbnew.PCB_VIA(self.b)
            v.SetPosition(P(c[0] * g, c[1] * g)); v.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(VIA_D)); v.SetDrill(pcbnew.FromMM(VIA_DRILL))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(code)
            self.b.Add(v)
        return len(vias)


def release(board, nets, vias_at):
    """Manual help for sealed-in pins: remove the unlocked tracks and vias of `nets` (they are routed again)
    and the vias at the given board positions (x, y in mm, also locked ones)."""
    n = 0
    near = lambda p: any(math.hypot(p[0] - vx, p[1] - vy) < 0.05 for vx, vy in vias_at)
    for t in list(board.GetTracks()):
        if t.GetClass() == "PCB_VIA":
            hit = near(unP(t.GetPosition()))
        else:                                  # track stubs that end at a released via go with it
            hit = near(unP(t.GetStart())) or near(unP(t.GetEnd()))
        if (t.GetNetname() in nets and not t.IsLocked()) or hit:
            board.Remove(t)
            n += 1
    return n


def add_manual(board, man):
    """Hand-placed tracks and vias from the manual touch-up file (locked)."""
    for tr in man.get("tracks", []):
        for p0, p1 in zip(tr["pts"], tr["pts"][1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(*p0)); t.SetEnd(P(*p1)); t.SetWidth(pcbnew.FromMM(tr["width"]))
            t.SetLayer(LAYER[tr["layer"]]); t.SetNet(board.FindNet(tr["net"])); t.SetLocked(True)
            board.Add(t)
    for vi in man.get("vias", []):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(*vi["at"])); v.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(vi.get("d", VIA_D)))
        v.SetDrill(pcbnew.FromMM(vi.get("drill", VIA_DRILL))); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(board.FindNet(vi["net"])); v.SetLocked(True)
        board.Add(v)
    return len(man.get("tracks", [])), len(man.get("vias", []))


def main(src, dst, g=0.05, layers="FB", rip=False, rounds=4, rip_rounds=1, first=(), rel_nets=(), rel_vias=(), manual=None,
         plane_nets=()):
    iface = json.loads((ROOT / "CAD" / "board_interface.json").read_text(encoding="utf-8"))
    board = pcbnew.LoadBoard(str(src))
    man = json.loads(Path(manual).read_text(encoding="utf-8")) if manual else {}
    rel_nets = tuple(rel_nets) + tuple(man.get("release_nets", []))
    rel_vias = tuple(rel_vias) + tuple(tuple(v) for v in man.get("release_vias", []))
    if rel_nets or rel_vias or man:
        print(f"  released {release(board, rel_nets, rel_vias)} tracks/vias: {list(rel_nets)} {list(rel_vias)}")
        if man:
            print("  manual tracks, vias:", add_manual(board, man))
        src = Path(dst).with_name("touchup_tmp.kicad_pcb")
        pcbnew.SaveBoard(str(src), board)
        # pcbnew objects are not reliable after removing items and saving: route in a fresh process
        args = [a for a in sys.argv[3:] if not a.startswith(("--release", "--manual", "--first"))]
        if first or man.get("first"):
            args.append("--first=" + ",".join(list(first) + man.get("first", [])))
        raise SystemExit(subprocess.run([sys.executable, sys.argv[0], str(src), str(dst), *args]).returncode)
    todo = open_connections(src)
    ox, oy = ORIGIN
    grid = Grid(board, iface, g, layers, plane_nets)
    done, failed, total = 0, [], len(todo)
    tmp = Path(dst).with_name("touchup_tmp.kicad_pcb")
    for rnd in range(rounds):
        failed = []
        # short connections first: they are the least likely to block others
        todo.sort(key=lambda t: math.dist(t[1], t[2]))
        todo.sort(key=lambda t: first.index(t[0]) if t[0] in first else len(first))     # stable: given nets first
        n_rip = 0
        for net, a, b in todo:
            a, b = (a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy)
            res = None
            for use_rip in ((False, True) if rip and rnd < rip_rounds else (False,)):
                prim = grid.collect()
                res = grid.route(prim, net, a, b, use_rip) or grid.route(prim, net, b, a, use_rip)
                if res:
                    break
            if res is None:
                failed.append(f"{net} ({a[0]:.1f},{a[1]:.1f})-({b[0]:.1f},{b[1]:.1f})")
                continue
            path, width, ripped, a, b = res
            for obj in ripped:
                board.Remove(obj)
            n_rip += len(ripped)
            nv = grid.commit(net, path, width, a, b)
            done += 1
            print(f"  routed {net}: {len(path) * g:.1f} mm, {nv} vias" + (", uses In1" if any(l == "I" for _c, l in path) else "")
                  + (f", ripped up {len(ripped)} segments" if ripped else ""))
        pcbnew.SaveBoard(str(dst), board)
        if not n_rip and not failed:
            break
        if not n_rip and rnd >= rip_rounds:
            break
        # what was ripped up is open now: next round
        tmp.write_text(Path(dst).read_text(encoding="utf-8"), encoding="utf-8")
        todo = open_connections(tmp)
        tmp.unlink()
        todo = [t for t in todo]
        print(f"  round {rnd + 1}: {n_rip} segments ripped up, {len(todo)} connections open")
    print(f"touch-up: {done} connections routed (started with {total} open); left: {failed}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    B_COST = next((float(a.split("=")[1]) for a in sys.argv if a.startswith("--bcost=")), 1.0)
    OPEN_COST = next((float(a.split("=")[1]) for a in sys.argv if a.startswith("--opencost=")), 1.0)
    OPEN_R = next((float(a.split("=")[1]) for a in sys.argv if a.startswith("--openr=")), 0.7)
    grid_step = next((float(a.split("=")[1]) for a in sys.argv if a.startswith("--grid=")), 0.05)
    opt = lambda k: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{k}=")), "")
    main(args[0], args[1], grid_step, "FBI" if "--inner" in sys.argv else "FB", "--rip" in sys.argv,
         first=tuple(n for n in opt("first").split(",") if n),
         rel_nets=tuple(n for n in opt("release").split(",") if n),
         rel_vias=tuple(tuple(float(v) for v in q.split("/")) for q in opt("release-vias").split(",") if q),
         manual=opt("manual") or None, plane_nets=tuple(n for n in opt("plane-nets").split(",") if n))
