"""Build the BekantX board from the schematic netlist and the enclosure interface.

Run with KiCad's Python:
  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_layout.py [--out build/layout/BekantX.kicad_pcb]

Steps: project rules (net classes) -> empty 4-layer board -> outline, mounting holes and keep-outs from
CAD/board_interface.json -> footprints with nets from the netlist -> placement (fixed parts by hand, the
small parts by a greedy placer next to the pads they connect to) -> zones -> hand-routed, locked tracks
(RF feed, USB pairs). The autorouter (tools/pcb/autoroute.py) does the rest.

The board is rebuilt from scratch on every run, so the placement stays reproducible.
Board coordinates are those of CAD/board_interface.json (origin = board corner, x right, y down, seen on
F.Cu); ORIGIN shifts them onto the KiCad sheet.
"""
import argparse, json, math, subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[2]
PROJ = ROOT / "Pcb_Controller"
KICAD_BIN = Path("C:/Program Files/KiCad/10.0/bin")
FP_DIR = Path("C:/Program Files/KiCad/10.0/share/kicad/footprints")
ORIGIN = (100.0, 80.0)
MM = pcbnew.FromMM
GLOBAL_NETS = {"GND", "+3V3"}

# ---------------------------------------------------------------- rules
NETCLASSES = {
    # name: (track, clearance, via, drill, [net patterns])
    # 0.15/0.15 mm with a 0.5/0.3 mm via: with 0.2/0.2 and 0.6 mm vias the two 0.5 mm pitch QFNs could not
    # be routed out on two signal layers (4 to 13 connections stayed open in seven runs).
    # JLCPCB builds 0.09/0.09 mm and 0.45/0.2 mm vias on 4 layers, so this is still conservative.
    "Default": (0.15, 0.15, 0.5, 0.3, []),
    # 0.3 mm is the widest track that leaves a 0.5 mm pitch pad (QFN, FPC) straight with 0.2 mm clearance;
    # +3V3 is distributed by the plane on In1, the tracks are only the stubs to the vias
    "Power": (0.3, 0.2, 0.6, 0.3, ["+3.3VA", "VCC_SPI"]),
    # plane nets: every SMD pad gets its own via by drop_plane_vias(); the autorouter ignores this class
    # clearance 0.15 like Default (2026-11-18): 0.2 blocked the escape of fine-pitch pins next to decoupling pads
    "Planes": (0.3, 0.15, 0.6, 0.3, ["GND", "+3V3"]),
    "PowerMid": (0.4, 0.2, 0.8, 0.4, ["+12V", "VBUS"]),
    # up to 53 V (TVS clamp) on these nets
    "PowerHV": (0.5, 0.3, 0.8, 0.4, ["VDESK", "VIN", "VCC", "Net-(U9-SW)", "Net-(D20-K)", "Net-(U9-CB)",
                                      "Net-(U20-CB)", "Net-(U9-~{SHDN})", "Net-(U20-~{SHDN})"]),
    "LIN": (0.3, 0.3, 0.6, 0.3, ["LINBUS", "Net-(D70-K)"]),
    # USB 2.0 full speed only (12 Mbit/s): no impedance control, 0.15 mm clearance is enough
    "USB": (0.25, 0.15, 0.6, 0.3, ["USB*", "Net-(J1-D*", "Net-(U8-D*"]),
    "RF": (0.35, 0.2, 0.6, 0.3, ["Net-(U2-LNA_IN)", "Net-(AE1-FEED)"]),
}


