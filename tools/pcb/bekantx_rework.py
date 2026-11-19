"""Local rework of the routed BekantX board after the PCB review of 2026-11-15 (verdict PASS WITH NOTES).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_rework.py <routed.kicad_pcb> <out.kicad_pcb>

Instead of routing the whole board again (a new Freerouting run seals other pins in, e.g. at the USB mux U8),
only the parts named in the review are moved; the rest of the routing stays as it was:
  Major 1/2  U20 (12 V buck) as one compact cell: C25 on VIN, C26 between CB and SW, D20 at SW, L20 next to it
  Major 3    C15 (input capacitor of U9) next to VIN/GND, Minor 5: R41/R42 at the FB pin of U9
  Minor 3    C7 at the VDD3P3 pins 2/3 of the ESP32-C3, L1 behind it
The positions are the ones bekantx_placement.py computes now (same rules for a full rebuild), except C7/L1.

Steps: move the parts, remove the tracks and vias that hung on their pads or are now in the way, remove
dangling leftovers, give the moved plane pads their vias, place the switching loop of U20 as short straight
tracks (locked). The touch-up router connects the rest; bekantx_finish.py pours and checks.
"""
import math, sys
from pathlib import Path

import pcbnew

from bekantx_layout import MM, P, add_track, add_via, drop_plane_vias, unP
import json

ROOT = Path(__file__).resolve().parents[2]

# ref: (x, y, orientation) in board coordinates, as in build/bx9/placed (bekantx_placement.py after the review)
MOVES = {
    "U20": (83.0, 33.4, 90.0), "C25": (83.0, 30.05, 0.0), "C26": (85.78, 33.4, 90.0),
    "D20": (88.65, 33.4, -90.0), "L20": (94.05, 33.4, 0.0), "C27": (99.0, 32.0, 90.0), "C34": (100.5, 35.75, 0.0),
    "R20": (93.5, 23.0, 0.0), "R40": (94.0, 25.25, 180.0),
    "C15": (97.25, 24.0, -90.0), "R41": (96.75, 27.75, 0.0), "R42": (100.5, 27.5, 0.0),
    # C7/L1: 0.4 mm lower than in a full rebuild, because C4/C6 keep their routed positions here
    "C7": (10.9, 22.4, 180.0), "L1": (10.2, 23.9, 0.0),
}
# nets that only connect moved parts (or a moved part and a fixed pin next to it): routed again completely
LOCAL_NETS = {"Net-(U20-CB)", "Net-(D20-K)", "U2_FB", "Net-(U20-~{SHDN})", "U9_FB", "+3.3VA",
              "Net-(U9-~{SHDN})"}


def pad_rects(fp, grow=0.0):
    out = []
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
        x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        out.append(((x0 - grow, y0 - grow, x1 + grow, y1 + grow), p.GetNetname()))
    return out


def inside(pt, r):
    return r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]


def seg_hits_rect(a, b, r, n=40):
    return any(inside((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n), r) for i in range(n + 1))


def _segd(p, a, b):
    l2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    u = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / l2))
    return math.hypot(p[0] - a[0] - u * (b[0] - a[0]), p[1] - a[1] - u * (b[1] - a[1]))


