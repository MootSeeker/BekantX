"""Silkscreen of the controller board: reference designators, function labels, title block with logo and QR code
(layout rule 2026-11-19: "PCB-Beschriftung fehlt noch; wer es gemacht hat, Logo etc.").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_silk.py <in.kicad_pcb> <out.kicad_pcb>

1. Title block on F.SilkS in the free strip next to the mounting hole H1: QR code to the repository, a desk logo
   (table top, two telescopic legs, up/down arrow), the name, revision, credits.
2. Function labels: test points get their signal name instead of the reference (TP refs stay on Fab), the
   connectors and switches a short purpose (USB-C, SWD, OLED, RST, BOOT, USB SEL).
3. Every footprint reference moves from Fab to the silkscreen of its side, 1.0 mm high (0.8 mm where 1.0 mm does
   not fit), 0.15 mm stroke (JLCPCB minimum line width 0.15 mm). The spot is the free one closest to the part:
   no overlap with pads (0.1 mm), other silk (0.1 mm), other labels, the board edge (0.4 mm); spots over other
   parts' courtyards only when nothing else fits. A reference that finds no spot stays on Fab (reported).
4. "JLCJLCJLCJLC" on B.SilkS: JLCPCB puts its order number there instead of a random place.
Existing board texts (desk connector pin names) are kept.
"""
import math, sys

import pcbnew

from bekantx_layout import MM, P, ROOT, add_rule_area, unP
from straighten_pads import seg_rect

REPO = "https://github.com/MootSeeker/BekantX"
STROKE = 0.15
SIZES = (1.0, 0.8)
LABELS = {          # ref: text placed as the part's label (test points: signal name)
    "J1": "USB-C", "J2": "SWD", "J3": "OLED", "J10": "DESK", "SW1": "RST", "SW9": "BOOT", "SW2": "USB SEL",
}
TP_NAMES = {"+3V3": "3V3", "+12V": "12V", "U0RXD": "RXD", "U0TXD": "TXD", "VCC_SPI": "VSPI", "HMI_I2C_SCL": "SCL",
            "HMI_I2C_SDA": "SDA", "BTN_1_SW": "B1", "BTN_2_SW": "B2", "BTN_3_SW": "B3", "BTN_4_SW": "B4",
            "BTN_5_SW": "B5", "BTN_6_SW": "B6"}


def box(item):
    bb = item.GetBoundingBox()
    return unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())) + unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))


def overlap(a, b, m=0.0):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


class Side:
    """Obstacles on one side of the board."""

    def __init__(self, board, back):
        self.back = back
        self.cu = pcbnew.B_Cu if back else pcbnew.F_Cu
        self.silk = pcbnew.B_SilkS if back else pcbnew.F_SilkS
        crt = pcbnew.B_CrtYd if back else pcbnew.F_CrtYd
        self.pads, self.segs, self.blobs, self.courts, self.labels = [], [], [], [], []
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(self.cu) or p.HasHole():
                    self.pads.append(box(p))
            for g in fp.GraphicalItems():
                if g.GetLayer() == self.silk:
                    self.add_graphic(g)
            if fp.IsFlipped() == back:
                c = fp.GetCourtyard(crt)
                if c.OutlineCount():
                    bb = c.BBox()
                    self.courts.append((fp.GetReference(), unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())) +
                                        unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))))
        for d in board.GetDrawings():
            if d.GetLayer() == self.silk:
                self.add_graphic(d)
        ps = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(ps, True)
        self.outline = ps

    def add_graphic(self, g):
        if g.GetClass() == "PCB_SHAPE" and g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            self.segs.append((unP(g.GetStart()), unP(g.GetEnd()), pcbnew.ToMM(g.GetWidth())))
        else:
            self.blobs.append(box(g))

    def inside(self, r, m=0.4):
        pts = [(r[0] - m, r[1] - m), (r[2] + m, r[1] - m), (r[2] + m, r[3] + m), (r[0] - m, r[3] + m)]
        return all(self.outline.Contains(P(*q)) for q in pts)

    def free(self, r, own=None, courts=True):
        if not self.inside(r):
            return False
        if any(overlap(r, p, 0.1) for p in self.pads):
            return False
        if any(overlap(r, b, 0.1) for b in self.blobs) or any(overlap(r, l, 0.15) for l in self.labels):
            return False
        if any(seg_rect(a, b, r) < w / 2 + 0.1 for a, b, w in self.segs
               if overlap(r, (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])), w / 2 + 0.1)):
            return False
        if courts and any(ref != own and overlap(r, c, -0.05) for ref, c in self.courts):
            return False
        return True


