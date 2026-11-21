"""Move the middle of long outer-layer runs of slow signals onto In1 (user request 2026-11-21: "gewisse Leiterbahnen
durch Midlayer 1 fuehren, wenn es die aeusseren Lagen entspannen kann").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/in1_drop.py <in.kicad_pcb> <workdir> [--min=8] [--span=5] [--nets=A,B]

In1 carries the +3V3 plane and the VCC area as zones and no tracks; a signal track there only costs a slot in
the plane. For every chain (pcb manhattan.Fixer chains) of a Default-class signal on F.Cu/B.Cu longer than --min
mm, longest first:
  1. the first and the last point along the chain, at least ESCAPE mm from its ends, where a via of the net fits
     (all clearances on F.Cu, B.Cu and In1, hole to hole, not touching an own pad) become two vias,
  2. the part between them (at least --span mm) moves to In1 with the same geometry (stays straight), checked
     against everything on In1 (vias, THT pads, tracks, the antenna keep-out, the board edge),
  3. the board is kept when the outer GND islands shrink (area of all outer pour pieces except the largest per
     layer, refilled), every zone on In1 still fills as one piece, and the DRC has no unconnected item, no error
     and no new dangling track, and no USB/RF track on F.Cu runs over the slot the In1 track cuts into the
     plane (F.Cu signals reference In1).
Not moved: USB, RF, crystal, power and LIN bus nets (other net classes or by name), locked tracks.
Each trial runs in its own process (pcbnew is unreliable after several LoadBoard/Remove in one process).
The best board is <workdir>/best.kicad_pcb.
"""
import json, math, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "C:/Program Files/KiCad/10.0/bin/python.exe"
ESCAPE = 1.2            # mm kept on the outer layer at each chain end (pad escape)
EXCLUDE = re.compile(r"USB|U8-D|J1-|XTAL|LNA|FEED|C10-Pad|C11-Pad|LINBUS|D70")
VIA, DRILL = 0.5, 0.3
SENSITIVE = re.compile(r"USB|U8-D|J1-|LNA|FEED|XTAL")   # F.Cu nets that must keep In1 below them (reference plane)


def candidates(path, min_len):
    import pcbnew
    from bekantx_layout import NETCLASSES
    import fnmatch
    from manhattan import Fixer
    b = pcbnew.LoadBoard(str(path))
    fx = Fixer(b)

    def default_class(net):
        return not any(fnmatch.fnmatchcase(net, p.replace("[", "[[]")) if "*" in p else net == p
                       for _n, (_w, _c, _v, _d, pats) in NETCLASSES.items() for p in pats)

    out = []
    for ch in fx.build_chains():
        if ch.lay not in (pcbnew.F_Cu, pcbnew.B_Cu) or ch.locked or EXCLUDE.search(ch.net) or not default_class(ch.net):
            continue
        L = sum(math.dist(ch.pts[k], ch.pts[k + 1]) for k in range(len(ch.pts) - 1))
        if L >= min_len:
            out.append(dict(net=ch.net, lay=int(ch.lay), a=list(ch.pts[0]), b=list(ch.pts[-1]), len=round(L, 1)))
    out.sort(key=lambda c: -c["len"])
    return out


def slot_overlap(path):
    """mm of F.Cu copper of SENSITIVE nets lying over the slot an In1 track cuts into the plane (track + 0.3 mm)."""
    import pcbnew
    from bekantx_layout import unP
    b = pcbnew.LoadBoard(str(path))
    inner = [(unP(t.GetStart()), unP(t.GetEnd())) for t in b.GetTracks()
             if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.In1_Cu]
    from manhattan import pt_seg
    tot = 0.0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != pcbnew.F_Cu or not SENSITIVE.search(t.GetNetname()):
            continue
        a, c = unP(t.GetStart()), unP(t.GetEnd())
        L = math.dist(a, c)
        n = max(1, int(L / 0.1))
        w = pcbnew.ToMM(t.GetWidth()) / 2
        for k in range(n):
            p = (a[0] + (c[0] - a[0]) * (k + 0.5) / n, a[1] + (c[1] - a[1]) * (k + 0.5) / n)
            if any(pt_seg(p, ia, ic) < 0.075 + 0.3 + w for ia, ic in inner):
                tot += L / n
    print(f"SLOT {tot:.2f}")


