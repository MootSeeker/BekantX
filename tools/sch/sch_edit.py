"""Text-level editing helpers for KiCad 10 schematic files (.kicad_sch).

The file is never re-serialised: blocks are located by balanced-parenthesis
scanning and new blocks are inserted as text, so untouched parts of the file
keep their exact formatting (small diffs). After every scripted edit, prove the
file still loads: kicad-cli sch erc / export netlist on the ROOT sheet.

Coordinates are millimetres on the sheet (y grows downwards).
"""
from __future__ import annotations

import math
import re
import uuid as _uuid

NUM = r"-?\d+(?:\.\d+)?"


def new_uuid() -> str:
    return str(_uuid.uuid4())


def fmt(v: float) -> str:
    s = f"{round(v, 4):.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class Sheet:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            raw = f.read().decode("utf-8")
        self.nl = "\r\n" if "\r\n" in raw else "\n"
        self.text = raw.replace("\r\n", "\n")

    def save(self) -> None:
        check_balanced(self.text)
        for s, e, _ in self.blocks(("symbol",)):
            t = self.text[s:e]
            if not (t.count('(property "Reference"') == 1 and t.count("(lib_id") == 1 and t.count("(instances") == 1):
                raise ValueError(f"malformed symbol block at offset {s} in {self.path}")
        with open(self.path, "wb") as f:
            f.write(self.text.replace("\n", self.nl).encode("utf-8"))

    # ---- structure ------------------------------------------------------
    def blocks(self, kinds=None):
        """Yield (start, end, kind) of the root element's direct children."""
        out = []
        for s, e in child_spans(self.text, self.text.index("(")):
            kind = re.match(r"\(([^\s()]+)", self.text[s:e]).group(1)
            if kinds is None or kind in kinds:
                out.append((s, e, kind))
        return out

    def block_text(self, span) -> str:
        return self.text[span[0]:span[1]]

    def remove_spans(self, spans) -> None:
        for s, e, *_ in sorted(spans, reverse=True):
            # also drop the line's leading indentation and trailing newline
            ls = self.text.rfind("\n", 0, s) + 1
            le = e + 1 if self.text[e:e + 1] == "\n" else e
            self.text = self.text[:ls] + self.text[le:]

    def append(self, block: str) -> None:
        """Insert a top-level block (tab-indented text) before sheet_instances / end."""
        m = re.search(r"\n\t\((sheet_instances|embedded_fonts)", self.text)
        pos = m.start() + 1 if m else self.text.rstrip().rfind(")")
        self.text = self.text[:pos] + block.rstrip("\n") + "\n" + self.text[pos:]

    # ---- lib symbols ----------------------------------------------------
    def lib_span(self):
        for s, e, kind in self.blocks(("lib_symbols",)):
            return s, e
        raise ValueError("no lib_symbols")

    def lib_defs(self) -> dict:
        s, e = self.lib_span()
        out = {}
        for cs, ce in child_spans(self.text, s):
            name = re.match(r'\(symbol "([^"]+)"', self.text[cs:ce])
            if name:
                out[name.group(1)] = (cs, ce)
        return out

    def lib_def_text(self, lib_id: str) -> str:
        s, e = self.lib_defs()[lib_id]
        return self.text[s:e]

    def add_lib_def(self, lib_id: str, def_text: str) -> None:
        if lib_id in self.lib_defs():
            return
        s, e = self.lib_span()
        if self.text[s:e].strip() == "(lib_symbols)":
            self.text = self.text[:e - 1] + "\n\t\t" + def_text + "\n\t)" + self.text[e:]
        else:
            ins = self.text.rfind("\n", s, e) + 1  # start of the closing line
            self.text = self.text[:ins] + "\t\t" + def_text + "\n" + self.text[ins:]

    def remove_lib_def(self, lib_id: str) -> None:
        d = self.lib_defs()
        if lib_id in d:
            self.remove_spans([d[lib_id]])

    # ---- queries --------------------------------------------------------
    def instance_path(self) -> tuple[str, str]:
        m = re.search(r'\(project "([^"]+)"\s*\(path "([^"]+)"', self.text)
        return m.group(1), m.group(2)

    def symbols(self):
        """List of dicts for every placed symbol."""
        out = []
        for s, e, _ in self.blocks(("symbol",)):
            t = self.text[s:e]
            at = re.search(rf"\(at ({NUM}) ({NUM}) ({NUM})\)", t)
            mir = re.search(r"\(mirror (\w+)\)", t)
            out.append({
                "span": (s, e),
                "lib_id": re.search(r'\(lib_id "([^"]+)"', t).group(1),
                "ref": re.search(r'\(property "Reference" "([^"]*)"', t).group(1),
                "value": re.search(r'\(property "Value" "([^"]*)"', t).group(1),
                "at": (float(at.group(1)), float(at.group(2))),
                "rot": int(float(at.group(3))),
                "mirror": mir.group(1) if mir else None,
                "unit": int(re.search(r"\(unit (\d+)\)", t).group(1)),
            })
        return out

    def symbol(self, ref: str):
        hits = [x for x in self.symbols() if x["ref"] == ref]
        if len(hits) != 1:
            raise KeyError(f"{ref}: {len(hits)} matches in {self.path}")
        return hits[0]

    def pin_pos(self, ref: str, number: str) -> tuple[float, float]:
        sym = self.symbol(ref)
        pins = lib_pins(self.lib_def_text(sym["lib_id"]))
        x, y = pins[number]
        return transform(x, y, sym["at"], sym["rot"], sym["mirror"])

    def used_refs(self) -> set:
        return set(re.findall(r'\(reference "([^"]+)"\)', self.text))

    # ---- edits ----------------------------------------------------------
    def replace_in_span(self, span, old: str, new: str, count: int = 1) -> None:
        s, e = span[0], span[1]
        t = self.text[s:e]
        if t.count(old) < 1:
            raise ValueError(f"{old!r} not found in block")
        self.text = self.text[:s] + t.replace(old, new, count) + self.text[e:]

    def set_ref(self, ref: str, new_ref: str) -> None:
        sp = self.symbol(ref)["span"]
        t = self.text[sp[0]:sp[1]]
        t = t.replace(f'(property "Reference" "{ref}"', f'(property "Reference" "{new_ref}"')
        t = t.replace(f'(reference "{ref}")', f'(reference "{new_ref}")')
        self.text = self.text[:sp[0]] + t + self.text[sp[1]:]

    def set_property(self, ref: str, name: str, value: str) -> None:
        """Set an existing property or add a hidden one."""
        sym = self.symbol(ref)
        s, e = sym["span"]
        t = self.text[s:e]
        pat = re.compile(rf'\(property "{re.escape(name)}" "[^"]*"')
        if pat.search(t):
            t = pat.sub(f'(property "{name}" "{value}"', t, count=1)
        else:
            x, y = sym["at"]
            prop = (f'\t\t(property "{name}" "{value}"\n\t\t\t(at {fmt(x)} {fmt(y)} 0)\n'
                    "\t\t\t(hide yes)\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n"
                    "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n")
            i = t.index("\t\t(pin ") if "\t\t(pin " in t else t.index("\t\t(instances")
            t = t[:i] + prop + t[i:]
        self.text = self.text[:s] + t + self.text[e:]

    def move_field(self, ref: str, name: str, at, angle: int | None = None, hide: bool | None = None,
                   justify: str | None = None) -> None:
        """Reposition a property text. For symbols rotated 90/270 use angle=90 to keep the text horizontal."""
        s, e = self.symbol(ref)["span"]
        t = self.text[s:e]
        m = re.search(rf'(\(property "{re.escape(name)}" "[^"]*"\s*\(at ){NUM} {NUM} ({NUM})\)', t)
        a = m.group(2) if angle is None else str(angle)
        new = f"{m.group(1)}{fmt(at[0])} {fmt(at[1])} {a})"
        if hide and "(hide yes)" not in t[m.end():m.end() + 30]:
            new += "\n\t\t\t(hide yes)"
        t = t[:m.start()] + new + t[m.end():]
        if justify:
            ps = m.start()
            assert t.startswith("(property", ps)
            pe = child_end(t, ps)
            blk = t[ps:pe]
            if "(justify" in blk:
                blk = re.sub(r"\(justify [^)]*\)", f"(justify {justify})", blk)
            else:
                blk = blk.replace("\t\t\t\t)\n\t\t\t)", f"\t\t\t\t)\n\t\t\t\t(justify {justify})\n\t\t\t)", 1)
            t = t[:ps] + blk + t[pe:]
        self.text = self.text[:s] + t + self.text[e:]

    def clone(self, spans, dx: float, dy: float, ref_map: dict, text_map: dict | None = None):
        """Copy top-level blocks shifted by (dx, dy) with fresh uuids.

        ref_map: old reference -> new reference (must cover every symbol copied).
        text_map: label/text name replacements ("old" -> "new", applied to quoted strings).
        """
        out = []
        for sp in spans:
            t = self.text[sp[0]:sp[1]]
            t = shift(t, dx, dy)
            t = re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{new_uuid()}")', t)
            m = re.search(r'\(property "Reference" "([^"]*)"', t)
            if m:
                old = m.group(1)
                new = ref_map[old] if old in ref_map else self.next_hidden_ref(old)
                t = t.replace(f'(property "Reference" "{old}"', f'(property "Reference" "{new}"')
                t = t.replace(f'(reference "{old}")', f'(reference "{new}")')
            for old, new in (text_map or {}).items():
                t = t.replace(f'"{old}"', f'"{new}"')
            out.append("\t" + t)
        for t in out:
            self.append(t)

    def in_box(self, box, kinds=None):
        """Blocks whose every coordinate lies inside box=(x0, y0, x1, y1)."""
        x0, y0, x1, y1 = box
        hits = []
        for s, e, kind in self.blocks(kinds):
            if kind in ("lib_symbols", "sheet_instances", "title_block", "version", "generator",
                        "generator_version", "uuid", "paper", "embedded_fonts"):
                continue
            pts = coords(self.text[s:e], kind)
            if pts and all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in pts):
                hits.append((s, e, kind))
        return hits

    # ---- generators -----------------------------------------------------
    def add_wire(self, *pts) -> None:
        for a, b in zip(pts, pts[1:]):
            self.append(
                f"\t(wire\n\t\t(pts\n\t\t\t(xy {fmt(a[0])} {fmt(a[1])}) (xy {fmt(b[0])} {fmt(b[1])})\n\t\t)\n"
                f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid \"{new_uuid()}\")\n\t)")

    def add_junction(self, p) -> None:
        self.append(f"\t(junction\n\t\t(at {fmt(p[0])} {fmt(p[1])})\n\t\t(diameter 0)\n"
                    f"\t\t(color 0 0 0 0)\n\t\t(uuid \"{new_uuid()}\")\n\t)")

    def add_no_connect(self, p) -> None:
        self.append(f"\t(no_connect\n\t\t(at {fmt(p[0])} {fmt(p[1])})\n\t\t(uuid \"{new_uuid()}\")\n\t)")

    def add_text(self, s: str, p, size: float = 1.27) -> None:
        s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        self.append(f"\t(text \"{s}\"\n\t\t(exclude_from_sim no)\n\t\t(at {fmt(p[0])} {fmt(p[1])} 0)\n"
                    f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {fmt(size)} {fmt(size)})\n\t\t\t)\n"
                    f"\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid \"{new_uuid()}\")\n\t)")

    def add_rect(self, box) -> None:
        self.append(f"\t(rectangle\n\t\t(start {fmt(box[0])} {fmt(box[1])})\n\t\t(end {fmt(box[2])} {fmt(box[3])})\n"
                    "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(fill\n\t\t\t(type none)\n\t\t)\n"
                    f"\t\t(uuid \"{new_uuid()}\")\n\t)")

    def add_global_label(self, name: str, p, rot: int = 0, shape: str = "bidirectional") -> None:
        just = {0: "left", 180: "right", 90: "left", 270: "right"}[rot]
        self.append(
            f"\t(global_label \"{name}\"\n\t\t(shape {shape})\n\t\t(at {fmt(p[0])} {fmt(p[1])} {rot})\n"
            f"\t\t(fields_autoplaced yes)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {just})\n\t\t)\n\t\t(uuid \"{new_uuid()}\")\n"
            f"\t\t(property \"Intersheetrefs\" \"${{INTERSHEET_REFS}}\"\n\t\t\t(at {fmt(p[0])} {fmt(p[1])} 0)\n"
            "\t\t\t(hide yes)\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify {just})\n\t\t\t)\n\t\t)\n\t)")

    def add_label(self, name: str, p, rot: int = 0) -> None:
        just = "left bottom" if rot in (0, 90) else "right bottom"
        self.append(f"\t(label \"{name}\"\n\t\t(at {fmt(p[0])} {fmt(p[1])} {rot})\n\t\t(effects\n\t\t\t(font\n"
                    f"\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {just})\n\t\t)\n\t\t(uuid \"{new_uuid()}\")\n\t)")

    def add_symbol(self, lib_id: str, ref: str, value: str, p, rot: int = 0, footprint: str = "",
                   props: dict | None = None, dnp: bool = False, ref_at=None, value_at=None,
                   hide_value: bool = False) -> None:
        """Place a symbol whose definition is already in lib_symbols."""
        d = self.lib_def_text(lib_id)
        pins = lib_pins(d)
        power = "(power" in d.split("(property", 1)[0]
        project, path = self.instance_path()
        x, y = p
        ref_at = ref_at or (x + 2.54, y - 2.54)
        value_at = value_at or (x + 2.54, y + 2.54)

        def prop(name, val, at, hide=False, just="left"):
            return (f"\t\t(property \"{name}\" \"{val}\"\n\t\t\t(at {fmt(at[0])} {fmt(at[1])} 0)\n"
                    + ("\t\t\t(hide yes)\n" if hide else "")
                    + "\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n\t\t\t\t(font\n"
                      "\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
                    + (f"\t\t\t\t(justify {just})\n" if just and not hide else "")
                    + "\t\t\t)\n\t\t)\n")

        desc = re.search(r'\(property "Description" "((?:[^"\\]|\\.)*)"', d)
        ds = re.search(r'\(property "Datasheet" "((?:[^"\\]|\\.)*)"', d)
        t = (f"\t(symbol\n\t\t(lib_id \"{lib_id}\")\n\t\t(at {fmt(x)} {fmt(y)} {rot})\n\t\t(unit 1)\n"
             "\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n"
             f"\t\t(in_bom {'no' if power else 'yes'})\n\t\t(on_board yes)\n\t\t(in_pos_files yes)\n"
             f"\t\t(dnp {'yes' if dnp else 'no'})\n\t\t(uuid \"{new_uuid()}\")\n")
        t += prop("Reference", ref, ref_at, hide=power)
        t += prop("Value", value, value_at if not power else (x, y + (3.81 if "GND" in value else -3.81)),
                  hide=hide_value, just="" if power else "left")
        t += prop("Footprint", footprint, (x, y), hide=True)
        t += prop("Datasheet", ds.group(1) if ds else "", (x, y), hide=True)
        t += prop("Description", desc.group(1) if desc else "", (x, y), hide=True)
        for k, v in (props or {}).items():
            t += prop(k, v, (x, y), hide=True)
        for n in pins:
            t += f"\t\t(pin \"{n}\"\n\t\t\t(uuid \"{new_uuid()}\")\n\t\t)\n"
        t += (f"\t\t(instances\n\t\t\t(project \"{project}\"\n\t\t\t\t(path \"{path}\"\n"
              f"\t\t\t\t\t(reference \"{ref}\")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)")
        self.append(t)

    _pwr = 200  # set above the highest #PWR/#FLG number of the project before a run

    def next_hidden_ref(self, like: str = "#PWR") -> str:
        """Fresh '#PWRnnnn' / '#FLGnnnn' reference (unique within one script run)."""
        prefix = re.match(r"#[A-Z]+", like).group(0)
        used = self.used_refs()
        while f"{prefix}{Sheet._pwr:04d}" in used:
            Sheet._pwr += 1
        ref = f"{prefix}{Sheet._pwr:04d}"
        Sheet._pwr += 1
        return ref

    def add_power(self, name: str, p, rot: int = 0, lib: str | None = None) -> None:
        """Place a power symbol whose net name is `name`.

        lib: lib_id to draw it with (default power:<name>); KiCad takes the net
        name from the Value field, so e.g. power:VDD can carry the net "VIN".
        """
        lib = lib or f"power:{name}"
        self.add_symbol(lib, self.next_hidden_ref("#FLG" if "PWR_FLAG" in lib else "#PWR"), name, p, rot)

    def set_lib_id(self, ref: str, lib_id: str) -> None:
        """Swap the library symbol of a placed symbol (pin numbers/positions must match)."""
        sym = self.symbol(ref)
        assert lib_id in self.lib_defs(), lib_id
        self.replace_in_span(sym["span"], f'(lib_id "{sym["lib_id"]}")', f'(lib_id "{lib_id}")')

    def remove_refs(self, *refs) -> None:
        self.remove_spans([self.symbol(r)["span"] for r in refs])

    def find(self, kind: str, at=None, name: str | None = None):
        """Blocks of a kind touching point `at` (any coordinate) and/or with the given label/text name."""
        hits = []
        for sp in self.blocks((kind,)):
            t = self.text[sp[0]:sp[1]]
            if name is not None and not t.startswith(f'({kind} "{name}"'):
                continue
            if at is not None and (round(at[0], 2), round(at[1], 2)) not in [
                    (round(x, 2), round(y, 2)) for x, y in coords(t, kind)]:
                continue
            hits.append(sp)
        return hits