def place_text(side, text_item, own, rect_of):
    """Try spots around a footprint (centre and courtyard given by own); returns True when placed."""
    ref, cbox = own
    cx, cy = (cbox[0] + cbox[2]) / 2, (cbox[1] + cbox[3]) / 2
    for courts in (True, False):
        for size in SIZES:
            best = None
            for ang in (0, 90):
                w, h = rect_of(size, ang)
                spots = []
                for gap in ((0.15, 0.4, 0.8, 1.3, 2.0) if courts else (0.15, 0.4, 0.8, 1.3, 2.0, 2.6, 3.2)):
                    for s in (0.0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5, 2.5, -2.5):
                        spots += [(cx + s, cbox[1] - gap - h / 2), (cx + s, cbox[3] + gap + h / 2),
                                  (cbox[0] - gap - w / 2, cy + s), (cbox[2] + gap + w / 2, cy + s)]
                if not courts:                 # last resort: on the own body, between the pads
                    spots.append((cx, cy))
                for x, y in spots:
                    r = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                    if side.free(r, ref, courts):
                        d = math.dist((x, y), (cx, cy)) + (0.6 if ang else 0.0)
                        if best is None or d < best[0]:
                            best = (d, x, y, ang, r)
            if best:
                _d, x, y, ang, r = best
                text_item.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
                text_item.SetTextThickness(MM(STROKE))
                text_item.SetTextAngleDegrees(ang)
                text_item.SetPosition(P(x, y))
                side.labels.append(r)
                return size, courts
    return None


def text_rect_fn(board, item):
    """Width/height of the text item for a size and angle (measured with KiCad's font)."""
    cache = {}

    def f(size, ang):
        if (size, ang) not in cache:
            item.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
            item.SetTextThickness(MM(STROKE))
            item.SetTextAngleDegrees(ang)
            item.SetPosition(P(50, 50))
            b = box(item)
            cache[(size, ang)] = (b[2] - b[0], b[3] - b[1])
        return cache[(size, ang)]
    return f


def add_text(board, text, x, y, size, back=False, thick=STROKE, justify=pcbnew.GR_TEXT_H_ALIGN_LEFT, bold=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(pcbnew.B_SilkS if back else pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(thick))
    t.SetHorizJustify(justify)
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetMirrored(back)
    t.SetPosition(P(x, y))
    board.Add(t)
    return t


def add_poly(board, pts, layer=pcbnew.F_SilkS):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_POLY)
    s.SetFilled(True)
    s.SetWidth(MM(0.1))
    s.SetLayer(layer)
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in pts:
        v = P(x, y)
        ps.Append(v.x, v.y)
    s.SetPolyShape(ps)
    board.Add(s)
    return s


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def desk_logo(board, x, y, s=1.0):
    """A standing desk seen from the front, 8 x 7 mm at scale 1: table top, two telescopic legs (inner tube,
    outer tube), feet, and an up/down arrow between the legs. Origin top left."""
    q = lambda pts: [(x + px * s, y + py * s) for px, py in pts]
    items = [rect(0.0, 0.0, 8.0, 0.9)]                                   # table top
    for lx in (1.3, 5.7):                                                # legs, centre x of each
        items.append(rect(lx - 0.35, 0.9, lx + 0.35, 3.4))              # inner tube
        items.append(rect(lx - 0.6, 3.4, lx + 0.6, 6.2))                # outer tube
        items.append(rect(lx - 1.3, 6.2, lx + 1.3, 6.8))                # foot
    ax = 3.5                                                             # arrow between the legs
    items.append([(ax, 1.6), (ax + 0.8, 2.6), (ax + 0.3, 2.6), (ax + 0.3, 4.6), (ax + 0.8, 4.6), (ax, 5.6),
                  (ax - 0.8, 4.6), (ax - 0.3, 4.6), (ax - 0.3, 2.6), (ax - 0.8, 2.6)])
    for pts in items:
        add_poly(board, q(pts))
    return (x, y, x + 8.0 * s, y + 6.8 * s)


def qr(board, text, x, y, size):
    c = pcbnew.PCB_BARCODE(board)
    c.SetLayer(pcbnew.F_SilkS)
    c.SetKind(pcbnew.BARCODE_T_QR_CODE)
    c.SetErrorCorrection(pcbnew.BARCODE_ECC_T_M)
    c.SetText(text)
    c.SetShowText(False)
    c.SetWidth(MM(size))
    c.SetHeight(MM(size))
    c.SetPosition(P(x + size / 2, y + size / 2))
    c.AssembleBarcode()
    board.Add(c)
    return (x, y, x + size, y + size)


QR_BOX = (7.4, 1.05, 6.5)       # x, y, size: 1 mm quiet zone (KiCad barcode rule) clear of the pad vias of SW1/SW3


