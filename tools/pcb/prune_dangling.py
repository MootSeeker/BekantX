"""Clean up dangling tracks and vias as KiCad's DRC reports them (track_dangling, via_dangling). Left over by
release_mid.py when the router joins a released net at another point than the kept escape, and by later
straightening.

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/prune_dangling.py <in.kicad_pcb> <out.kicad_pcb>

The output path needs the project file next to it (<out>.kicad_pro, net classes).
- track_dangling: the segment (matched by net, length and position) is removed.
- via_dangling on a signal net: the via joins tracks of one layer only. Their ends are moved onto the via centre
  (so that they meet each other) and the via is removed. Vias of the plane nets stay (they reach their plane).
One round per process (pcbnew proxies are not reliable after Remove()); repeats until nothing dangles, at most
six rounds. Every round must leave the number of unconnected items unchanged, otherwise it stops with an error.
"""
import json, math, re, shutil, subprocess, sys, tempfile
from pathlib import Path

import pcbnew

from bekantx_layout import KICAD_BIN, ORIGIN, P, unP

PLANE_NETS = ("GND", "VCC", "+3V3")


def drc(path):
    with tempfile.TemporaryDirectory() as d:
        rep = Path(d) / "drc.json"
        subprocess.run([str(KICAD_BIN / "kicad-cli.exe"), "pcb", "drc", "--format", "json", "--severity-all",
                        "-o", str(rep), str(path)], capture_output=True)
        data = json.loads(rep.read_text(encoding="utf-8"))
    out = []
    for v in data["violations"]:
        if v["type"] in ("track_dangling", "via_dangling"):
            for it in v["items"]:
                net = re.search(r"\[([^\]]+)\]", it["description"])
                ln = re.search(r"([0-9.]+) mm", it["description"])
                out.append((v["type"], net.group(1) if net else "", (it["pos"]["x"] - ORIGIN[0], it["pos"]["y"] - ORIGIN[1]),
                            float(ln.group(1)) if ln else None))
    return [d for d in out if not (d[0] == "via_dangling" and d[1] in PLANE_NETS)], len(data["unconnected_items"])


def one_round(path):
    found, n_open = drc(path)
    if not found:
        return 0, n_open
    board = pcbnew.LoadBoard(str(path))
    tracks = list(board.GetTracks())
    dead = []
    for kind, net, pos, length in found:
        if kind == "track_dangling":
            cand = [t for t in tracks if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net
                    and (length is None or abs(pcbnew.ToMM(t.GetLength()) - length) < 0.002)]
            cand.sort(key=lambda t: min(math.dist(unP(t.GetStart()), pos), math.dist(unP(t.GetEnd()), pos)))
            if cand and all(cand[0] is not o for o in dead):
                dead.append(cand[0])
        else:
            vs = [t for t in tracks if t.GetClass() == "PCB_VIA" and t.GetNetname() == net and math.dist(unP(t.GetPosition()), pos) < 0.01]
            if not vs:
                continue
            v = vs[0]
            c, r = unP(v.GetPosition()), pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)) / 2
            for t in tracks:
                if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net:
                    if math.dist(unP(t.GetStart()), c) <= r:
                        t.SetStart(P(*c))
                    if math.dist(unP(t.GetEnd()), c) <= r:
                        t.SetEnd(P(*c))
            dead.append(v)
    for t in dead:                             # removals last: pcbnew proxies break after Remove()
        board.Remove(t)
    pcbnew.SaveBoard(str(path), board)
    _f, n_after = drc(path)
    if n_after != n_open:
        raise SystemExit(f"prune_dangling: unconnected items {n_open} -> {n_after}; check {path} by hand")
    return len(dead), n_after


def main(src, dst):
    dst = Path(dst)
    if Path(src).resolve() != dst.resolve():
        shutil.copyfile(src, dst)
    total = 0
    for _round in range(6):
        r = subprocess.run([sys.executable, __file__, "--round", str(dst)], capture_output=True, text=True)
        m = re.search(r"ROUND (\d+)", r.stdout)
        if r.returncode or not m:
            raise SystemExit(r.stdout + r.stderr)
        if int(m.group(1)) == 0:
            break
        total += int(m.group(1))
    print(f"dangling tracks/vias cleaned up: {total}")


if __name__ == "__main__":
    if sys.argv[1] == "--round":
        n, _o = one_round(Path(sys.argv[2]))
        print(f"ROUND {n}")
    else:
        main(sys.argv[1], sys.argv[2])