def write_project_rules():
    pro_path = PROJ / "BekantX.kicad_pro"
    pro = json.loads(pro_path.read_text(encoding="utf-8"))
    base = pro["net_settings"]["classes"][0]
    classes, patterns = [], []
    for prio, (name, (w, cl, via, drill, pats)) in enumerate(NETCLASSES.items()):
        c = dict(base)
        c.update(name=name, track_width=w, clearance=cl, via_diameter=via, via_drill=drill,
                 priority=2147483647 if name == "Default" else prio)
        if name == "USB":
            c.update(diff_pair_width=0.25, diff_pair_gap=0.15, diff_pair_via_gap=0.25)
        classes.append(c)
        patterns += [{"netclass": name, "pattern": p} for p in pats]
    pro["net_settings"]["classes"] = classes
    pro["net_settings"]["netclass_patterns"] = patterns
    r = pro["board"]["design_settings"]["rules"]
    # JLCPCB 4-layer capability is 0.09/0.09 mm, via 0.45/0.2; these are deliberately looser
    r.update(min_clearance=0.15, min_track_width=0.15, min_via_diameter=0.5, min_through_hole_diameter=0.3,
             min_via_annular_width=0.1, min_hole_clearance=0.25, min_hole_to_hole=0.25,
             min_copper_edge_clearance=0.3, min_silk_clearance=0.0, min_resolved_spokes=1)
    pro_path.write_text(json.dumps(pro, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- helpers
def P(x, y):
    return pcbnew.VECTOR2I(MM(x + ORIGIN[0]), MM(y + ORIGIN[1]))


def unP(v):
    return (pcbnew.ToMM(v.x) - ORIGIN[0], pcbnew.ToMM(v.y) - ORIGIN[1])


def load_netlist():
    xml = ROOT / "build" / "layout" / "netlist.xml"
    xml.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(KICAD_BIN / "kicad-cli.exe"), "sch", "export", "netlist", "--format", "kicadxml",
                    "-o", str(xml), str(PROJ / "BekantX.kicad_sch")], check=True, capture_output=True)
    root = ET.parse(xml).getroot()
    comps = {}
    for c in root.find("components"):
        props = {p.get("name"): p.get("value") for p in c.findall("property")}
        sp = c.find("sheetpath")
        comps[c.get("ref")] = dict(
            value=c.findtext("value"), footprint=c.findtext("footprint"),
            description=c.findtext("description") or "", datasheet=c.findtext("datasheet") or "",
            no_bom="exclude_from_bom" in props,
            fields={f.get("name"): (f.text or "") for f in c.findall("fields/field")},
            dnp="dnp" in props, sheet=sp.get("names"), sheetfile=props.get("Sheetfile", ""),
            path=sp.get("tstamps") + c.findtext("tstamps"), pads={})
    nets = {}
    for n in root.find("nets"):
        name = n.get("name")
        nets[name] = [(x.get("ref"), x.get("pin")) for x in n.findall("node")]
        for x in n.findall("node"):
            comps[x.get("ref")]["pads"][x.get("pin")] = (name, x.get("pinfunction") or "", x.get("pintype") or "")
    return comps, nets


