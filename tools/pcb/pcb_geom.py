"""Copper model of a board for scripted edits: clearance checks with KiCad's own shapes.

Used by the post-routing scripts (plane_stubs.py, chamfer_corners.py, gnd_pour.py). Coordinates in board mm
(file coordinates minus the origin of bekantx_layout, see P/unP). Every check uses the net class clearance of both
nets (the larger one counts), the board edge clearance and the rule areas that forbid tracks or vias.
"""
import math

import pcbnew

from bekantx_layout import MM, NETCLASSES, P, net_clearance, unP

EDGE_CLEARANCE = 0.3          # board setup copper_edge_clearance
HOLE_TO_HOLE = 0.25           # board setup min_hole_to_hole
OUTER = (pcbnew.F_Cu, pcbnew.B_Cu)


def net_width(net):
    """Track width of the net class of a net (same patterns as in the project file)."""
    import fnmatch
    for _name, (w, _c, _v, _d, pats) in NETCLASSES.items():
        if any(fnmatch.fnmatchcase(net, p.replace("[", "[[]")) if "*" in p else net == p for p in pats):
            return w
    return NETCLASSES["Default"][0]


def uid(item):
    """Stable identity of a board item (Python ids of pcbnew proxies differ between lookups)."""
    return item.m_Uuid.AsString()


def bbox_mm(item):
    bb = item.GetBoundingBox()
    x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
    x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
    return (x0, y0, x1, y1)


class Copper:
    """Snapshot of all copper of a board. Call refresh() after adding or removing items."""

    def __init__(self, board):
        self.board = board
        self.refresh()

    def refresh(self):
        b = self.board
        self.items = []                    # dict(obj, kind, net, layers, box)
        self.holes = []                    # (x, y, r) of every drilled hole (vias, THT, NPTH)
        for fp in b.GetFootprints():
            for p in fp.Pads():
                lays = [l for l in OUTER if p.IsOnLayer(l)]
                self.items.append(dict(obj=p, kind="pad", net=p.GetNetname(), layers=lays, box=bbox_mm(p),
                                       ref=fp.GetReference()))
                if p.HasHole():
                    x, y = unP(p.GetPosition())
                    self.holes.append((x, y, pcbnew.ToMM(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2, p))
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                self.items.append(dict(obj=t, kind="via", net=t.GetNetname(), layers=list(OUTER), box=bbox_mm(t)))
                x, y = unP(t.GetPosition())
                self.holes.append((x, y, pcbnew.ToMM(t.GetDrillValue()) / 2, t))
            elif t.GetLayer() in OUTER:
                self.items.append(dict(obj=t, kind="track", net=t.GetNetname(), layers=[t.GetLayer()], box=bbox_mm(t)))
        self.keep_tracks, self.keep_vias = [], []
        for z in b.Zones():
            if z.GetIsRuleArea():
                if z.GetDoNotAllowTracks():
                    self.keep_tracks.append(z)
                if z.GetDoNotAllowVias():
                    self.keep_vias.append(z)
        ps = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(ps, True)
        self.outline = ps
        self.edge_segs = []                # (SEG, box mm); arcs come as many short segments
        for i in range(ps.OutlineCount()):
            ch = ps.Outline(i)
            for k in range(ch.SegmentCount()):
                sg = ch.CSegment(k)
                a, c = unP(sg.A), unP(sg.B)
                self.edge_segs.append((pcbnew.SEG(sg.A, sg.B), (min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1]))))

    # ---------------------------------------------------------------- primitives
    def _edge_ok(self, shape, box):
        """The shape stays EDGE_CLEARANCE inside the board outline."""
        m = EDGE_CLEARANCE
        for sg, sb in self.edge_segs:
            if sb[0] - m > box[2] or sb[2] + m < box[0] or sb[1] - m > box[3] or sb[3] + m < box[1]:
                continue
            if shape.Collide(sg, MM(m) - 1000):
                return False
        c = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        return self.outline.Contains(P(*c))

    def _hits(self, shape, box, net, layers, skip, extra=0.0):
        for it in self.items:
            if uid(it["obj"]) in skip or (it["net"] == net and net):
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

    def seg_clear(self, a, b, w, net, layer, skip=()):
        """Track a-b of width w on layer keeps the clearance to everything of other nets and to the edge."""
        if math.dist(a, b) < 1e-6:
            shape = pcbnew.SHAPE_CIRCLE(P(*a), MM(w / 2))
        else:
            shape = pcbnew.SHAPE_SEGMENT(P(*a), P(*b), MM(w))
        box = (min(a[0], b[0]) - w / 2, min(a[1], b[1]) - w / 2, max(a[0], b[0]) + w / 2, max(a[1], b[1]) + w / 2)
        if not self._edge_ok(shape, box):
            return False
        for z in self.keep_tracks:
            if any(z.IsOnLayer(layer) and z.Outline().Contains(P(*q)) for q in (a, b, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))):
                return False
        return self._hits(shape, box, net, [layer], {uid(o) for o in skip}) is None

    def via_clear(self, p, dia, drill, net, skip=(), own_pad_gap=0.1):
        """Via at p: clearance on both outer layers, hole to hole, rule areas, and its ring at least own_pad_gap
        away from pads of its own net (no via in or touching a pad: solder wicking)."""
        r = dia / 2
        shape = pcbnew.SHAPE_CIRCLE(P(*p), MM(r))
        box = (p[0] - r, p[1] - r, p[0] + r, p[1] + r)
        if not self._edge_ok(shape, box):
            return False
        if any(z.Outline().Contains(P(*p)) for z in self.keep_vias):
            return False
        for x, y, hr, obj in self.holes:
            if uid(obj) in {uid(o) for o in skip}:
                continue
            if math.hypot(p[0] - x, p[1] - y) < drill / 2 + hr + HOLE_TO_HOLE:
                return False
        if self._hits(shape, box, net, list(OUTER), {uid(o) for o in skip}) is not None:
            return False
        if own_pad_gap is not None:
            for it in self.items:
                if it["kind"] == "pad" and it["net"] == net and uid(it["obj"]) not in {uid(o) for o in skip}:
                    for lay in it["layers"]:
                        if it["obj"].GetEffectiveShape(lay).Collide(shape, MM(own_pad_gap) - 1000):
                            return False
        return True


def plane_fill(board, net):
    """Filled area of the inner-layer zone of a net (In1 VCC area / +3V3 plane, In2 GND plane), or None."""
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net:
            continue
        lay = z.GetFirstLayer()
        if lay in (pcbnew.In1_Cu, pcbnew.In2_Cu):
            return z.GetFilledPolysList(lay)
    return None


def on_plane(fill, p, margin=0.35):
    """p and a ring of radius margin around it lie in the filled plane."""
    if fill is None:
        return False
    pts = [p] + [(p[0] + margin * math.cos(a), p[1] + margin * math.sin(a)) for a in
                 [k * math.pi / 4 for k in range(8)]]
    return all(fill.Contains(P(*q)) for q in pts)
