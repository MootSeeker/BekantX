"""Add teardrops to the vias (layout rule 2026-11-21: "Verwende Teardrops bei Vias").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/teardrops.py <in.kicad_pcb> <out.kicad_pcb>

pcbnew's Python API has no teardrop generator and no way to build the TEARDROP_TYPE enum, so the zones are written
into the file text, in the format KiCad itself saves (`(attr (teardrop (type padvia)))`, priority 30000, solid fill
that the zone filler trims against other nets). Existing teardrop zones are removed first, so the script can be
run again after the tracks changed.

For every via and every outer-layer track that ends in it (through its centre, along the track axis) the
polygon is the taper between the two points where the track edges are LENGTH mm behind the via edge and the two
tangent points on the via circle. The taper is shortened (never wider) until it keeps the clearance to the copper
of other nets, and skipped when no track is attached, the track is as wide as the via allows, or no room is left.
Run it after the last track edit and before the final zone fill (gnd_pour.py fills).
"""
import math, re, sys, uuid

import pcbnew

from bekantx_layout import MM, ORIGIN, P, net_clearance, unP
from manhattan import Fast
from pcb_geom import OUTER, bbox_mm, uid

LENGTH = 0.55           # mm of taper beyond the via edge (KiCad default: 0.5 x diameter)
MIN_LEN = 0.12          # shortest taper worth drawing, beyond the via edge
WIDTH_RATIO = 0.9       # no teardrop when the track is wider than this share of the via diameter


def strip_teardrops(text):
    """Remove all teardrop zones from the file text."""
    out, i = [], 0
    while True:
        j = text.find("\n\t(zone", i)
        if j < 0:
            out.append(text[i:])
            break
        # end of this top-level zone block: next "\n\t)\n"
        k = text.find("\n\t)\n", j)
        block = text[j:k + 3]
        out.append(text[i:j])
        if "(teardrop" not in block:
            out.append(block)
        i = k + 3                          # keep the newline: the next zone starts right behind it
    return "".join(out)


def taper(c, ang, r, h, d):
    """Taper polygon (board mm) for a via at c, radius r, track half width h leaving at angle ang, reach d."""
    rho = math.hypot(d, h)
    alpha = math.atan2(h, d)
    phi = alpha + math.acos(r / rho)
    loc = [(d, h), (r * math.cos(phi), r * math.sin(phi)), (r * math.cos(phi), -r * math.sin(phi)), (d, -h)]
    ca, sa = math.cos(ang), math.sin(ang)
    return [(c[0] + x * ca - y * sa, c[1] + x * sa + y * ca) for x, y in loc]


def poly_shape(pts):
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in pts:
        ps.Append(P(x, y))
    return ps


def main(src, dst):
    board = pcbnew.LoadBoard(str(src))
    cu = Fast(board)
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() in OUTER]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    made, skipped = [], {"wide": 0, "off centre": 0, "no room": 0, "short": 0}
    for v in vias:
        c = unP(v.GetPosition())
        net = v.GetNetname()
        r = pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)) / 2
        for t in tracks:
            if t.GetNetname() != net:
                continue
            a, b = unP(t.GetStart()), unP(t.GetEnd())
            if math.dist(a, c) < 0.002:
                far = b
            elif math.dist(b, c) < 0.002:
                far = a
            else:
                if v.HitTest(t.GetStart()) or v.HitTest(t.GetEnd()):
                    skipped["off centre"] += 1
                continue
            w = pcbnew.ToMM(t.GetWidth())
            if w > r * 2 * WIDTH_RATIO:
                skipped["wide"] += 1
                continue
            seg = math.dist(c, far)
            ang = math.atan2(far[1] - c[1], far[0] - c[0])
            # a short first piece: the taper may run on over a collinear continuation of the same track
            for _ in range(3):
                if seg - 0.02 - r >= LENGTH:
                    break
                nxt = None
                for u in tracks:
                    if u is t or u.GetNetname() != net or u.GetLayer() != t.GetLayer():
                        continue
                    ua, ub = unP(u.GetStart()), unP(u.GetEnd())
                    for p0, p1 in ((ua, ub), (ub, ua)):
                        if math.dist(p0, far) < 0.002 and math.dist(p0, p1) > 1e-3:
                            if abs(math.sin(math.atan2(p1[1] - p0[1], p1[0] - p0[0]) - ang)) < 0.01 and                                     math.cos(math.atan2(p1[1] - p0[1], p1[0] - p0[0]) - ang) > 0:
                                nxt = p1
                if nxt is None:
                    break
                far = nxt
                seg = math.dist(c, far)
            lay = t.GetLayer()
            d = min(r + LENGTH, seg - 0.02)
            ok = None
            while d - r >= MIN_LEN:
                pts = taper(c, ang, r, w / 2, d)
                shape = poly_shape(pts)
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                box = (min(xs), min(ys), max(xs), max(ys))
                skip = {uid(v), uid(t)}
                if cu._hits(shape, box, net, [lay], skip) is None and cu._edge_ok(shape, box):
                    ok = pts
                    break
                d -= 0.08
            if ok is None:
                skipped["no room" if seg - 0.02 - r >= MIN_LEN else "short"] += 1
                continue
            made.append((lay, net, ok))
    text = strip_teardrops(open(src, encoding="utf-8").read())
    blocks = []
    for lay, net, pts in made:
        xy = " ".join(f"(xy {x + ORIGIN[0]:.4f} {y + ORIGIN[1]:.4f})" for x, y in pts)
        blocks.append(f'''	(zone
		(net "{net}")
		(layer "{board.GetLayerName(lay)}")
		(uuid "{uuid.uuid4()}")
		(name "teardrop")
		(hatch edge 0.5)
		(priority 30000)
		(attr
			(teardrop
				(type padvia)
			)
		)
		(connect_pads yes
			(clearance 0)
		)
		(min_thickness 0.0254)
		(filled_areas_thickness no)
		(fill yes
			(thermal_gap 0.5)
			(thermal_bridge_width 0.5)
		)
		(polygon
			(pts
				{xy}
			)
		)
	)
''')
    i = text.rindex(")")
    text = text[:i].rstrip("\n") + "\n" + "".join(blocks) + text[i:]
    open(dst, "w", encoding="utf-8", newline="\n").write(text)
    print(f"teardrops: {len(made)} ({sum(1 for m in made if m[0] == pcbnew.F_Cu)} F.Cu, "
          f"{sum(1 for m in made if m[0] == pcbnew.B_Cu)} B.Cu); skipped {skipped}; vias {len(vias)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
