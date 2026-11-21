"""Route a board with one track direction per layer (user rule 2026-11-21: "Leiterbahnen auf einem Layer entweder
senkrecht oder waagrecht, nicht gemischt, um moeglichst viele Plane-Verbindungen zu haben").

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/hv_route.py <board.kicad_pcb> <workdir> --dirs=F.Cu:V,B.Cu:H
        [--against=20] [--via-costs=30] [--no-snap] [--fanout] [--profile=bekantx] [--keep] [--timeout=1800]

Freerouting gets a rules file next to the DSN: snap angle 90 degrees (no 45 degree pieces from the router) and per
layer a preferred direction with a high cost against it (--against, preferred = 1). Unlocked tracks are removed
first unless --keep (locked tracks, e.g. the hand-made power and plane stubs, stay). Layers missing in --dirs are
not routed (inactive). After the import the result is measured: open connections, DRC delta, vias, and per layer
the track length along / against its direction.
Freerouting 2.5 reads such a rules file when it is given in -de as "<dsn>+<rules>" (RulesReader: snap_angle,
autoroute_settings with layer_rule ... preferred_direction ...).
"""
import json, math, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autoroute  # noqa: E402

PY = "C:/Program Files/KiCad/10.0/bin/python.exe"


def rules_text(design, dirs, layers, against, via_costs, snap=True, fanout=False):
    rl = []
    for lay in layers:
        d = dirs.get(lay)
        rl.append(f"""    (layer_rule {lay}
      (active {'on' if d else 'off'})
      (preferred_direction {'horizontal' if d == 'H' else 'vertical'})
      (preferred_direction_trace_costs 1.0)
      (against_preferred_direction_trace_costs {against if d else 1.0})
    )""")
    return f"""(rules PCB {design}
  (snap_angle
    {'ninety_degree' if snap else 'fortyfive_degree'}
  )
  (autoroute_settings
    (fanout {'on' if fanout else 'off'})
    (autoroute on)
    (postroute on)
    (vias on)
    (via_costs {via_costs})
    (plane_via_costs 5)
    (start_ridge_costs 100)
    (start_pass_no 1)
{chr(10).join(rl)}
  )
)
"""


def measure(path, dirs):
    import pcbnew
    sys.path.insert(0, str(HERE))
    from bekantx_layout import unP
    b = pcbnew.LoadBoard(str(path))
    out = {}
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            continue
        name = b.GetLayerName(t.GetLayer())
        canon = pcbnew.BOARD.GetStandardLayerName(t.GetLayer())
        a, c = unP(t.GetStart()), unP(t.GetEnd())
        L = math.dist(a, c)
        dx, dy = abs(c[0] - a[0]), abs(c[1] - a[1])
        kind = "H" if dy < 1e-3 else "V" if dx < 1e-3 else "D"
        o = out.setdefault(canon, {"H": 0.0, "V": 0.0, "D": 0.0, "against_long": 0})
        o[kind] += L
        want = dirs.get(canon)
        if want and kind != want and L > 1.0:
            o["against_long"] += 1
    return {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in out.items()}


def split_zones(text):
    import re
    """(text without teardrop zones and outer GND pours, list of the outer pour blocks)."""
    out, pours, i = [], [], 0
    while True:
        j = text.find("\n\t(zone", i)
        if j < 0:
            out.append(text[i:])
            break
        k = text.find("\n\t)\n", j)
        block = text[j:k + 3]
        out.append(text[i:j])
        if "(teardrop" in block:
            pass
        elif '(name "GND top' in block or '(name "GND bottom' in block:
            pours.append(block)
        elif '(name "GND plane only")' in block:
            pours.append(block)              # a no-track area on an inner layer stops Freerouting from setting vias
        elif '(name "antenna clearance")' in block and "In1.Cu" in block:
            pours.append(block)              # same: only its outer-layer part stays for the router
            out.append(re.sub(r'[(]layers [^)]*[)]', '(layers "F.Cu" "B.Cu")', block, count=1))
        else:
            out.append(block)
        i = k + 3
    return "".join(out), pours