# ---- free functions -------------------------------------------------------
KICAD_SYMBOLS = r"C:/Program Files/KiCad/10.0/share/kicad/symbols"


def kicad_lib_def(lib: str, name: str, symbols_dir: str = KICAD_SYMBOLS) -> str:
    """Definition of <lib>:<name> from the KiCad standard library, renamed for lib_symbols."""
    with open(f"{symbols_dir}/{lib}.kicad_sym", encoding="utf-8") as f:
        t = f.read()
    for s, e in child_spans(t, t.index("(")):
        if t[s:e].startswith(f'(symbol "{name}"'):
            d = t[s:e]
            if "(extends " in d[:300]:
                raise ValueError(f"{lib}:{name} is a derived symbol; flatten it by hand")
            d = d.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
            # library files are indented one level less than lib_symbols entries
            return d.replace("\n\t", "\n\t\t")
    raise KeyError(f"{lib}:{name}")
def child_spans(text: str, start: int):
    """Spans of the direct child lists of the list opening at text[start]."""
    assert text[start] == "("
    depth, i, n, spans, cs = 0, start, len(text), [], None
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            depth += 1
            if depth == 2:
                cs = i
        elif c == ")":
            depth -= 1
            if depth == 1:
                spans.append((cs, i + 1))
            elif depth == 0:
                return spans
        i += 1
    raise ValueError("unbalanced")


