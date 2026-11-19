"""Finish a routed BekantX board: outer GND pours, plane-only rule for the inner layers, GND stitching
vias, stackup, zone refill. Writes the result to Pcb_Controller/BekantX.kicad_pcb (or --out).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_finish.py <routed.kicad_pcb> [--out <file>]
"""
import argparse, json, math
from pathlib import Path

import pcbnew

from bekantx_layout import (LATE_VIA_REFS, MM, P, PROJ, ROOT, _rect_dist, _seg_dist, add_rule_area, add_via, add_zone,
                            drop_plane_vias, net_clearance, unP)

# JLCPCB JLC04161H-7628 (1.6 mm, 1 oz outer, 0.5 oz inner), values from JLCPCB's published stackup;
# confirm in the order form. 50 ohm microstrip on L1/L4 over L2/L3 is about 0.35 mm wide.
STACKUP = '''		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
'''


def stitch(board, iface, pitch=5.0, via=0.6, drill=0.3, extra=()):
    """GND vias on a grid (and at the extra points) wherever both outer layers are free."""
    r = via / 2
    W, H = iface["board"]["width"], iface["board"]["depth"]
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
            x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            pads.append(((x0, y0, x1, y1), pad.GetNetname()))
    segs, vias = [], []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias.append(unP(t.GetPosition()) + (pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, t.GetNetname()))
        else:
            segs.append((unP(t.GetStart()), unP(t.GetEnd()), pcbnew.ToMM(t.GetWidth()), t.GetNetname()))
    keep = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    holes = [(h["x"], h["y"], h["keepout_d_front"] / 2) for h in iface["mounting_holes"]]

    def ok(x, y):
        if not (1.0 <= x <= W - 1.0 and 1.0 <= y <= H - 1.0):
            return False
        if any(math.hypot(x - hx, y - hy) < hr + r for hx, hy, hr in holes):
            return False
        if any(z.Outline().Contains(P(x, y)) for z in keep):
            return False
        for rect, n in pads:
            if _rect_dist(x, y, rect) < r + max(0.25, net_clearance(n)):
                return False
        for vx, vy, vr, n in vias:
            if math.hypot(x - vx, y - vy) < r + vr + (0.5 if n == "GND" else max(0.25, net_clearance(n))):
                return False
        for a, b, w, n in segs:
            if n != "GND" and _seg_dist((x, y), a, b) < r + w / 2 + max(0.25, net_clearance(n)):
                return False
        return True

    pts = list(extra)
    nx, ny = int(W / pitch), int(H / pitch)
    pts += [(pitch / 2 + i * pitch, pitch / 2 + j * pitch) for i in range(nx + 1) for j in range(ny + 1)]
    n = 0
    for k, (x, y) in enumerate(pts):
        # grid points only where no GND via is within half a pitch yet: a board that was finished before keeps
        # its stitching and only the gaps (e.g. after a rework) are filled; the fence points always count
        if k >= len(extra) and any(vn == "GND" and math.hypot(x - vx, y - vy) < pitch / 2 for vx, vy, _vr, vn in vias):
            continue
        for dx, dy in ((0, 0), (0.6, 0), (-0.6, 0), (0, 0.6), (0, -0.6), (1.2, 0), (-1.2, 0), (0, 1.2), (0, -1.2)):
            if ok(x + dx, y + dy):
                add_via(board, "GND", (x + dx, y + dy), via, drill, locked=False)
                vias.append((x + dx, y + dy, r, "GND"))
                n += 1
                break
    return n


def silk(board, text, x, y, back=True, size=0.9, justify=pcbnew.GR_TEXT_H_ALIGN_LEFT):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(pcbnew.B_SilkS if back else pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(0.15))
    t.SetHorizJustify(justify)
    t.SetMirrored(back)
    t.SetPosition(P(x, y))
    board.Add(t)