def main(board, work, dirs, against, profile, keep, timeout, via_costs, snap=True, fanout=False):
    work = Path(work).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    me = [PY, str(HERE / "autoroute.py")]
    # the router must not see the outer GND pours (it takes them for planes) nor the teardrop zones
    src = Path(board).resolve()
    text, pours = split_zones(src.read_text(encoding="utf-8"))
    bare = work / "bare.kicad_pcb"
    bare.write_text(text, encoding="utf-8", newline="\n")
    shutil.copy(src.with_suffix(".kicad_pro"), bare.with_suffix(".kicad_pro"))
    (work / "pours.txt").write_text("".join(pours), encoding="utf-8", newline="\n")
    r = subprocess.run(me + ["_prepare", str(bare), str(work), "0" if keep else "1"], capture_output=True, text=True)
    dsn = work / "in.dsn"
    if not dsn.exists():
        sys.exit("DSN export failed: " + r.stderr[-500:])
    design = dsn.stem                  # Freerouting compares the rules header with the DSN file name
    import re
    layers = re.findall(r"^\s*\(layer (\S+)\s*$", dsn.read_text(encoding="utf-8", errors="replace"), re.M)
    rules = work / "in.rules"
    rules.write_text(rules_text(design, dirs, layers, against, via_costs, snap, fanout), encoding="utf-8")
    settings = autoroute.load_profile(profile)
    args = [str(autoroute.JAVA), "-Xmx2g", f"-XX:ErrorFile={work / 'jvm_crash.log'}", "-jar", str(autoroute.FR_JAR),
            "-de", f"{dsn}+{rules}", "-do", str(work / "out.ses"), "-da", "--gui.enabled=false",
            f"--logging.file.location={work}", f"--router.result_json={work / 'result.json'}", "--router.max_threads=2"]
    for k, v in settings.items():
        if k.startswith("_") or k == "scoring.via_costs" or (fanout and k == "fanout.enabled"):
            continue
        if isinstance(v, bool):
            v = str(v).lower()
        if isinstance(v, list):
            v = ",".join(map(str, v))
        args.append(f"--router.{k}={v}")
    args.append(f"--router.scoring.via_costs={via_costs}")
    if fanout:
        args.append("--router.fanout.enabled=true")
    with open(work / "freerouting.out", "w", encoding="utf-8") as log:
        p = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
    if not (work / "out.ses").exists():
        sys.exit("no SES; see " + str(work / "freerouting.out"))
    subprocess.run(me + ["_finish", str(work)], capture_output=True, text=True)
    # outer GND pours back (filled later by gnd_pour.py)
    rt = (work / "routed.kicad_pcb").read_text(encoding="utf-8")
    # drop the router copy of the antenna area (outer layers only); the original comes back with the pours
    j = rt.find('(name "antenna clearance")')
    if j >= 0:
        z0 = rt.rfind("\n\t(zone", 0, j)
        z1 = rt.find("\n\t)\n", j) + 3
        rt = rt[:z0] + rt[z1:]
    i = rt.rindex(")")
    (work / "routed_pours.kicad_pcb").write_text(rt[:i].rstrip("\n") + "\n" + "".join(pours) + rt[i:], encoding="utf-8", newline="\n")
    m = json.loads((work / "finish.json").read_text(encoding="utf-8")) if (work / "finish.json").exists() else {}
    r = subprocess.run([PY, str(HERE / "hv_route.py"), "--measure", str(work / "routed.kicad_pcb"), json.dumps(dirs)],
                       capture_output=True, text=True)
    m["by_layer"] = json.loads([l for l in r.stdout.splitlines() if l.startswith("{")][-1]) if "{" in r.stdout else r.stderr[-300:]
    (work / "hv_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(json.dumps(m, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "--measure":
        print(json.dumps(measure(sys.argv[2], json.loads(sys.argv[3]))))
        sys.exit()
    opt = lambda k, d: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{k}=")), d)
    dirs = dict(x.split(":") for x in opt("dirs", "F.Cu:V,B.Cu:H").split(","))
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], dirs, float(opt("against", "20")), opt("profile", "bekantx"), "--keep" in sys.argv,
         int(opt("timeout", "1800")), int(opt("via-costs", "30")), "--no-snap" not in sys.argv, "--fanout" in sys.argv)