def apply_one(src, dst, cand, span):
    """Move the middle of one chain to In1; prints RESULT ok/fail."""
    import pcbnew
    from bekantx_layout import MM, P, add_via
    from manhattan import Fixer
    from pcb_geom import bbox_mm
    b = pcbnew.LoadBoard(str(src))
    fx = Fixer(b)
    cu = fx.cu
    IN1 = pcbnew.In1_Cu
    ch = None
    for c in fx.build_chains():
        if c.net == cand["net"] and int(c.lay) == cand["lay"]:
            ends = (c.pts[0], c.pts[-1])
            if (math.dist(ends[0], cand["a"]) < 0.01 and math.dist(ends[1], cand["b"]) < 0.01) or \
                    (math.dist(ends[0], cand["b"]) < 0.01 and math.dist(ends[1], cand["a"]) < 0.01):
                ch = c
                break
    if ch is None:
        print("RESULT fail chain not found"); return
    pts, segs = ch.pts, ch.segs
    cum = [0.0]
    for k in range(len(pts) - 1):
        cum.append(cum[-1] + math.dist(pts[k], pts[k + 1]))
    L = cum[-1]

    def at(s):
        for k in range(len(pts) - 1):
            if cum[k] <= s <= cum[k + 1] + 1e-9:
                t = (s - cum[k]) / max(cum[k + 1] - cum[k], 1e-9)
                return (pts[k][0] + (pts[k + 1][0] - pts[k][0]) * t, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * t)
        return pts[-1]

    def via_ok(q):
        if not cu.via_clear(q, VIA, DRILL, ch.net, skip=segs, own_pad_gap=0.1):
            return False
        shape = pcbnew.SHAPE_CIRCLE(P(*q), MM(VIA / 2))
        box = (q[0] - VIA / 2, q[1] - VIA / 2, q[0] + VIA / 2, q[1] + VIA / 2)
        return cu._hits(shape, box, ch.net, [IN1], {u for u in ()}) is None

    step = 0.05
    sa = next((s for s in [ESCAPE + i * step for i in range(int((L - 2 * ESCAPE) / step) + 1)] if via_ok(at(s))), None)
    sb = next((s for s in [L - ESCAPE - i * step for i in range(int((L - 2 * ESCAPE) / step) + 1)] if via_ok(at(s))), None)
    if sa is None or sb is None or sb - sa < span:
        print("RESULT fail no via pair"); return
    # the In1 part must keep every clearance on In1
    widths = [pcbnew.ToMM(t.GetWidth()) for t in segs]
    parts = []                       # (k, lo, hi, layer)
    for k in range(len(pts) - 1):
        lo, hi = cum[k], cum[k + 1]
        for a, c, lay in ((lo, min(hi, sa), ch.lay), (max(lo, sa), min(hi, sb), IN1), (max(lo, sb), hi, ch.lay)):
            if c - a > 1e-6:
                parts.append((k, a, c, lay))
    for k, a, c, lay in parts:
        if lay == IN1:
            pa, pc = at(a), at(c)
            if not fx.hole_ok(pa, pc, widths[k]) or not cu.seg_clear(pa, pc, widths[k], ch.net, IN1, skip=segs):
                print("RESULT fail In1 clearance"); return
    # apply: the first part of every segment reuses the segment, the others are new tracks
    used = set()
    for k, a, c, lay in parts:
        pa, pc = at(a), at(c)
        if k not in used:
            t = segs[k]
            used.add(k)
        else:
            t = pcbnew.PCB_TRACK(b)
            t.SetNet(segs[k].GetNet()); t.SetWidth(segs[k].GetWidth())
            b.Add(t)
        t.SetLayer(lay); t.SetStart(P(*pa)); t.SetEnd(P(*pc))
    for s in (sa, sb):
        add_via(b, ch.net, at(s), VIA, DRILL, locked=False)
    pcbnew.SaveBoard(str(dst), b)
    print(f"RESULT ok In1 {sb - sa:.1f} mm vias at ({at(sa)[0]:.2f},{at(sa)[1]:.2f}) ({at(sb)[0]:.2f},{at(sb)[1]:.2f})")