def labels(board):
    """Silkscreen on the back: desk connector pin names beyond the pin tips (the area under the cable housing
    is free of parts) and the board name. On mirrored text GR_TEXT_H_ALIGN_RIGHT grows towards +x."""
    j10 = board.FindFootprintByReference("J10")
    names = {"VDESK": "VDESK", "GND": "GND", "LINBUS": "LIN"}
    ys = []
    for pad in j10.Pads():
        x, y = unP(pad.GetPosition())
        ys.append(y)
        silk(board, names.get(pad.GetNetname(), pad.GetNetname()), x + 11.0, y, justify=pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    silk(board, "BekantX r1", x + 11.0, min(ys) - 1.25, size=0.8, justify=pcbnew.GR_TEXT_H_ALIGN_RIGHT)


# footprints without a model in the KiCad library get an envelope model (CAD/src/make_pcb_models.py);
# the buttons use the 4.3 mm high variant of the library model (Omron B3F-1000)
MODELS = {
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": "${KIPRJMOD}/3d/USB_C_HRO_TYPE-C-31-M-12.step",
    "SW_SPDT_CK_JS102011SAQN": "${KIPRJMOD}/3d/SW_CK_JS102011SAQN.step",
    "LED_SK6812MINI_PLCC4_3.5x3.5mm_P1.75mm": "${KIPRJMOD}/3d/LED_SK6812MINI.step",
    "LED_Cree-PLCC4_3.2x2.8mm_CCW": "${KIPRJMOD}/3d/LED_Cree_CLVBA-FKA.step",
    "Johanson_2450AT18x100": "${KIPRJMOD}/3d/Johanson_2450AT18A100.step",
    "SW_PUSH_6mm": "${KICAD10_3DMODEL_DIR}/Button_Switch_THT.3dshapes/SW_PUSH_6mm_H4.3mm.step",
}


def trim_offboard_silk(board, iface, margin=0.2):
    """Remove footprint silkscreen lines that end beyond the board edge (the USB-C outline in front of the tab).
    They would not be printed anyway; removing them clears the silk_edge_clearance warnings."""
    xmax = max(q[0] for q in iface["board"]["outline"])
    n = 0
    for fp in board.GetFootprints():
        for g in list(fp.GraphicalItems()):
            if g.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS) or g.GetClass() != "PCB_SHAPE":
                continue
            if max(unP(g.GetStart())[0], unP(g.GetEnd())[0]) > xmax - margin:
                fp.Remove(g)
                n += 1
    return n


def attach_models(board):
    n = 0
    for fp in board.GetFootprints():
        name = str(fp.GetFPID().GetLibItemName())
        if name in MODELS:
            ms = fp.Models()
            keep = [m for m in ms if name == "SW_PUSH_6mm"]
            ms.clear()
            m = pcbnew.FP_3DMODEL()
            if keep:                         # same offset and rotation as the library model
                m.m_Offset, m.m_Rotation, m.m_Scale = keep[0].m_Offset, keep[0].m_Rotation, keep[0].m_Scale
            m.m_Filename = MODELS[name]
            ms.push_back(m)
            n += 1
    return n


def finish(src, out):
    iface = json.loads((ROOT / "CAD" / "board_interface.json").read_text(encoding="utf-8"))
    board = pcbnew.LoadBoard(str(src))
    inner = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.In2_Cu]
    if inner:
        raise RuntimeError(f"{len(inner)} tracks on In2; the GND plane must stay solid")
    n_in1 = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.In1_Cu)
    print(f"tracks on In1 (+3V3 plane): {n_in1}")
    ol = [tuple(q) for q in iface["board"]["outline"]]
    H = iface["board"]["depth"]
    if LATE_VIA_REFS:
        nv, failed = drop_plane_vias(board, iface, only=LATE_VIA_REFS, ep_grid={"U1": (33, 3), "U2": (33, 3)})
        print(f"late plane vias: {nv}, pads without via: {failed}")
    names = [z.GetZoneName() for z in board.Zones()]
    if "GND plane only" not in names:
        # the GND plane stays solid; In1 (+3V3) may carry the few tracks of the touch-up router
        add_rule_area(board, ol, "GND plane only", [pcbnew.In2_Cu], tracks=True, vias=False, pour=False)
    if "+3V3 plane" not in names:
        add_zone(board, "+3V3", pcbnew.In1_Cu, ol, "+3V3 plane", solid=True)
    if "GND top" not in names:
        add_zone(board, "GND", pcbnew.F_Cu, ol, "GND top")
        add_zone(board, "GND", pcbnew.B_Cu, ol, "GND bottom")
    # ground vias along the edge of the antenna clearance (recommended by the antenna data sheet)
    fence = [(x, H - 6.5 - 0.7) for x in (0.9, 3.6, 5.2, 6.8)] + [(6.5 + 0.7, y) for y in (H - 5.2, H - 3.6, H - 2.0, H - 0.9)]
    print("3D models attached:", attach_models(board))
    # trim_offboard_silk() would clear the 2 silk_edge_clearance warnings of J1, but makes J1 differ from the
    # library (lib_footprint_mismatch), so the library footprint stays untouched.
    n = stitch(board, iface, extra=fence)
    if not any(d.GetClass() == "PCB_TEXT" for d in board.GetDrawings()):
        labels(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    out = Path(out)
    pcbnew.SaveBoard(str(out), board)
    txt = out.read_text(encoding="utf-8")
    if "(stackup" not in txt:
        txt = txt.replace("\t(setup\n", "\t(setup\n" + STACKUP, 1)
        out.write_text(txt, encoding="utf-8")
    board = pcbnew.LoadBoard(str(out))      # prove that it loads again
    vias = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
    print(f"saved {out}: {len(board.GetFootprints())} footprints, {len(board.GetTracks()) - vias} track segments, "
          f"{vias} vias ({n} stitching), {len(board.Zones())} zones")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default=str(PROJ / "BekantX.kicad_pcb"))
    a = ap.parse_args()
    finish(a.src, a.out)
