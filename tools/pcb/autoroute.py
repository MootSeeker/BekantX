"""Freerouting pipeline for KiCad boards: export DSN -> route -> import SES -> measure.

Run with KiCad's Python (it provides pcbnew):
  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/autoroute.py route <board.kicad_pcb> --profile balanced
  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/autoroute.py tune  <board.kicad_pcb> --via-costs 15 30 60 --ripup-costs 50 100

Never touches the source board: every run works on a copy in <out>/<run>/ and prints metrics.
Use --apply to write the best result back to a new file (<board>_routed.kicad_pcb), never over the source.
"""
import argparse, json, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TOOLS = Path.home() / "tools"
FR_JAR = Path(os.environ.get("FREEROUTING_JAR", TOOLS / "freerouting/freerouting.jar"))
JAVA = Path(os.environ.get("JAVA_EXE", next(iter(sorted((TOOLS / "jdk25").glob("jdk-*/bin/java.exe"))), "java")))
KICAD_BIN = Path(os.environ.get("KICAD_BIN", "C:/Program Files/KiCad/10.0/bin"))
CLI = KICAD_BIN / "kicad-cli.exe"
PROFILES = Path(__file__).parent / "profiles"


def load_profile(name_or_path):
    p = Path(name_or_path)
    if not p.exists():
        p = PROFILES / f"{name_or_path}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def prepare(board_path, work, clear):
    """Copy board+project into work dir, optionally strip unlocked tracks/vias, export DSN."""
    import pcbnew
    work.mkdir(parents=True, exist_ok=True)
    src = Path(board_path)
    dst = work / "in.kicad_pcb"
    shutil.copy(src, dst)
    pro = src.with_suffix(".kicad_pro")
    if pro.exists():
        shutil.copy(pro, work / "in.kicad_pro")
    board = pcbnew.LoadBoard(str(dst))
    if clear:
        for t in list(board.GetTracks()):
            if not t.IsLocked():
                board.Remove(t)
        board.Save(str(dst))
        board = pcbnew.LoadBoard(str(dst))
    if not pcbnew.ExportSpecctraDSN(board, str(work / "in.dsn")):
        raise RuntimeError("DSN export failed")


def run_freerouting(work, settings, timeout):
    args = [str(JAVA), "-Xmx1g", f"-XX:ErrorFile={work / 'jvm_crash.log'}", "-jar", str(FR_JAR), "-de", str(work / "in.dsn"), "-do", str(work / "out.ses"), "-da",
            "--gui.enabled=false", f"--logging.file.location={work}",
            f"--router.result_json={work / 'result.json'}", "--router.max_threads=2"]
    rules = settings.get("_rules")
    if rules:
        args[2] = f"{work / 'in.dsn'}+{Path(rules).resolve()}"
    for k, v in settings.items():
        if k.startswith("_"):
            continue
        if isinstance(v, bool):
            v = str(v).lower()
        elif isinstance(v, float) and v.is_integer():
            v = int(v)  # freerouting rejects "15.0" for integer settings
        if isinstance(v, list):
            v = ",".join(map(str, v))
        args.append(f"--router.{k}={v}")
    log = open(work / "freerouting.out", "w", encoding="utf-8")
    t0 = time.time()
    proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
    return time.time() - t0, (work / "out.ses").exists()


def finish(work):
    """Import SES into the copy, save, and measure."""
    import pcbnew
    board = pcbnew.LoadBoard(str(work / "in.kicad_pcb"))
    ok = pcbnew.ImportSpecctraSES(board, str(work / "out.ses"))
    out = work / "routed.kicad_pcb"
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())  # fills are stale after the import; DRC needs fresh ones
    pcbnew.SaveBoard(str(out), board)
    board = pcbnew.LoadBoard(str(out))
    conn = board.GetConnectivity()
    conn.RecalculateRatsnest()
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    tracks = [t for t in board.GetTracks() if t.GetClass() != "PCB_VIA"]
    length_mm = sum(t.GetLength() for t in tracks) / 1e6
    m = {"ses_imported": bool(ok), "unrouted": conn.GetUnconnectedCount(True), "vias": len(vias),
         "tracks": len(tracks), "length_mm": round(length_mm, 1)}
    def run_drc(pcb, out_json):
        subprocess.run([str(CLI), "pcb", "drc", "--format", "json", "--severity-all", "--refill-zones", "-o", str(out_json), str(pcb)],
                       capture_output=True, timeout=300)
        if not out_json.exists():
            return None
        d = json.loads(out_json.read_text(encoding="utf-8"))
        errs = {}
        for x in d.get("violations", []):
            if x.get("severity") == "error":
                errs[x["type"]] = errs.get(x["type"], 0) + 1
        return errs, sum(1 for x in d.get("violations", []) if x.get("severity") == "warning"), len(d.get("unconnected_items", []))

    base = run_drc(work / "in.kicad_pcb", work / "drc_base.json")
    res = run_drc(out, work / "drc.json")
    if res:
        errs, warns, unconn = res
        base_errs = base[0] if base else {}
        new = {t: n - base_errs.get(t, 0) for t, n in errs.items() if n > base_errs.get(t, 0)}
        m["drc_errors"] = sum(errs.values())
        m["drc_new_errors"] = sum(new.values())
        m["drc_new_by_type"] = new
        m["drc_warnings"] = warns
        m["drc_unconnected"] = unconn
    return m


