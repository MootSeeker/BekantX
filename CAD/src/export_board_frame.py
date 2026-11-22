"""Export case, lid and keypad of enclosure r3 in the frame of the KiCad board STEP (for renders with the board).

  "%USERPROFILE%/.venvs/bekantx-cad/Scripts/python.exe" CAD/src/export_board_frame.py <out_dir> [--lid-lift=0]

The enclosure script works in its own frame (x across, y from the front, z up from the open side); the board STEP
(kicad-cli pcb export step --user-origin 100x80mm) has the board corner as origin, y pointing up the sheet and the
board top at z = 0. The mapping between the two is a rotation of 180 degrees about x and a shift of (64.5, 5.5, 9.6)
mm; it was found by matching the case against the case model of the README renders (overlap 100 %) and is checked
again on every run. Writes case/lid/keypad as .step and .stl (assembly position; the lid optionally lifted along
the case axis by --lid-lift mm for an exploded view). Nothing in CAD/ is rewritten.
"""
import sys
from pathlib import Path

from build123d import Pos, Rotation, export_step, export_stl

import bekantx_enclosure as E

ROT = Rotation(180, 0, 0)
SHIFT = (64.5, 5.5, 9.6)


def to_board(part):
    return Pos(*SHIFT) * (ROT * part)


def main(out, lid_lift):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    case, lid, keypad = E.build_case(), E.build_lid(), E.build_keypad()
    if lid_lift:
        lid = Pos(0, 0, lid_lift) * lid          # along the case z axis: away from the case opening
    parts = {"case": to_board(case), "lid": to_board(lid), "keypad": to_board(keypad)}
    bb = parts["case"].bounding_box()
    expect = (-5.5, -71.19, -43.4, 134.5, 5.5, 9.6)  # bounding box of the case in the board frame (README model)
    got = (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z)
    if max(abs(a - b) for a, b in zip(got, expect)) > 0.05:
        raise SystemExit(f"case does not land where expected in the board frame: {got}")
    for name, part in parts.items():
        export_step(part, str(out / f"{name}.step"))
        export_stl(part, str(out / f"{name}.stl"), tolerance=0.02, angular_tolerance=0.1)
        b = part.bounding_box()
        print(f"{name}: z {b.min.Z:.1f} .. {b.max.Z:.1f}")


if __name__ == "__main__":
    lift = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--lid-lift=")), "0"))
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], lift)