class Part:
    """A footprint plus cached pad/courtyard geometry for the four orientations (board mm, relative)."""

    def __init__(self, board, ref, comp):
        lib, name = comp["footprint"].split(":")
        fp = pcbnew.FootprintLoad(str(FP_DIR / f"{lib}.pretty"), name)
        if fp is None:
            raise RuntimeError(f"{ref}: footprint {comp['footprint']} not found")
        fp.SetReference(ref)
        fp.SetValue(comp["value"])
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetPath(pcbnew.KIID_PATH(comp["path"]))
        fp.SetSheetname(comp["sheet"].rstrip("/") or "/")
        fp.SetSheetfile(comp["sheetfile"])
        fields = dict(comp["fields"], Description=comp["description"], Datasheet=comp["datasheet"])
        for k, v in fields.items():
            if k != "Footprint" and v:
                fp.SetField(k, v)
                fp.GetField(k).SetVisible(False)
        attr = fp.GetAttributes() & ~(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_DNP)
        attr |= (pcbnew.FP_EXCLUDE_FROM_BOM if comp["no_bom"] else 0) | (pcbnew.FP_DNP if comp["dnp"] else 0)
        fp.SetAttributes(attr)
        # reference designators live on the fab layer: the board is too dense for readable silkscreen
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.6), MM(0.6)))
        fp.Reference().SetTextThickness(MM(0.09))
        fp.Value().SetVisible(False)
        board.Add(fp)
        self.fp, self.ref, self.comp, self.placed, self.side = fp, ref, comp, False, "F"
        self.nets = {}
        for pad in fp.Pads():
            info = comp["pads"].get(pad.GetNumber())
            if info:
                pad.SetNet(board.FindNet(info[0]))
                pad.SetPinFunction(info[1])
                pad.SetPinType(info[2])
                self.nets.setdefault(info[0], [])
        self.geom = None

    def cache(self, side):
        """Pad offsets per net and courtyard box for rot 0/90/180/270 on the given side."""
        fp = self.fp
        fp.SetPosition(P(0, 0))
        fp.SetOrientationDegrees(0)
        if (side == "B") != fp.IsFlipped():
            fp.Flip(P(0, 0), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        self.side = side
        self.geom = {}
        for rot in (0, 90, 180, 270):
            fp.SetOrientationDegrees(rot)
            pads = {}
            for pad in fp.Pads():
                x, y = unP(pad.GetPosition())
                pads.setdefault(pad.GetNetname(), []).append((x, y))
            bb = fp.GetCourtyard(pcbnew.B_CrtYd if side == "B" else pcbnew.F_CrtYd).BBox()
            if bb.GetWidth() <= 0:
                bb = fp.GetBoundingBox(False)
            x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            # every pad as an obstacle for the other side if it is a through-hole pad
            tht = [unP(p.GetPosition()) + (pcbnew.ToMM(max(p.GetSize().x, p.GetSize().y)) / 2,)
                   for p in fp.Pads() if p.HasHole()]
            self.geom[rot] = dict(pads=pads, box=(x0, y0, x1, y1), tht=tht)
        fp.SetOrientationDegrees(0)

    def put(self, x, y, rot=0, side=None):
        if side is not None and (self.geom is None or side != self.side):
            self.cache(side)
        if self.geom is None:
            self.cache("F")
        self.fp.SetPosition(P(x, y))
        self.fp.SetOrientationDegrees(rot)
        self.x, self.y, self.rot, self.placed = x, y, rot % 360, True
        return self

    def box(self, x=None, y=None, rot=None):
        g = self.geom[self.rot if rot is None else rot]["box"]
        x = self.x if x is None else x
        y = self.y if y is None else y
        return (g[0] + x, g[1] + y, g[2] + x, g[3] + y)

    def pad_xy(self, net, x=None, y=None, rot=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        return [(px + x, py + y) for px, py in self.geom[self.rot if rot is None else rot]["pads"].get(net, [])]

    def pad(self, number):
        for p in self.fp.Pads():
            if p.GetNumber() == str(number):
                return unP(p.GetPosition())
        raise KeyError(f"{self.ref}.{number}")


def overlap(a, b, m=0.0):
    return a[0] < b[2] + m and b[0] < a[2] + m and a[1] < b[3] + m and b[1] < a[3] + m


class Placer:
    def __init__(self, parts, nets, iface):
        self.parts, self.nets, self.iface = parts, nets, iface
        self.obst = {"F": [], "B": []}      # (box, why)
        b = iface["board"]
        self.W, self.H = b["width"], b["depth"]

    def keepout(self, side, box, why):
        for s in side:
            self.obst[s].append((box, why))

    def boxes(self, side, skip=None):
        out = [o[0] for o in self.obst[side]]
        for p in self.parts.values():
            if not p.placed or p is skip:
                continue
            if p.side == side:
                out.append(p.box())
            for (tx, ty, r) in p.geom[p.rot]["tht"]:        # THT pads block both sides
                out.append((p.x + tx - r - 0.3, p.y + ty - r - 0.3, p.x + tx + r + 0.3, p.y + ty + r + 0.3))
        return out

    def targets(self, part, extra):
        """Points a part wants to be close to: {net: [(x, y), ...]} from placed parts."""
        t = {}
        for net in part.nets:
            if net in extra:
                t[net] = extra[net]
                continue
            if net in GLOBAL_NETS or net.startswith("unconnected"):
                continue
            pts = []
            for ref, _pin in self.nets[net]:
                q = self.parts[ref]
                if q.placed and q is not part:
                    pts += q.pad_xy(net)
            if pts:
                t[net] = pts
        return t

    def auto(self, ref, side="B", region=None, near=None, radius=14.0, step=0.25, margin=0.2, rots=(0, 90, 180, 270)):
        """Place `ref` at the free spot with the shortest connections.
        near: {net: (x, y)} or (x, y) to override or add attraction points."""
        part = self.parts[ref]
        part.cache(side)
        extra = {}
        anchor = None
        if isinstance(near, dict):
            extra = {k: [v] for k, v in near.items()}
        elif near is not None:
            anchor = near
        t = self.targets(part, extra)
        pts = [q for v in t.values() for q in v]
        if anchor is None:
            if not pts:
                raise RuntimeError(f"{ref}: nothing placed to attract it; give near=")
            anchor = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        boxes = self.boxes(side)
        reg = region or (0.6, 0.6, self.W - 0.6, self.H - 0.6)
        anchor = (min(max(anchor[0], reg[0]), reg[2]), min(max(anchor[1], reg[1]), reg[3]))
        cands = []
        n = int(radius / step)
        for rot in rots:
            g = part.geom[rot]
            for i in range(-n, n + 1):
                for j in range(-n, n + 1):
                    x, y = round((anchor[0] + i * step) / step) * step, round((anchor[1] + j * step) / step) * step
                    bx = (g["box"][0] + x, g["box"][1] + y, g["box"][2] + x, g["box"][3] + y)
                    if bx[0] < reg[0] or bx[1] < reg[1] or bx[2] > reg[2] or bx[3] > reg[3]:
                        continue
                    cost = 0.0
                    for net, tp in t.items():
                        best = 1e9
                        for px, py in g["pads"].get(net, []):
                            for qx, qy in tp:
                                d = abs(px + x - qx) + abs(py + y - qy)
                                if d < best:
                                    best = d
                        cost += best
                    if not t:
                        cost = abs(x - anchor[0]) + abs(y - anchor[1])
                    cands.append((cost + 0.02 * (abs(x - anchor[0]) + abs(y - anchor[1])), x, y, rot, bx))
        cands.sort(key=lambda c: c[0])
        for cost, x, y, rot, bx in cands:
            if not any(overlap(bx, o, margin) for o in boxes):
                part.put(x, y, rot)
                return part
        if radius < 40:
            return self.auto(ref, side, region, near, radius * 1.6, step, margin, rots)
        raise RuntimeError(f"{ref}: no free position near {anchor}")


# ---------------------------------------------------------------- board
def add_line(board, a, b, layer=pcbnew.Edge_Cuts, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(layer)
    s.SetWidth(MM(width))
    board.Add(s)


def add_zone(board, net, layer, pts, name="", clearance=0.3, min_w=0.2, prio=0, solid=False):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    if net:
        z.SetNet(board.FindNet(net))
    z.SetZoneName(name)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(P(x, y).x, P(x, y).y)
    z.SetLocalClearance(MM(clearance))
    z.SetHatchStyle(pcbnew.ZONE_BORDER_DISPLAY_STYLE_NO_HATCH) if hasattr(pcbnew, "ZONE_BORDER_DISPLAY_STYLE_NO_HATCH") else None
    z.SetMinThickness(MM(min_w))
    z.SetAssignedPriority(prio)
    z.SetThermalReliefGap(MM(0.25))
    z.SetThermalReliefSpokeWidth(MM(0.4))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid else pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z


def add_rule_area(board, pts, name, layers, tracks=True, vias=True, pour=True, footprints=False):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetZoneName(name)
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowZoneFills(pour)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(footprints)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(P(x, y).x, P(x, y).y)
    board.Add(z)
    return z


def add_track(board, net, pts, width, layer, locked=True):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(MM(width))
        t.SetLayer(layer)
        t.SetNet(board.FindNet(net))
        t.SetLocked(locked)
        board.Add(t)


def add_via(board, net, xy, dia=0.6, drill=0.3, locked=True):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*xy))
    v.SetWidth(pcbnew.F_Cu, MM(dia))
    v.SetDrill(MM(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(board.FindNet(net))
    v.SetLocked(locked)
    board.Add(v)
    return v


def net_clearance(net):
    """Clearance of the net class a net belongs to (same patterns as in the project file)."""
    import fnmatch
    for name, (_w, c, _v, _d, pats) in NETCLASSES.items():
        if any(fnmatch.fnmatchcase(net, p.replace("[", "[[]")) if "*" in p else net == p for p in pats):
            return c
    return NETCLASSES["Default"][1]


def _rect_dist(px, py, r):
    dx = max(r[0] - px, 0, px - r[2])
    dy = max(r[1] - py, 0, py - r[3])
    return math.hypot(dx, dy)


def _seg_dist(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    l2 = (bx - ax) ** 2 + (by - ay) ** 2
    u = 0 if l2 == 0 else max(0, min(1, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / l2))
    return math.hypot(p[0] - ax - u * (bx - ax), p[1] - ay - u * (by - ay))


# Parts whose plane vias are set after routing instead of before. Tried for all fine-pitch ICs: worse,
# the router leaves no room next to the pins (13 pads without via). So: none.
LATE_VIA_REFS = ()


def drop_plane_vias(board, iface, nets=("GND", "+3V3"), via=0.6, drill=0.3, clearance=0.2, ep_grid=None,
                    skip=(), only=None, pads_only=None):
    """Give every SMD pad of the plane nets a via next to it (short stub), locked.
    Exposed pads listed in ep_grid {ref: (pad number, n)} get an n x n via array inside the pad.
    Returns the number of vias and the pads that found no place."""
    r_via = via / 2
    eps = 1e-4
    pads, vias, failed = [], [], []           # pads: (rect, net, sides, pad, footprint)

    def cl(other_net):
        """Clearance to an object of another net: the larger net class value counts."""
        return max(clearance, net_clearance(other_net))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            side = "FB" if pad.HasHole() else ("B" if pad.IsOnLayer(pcbnew.B_Cu) else "F")
            pads.append(((x0, y0, x1, y1), pad.GetNetname(), side, pad, fp))
    segs = [(unP(t.GetStart()), unP(t.GetEnd()), pcbnew.ToMM(t.GetWidth()), t.GetNetname(),
             "B" if t.GetLayer() == pcbnew.B_Cu else "F") for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    for t in board.GetTracks():               # vias that are already there (x, y, net, radius)
        if t.GetClass() == "PCB_VIA":
            vias.append(unP(t.GetPosition()) + (t.GetNetname(), pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
    n_before = len(vias)
    holes = [(h["x"], h["y"], h["drill"] / 2) for h in iface["mounting_holes"]]
    ol = [tuple(q) for q in iface["board"]["outline"]]
    W, H = iface["board"]["width"], iface["board"]["depth"]
    tab = [q for q in ol if q[0] > W]
    ty0, ty1, tx = min(q[1] for q in tab), max(q[1] for q in tab), max(q[0] for q in tab)
    keep = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]

    def inside_board(x, y, m):
        if not (m <= y <= H - m) or x < m:
            return False
        return x <= (tx if ty0 + m <= y <= ty1 - m else W) - m

    def via_ok(x, y, net, own):
        if not inside_board(x, y, r_via + 0.4):
            return False
        for hx, hy, hr in holes:
            if math.hypot(x - hx, y - hy) < hr + r_via + 0.4:
                return False
        for z in keep:
            if z.Outline().Contains(P(x, y)):
                return False
        for rect, n, side, pad, _fp in pads:
            if pad is own:
                continue
            # no via in or at a pad (solder wicking); 0.15 mm to pads of the same net
            if _rect_dist(x, y, rect) < r_via + cl(n) + (0.1 if side == "FB" else 0) - eps:
                return False
        for vx, vy, vn, vr in vias:
            if math.hypot(x - vx, y - vy) < (r_via + vr + cl(vn) if vn != net else drill + 0.5) - eps:
                return False
        for a, b, w, n, _side in segs:
            if n != net and _seg_dist((x, y), a, b) < r_via + w / 2 + cl(n) - eps:
                return False
        return True

    def stub_ok(a, b, w, net, side, own):
        n = max(2, int(math.dist(a, b) / 0.1))
        for i in range(n + 1):
            q = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            for rect, pn, pside, pad, _fp in pads:
                if pad is own or pn == net or side not in pside:
                    continue
                if _rect_dist(q[0], q[1], rect) < w / 2 + cl(pn) - eps:
                    return False
            for sa, sb, sw, sn, sside in segs:
                if sn != net and sside == side and _seg_dist(q, sa, sb) < w / 2 + sw / 2 + cl(sn) - eps:
                    return False
            for vx, vy, vn, vr in vias:
                if vn != net and math.hypot(q[0] - vx, q[1] - vy) < w / 2 + vr + cl(vn) - eps:
                    return False
        return True

    ep = ep_grid or {}
    for rect, net, side, pad, fp in list(pads):
        ref = fp.GetReference()
        if net not in nets or side == "FB":
            continue
        if ref in ep and pad.GetNumber() == str(ep[ref][0]) and only is not None:
            continue                       # the via array of the exposed pad was set before routing
        fx, fy = unP(fp.GetPosition())
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        layer = pcbnew.B_Cu if side == "B" else pcbnew.F_Cu
        if ref in ep and pad.GetNumber() == str(ep[ref][0]):
            n = ep[ref][1]
            wx, wy = (rect[2] - rect[0]) / n, (rect[3] - rect[1]) / n
            for i in range(n):
                for j in range(n):
                    x, y = rect[0] + wx * (i + 0.5), rect[1] + wy * (j + 0.5)
                    add_via(board, net, (x, y), via, drill)
                    vias.append((x, y, net, r_via))
            continue
        if ref in skip or (only is not None and ref not in only):
            continue
        if pads_only is not None and (ref, pad.GetNumber()) not in pads_only:
            continue
        w = min(0.3, rect[2] - rect[0], rect[3] - rect[1])
        hx, hy = (rect[2] - rect[0]) / 2, (rect[3] - rect[1]) / 2
        ang0 = math.atan2(cy - fy, cx - fx) if (abs(cx - fx) + abs(cy - fy)) > 0.05 else 0.0
        if hx > 1.5 * hy:        # long pads (QFN, FPC, SOIC): leave along the pad axis, away from the part
            ang0 = 0.0 if cx >= fx else math.pi
        elif hy > 1.5 * hx:
            ang0 = math.pi / 2 if cy >= fy else -math.pi / 2
        best = None
        for vx, vy, vn, _vr in vias:       # a via of the same net close by is shared
            if vn == net and _rect_dist(vx, vy, rect) < 0.9 and stub_ok((cx, cy), (vx, vy), w, net, side, pad):
                best = (vx, vy, False)
                break
        if best is None:
            # fine-pitch pads: via 0.9 mm further out, outside the ring where the neighbour pins escape
            fine = 0.9 if min(hx, hy) <= 0.18 and max(hx, hy) > 1.5 * min(hx, hy) else 0.0
            for extra in [fine + e for e in (0.0, 0.25, 0.5, 0.8, 1.2, 1.7, 2.3, 3.0)]:
                for da in (0, 45, -45, 90, -90, 135, -135, 180):      # away from the part centre first
                    a = ang0 + math.radians(da)
                    ux, uy = math.cos(a), math.sin(a)
                    te = min(hx / abs(ux) if abs(ux) > 1e-6 else 1e9, hy / abs(uy) if abs(uy) > 1e-6 else 1e9)
                    d = te + clearance + r_via + extra
                    x, y = round(cx + ux * d, 3), round(cy + uy * d, 3)
                    if via_ok(x, y, net, pad) and stub_ok((cx, cy), (x, y), w, net, side, pad):
                        best = (x, y, True)
                        break
                if best:
                    break
        if best is None:          # fall back: any free spot on rings around the pad, straight stub
            for d in [0.6 + 0.2 * k for k in range(18)]:
                for k in range(24):
                    a = ang0 + math.radians(15 * ((k + 1) // 2) * (1 if k % 2 else -1))
                    x, y = round(cx + math.cos(a) * d, 3), round(cy + math.sin(a) * d, 3)
                    if via_ok(x, y, net, pad) and stub_ok((cx, cy), (x, y), w, net, side, pad):
                        best = (x, y, True)
                        break
                if best:
                    break
        if best is None:          # a pad of the same net close by (the decoupling capacitor): connect pin and pad directly
            near = sorted(((_rect_dist(cx, cy, r2), r2) for r2, n2, s2, _p2, f2 in pads
                           if n2 == net and f2 is not fp and side in s2), key=lambda q: q[0])
            for d2, r2 in near[:4]:
                if d2 > 3.0:
                    break
                q = (min(max(cx, r2[0] + 0.2), r2[2] - 0.2), min(max(cy, r2[1] + 0.2), r2[3] - 0.2))
                if stub_ok((cx, cy), q, w, net, side, pad):
                    best = (q[0], q[1], False)
                    break
        if best is None:          # pin next to an exposed pad of the same net: connect it to that pad
            for erect, enet, eside, epad, efp in pads:
                if efp is fp and enet == net and epad is not pad and side in eside and \
                        (erect[2] - erect[0]) * (erect[3] - erect[1]) > 4.0:
                    tx_, ty_ = min(max(cx, erect[0] + 0.3), erect[2] - 0.3), min(max(cy, erect[1] + 0.3), erect[3] - 0.3)
                    if stub_ok((cx, cy), (tx_, ty_), w, net, side, pad):
                        best = (tx_, ty_, False)
                        break
        if best is None:
            failed.append(f"{ref}.{pad.GetNumber()}")
            continue
        if best[2]:
            add_via(board, net, best[:2], via, drill)
            vias.append((best[0], best[1], net, r_via))
        add_track(board, net, [(cx, cy), best[:2]], w, layer)
        segs.append(((cx, cy), best[:2], w, net, side))
    return len(vias) - n_before, failed


def mounting_hole(board, i, x, y, drill):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("BekantX", "MountingHole_2.9mm_NPTH"))   # an empty name breaks the SES import
    fp.SetReference(f"H{i}")
    fp.SetValue(f"M2.5 hole {drill} mm")
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    pad = pcbnew.PAD(fp)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(pcbnew.VECTOR2I(MM(drill), MM(drill)))
    pad.SetDrillSize(pcbnew.VECTOR2I(MM(drill), MM(drill)))
    pad.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
    fp.Add(pad)
    board.Add(fp)
    lib = PROJ / "BekantX.pretty"          # project library, so that the footprint has a home
    if not (lib / "MountingHole_2.9mm_NPTH.kicad_mod").exists():
        lib.mkdir(exist_ok=True)
        (lib / "MountingHole_2.9mm_NPTH.kicad_mod").write_text(
            '(footprint "MountingHole_2.9mm_NPTH"\n\t(version 20260206)\n\t(generator "bekantx_layout")\n\t(layer "F.Cu")\n'
            '\t(descr "Mounting hole for M2.5, 2.9 mm, not plated (enclosure r3)")\n'
            '\t(attr board_only exclude_from_pos_files exclude_from_bom)\n'
            f'\t(pad "" np_thru_hole circle\n\t\t(at 0 0)\n\t\t(size {drill} {drill})\n\t\t(drill {drill})\n'
            '\t\t(layers "*.Cu" "*.Mask")\n\t)\n)\n', encoding="utf-8")
        (PROJ / "fp-lib-table").write_text(
            '(fp_lib_table\n  (version 7)\n  (lib (name "BekantX")(type "KiCad")(uri "${KIPRJMOD}/BekantX.pretty")'
            '(options "")(descr "BekantX project footprints"))\n)\n', encoding="utf-8")
    fp.SetPosition(P(x, y))
    return fp


def build(out_path, place_fn, verbose=True):
    write_project_rules()
    iface = json.loads((ROOT / "CAD" / "board_interface.json").read_text(encoding="utf-8"))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # an empty board next to a copy of the project file, so that the net classes are loaded with it
    out_path.write_text('(kicad_pcb (version 20260206) (generator "pcbnew") (generator_version "10.0")\n)\n', encoding="utf-8")
    if out_path.parent.resolve() != PROJ.resolve():
        (out_path.with_suffix(".kicad_pro")).write_text((PROJ / "BekantX.kicad_pro").read_text(encoding="utf-8"), encoding="utf-8")
    board = pcbnew.LoadBoard(str(out_path))
    board.SetCopperLayerCount(4)
    # stack: F.Cu (buttons, OLED connector) / In1 +3V3 / In2 GND / B.Cu (all other parts, RF line, USB).
    # GND is the plane next to B.Cu so that the 50 ohm line and nearly all signals run over ground.
    board.SetLayerName(pcbnew.In1_Cu, "In1.PWR")
    board.SetLayerName(pcbnew.In2_Cu, "In2.GND")
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(1.6))
    ds.SetAuxOrigin(P(0, 0))

    comps, nets = load_netlist()
    for name in nets:
        board.Add(pcbnew.NETINFO_ITEM(board, name))
    parts = {ref: Part(board, ref, c) for ref, c in sorted(comps.items())}

    # outline (with the USB tab), mounting holes
    ol = [tuple(p) for p in iface["board"]["outline"]]
    for a, b in zip(ol, ol[1:] + ol[:1]):
        add_line(board, a, b)
    pl = Placer(parts, nets, iface)
    for i, h in enumerate(iface["mounting_holes"], 1):
        mounting_hole(board, i, h["x"], h["y"], h["drill"])
        for side, d in (("F", h["keepout_d_front"]), ("B", h["keepout_d_back"])):
            pl.keepout(side, (h["x"] - d / 2, h["y"] - d / 2, h["x"] + d / 2, h["y"] + d / 2), "screw")

    err = None
    try:
        place_fn(board, pl, parts, iface)
    except RuntimeError as e:        # save what there is so that the state can be looked at
        err = e
    missing = [r for r, p in parts.items() if not p.placed]
    for i, r in enumerate(missing):
        parts[r].put(5 + 9 * (i % 14), pl.H + 12 + 10 * (i // 14), 0, "F")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(out_path), board)
    board = pcbnew.LoadBoard(str(out_path))     # prove that it loads again
    if verbose:
        print(f"saved {out_path}: {len(board.GetFootprints())} footprints, {board.GetNetCount()} nets, "
              f"{len(board.GetTracks())} tracks, {len(board.Zones())} zones")
    if err or missing:
        raise RuntimeError(f"placement incomplete: {err}; not placed: {missing}")
    return board


if __name__ == "__main__":
    from bekantx_placement import place
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "build" / "layout" / "BekantX.kicad_pcb"))
    a = ap.parse_args()
    build(a.out, place)