def dangling(items, pads, gone):
    """Indices of items to remove because they touch nothing any more (repeat until stable).
    items: dicts with kind ("t"/"v"), net, layer, a, b (track) or p, r (via); pads: (rect, net, layers).
    Plane vias (GND/+3V3) without tracks stay (stitching) unless a removed track ended at them.
    Pure Python: pcbnew proxies break after board.Remove(), so nothing is removed before this is decided."""
    gone = set(gone)
    ends = [q for i in gone if items[i]["kind"] == "t" for q in (items[i]["a"], items[i]["b"])]
    while True:
        live = [i for i in range(len(items)) if i not in gone]
        tr = [i for i in live if items[i]["kind"] == "t"]
        vi = [i for i in live if items[i]["kind"] == "v"]

        def touched(q, me):
            m = items[me]
            for i in tr:
                o = items[i]
                # connected only if the end lies on the other centre line (wide neighbours overlap anyway)
                if i != me and o["net"] == m["net"] and o["layer"] == m["layer"] and _segd(q, o["a"], o["b"]) <= 0.01:
                    return True
            for i in vi:
                o = items[i]
                if o["net"] == m["net"] and math.dist(q, o["p"]) < o["r"]:
                    return True
            for r, n, lay in pads:
                if n == m["net"] and m["layer"] in lay and inside(q, r):
                    return True
            return False
        new_gone = [i for i in tr if not (touched(items[i]["a"], i) and touched(items[i]["b"], i))]
        for i in new_gone:
            ends += [items[i]["a"], items[i]["b"]]
        tr2 = [i for i in tr if i not in new_gone]
        for i in vi:
            v = items[i]
            n = sum(1 for k in tr2 if items[k]["net"] == v["net"] and
                    min(math.dist(items[k]["a"], v["p"]), math.dist(items[k]["b"], v["p"])) < v["r"])
            lost = any(math.dist(q, v["p"]) < v["r"] for q in ends)
            in_pad = any(n2 == v["net"] and inside(v["p"], r) for r, n2, _l in pads)
            plane = v["net"] in ("GND", "+3V3")
            # a signal via with a single track and no pad is a dead end (left over from a removed route)
            if (n == 0 and (not plane or lost)) or (n == 1 and not plane and not in_pad):
                new_gone.append(i)
        if not new_gone:
            return gone
        gone |= set(new_gone)


def main(src, dst):
    """Phase 1: decide on a Python copy, move, remove in one go, save. Phase 2 runs in a fresh process."""
    board = pcbnew.LoadBoard(str(src))
    fps = {r: board.FindFootprintByReference(r) for r in MOVES}
    objs = list(board.GetTracks())
    items = []
    for t in objs:
        if t.GetClass() == "PCB_VIA":
            items.append(dict(kind="v", net=t.GetNetname(), layer=None, p=unP(t.GetPosition()),
                              r=pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            items.append(dict(kind="t", net=t.GetNetname(), layer=t.GetLayer(), a=unP(t.GetStart()), b=unP(t.GetEnd()),
                              w=pcbnew.ToMM(t.GetWidth())))
    def pad_list(grow=0.0, refs=None):
        out = []
        for fp in board.GetFootprints():
            if refs is not None and fp.GetReference() not in refs:
                continue
            for p in fp.Pads():
                bb = p.GetBoundingBox()
                x0, y0 = unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
                x1, y1 = unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
                lay = {pcbnew.F_Cu, pcbnew.B_Cu} if p.HasHole() else {pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu}
                out.append(((x0 - grow, y0 - grow, x1 + grow, y1 + grow), p.GetNetname(), lay))
        return out

    # 1. tracks and vias on the pads of the moved parts (old position), and the local nets completely
    old = pad_list(0.01, set(MOVES))
    gone = set()
    for i, it in enumerate(items):
        pts = [it["p"]] if it["kind"] == "v" else [it["a"], it["b"]]
        if it["net"] in LOCAL_NETS or any(inside(q, r) and n == it["net"] for q in pts for r, n, _l in old):
            gone.add(i)
    n1 = len(gone)

    # 2. move
    for r, (x, y, rot) in MOVES.items():
        fps[r].SetPosition(P(x, y))
        fps[r].SetOrientationDegrees(rot)
    pads = pad_list()

    # 3. everything of other nets in the way of the new positions (pads + clearance, courtyard for vias)
    new = pad_list(0.35, set(MOVES))
    crt = []
    for r in MOVES:
        bb = fps[r].GetCourtyard(pcbnew.B_CrtYd if fps[r].IsFlipped() else pcbnew.F_CrtYd).BBox()
        crt.append(unP(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())) + unP(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom())))
    for i, it in enumerate(items):
        if i in gone:
            continue
        if it["kind"] == "v":
            hit = any(inside(it["p"], (c[0] - 0.4, c[1] - 0.4, c[2] + 0.4, c[3] + 0.4)) for c in crt)
        else:
            w = it["w"] / 2
            hit = it["layer"] == pcbnew.B_Cu and any(
                n != it["net"] and seg_hits_rect(it["a"], it["b"], (r[0] - w, r[1] - w, r[2] + w, r[3] + w)) for r, n, _l in new)
        if hit:
            gone.add(i)
    n2 = len(gone) - n1
    gone = dangling(items, pads, gone)
    print(f"removed: {n1} at the old positions, {n2} in the way, {len(gone) - n1 - n2} dangling")
    for i in sorted(gone):
        board.Remove(objs[i])

    tmp = Path(dst).with_name("rework_phase1.kicad_pcb")
    pcbnew.SaveBoard(str(tmp), board)
    import subprocess
    raise SystemExit(subprocess.run([sys.executable, __file__, "--phase2", str(tmp), str(dst)]).returncode)


