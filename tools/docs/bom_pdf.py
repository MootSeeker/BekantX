"""Bill of materials of the controller board as a formatted PDF (English).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/docs/bom_pdf.py [out.pdf]    # default: Docs/BekantX_Bill_of_Materials.pdf

Exports one line per symbol from the root schematic with kicad-cli, checks it against the footprints of the board
(same references, values and footprints, same DNP flags; aborts on any difference), merges lines with the same MPN
and footprint, and prints the table with headless Microsoft Edge (same engine and approach as makerworld_pdf.py).
Needs KiCad's Python (pcbnew) and Edge. Intermediate files go to build/bom/ (git-ignored).
"""
import csv
import datetime
import html
import re
import subprocess
import sys
import time
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[2]
SCH = ROOT / "Pcb_Controller" / "BekantX.kicad_sch"
PCB = ROOT / "Pcb_Controller" / "BekantX.kicad_pcb"
WORK = ROOT / "build" / "bom"
DEFAULT_OUT = ROOT / "Docs" / "BekantX_Bill_of_Materials.pdf"
CLI = Path("C:/Program Files/KiCad/10.0/bin/kicad-cli.exe")
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")

# Parts outside the PCB, as in the assembly guide (Docs/Montageanleitung.md): qty, part, details, note
EXTRA = [
    ("1", "Enclosure case", "<code>BekantX_Case_r3</code> – printed, PLA (prototype) or PETG (final)", ""),
    ("1", "Enclosure lid", "<code>BekantX_Lid_r3</code> – printed", ""),
    ("1", "Keypad", "<code>BekantX_Keypad_r3</code> – printed, six button caps on one spine", ""),
    ("1", "OLED display module", "EastRising ER-OLED1.29-2, 1.29\" 128 × 64, 16-pin FPC", "mates with J3"),
    ("8", "Screw M2.5 × 6, pan head", "ISO 7045 or ISO 14583; 6 for the board, 2 for the lid; self-tapping into the plastic", ""),
    ("2", "Countersunk wood screw", "hole 4.5 mm, countersink 8.5 mm; length to suit the desktop", ""),
    ("1", "Double-sided tape, thin", "holds the display glass", ""),
    ("1–2", "Cable tie, max. 3.2 mm wide", "strain relief of the desk cable", ""),
    ("1", "Desk cable with 3-pin plug, 2.54 mm pitch", "mates with J10", "unverified"),
]


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True, **kw)


def export_and_check():
    """One CSV line per symbol, cross-checked against the board. Returns the rows."""
    WORK.mkdir(parents=True, exist_ok=True)
    csv_path = WORK / "bom_each.csv"
    run([CLI, "sch", "export", "bom", "--fields", "Reference,Value,Footprint,Manufacturer,MPN,DNP",
         "--labels", "Ref,Value,Footprint,Manufacturer,MPN,DNP", "--ref-range-delimiter", "",
         "-o", csv_path, SCH])
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    sch = {r["Ref"]: r for r in rows}
    if len(sch) != len(rows):
        raise SystemExit("duplicate references in the schematic BOM")
    board = pcbnew.LoadBoard(str(PCB))
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    on_board = {k for k, f in fps.items() if not f.IsExcludedFromBOM()}
    problems = []
    if set(sch) != on_board:
        problems.append(f"references differ: only in schematic {sorted(set(sch) - on_board)}, "
                        f"only on board {sorted(on_board - set(sch))}")
    for k in sorted(set(sch) & on_board):
        f = fps[k]
        if f.GetValue() != sch[k]["Value"]:
            problems.append(f"{k}: value {sch[k]['Value']!r} vs board {f.GetValue()!r}")
        if f.GetFPIDAsString() != sch[k]["Footprint"]:
            problems.append(f"{k}: footprint differs")
        if f.IsDNP() != bool(sch[k]["DNP"]):
            problems.append(f"{k}: DNP flag differs")
    if problems:
        raise SystemExit("schematic and board disagree:\n  " + "\n  ".join(problems))
    excluded = sorted((k for k, f in fps.items() if f.IsExcludedFromBOM()), key=natural)
    return rows, excluded