def clear_qr_area(board):
    """The QR code needs 1 mm to all copper: stitching vias (GND, no track attached) in that area go, and a rule
    area keeps new ones out (bekantx_finish.py stitches around it)."""
    x, y, s = QR_BOX
    area = [(x - 1.1, y - 1.1), (x + s + 1.1, y - 1.1), (x + s + 1.1, y + s + 1.1), (x - 1.1, y + s + 1.1)]
    if not any(z.GetIsRuleArea() and z.GetZoneName() == "QR code" for z in board.Zones()):
        add_rule_area(board, area, "QR code", [pcbnew.F_Cu, pcbnew.B_Cu], tracks=False, vias=True, pour=False)
    ends = set()
    for tr in board.GetTracks():
        if tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == "GND":
            for q in (unP(tr.GetStart()), unP(tr.GetEnd())):
                ends.add((round(q[0], 2), round(q[1], 2)))
    dead = []
    for v in board.GetTracks():
        if v.GetClass() != "PCB_VIA":
            continue
        p = unP(v.GetPosition())
        r = pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)) / 2
        if x - 1.0 - r < p[0] < x + s + 1.0 + r and y - 1.0 - r < p[1] < y + s + 1.0 + r:
            if v.GetNetname() != "GND" or any(math.dist(p, e) <= r for e in ends):
                raise SystemExit(f"QR code area: via {v.GetNetname()} at {p} is not a free stitching via")
            dead.append(v)
    return dead


def title_block(board, front):
    """Strip x 7.4..44, y 0.9..10 on the front (free: mounting hole H1 keep-out ends at x 6.5, the button row
    starts at y 11)."""
    x, y, s = QR_BOX
    blocks = [qr(board, REPO, x, y, s)]
    blocks.append(desk_logo(board, 15.3, 1.6, 0.85))
    t = add_text(board, "BekantX", 23.4, 2.75, 2.6, thick=0.4)
    blocks.append(box(t))
    # 1.0 mm lines (JLCPCB: 0.15 mm stroke needs about 1 mm height); the repository URL is in the QR code
    for i, line in enumerate(("BEKANT controller r1", "by MootSeeker 2026", "AI-assisted layout")):
        blocks.append(box(add_text(board, line, 23.4, 5.5 + i * 1.5, 1.0, thick=STROKE)))
    for b in blocks[1:]:
        if not front.free(b):
            print(f"  title block item at {b} overlaps a pad or other silk")
    for b in blocks:
        front.labels.append(b)
    return blocks


def main(src, dst):
    board = pcbnew.LoadBoard(str(src))
    front, back = Side(board, False), Side(board, True)
    for side in (front, back):
        for d in board.GetDrawings():         # existing board texts (desk connector pins) count as labels
            if d.GetLayer() == side.silk and d.GetClass() == "PCB_TEXT":
                side.labels.append(box(d))
    dead = clear_qr_area(board)
    title_block(board, front)
    jlc = add_text(board, "JLCJLCJLCJLC", 39.0, 2.0, 1.0, back=True, justify=pcbnew.GR_TEXT_H_ALIGN_CENTER)
    back.labels.append(box(jlc))
    placed, small, crowded, failed = 0, 0, 0, []
    # big parts first: they have the fewest spots and the most obvious place
    fps = sorted(board.GetFootprints(), key=lambda f: -(lambda b: (b[2] - b[0]) * (b[3] - b[1]))(box(f)))
    for fp in fps:
        ref = fp.GetReference()
        side = back if fp.IsFlipped() else front
        own = next((c for c in side.courts if c[0] == ref), (ref, box(fp)))
        field = fp.Reference()
        if ref.startswith("TP"):
            net = fp.Pads()[0].GetNetname()
            label = TP_NAMES.get(net, net)
        else:
            label = LABELS.get(ref)
        if ref.startswith("H"):
            continue                           # mounting holes: no label
        if label:                              # a function label as a board text; the reference stays on Fab
            item = pcbnew.PCB_TEXT(board)
            item.SetText(label)
            item.SetLayer(side.silk)
            item.SetMirrored(side.back)
            item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            board.Add(item)
            res = place_text(side, item, own, text_rect_fn(board, item))
            if res is None:
                board.Remove(item)
                failed.append(f"{ref} label {label}")
                continue
            placed += 1
            continue
        field.SetLayer(side.silk)
        field.SetMirrored(side.back)
        field.SetVisible(True)
        field.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        field.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        res = place_text(side, field, own, text_rect_fn(board, field))
        if res is None:
            field.SetLayer(pcbnew.B_Fab if side.back else pcbnew.F_Fab)
            field.SetTextSize(pcbnew.VECTOR2I(MM(0.6), MM(0.6)))
            field.SetTextThickness(MM(0.1))
            field.SetTextAngleDegrees(0)
            field.SetPosition(P(*(lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))(box(fp))))
            failed.append(ref)
            continue
        placed += 1
        small += res[0] < 1.0
        crowded += not res[1]
    for v in dead:                             # removals last: pcbnew proxies break after Remove()
        board.Remove(v)
    pcbnew.SaveBoard(str(dst), board)
    print(f"stitching vias removed under the QR code: {len(dead)}")
    print(f"silkscreen: {placed} labels placed ({small} at 0.8 mm, {crowded} over another part's courtyard); "
          f"no room, kept on Fab: {len(failed)} {failed}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