def score(m):
    """Lower is better. Completeness first, then DRC errors, then vias and length."""
    if not m.get("ses_imported", False) or "drc_new_errors" not in m:
        return 1e12
    return (m["unrouted"] * 1e6 + m.get("drc_unconnected", 0) * 1e6 + m["drc_new_errors"] * 1e4
            + m["vias"] * 20 + m["length_mm"] * 1.0)


def one_run(board, out, name, settings, clear, timeout):
    work = Path(out) / name
    if work.exists():
        shutil.rmtree(work)
    # pcbnew steps run in their own process each (several boards in one pcbnew process misbehave)
    me = [sys.executable, str(Path(__file__).resolve())]
    work.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(me + ["_prepare", str(board), str(work), "1" if clear else "0"], capture_output=True, text=True)
    if not (work / "in.dsn").exists():
        return {"run": name, "seconds": 0, "settings": settings, "score": 1e12, "ses_imported": False,
                "unrouted": -1, "error": "DSN export failed: " + r.stderr[-300:]}
    secs, ok = run_freerouting(work, settings, timeout)
    if not ok and (work / "jvm_crash.log").exists():  # sporadic JVM crash: retry once
        secs, ok = run_freerouting(work, settings, timeout)
    m = {"ses_imported": False, "unrouted": -1}
    if ok:
        subprocess.run(me + ["_finish", str(work)], capture_output=True, text=True)
        if (work / "finish.json").exists():
            m = json.loads((work / "finish.json").read_text(encoding="utf-8"))
    m.update(run=name, seconds=round(secs, 1), settings=settings)
    m["score"] = score(m)
    (work / "metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    return m


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_prepare":
        prepare(sys.argv[2], Path(sys.argv[3]), sys.argv[4] == "1")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "_finish":
        w = Path(sys.argv[2])
        (w / "finish.json").write_text(json.dumps(finish(w)), encoding="utf-8")
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["route", "tune"])
    ap.add_argument("board")
    ap.add_argument("--profile", default="balanced")
    ap.add_argument("--out", default="build/route")
    ap.add_argument("--keep-tracks", action="store_true", help="do not strip existing unlocked tracks first")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per freerouting run")
    ap.add_argument("--via-costs", type=float, nargs="*", default=[15, 30, 60, 100], help="tune: scoring.via_costs grid")
    ap.add_argument("--ripup-costs", type=float, nargs="*", default=[50, 100, 200], help="tune: scoring.start_ripup_costs grid")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) // 3))
    ap.add_argument("--apply", action="store_true", help="write best result to <board>_routed.kicad_pcb")
    a = ap.parse_args()
    clear = not a.keep_tracks

    if a.mode == "route":
        results = [one_run(a.board, a.out, f"route-{a.profile}", load_profile(a.profile), clear, a.timeout)]
    else:
        jobs = []
        base = load_profile(a.profile)
        for vc in a.via_costs:
            for rc in a.ripup_costs:
                st = dict(base)
                st["scoring.via_costs"] = vc
                st["scoring.start_ripup_costs"] = rc
                jobs.append((f"via{vc:g}-ripup{rc:g}", st))
        with ThreadPoolExecutor(a.jobs) as ex:
            futs = [ex.submit(one_run, a.board, a.out, n, st, clear, a.timeout) for n, st in jobs]
            results = [f.result() for f in futs]

    results.sort(key=lambda m: m["score"])
    print(f"{'run':24} {'score':>10} {'unrouted':>8} {'drc_new':>7} {'vias':>5} {'len_mm':>8} {'sec':>6}")
    for m in results:
        print(f"{m['run']:24} {m['score']:10.0f} {m.get('unrouted', -1):8} {m.get('drc_new_errors', -1):7} "
              f"{m.get('vias', -1):5} {m.get('length_mm', 0):8} {m['seconds']:6}")
    best = results[0]
    (Path(a.out) / "best.json").write_text(json.dumps(best, indent=2), encoding="utf-8")
    print("best:", best["run"], "settings:", json.dumps(best["settings"]))
    if a.apply and best["score"] < 1e12:
        dst = Path(a.board).with_name(Path(a.board).stem + "_routed.kicad_pcb")
        shutil.copy(Path(a.out) / best["run"] / "routed.kicad_pcb", dst)
        print("written:", dst)


if __name__ == "__main__":
    sys.exit(main())