def natural(ref):
    m = re.match(r"([A-Za-z]+)(\d+)", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def pretty_value(v):
    """'100n' -> '100 nF', '4k7' -> '4.7 kΩ', '22R' -> '22 Ω', '10uF 25V' -> '10 µF · 25 V'; others unchanged."""
    v = v.strip()
    if m := re.fullmatch(r"(\d+)([kM])(\d+)", v):
        return f"{m[1]}.{m[3]} {m[2]}Ω"
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)([kM]|R)", v):
        return f"{m[1]} {'' if m[2] == 'R' else m[2]}Ω"
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)R@(\d+)MHz", v):
        return f"{m[1]} Ω @ {m[2]} MHz"
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*([pnuµ])([FH]?)(?:\s+(\d+)V)?", v):
        unit = {"u": "µ"}.get(m[2], m[2]) + (m[3] or "F")
        return f"{m[1]} {unit}" + (f" · {m[4]} V" if m[4] else "")
    return v


def pretty_footprint(fp):
    name = fp.split(":", 1)[-1]
    if m := re.match(r"[RCL]_(\d{4})_\d{4}Metric$", name):
        return {"0402": "0402", "0805": "0805", "1206": "1206"}.get(m[1], m[1])
    return name.replace("_", " ")


def group(rows):
    """Merge lines with the same MPN + footprint + DNP (parts without an MPN: value + footprint + DNP)."""
    groups = {}
    for r in rows:
        key = (r["MPN"] or "", r["Footprint"], bool(r["DNP"]), "" if r["MPN"] else r["Value"])
        groups.setdefault(key, []).append(r)
    out = []
    for (mpn, fp, dnp, _), g in groups.items():
        refs = sorted((r["Ref"] for r in g), key=natural)
        value = max((r["Value"] for r in g), key=len)       # '100nF 50V' beats '100n'
        out.append(dict(refs=refs, qty=len(refs), value=pretty_value(value), footprint=pretty_footprint(fp),
                        manufacturer=g[0]["Manufacturer"], mpn=mpn, dnp=dnp))
    out.sort(key=lambda x: natural(x["refs"][0]))
    return out


def esc(s):
    return html.escape(s)


def build_html(rows, excluded, groups_):
    n_all, n_dnp = len(rows), sum(1 for r in rows if r["DNP"])
    n_lines = sum(1 for g in groups_ if not g["dnp"])
    n_mpn = len({g["mpn"] for g in groups_ if g["mpn"] and not g["dnp"]})
    no_mpn = [g for g in groups_ if not g["mpn"]]
    rev = run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"]).stdout.strip()
    today = datetime.date.today().isoformat()
    n_tp = sum(1 for k in excluded if k.startswith("TP"))
    n_h = sum(1 for k in excluded if k.startswith("H"))
    other_ex = [k for k in excluded if not k.startswith(("TP", "H"))]

    trs = []
    for i, g in enumerate(groups_, 1):
        note = ""
        if g["dnp"]:
            note = '<span class="badge dnp">DNP</span>'
        elif not g["mpn"]:
            note = '<span class="badge open">MPN open</span>'
        if "J10" in g["refs"]:
            note += ' <span class="badge open">unverified</span>'
        cls = " dnp" if g["dnp"] else ""
        trs.append(
            f'<tr class="{cls.strip()}"><td class="n">{i}</td><td class="q">{g["qty"]}</td>'
            f'<td class="r">{esc(", ".join(g["refs"]))}</td><td>{esc(g["value"])}</td>'
            f'<td class="f">{esc(g["footprint"])}</td><td>{esc(g["manufacturer"])}</td>'
            f'<td class="m">{esc(g["mpn"]) or "–"}</td><td>{note}</td></tr>')

    open_badge = '<span class="badge open">unverified</span>'
    extra = "".join(
        f'<tr><td class="q">{q}</td><td><b>{esc(p)}</b></td><td>{d}</td>'
        f'<td>{open_badge if n == "unverified" else esc(n)}</td></tr>'
        for q, p, d, n in EXTRA)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>BekantX – Bill of Materials</title>
