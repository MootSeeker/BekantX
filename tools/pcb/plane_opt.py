"""Greedy re-routing of single nets so that the outer GND planes are cut less (user rule 2026-11-21: "Leiterbahnen so
fuehren, dass die Plane so wenig wie moeglich zerschnitten wird").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/plane_opt.py <in.kicad_pcb> <workdir> NET,NET,... [--opencost=4]
        [--inner [--innercost=1.5]] [--keep-escapes]

--keep-escapes releases only the middle of each long chain (release_mid.py, pad escapes stay) instead of the
whole net. --inner lets the router use In1 (the +3V3 plane / VCC area layer) for a net; the result is then only kept when
every zone on In1 still fills as one piece (a track must not cut the plane apart) and the DRC stays clean.

For every net in the list (in that order) the unlocked routing of that net is removed and routed again by
touchup_router.py with --opencost (new tracks hug existing copper instead of crossing free copper area). The result
is kept when the net is fully connected and the metric improves: metric = area of all pieces of the outer GND zones
except the largest one per layer (islands cut off by tracks), counted with refilled zones. A rejected net leaves the
board as it was. Prints one line per net; the best board is <workdir>/best.kicad_pcb.
"""
import shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "C:/Program Files/KiCad/10.0/bin/python.exe"


def run(script, *args):
    r = subprocess.run([PY, "-u", str(HERE / script), *[str(a) for a in args]], cwd=HERE, capture_output=True, text=True)
    return r.returncode, "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "memory leak" not in l and "duplicate image" not in l)


METRIC = r'''
import sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
tot, cnt = 0.0, 0
for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
    areas = []
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND" or z.IsTeardropArea() or z.GetFirstLayer() != lay:
            continue
        f = z.GetFilledPolysList(lay)
        areas += [f.Outline(i).Area() / 1e12 for i in range(f.OutlineCount())]
    areas.sort(reverse=True)
    tot += sum(areas[1:]); cnt += len(areas) - 1
inner = []
for z in b.Zones():
    if not z.GetIsRuleArea() and z.IsOnLayer(pcbnew.In1_Cu):
        f = z.GetFilledPolysList(pcbnew.In1_Cu)
        inner.append("%s:%d:%.0f" % (z.GetNetname(), f.OutlineCount(), sum(f.Outline(i).Area() for i in range(f.OutlineCount())) / 1e12))
ilen = sum(pcbnew.ToMM(t.GetLength()) for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.In1_Cu)
print("METRIC %.1f %d %.1f %s" % (tot, cnt, ilen, ",".join(sorted(inner))))
'''


def metric(board):
    Path(HERE / "_metric.py").write_text(METRIC, encoding="utf-8")
    rc, out = run("_metric.py", board)
    for l in out.splitlines():
        if l.startswith("METRIC"):
            _m, a, n, ilen, inner = l.split()
            planes = {x.split(":")[0]: (int(x.split(":")[1]), float(x.split(":")[2])) for x in inner.split(",")}
            return float(a), int(n), float(ilen), planes
    raise RuntimeError(out)


def drc_counts(board):
    """(unconnected items, errors) of a full DRC with refilled zones; the board needs its project and fp-lib-table next to it."""
    import json
    rep = Path(board).with_suffix(".drc.json")
    subprocess.run(["C:/Program Files/KiCad/10.0/bin/kicad-cli.exe", "pcb", "drc", "--format", "json", "--refill-zones",
                    "-o", str(rep), str(board)], capture_output=True)
    d = json.loads(rep.read_text(encoding="utf-8"))
    return len(d.get("unconnected_items", [])), sum(1 for v in d.get("violations", []) if v["severity"] == "error"),         sum(1 for v in d.get("violations", []) if v["type"] in ("track_dangling", "via_dangling"))


def main(src, work, nets, opencost, extra=(), keep_escapes=False):
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    src = Path(src).resolve()
    pro = src.with_suffix(".kicad_pro")
    best = work / "best.kicad_pcb"
    shutil.copy(src, best)
    shutil.copy(pro, best.with_suffix(".kicad_pro"))
    for f in ("fp-lib-table",):
        if (src.parent / f).exists():
            shutil.copy(src.parent / f, work / f)
    if (src.parent / "BekantX.pretty").exists() and not (work / "BekantX.pretty").exists():
        shutil.copytree(src.parent / "BekantX.pretty", work / "BekantX.pretty")
    m0 = metric(best)
    d0 = drc_counts(best)
    print(f"start: islands {m0[0]:.0f} mm2 in {m0[1]} pieces, In1 {m0[3]}", flush=True)
    for k, net in enumerate(nets):
        cand = work / f"try{k}.kicad_pcb"
        shutil.copy(pro, cand.with_suffix(".kicad_pro"))
        if keep_escapes:          # keep the first/last 1.5 mm of every long chain (pad escapes at the QFNs), re-route the rest
            mid = work / f"mid{k}.kicad_pcb"
            shutil.copy(pro, mid.with_suffix(".kicad_pro"))
            rc, out = run("release_mid.py", best, mid, net, "--layers=F,B", "--min=6")
            if rc != 0 or "released" not in out:
                print(f"{net}: no long chain to release, skipped", flush=True)
                continue
            rc, out = run("touchup_router.py", mid, cand, "--bcost=1.5", f"--opencost={opencost}", f"--first={net}", *extra)
        else:
            rc, out = run("touchup_router.py", best, cand, "--bcost=1.5", f"--opencost={opencost}", f"--release={net}", f"--first={net}", *extra)
        last = out.splitlines()[-1] if out else ""
        if rc != 0 or "left: []" not in last:
            print(f"{net}: not routed ({last[:100]}), kept", flush=True)
            continue
        m1 = metric(cand)
        dc = drc_counts(cand)
        if dc[0] or dc[1] or dc[2] > d0[2]:
            print(f"{net}: DRC after re-routing: {dc[0]} unconnected, {dc[1]} errors, {dc[2]} dangling: rejected", flush=True)
            continue
        cut = [n for n, (pc, _a) in m1[3].items() if pc > m0[3].get(n, (1, 0))[0]]
        if cut:
            print(f"{net}: In1 zone(s) {cut} split into more pieces: rejected", flush=True)
            continue
        if m1[0] < m0[0] - 1.0:
            lost = {n: round(m0[3][n][1] - a) for n, (_p, a) in m1[3].items() if n in m0[3]}
            print(f"{net}: islands {m0[0]:.0f} -> {m1[0]:.0f} mm2, pieces {m0[1]} -> {m1[1]}, In1 track "
                  f"{m0[2]:.1f} -> {m1[2]:.1f} mm, In1 plane area lost {lost} mm2: accepted", flush=True)
            shutil.copy(cand, best)
            m0 = m1
        else:
            print(f"{net}: islands {m0[0]:.0f} -> {m1[0]:.0f} mm2: rejected", flush=True)
    print(f"end: islands {m0[0]:.0f} mm2 in {m0[1]} pieces -> {best}", flush=True)


if __name__ == "__main__":
    oc = next((a.split("=")[1] for a in sys.argv if a.startswith("--opencost=")), "4")
    extra = [a for a in sys.argv[1:] if a == "--inner" or a.startswith("--innercost=")]
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], [n for n in pos[2].split(",") if n], oc, extra, "--keep-escapes" in sys.argv)