def child_end(text: str, start: int) -> int:
    """Index just past the list that opens at text[start]."""
    depth, i = 0, start
    while True:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1


def check_balanced(text: str) -> None:
    spans = child_spans(text, text.index("("))
    if not spans:
        raise ValueError("empty schematic")


def coords(block: str, kind: str):
    if kind in ("wire", "bus", "polyline"):
        return [(float(a), float(b)) for a, b in re.findall(rf"\(xy ({NUM}) ({NUM})\)", block)]
    if kind == "rectangle":
        return [(float(a), float(b)) for a, b in re.findall(rf"\((?:start|end) ({NUM}) ({NUM})\)", block)]
    m = re.search(rf"\(at ({NUM}) ({NUM})", block)  # first (at) = anchor of symbol/label/junction/text
    return [(float(m.group(1)), float(m.group(2)))] if m else []


def shift(block: str, dx: float, dy: float) -> str:
    def at(m):
        return f"({m.group(1)} {fmt(float(m.group(2)) + dx)} {fmt(float(m.group(3)) + dy)}"
    return re.sub(rf"\((at|xy|start|end) ({NUM}) ({NUM})", at, block)


def lib_pins(def_text: str) -> dict:
    """pin number -> (x, y) connection point in library coordinates (y up)."""
    out = {}
    for m in re.finditer(rf"\(pin \w+ \w+\s*\(at ({NUM}) ({NUM}) {NUM}\)", def_text):
        tail = def_text[m.end():]
        num = re.search(r'\(number "([^"]+)"', tail).group(1)
        out[num] = (float(m.group(1)), float(m.group(2)))
    return out


def transform(x: float, y: float, at, rot: int = 0, mirror: str | None = None):
    """Library pin coordinate -> sheet coordinate for a placed symbol."""
    if mirror == "y":
        x = -x
    elif mirror == "x":
        y = -y
    r = math.radians(rot)
    xr = x * math.cos(r) - y * math.sin(r)
    yr = x * math.sin(r) + y * math.cos(r)
    return (round(at[0] + xr, 4), round(at[1] - yr, 4))
