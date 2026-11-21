"""Greedy re-routing of single nets so that the outer GND planes are cut less (user rule 2026-11-21: "Leiterbahnen so
fuehren, dass die Plane so wenig wie moeglich zerschnitten wird").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/plane_opt.py <in.kicad_pcb> <workdir> NET,NET,... [--opencost=4]

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
print("METRIC %.1f %d" % (tot, cnt))
'''


def metric(board):
    Path(HERE / "_metric.py").write_text(METRIC, encoding="utf-8")
    rc, out = run("_metric.py", board)
    for l in out.splitlines():
        if l.startswith("METRIC"):
            _m, a, n = l.split()
            return float(a), int(n)
    raise RuntimeError(out)


def drc_counts(board):
    """(unconnected items, errors) of a full DRC with refilled zones; the board needs its project and fp-lib-table next to it."""
    import json
    rep = Path(board).with_suffix(".drc.json")
    subprocess.run(["C:/Program Files/KiCad/10.0/bin/kicad-cli.exe", "pcb", "drc", "--format", "json", "--refill-zones",
                    "-o", str(rep), str(board)], capture_output=True)
    d = json.loads(rep.read_text(encoding="utf-8"))
    return len(d.get("unconnected_items", [])), sum(1 for v in d.get("violations", []) if v["severity"] == "error"),         sum(1 for v in d.get("violations", []) if v["type"] in ("track_dangling", "via_dangling"))


def main(src, work, nets, opencost):
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
    print(f"start: islands {m0[0]:.0f} mm2 in {m0[1]} pieces", flush=True)
    for k, net in enumerate(nets):
        cand = work / f"try{k}.kicad_pcb"
        shutil.copy(pro, cand.with_suffix(".kicad_pro"))
        rc, out = run("touchup_router.py", best, cand, "--bcost=1.5", f"--opencost={opencost}", f"--release={net}", f"--first={net}")
        last = out.splitlines()[-1] if out else ""
        if rc != 0 or "left: []" not in last:
            print(f"{net}: not routed ({last[:100]}), kept", flush=True)
            continue
        m1 = metric(cand)
        dc = drc_counts(cand)
        if dc[0] or dc[1] or dc[2] > d0[2]:
            print(f"{net}: DRC after re-routing: {dc[0]} unconnected, {dc[1]} errors, {dc[2]} dangling: rejected", flush=True)
            continue
        if m1[0] < m0[0] - 1.0:
            print(f"{net}: islands {m0[0]:.0f} -> {m1[0]:.0f} mm2, pieces {m0[1]} -> {m1[1]}: accepted", flush=True)
            shutil.copy(cand, best)
            m0 = m1
        else:
            print(f"{net}: islands {m0[0]:.0f} -> {m1[0]:.0f} mm2: rejected", flush=True)
    print(f"end: islands {m0[0]:.0f} mm2 in {m0[1]} pieces -> {best}", flush=True)


if __name__ == "__main__":
    oc = next((a.split("=")[1] for a in sys.argv if a.startswith("--opencost=")), "4")
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], [n for n in pos[2].split(",") if n], oc)