def phase2(src, dst):
    iface = json.loads((ROOT / "CAD" / "board_interface.json").read_text(encoding="utf-8"))
    board = pcbnew.LoadBoard(str(src))
    fps = {r: board.FindFootprintByReference(r) for r in MOVES}
    # 4. plane vias for the moved parts
    n, failed = drop_plane_vias(board, iface, only=tuple(MOVES))
    print("plane vias for moved parts:", n, "failed:", failed)

    # 5. switching loop of U20: short straight tracks on B.Cu, locked (data sheet / AN-1149)
    pad = lambda r, num: unP([p for p in board.FindFootprintByReference(r).Pads() if p.GetNumber() == str(num)][0].GetPosition())
    vin, sw, cb = pad("U20", 5), pad("U20", 6), pad("U20", 1)
    c25v, c26cb, c26sw, d20k, l20sw = pad("C25", 1), pad("C26", 1), pad("C26", 2), pad("D20", 1), pad("L20", 1)
    for name, q in (("U20.5 VIN", vin), ("U20.6 SW", sw), ("U20.1 CB", cb), ("C25.1", c25v), ("C26.1", c26cb),
                    ("C26.2", c26sw), ("D20.1 K", d20k), ("L20.1", l20sw)):
        print(f"  {name:10s} {q[0]:.3f} {q[1]:.3f}")
    B = pcbnew.B_Cu
    add_track(board, "VCC", [vin, (vin[0], c25v[1] + 0.9), (c25v[0] + 0.0, c25v[1])], 0.5, B)
    add_track(board, "Net-(U20-CB)", [cb, (c26cb[0], cb[1]), c26cb], 0.4, B)
    add_track(board, "Net-(D20-K)", [sw, (c26sw[0], sw[1]), c26sw], 0.5, B)
    add_track(board, "Net-(D20-K)", [c26sw, (c26sw[0] + 0.6, c26sw[1]), (d20k[0], d20k[1] + 0.3), d20k], 0.6, B)
    add_track(board, "Net-(D20-K)", [d20k, (d20k[0] + 0.8, d20k[1]), (l20sw[0] - 1.0, l20sw[1]), l20sw], 0.8, B)
    # U9: VIN and GND are the middle pins of opposite rows, flanked by SHDN (4) and FB (3) on the C15 side.
    # Direct VIN track from C15 over pin 4 (0.33 mm to its pad, PowerHV needs 0.3) onto the feed of pin 5.
    c15v, u9vin = pad("C15", 1), pad("U9", 5)
    add_track(board, "VCC", [(c15v[0] + 0.35, c15v[1] - 0.3), (c15v[0] + 1.0, u9vin[1] - 1.24),
                             (u9vin[0], u9vin[1] - 1.24), u9vin], 0.5, B)
    print(f"  C15.1 {c15v[0]:.3f} {c15v[1]:.3f}   U9.5 {u9vin[0]:.3f} {u9vin[1]:.3f}")

    pcbnew.SaveBoard(str(dst), board)
    print("saved", dst)


if __name__ == "__main__":
    if sys.argv[1] == "--phase2":
        phase2(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1], sys.argv[2])