def sub(*args):
    r = subprocess.run([PY, "-u", str(HERE / Path(__file__).name), *[str(a) for a in args]], cwd=HERE,
                       capture_output=True, text=True)
    return "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "memory leak" not in l and "duplicate image" not in l)


def main(src, work, min_len, span, only=None):
    from plane_opt import drc_counts, metric
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    src = Path(src).resolve()
    pro = src.with_suffix(".kicad_pro")
    for f in ("fp-lib-table",):
        if (src.parent / f).exists():
            shutil.copy(src.parent / f, work / f)
    if (src.parent / "BekantX.pretty").exists() and not (work / "BekantX.pretty").exists():
        shutil.copytree(src.parent / "BekantX.pretty", work / "BekantX.pretty")
    best = work / "best.kicad_pcb"
    shutil.copy(src, best)
    shutil.copy(pro, best.with_suffix(".kicad_pro"))
    m0, d0 = metric(best), drc_counts(best)
    print(f"start: islands {m0[0]:.0f} mm2 in {m0[1]} pieces, In1 {m0[3]}, In1 track {m0[2]:.1f} mm", flush=True)
    out = sub("--list", best, min_len)
    cands = json.loads(out.splitlines()[-1])
    if only:
        cands = [c for c in cands if c["net"] in only]
    print(f"{len(cands)} candidate runs (>= {min_len} mm)", flush=True)
    for k, c in enumerate(cands):
        trial = work / f"t{k}.kicad_pcb"
        shutil.copy(pro, trial.with_suffix(".kicad_pro"))
        res = sub("--one", best, trial, json.dumps(c), span)
        line = next((l for l in res.splitlines() if l.startswith("RESULT")), "RESULT fail " + res[-200:])
        tag = f"{c['net']} {'F' if c['lay'] == 0 else 'B'}.Cu {c['len']} mm"
        if not line.startswith("RESULT ok"):
            print(f"{tag}: {line[7:]}", flush=True)
            continue
        slot = float(next((l.split()[1] for l in sub("--slot", trial).splitlines() if l.startswith("SLOT")), "99"))
        if slot > 0.2:
            print(f"{tag}: {slot:.1f} mm of a USB/RF track on F.Cu would run over the In1 slot: rejected", flush=True)
            continue
        m1 = metric(trial)
        if any(pc > m0[3].get(n, (1, 0))[0] for n, (pc, _a) in m1[3].items()):
            print(f"{tag}: an In1 zone would split: rejected", flush=True)
            continue
        if m1[0] > m0[0] - 3.0:
            print(f"{tag}: islands {m0[0]:.0f} -> {m1[0]:.0f} mm2: no gain, rejected", flush=True)
            continue
        dc = drc_counts(trial)
        if dc[0] or dc[1] or dc[2] > d0[2]:
            print(f"{tag}: DRC {dc[0]} unconnected, {dc[1]} errors, {dc[2]} dangling: rejected", flush=True)
            continue
        print(f"{tag}: islands {m0[0]:.0f} -> {m1[0]:.0f} mm2, {line[10:]}: accepted", flush=True)
        shutil.copy(trial, best)
        m0 = m1
    print(f"end: islands {m0[0]:.0f} mm2 in {m0[1]} pieces, In1 track {m0[2]:.1f} mm, In1 {m0[3]} -> {best}", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    if sys.argv[1] == "--list":
        print(json.dumps(candidates(sys.argv[2], float(sys.argv[3]))))
    elif sys.argv[1] == "--slot":
        slot_overlap(sys.argv[2])
    elif sys.argv[1] == "--one":
        apply_one(sys.argv[2], sys.argv[3], json.loads(sys.argv[4]), float(sys.argv[5]))
    else:
        opt = lambda k, d: next((float(a.split("=")[1]) for a in sys.argv if a.startswith(f"--{k}=")), d)
        pos = [a for a in sys.argv[1:] if not a.startswith("--")]
        nets = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--nets=")), "")
        main(pos[0], pos[1], opt("min", 8.0), opt("span", 5.0), set(nets.split(",")) - {""} or None)
