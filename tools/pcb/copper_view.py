"""Picture of the copper of one outer layer (pours, tracks, pads, vias, teardrops), in board coordinates.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/copper_view.py <board.kicad_pcb> <out.png> [F|B|I|I2|I3|I4] [--window=x0,y0,x1,y1] [--px=24] [--nets]

Board mm like CAD/board_interface.json (origin = board corner). Layer B is drawn mirrored like KiCad shows it
from the back is NOT done: both sides use the same x/y so pictures can be compared. Pours are pale, tracks
saturated; a track that is not horizontal/vertical gets a thin black centre line so odd angles stand out.
"""
import math, sys

import pcbnew
from PIL import Image, ImageDraw, ImageFont

from bekantx_layout import unP

COL = {"F": ((205, 60, 60), (240, 200, 200)), "B": ((70, 110, 205), (200, 212, 240)),
       "I": ((190, 120, 20), (245, 225, 190)), "I2": ((30, 150, 70), (200, 235, 210)),
       "I3": ((150, 60, 170), (230, 205, 235)), "I4": ((110, 110, 110), (225, 225, 225))}


def main(path, out, side="F", window=None, px=24, nets=False):
    b = pcbnew.LoadBoard(path)
    lay = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu, "I": pcbnew.In1_Cu, "I2": pcbnew.In2_Cu, "I3": pcbnew.In3_Cu,
           "I4": pcbnew.In4_Cu}[side]
    col, pale = COL[side]
    bb = b.GetBoardEdgesBoundingBox()
    w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    x0, y0, x1, y1 = window or (-1, -1, w + 1, h + 1)
    s = px * 2
    im = Image.new("RGB", (int((x1 - x0) * s), int((y1 - y0) * s)), (250, 250, 250))
    d = ImageDraw.Draw(im)
    T = lambda v: ((unP(v)[0] - x0) * s, (unP(v)[1] - y0) * s)
    for z in b.Zones():
        if z.GetIsRuleArea() or not z.IsOnLayer(lay):
            continue
        f = z.GetFilledPolysList(lay)
        colr = (60, 60, 60) if z.IsTeardropArea() else pale
        if z.IsTeardropArea():
            colr = col
        for i in range(f.OutlineCount()):
            o = f.Outline(i)
            d.polygon([T(o.CPoint(k)) for k in range(o.PointCount())], fill=colr)
            for hh in range(f.HoleCount(i)):
                ho = f.Hole(i, hh)
                d.polygon([T(ho.CPoint(k)) for k in range(ho.PointCount())], fill=(250, 250, 250))
    for g in b.GetDrawings():
        if g.GetLayer() == pcbnew.Edge_Cuts:
            try:
                d.line([T(g.GetStart()), T(g.GetEnd())], fill=(0, 0, 0), width=2)
            except Exception:
                pass
    odd = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" or t.GetLayer() != lay:
            continue
        a, c = T(t.GetStart()), T(t.GetEnd())
        wd = pcbnew.ToMM(t.GetWidth()) * s
        d.line([a, c], fill=col, width=max(1, int(wd)))
        r = wd / 2
        for q in (a, c):
            d.ellipse([q[0] - r, q[1] - r, q[2 - 2] + r if False else q[0] + r, q[1] + r], fill=col)
        ang = math.degrees(math.atan2(abs(c[1] - a[1]), abs(c[0] - a[0])))
        if 0.05 < ang < 89.95:
            odd.append((a, c, abs(ang - 45) < 0.05))
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if not pad.IsOnLayer(lay):
                continue
            sh = pad.GetEffectiveShape(lay)
            bx = pad.GetBoundingBox()
            a, c = T(pcbnew.VECTOR2I(bx.GetLeft(), bx.GetTop())), T(pcbnew.VECTOR2I(bx.GetRight(), bx.GetBottom()))
            colp = (150, 150, 150) if pad.GetNetname() == "GND" else col
            d.rounded_rectangle([a, c], radius=min(c[0] - a[0], c[1] - a[1]) * 0.2, fill=colp)
            if pad.HasHole():
                p = T(pad.GetPosition())
                r = pcbnew.ToMM(pad.GetDrillSize().x) / 2 * s
                d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=(40, 40, 40))
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        p = T(t.GetPosition())
        r = pcbnew.ToMM(t.GetWidth(lay)) / 2 * s
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col, outline=(30, 30, 30))
        r2 = pcbnew.ToMM(t.GetDrillValue()) / 2 * s
        d.ellipse([p[0] - r2, p[1] - r2, p[0] + r2, p[1] + r2], fill=(235, 190, 40))
        if nets:
            d.text((p[0] + r, p[1] - r), t.GetNetname(), fill=(0, 0, 0), font=ImageFont.load_default(size=int(s * 0.5)))
    for a, c, is45 in odd:
        d.line([a, c], fill=(0, 0, 0) if not is45 else (255, 255, 0), width=1)
    im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    im.save(out)


if __name__ == "__main__":
    win, px, nets = None, 24, "--nets" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--window="):
            win = tuple(float(v) for v in a.split("=")[1].split(","))
        if a.startswith("--px="):
            px = int(a.split("=")[1])
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], args[1], args[2] if len(args) > 2 else "F", win, px, nets)
