"""Debug picture of a board: courtyards, pads and references per side, in board coordinates
(both sides drawn as seen from the front, so x/y match CAD/board_interface.json).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/board_view.py <board.kicad_pcb> <out_prefix> [--tracks]
"""
import re
import sys
import pcbnew
from PIL import Image, ImageDraw, ImageFont

S = 14  # px per mm


def unconnected(drc_json, ox, oy):
    """Open connections from a kicad-cli DRC report (json, mm): [((x, y), (x, y), net)] in board mm."""
    import json
    out = []
    for u in json.load(open(drc_json, encoding="utf-8")).get("unconnected_items", []):
        it = u["items"]
        if len(it) == 2:
            m = re.search(r"\[([^\]]+)\]", it[0]["description"])
            out.append(((it[0]["pos"]["x"] - ox, it[0]["pos"]["y"] - oy), (it[1]["pos"]["x"] - ox, it[1]["pos"]["y"] - oy),
                        m.group(1) if m else "?"))
    return out


def main(path, prefix, tracks=False, window=None, drc=None):
    b = pcbnew.LoadBoard(path)
    bb = b.GetBoardEdgesBoundingBox()
    ox, oy = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
    w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    x0, y0, x1, y1 = window or (-2, -2, w + 2, h + 2)
    s = S if not window else min(60, int(1700 / (x1 - x0)))
    T = lambda v: ((pcbnew.ToMM(v.x) - ox - x0) * s, (pcbnew.ToMM(v.y) - oy - y0) * s)
    rats = unconnected(drc, ox, oy) if drc else []
    if rats:
        import collections
        print(len(rats), "open connections:", dict(collections.Counter(n for _a, _c, n in rats)))
    M = lambda q: ((q[0] - x0) * s, (q[1] - y0) * s)
    font = ImageFont.load_default(size=max(10, int(s * 0.8)))
    for side, cu, crt in (("F", pcbnew.F_Cu, pcbnew.F_CrtYd), ("B", pcbnew.B_Cu, pcbnew.B_CrtYd)):
        im = Image.new("RGB", (int((x1 - x0) * s), int((y1 - y0) * s)), "white")
        d = ImageDraw.Draw(im)
        for g in b.GetDrawings():
            if g.GetLayer() == pcbnew.Edge_Cuts:
                d.line([T(g.GetStart()), T(g.GetEnd())], fill="black", width=2)
        for z in b.Zones():
            if z.GetIsRuleArea():
                o = z.Outline().Outline(0)
                d.polygon([T(o.CPoint(i)) for i in range(o.PointCount())], outline="orange")
        if tracks:
            for t in b.GetTracks():
                if t.GetClass() == "PCB_VIA":
                    p = T(t.GetPosition()); r = pcbnew.ToMM(t.GetWidth(cu)) / 2 * s
                    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], outline="purple")
                else:
                    col = {pcbnew.F_Cu: (220, 60, 60), pcbnew.B_Cu: (60, 60, 220)}.get(t.GetLayer(), (60, 160, 60))
                    if t.GetLayer() == cu or t.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
                        d.line([T(t.GetStart()), T(t.GetEnd())], fill=col, width=max(1, int(pcbnew.ToMM(t.GetWidth()) * s)))
        for fp in b.GetFootprints():
            on = (fp.GetLayer() == cu)
            for pad in fp.Pads():
                if not (on or pad.HasHole()):
                    continue
                p = T(pad.GetPosition())
                sz = pad.GetBoundingBox()
                a, c = T(pcbnew.VECTOR2I(sz.GetLeft(), sz.GetTop())), T(pcbnew.VECTOR2I(sz.GetRight(), sz.GetBottom()))
                col = (255, 170, 0) if pad.HasHole() else ((200, 80, 80) if side == "F" else (80, 80, 200))
                if pad.GetNetname() == "GND":
                    col = (120, 120, 120)
                d.rectangle([a, c], fill=col)
            if on:
                c = fp.GetCourtyard(crt).BBox()
                if c.GetWidth() > 0:
                    d.rectangle([T(pcbnew.VECTOR2I(c.GetLeft(), c.GetTop())), T(pcbnew.VECTOR2I(c.GetRight(), c.GetBottom()))], outline=(0, 140, 0))
                p = T(fp.GetPosition())
                d.text((p[0], p[1]), fp.GetReference(), fill="black", font=font, anchor="mm")
        if rats:
            for a, c, net in rats:
                d.line([M(a), M(c)], fill=(255, 0, 255), width=2)
        for gx in range(0, int(w) + 1, 10):
            if x0 <= gx <= x1:
                d.text(((gx - x0) * s, 2), str(gx), fill=(150, 150, 150), font=font)
        for gy in range(0, int(h) + 1, 10):
            if y0 <= gy <= y1:
                d.text((2, (gy - y0) * s), str(gy), fill=(150, 150, 150), font=font)
        im.save(f"{prefix}_{side}.png")


if __name__ == "__main__":
    win = drc = None
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for a in sys.argv[1:]:
        if a.startswith("--drc="):
            drc = a.split("=", 1)[1]
        if a.startswith("--window="):
            win = tuple(float(v) for v in a.split("=")[1].split(","))
    main(args[0], args[1], "--tracks" in sys.argv, win, drc)