<style>
@page {{ size: A4 landscape; margin: 14mm 14mm 16mm 14mm;
  @bottom-left {{ content: "BekantX · Bill of materials · generated {today}"; font: 8pt "Segoe UI", sans-serif; color: #7a8790; }}
  @bottom-right {{ content: counter(page) " / " counter(pages); font: 8pt "Segoe UI", sans-serif; color: #7a8790; }} }}
:root {{ --accent:#12a4c8; --accent-dark:#0b6f88; --ink:#1c2a33; --muted:#5d6b74; --line:#d9e2e7; --tint:#eef8fb;
  --warn:#b26a00; --warn-bg:#fff6e6; --warn-line:#f0c26e; }}
* {{ box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
html {{ font-size:9.5pt; }}
body {{ margin:0; font-family:"Segoe UI",Arial,sans-serif; color:var(--ink); line-height:1.4; }}
h1,h2 {{ font-family:"Bahnschrift","Segoe UI",sans-serif; font-weight:600; line-height:1.2; margin:0; }}
h1 {{ font-size:24pt; }}
h2 {{ font-size:13pt; margin:6mm 0 2.5mm; padding-bottom:1.5mm; border-bottom:2px solid var(--accent); break-after:avoid; }}
code {{ font-family:"Cascadia Mono",Consolas,monospace; font-size:8pt; background:#f1f4f6; padding:0 1mm; border-radius:1mm; }}
.kicker {{ font:600 9pt "Bahnschrift",sans-serif; letter-spacing:.16em; text-transform:uppercase; color:var(--accent); margin-bottom:1.5mm; }}
.sub {{ color:var(--muted); margin:1.5mm 0 4mm; }}
.facts {{ display:flex; gap:4mm; margin-bottom:2mm; }}
.fact {{ flex:1; border:1px solid var(--line); border-radius:2.5mm; padding:2.5mm 4mm; }}
.fact b {{ display:block; font:600 15pt "Bahnschrift",sans-serif; color:var(--accent-dark); }}
.fact span {{ font-size:8.3pt; color:var(--muted); }}
.warn {{ border:1px solid var(--warn-line); background:var(--warn-bg); border-radius:2mm; padding:2.5mm 4mm; margin:3mm 0; break-inside:avoid; }}
.warn b.t {{ color:var(--warn); }}
.warn ul {{ margin:1mm 0 0; padding-left:5mm; }} .warn li {{ margin-bottom:.6mm; }}
table {{ width:100%; border-collapse:collapse; font-size:8.4pt; }}
th {{ text-align:left; font:600 7.8pt "Bahnschrift",sans-serif; letter-spacing:.05em; text-transform:uppercase; color:var(--muted);
  border-bottom:2px solid var(--ink); padding:1.4mm 2mm; background:#fff; }}
td {{ border-bottom:1px solid var(--line); padding:1.1mm 2mm; vertical-align:top; }}
table.bom {{ table-layout:fixed; }}
table.bom td {{ overflow-wrap:anywhere; }}
tr {{ break-inside:avoid; }}
thead {{ display:table-header-group; }}
td.n {{ width:8mm; color:var(--muted); text-align:right; }}
td.q {{ width:11mm; font-weight:600; text-align:right; }}
td.r {{ width:62mm; font-family:"Cascadia Mono",Consolas,monospace; font-size:7.8pt; }}
td.f {{ font-size:8pt; color:#33444e; }}
td.m {{ font-family:"Cascadia Mono",Consolas,monospace; font-size:7.9pt; }}
tr.dnp td {{ color:#8a979f; background:#f7f9fa; }}
tr:nth-child(even):not(.dnp) td {{ background:#fafcfd; }}
.badge {{ display:inline-block; font:600 7pt "Bahnschrift",sans-serif; letter-spacing:.04em; text-transform:uppercase; border-radius:1mm; padding:.2mm 1.5mm; white-space:nowrap; }}
.badge.dnp {{ background:#e9eef2; color:#4b5d68; }} .badge.open {{ background:var(--warn-bg); color:var(--warn); border:1px solid var(--warn-line); }}
.small {{ font-size:8pt; color:var(--muted); margin-top:2.5mm; }}
.pb {{ break-before:page; }}
</style></head><body>

<div class="kicker">BekantX controller · 6-layer board</div>
<h1>Bill of Materials</h1>
<p class="sub">Controller board <code>Pcb_Controller/BekantX</code> and the parts around it. Generated from the schematic on {today}
  (repository commit <code>{rev}</code>, KiCad 10); schematic and board were compared automatically and agree on references,
  values, footprints and DNP flags.</p>

<div class="facts">
  <div class="fact"><b>{n_all}</b><span>placements in the schematic and on the board</span></div>
  <div class="fact"><b>{n_all - n_dnp}</b><span>to populate ({n_dnp} marked DNP)</span></div>
  <div class="fact"><b>{n_mpn}</b><span>different manufacturer part numbers</span></div>
  <div class="fact"><b>{len(EXTRA)}</b><span>other parts outside the PCB</span></div>
</div>

<div class="warn"><b class="t">Before you order.</b>
  <ul>
    <li><b>No supplier part numbers (e.g. LCSC) are assigned yet</b>; availability and prices have not been checked.</li>
    <li><b>{len(no_mpn)} parts have no MPN:</b> {esc(", ".join(g["refs"][0] + " (" + g["value"] + ")" for g in no_mpn))} – choose parts that match the footprint.</li>
    <li><b>J10 / desk cable:</b> the desk's connector and pinout have not been measured; the 3-pin header is an assumption.</li>
    <li>U2 is listed as <code>ESP32-C3</code> (chip family name) – confirm the exact ordering code with the supplier.</li>
  </ul></div>

<h2>Parts outside the PCB</h2>
<table><thead><tr><th style="text-align:right">Qty</th><th>Part</th><th>Details</th><th>Note</th></tr></thead>
<tbody>{extra}</tbody></table>

<h2 class="pb" style="margin-top:0">Electronics (PCB)</h2>
<table class="bom"><colgroup><col style="width:8mm"><col style="width:10mm"><col style="width:56mm"><col style="width:30mm">
<col style="width:40mm"><col style="width:44mm"><col style="width:50mm"><col></colgroup>
<thead><tr><th style="text-align:right">#</th><th style="text-align:right">Qty</th><th>Reference</th><th>Value</th>
<th>Footprint</th><th>Manufacturer</th><th>MPN</th><th>Note</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table>

<p class="small"><b>Reading the table.</b> Lines with the same MPN and footprint are merged (the schematic spells some values
  differently, e.g. “100n” and “100nF 50V”; the longer text is shown). Greyed lines are marked Do-Not-Populate in the
  schematic and are not part of the quantity to order. Not in this list ({len(excluded)} board items excluded from the BOM):
  {n_h} mounting holes (H1–H{n_h}), {n_tp} test points (bare pads){", and " + esc(", ".join(other_ex)) + " (Tag-Connect TC2030 programming pads, no part)" if other_ex else ""}.
  Resistors and capacitors are listed by value only: voltage ratings, tolerances and dielectrics follow the MPN.</p>
</body></html>"""


def print_pdf(html_path, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    prof = WORK / ".edge-profile"
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={prof}",
           "--no-pdf-header-footer", "--generate-pdf-document-outline", f"--print-to-pdf={out}", html_path.as_uri()]
    run(cmd, timeout=120)
    last, t0 = -1, time.time()          # msedge hands the job to a browser process and may return early
    while time.time() - t0 < 90:
        size = out.stat().st_size if out.exists() else -1
        if size > 0 and size == last:
            break
        last = size
        time.sleep(1.5)
    else:
        raise SystemExit("Edge did not write the PDF")


if __name__ == "__main__":
    for exe in (CLI, EDGE):
        if not exe.exists():
            sys.exit(f"not found: {exe}")
    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUT
    rows, excluded = export_and_check()
    groups_ = group(rows)
    page = WORK / "bom.html"
    page.write_text(build_html(rows, excluded, groups_), encoding="utf-8")
    print(f"{len(rows)} placements -> {len(groups_)} lines, {sum(1 for r in rows if r['DNP'])} DNP, excluded: {len(excluded)}")
    print_pdf(page, out)
    print(f"{out} ({out.stat().st_size / 1e3:.0f} kB)")
