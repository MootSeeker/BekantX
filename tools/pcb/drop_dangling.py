"""Remove dangling vias and stubs that the routers left (fan-out vias whose pin got connected another way).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/drop_dangling.py <in.kicad_pcb> <out.kicad_pcb>

KiCad's DRC (via_dangling, track_dangling) names the items. One item at a time is removed (a via, or a stub track
by itself) and kept removed only if the DRC shows no more unconnected items than before (a via reported as
dangling can still carry a connection when the tracks only overlap it). Unlike prune_dangling.py nothing is moved.
"""
import json, math, subprocess, sys, tempfile
from pathlib import Path

import pcbnew

from bekantx_layout import KICAD_BIN, ORIGIN, unP


def drc(path):
    with tempfile.TemporaryDirectory() as d:
        rep = Path(d) / "drc.json"
        subprocess.run([str(KICAD_BIN / "kicad-cli.exe"), "pcb", "drc", "--format", "json", "--severity-all",
                        "-o", str(rep), str(path)], capture_output=True)
        return json.loads(rep.read_text(encoding="utf-8"))


def find_items(b, targets):
    """pcbnew items for the DRC targets, in target order (None where nothing matches)."""
    out = []
    for kind, pos in targets:
        if kind == "via_dangling":
            vs = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
            v = min(vs, key=lambda t: math.dist(unP(t.GetPosition()), pos))
            ok = math.dist(unP(v.GetPosition()), pos) < 0.01 and not (v.IsLocked() and v.GetNetname() in ("GND", "+3V3", "VCC"))
            out.append(v if ok else None)
        else:
            cand = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and
                    min(math.dist(unP(t.GetStart()), pos), math.dist(unP(t.GetEnd()), pos)) < 0.01]
            out.append(cand[0] if cand else None)
    return out


def remove(src, dst, targets, idx):
    b = pcbnew.LoadBoard(str(src))
    items = find_items(b, targets)
    for k in idx:
        if items[k] is not None:
            b.Remove(items[k])
    pcbnew.SaveBoard(str(dst), b)


def main(src, dst):
    import shutil
    rep = drc(src)
    targets = []
    for v in rep.get("violations", []):
        if v["type"] in ("via_dangling", "track_dangling"):
            it = v["items"][0]
            targets.append((v["type"], (it["pos"]["x"] - ORIGIN[0], it["pos"]["y"] - ORIGIN[1])))
    u0 = len(rep.get("unconnected_items", []))
    pro = Path(src).with_suffix(".kicad_pro")
    tmp = Path(dst).with_name(Path(dst).stem + "_try.kicad_pcb")
    shutil.copy(pro, tmp.with_suffix(".kicad_pro"))
    shutil.copy(pro, Path(dst).with_suffix(".kicad_pro"))
    keep = []
    for k in range(len(targets)):            # one item at a time: keep the removal only if nothing opens
        subprocess.run([sys.executable, __file__, "--remove", str(src), str(tmp), json.dumps(targets),
                        json.dumps(keep + [k])], capture_output=True)
        after = drc(tmp)
        if len(after.get("unconnected_items", [])) <= u0:
            keep.append(k)
    subprocess.run([sys.executable, __file__, "--remove", str(src), str(dst), json.dumps(targets), json.dumps(keep)],
                   capture_output=True)
    print(f"dangling items: {len(targets)} reported, {len(keep)} removed, {len(targets) - len(keep)} kept "
          f"(needed for a connection): {[targets[k] for k in range(len(targets)) if k not in keep]}")


if __name__ == "__main__":
    if sys.argv[1] == "--remove":
        remove(sys.argv[2], sys.argv[3], [tuple(x) if isinstance(x, list) and isinstance(x[0], str) else x for x in json.loads(sys.argv[4])],
               json.loads(sys.argv[5]))
    else:
        main(sys.argv[1], sys.argv[2])
