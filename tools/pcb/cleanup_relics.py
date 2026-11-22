"""Clean up the relics of the scripted routing that are hard to remove by hand in KiCad (2026-11-21).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/cleanup_relics.py <in.kicad_pcb> <out.kicad_pcb> [--keep-locks]

1. Unlock every track and via: the locks only told the routing pipeline what to keep (power stage, plane stubs,
   fan-out escapes); in KiCad they keep those items from being selected and deleted. Nothing moves.
2. Remove track pieces shorter than 0.02 mm (rounding leftovers at pad centres, invisible but in the way).
3. Remove dangling vias and stubs one by one (drop_dangling.py logic).
After steps 2 and 3 the DRC must not show more unconnected items than before, else that step is undone.
"""
import json, math, shutil, subprocess, sys
from pathlib import Path

import pcbnew

from bekantx_layout import unP
from drop_dangling import drc

HERE = Path(__file__).resolve().parent


def main(src, dst, keep_locks):
    src, dst = Path(src).resolve(), Path(dst).resolve()
    pro = src.with_suffix(".kicad_pro")
    u0 = len(drc(src).get("unconnected_items", []))
    b = pcbnew.LoadBoard(str(src))
    n_unlock = 0
    if not keep_locks:
        for t in b.GetTracks():
            if t.IsLocked():
                t.SetLocked(False)
                n_unlock += 1
    step1 = dst.with_name(dst.stem + "_1.kicad_pcb")
    shutil.copy(pro, step1.with_suffix(".kicad_pro"))
    pcbnew.SaveBoard(str(step1), b)
    # 2. tiny pieces (fresh process for the removal: pcbnew proxies break after Remove())
    step2 = dst.with_name(dst.stem + "_2.kicad_pcb")
    shutil.copy(pro, step2.with_suffix(".kicad_pro"))
    r = subprocess.run([sys.executable, __file__, "--tiny", str(step1), str(step2)], capture_output=True, text=True)
    n_tiny = int(next((l.split()[1] for l in r.stdout.splitlines() if l.startswith("TINY")), "0"))
    u2 = len(drc(step2).get("unconnected_items", []))
    if u2 > u0:
        print(f"removing {n_tiny} tiny pieces would open {u2 - u0} connections: skipped")
        shutil.copy(step1, step2)
        n_tiny = 0
    # 3. dangling vias and stubs, one by one with DRC check
    r = subprocess.run([sys.executable, str(HERE / "drop_dangling.py"), str(step2), str(dst)], capture_output=True, text=True)
    print(f"unlocked: {n_unlock}; tiny pieces removed: {n_tiny}")
    print("\n".join(l for l in r.stdout.splitlines() if "memory leak" not in l))
    shutil.copy(pro, dst.with_suffix(".kicad_pro"))


def remove_tiny(src, dst):
    b = pcbnew.LoadBoard(str(src))
    dead = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and math.dist(unP(t.GetStart()), unP(t.GetEnd())) < 0.02]
    for t in dead:
        b.Remove(t)
    pcbnew.SaveBoard(str(dst), b)
    print("TINY", len(dead), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--tiny":
        remove_tiny(sys.argv[2], sys.argv[3])
    else:
        pos = [a for a in sys.argv[1:] if not a.startswith("--")]
        main(pos[0], pos[1], "--keep-locks" in sys.argv)
