"""Layout polish of a finished, routed board in the order that works (user feedback 2026-11-21).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/layout_polish.py <in.kicad_pcb> <out.kicad_pcb> [--work=build/polish] [--no-route] [--trim]

1. manhattan.py        tracks through pad/via centres, horizontal/vertical runs with chamfers (the slow step, ~6 min)
2. prune_dangling.py   stubs the re-routing left (DRC-driven)
3. teardrops.py        teardrops on the vias (zones in the file text)
4. gnd_pour.py         stitching vias per pour piece, final zone fill
(gnd_trim.py + prune_gnd_vias.py shrink the outer pours to a margin around other copper; the user wants the opposite,
large GND planes, so they run only with --trim)
Every intermediate file gets the project file of <in> next to it (the zone filler reads the net class rules from it).
After the last step the full DRC with schematic parity runs and the counts are printed; the audit follows.
"""
import json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KICAD = Path("C:/Program Files/KiCad/10.0/bin")
PY = str(KICAD / "python.exe")


def run(script, *args):
    print(f"\n== {script} {' '.join(str(a) for a in args)}", flush=True)
    r = subprocess.run([PY, "-u", str(HERE / script), *[str(a) for a in args]], cwd=HERE, capture_output=True, text=True)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "memory leak" not in l and "duplicate image" not in l)
    print(out, flush=True)
    if r.returncode != 0:
        sys.exit(f"{script} failed ({r.returncode})")


def main(src, dst, work, route=True, trim=False):
    src, dst, work = Path(src).resolve(), Path(dst).resolve(), Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    pro = src.with_suffix(".kicad_pro")
    steps = [("manhattan.py", ["--passes=3"]), ("prune_dangling.py", []), ("teardrops.py", [])]
    if trim:
        steps += [("gnd_trim.py", ["--margin=0.9", "--close=0.6", "--open=0.3"]), ("prune_gnd_vias.py", [])]
    steps.append(("gnd_pour.py", []))
    if not route:
        steps = steps[1:]
    cur = src
    for k, (script, extra) in enumerate(steps):
        nxt = work / f"step{k + 1}_{script.replace('.py', '')}.kicad_pcb"
        shutil.copy(pro, nxt.with_suffix(".kicad_pro"))
        run(script, cur, nxt, *extra)
        cur = nxt
    shutil.copy(cur, dst)
    shutil.copy(pro, dst.with_suffix(".kicad_pro")) if not dst.with_suffix(".kicad_pro").exists() else None
    rep = work / "drc.json"
    subprocess.run([str(KICAD / "kicad-cli.exe"), "pcb", "drc", "--format", "json", "--refill-zones", "--schematic-parity",
                    "--severity-all", "-o", str(rep), str(dst)], capture_output=True)
    d = json.loads(rep.read_text(encoding="utf-8"))
    import collections
    print("\nDRC:", dict(collections.Counter((v["severity"], v["type"]) for v in d.get("violations", []))),
          "unconnected:", len(d.get("unconnected_items", [])), "parity:", len(d.get("schematic_parity", [])))
    run("layout_audit.py", dst)


if __name__ == "__main__":
    work = "build/polish"
    for a in sys.argv[1:]:
        if a.startswith("--work="):
            work = a.split("=", 1)[1]
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], work, "--no-route" not in sys.argv, "--trim" in sys.argv)
