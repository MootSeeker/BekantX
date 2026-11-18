"""Fit check of the real board (STEP from KiCad) against the enclosure r3.

  %USERPROFILE%/.venvs/bekantx-cad/Scripts/python.exe CAD/src/check_board_fit.py [CAD/BekantX_PCB.step]

The STEP must be exported with the board corner (x = 0, y = 0 of CAD/board_interface.json) as origin:
  kicad-cli pcb export step --subst-models --user-origin 100x80mm -o CAD/BekantX_PCB.step Pcb_Controller/BekantX.kicad_pcb

KiCad STEP: x right, y up, z up from the back side (board 0 .. 1.6, F.Cu on top).
Enclosure: Y grows with the KiCad y, Z = 0 at the front face; F.Cu looks towards the front (-Z).
So the board is turned 180 degrees about X and moved to its place.
"""
import sys
from pathlib import Path

from build123d import Axis, Pos, import_step

import bekantx_enclosure as enc

P = enc.P


def volume(s) -> float:
    return 0.0 if s is None else float(s.volume)


def main() -> None:
    step = Path(sys.argv[1]) if len(sys.argv) > 1 else enc.CAD_DIR / "BekantX_PCB.step"
    raw = import_step(str(step))
    board = Pos(enc.PCB_X0, enc.PCB_Y0, enc.PCB_BOTTOM_Z) * raw.rotate(Axis.X, 180)
    bb = board.bounding_box()
    print(f"board {step.name}: X {bb.min.X:.2f} .. {bb.max.X:.2f}  Y {bb.min.Y:.2f} .. {bb.max.Y:.2f}  "
          f"Z {bb.min.Z:.2f} .. {bb.max.Z:.2f}")
    print(f"  expected board body: X {enc.PCB_X0:.2f} .. {enc.USB_TAB_X1:.2f}  Y {enc.PCB_Y0:.2f} .. {enc.PCB_Y1:.2f}  "
          f"Z {P.pcb_top_z:.2f} .. {enc.PCB_BOTTOM_Z:.2f}")
    front_h, back_h = P.pcb_top_z - bb.min.Z, bb.max.Z - enc.PCB_BOTTOM_Z
    print(f"  tallest part front side {front_h:.2f} (free {P.pcb_top_z - P.face_t:.2f}), "
          f"back side {back_h:.2f} (free {enc.LEDGE_Z - enc.PCB_BOTTOM_Z:.2f}, limit {P.back_component_h})")
    print(f"  USB shell front at X {bb.max.X:.2f}, planned {enc.USB_FRONT_X:.2f}")

    case, lid, keypad = enc.build_case(), enc.build_lid(), enc.build_keypad()
    env = enc.build_board_envelope()
    worst = 0.0
    solids = board.solids()
    print(f"interference (mm3, must be 0), {len(solids)} solids in the board model:")
    for name, part in (("case", case), ("lid", lid), ("keypad", keypad), ("oled glass", env["oled"])):
        total, hits = 0.0, []
        pb = part.bounding_box()
        for s in solids:
            sb = s.bounding_box()
            if (sb.min.X > pb.max.X or sb.max.X < pb.min.X or sb.min.Y > pb.max.Y or sb.max.Y < pb.min.Y
                    or sb.min.Z > pb.max.Z or sb.max.Z < pb.min.Z):
                continue
            v = volume(part & s)
            if v > 1e-3:
                c = s.center()
                hits.append(f"{v:.2f} at board x {c.X - enc.PCB_X0:.1f} y {c.Y - enc.PCB_Y0:.1f}")
                total += v
        worst = max(worst, total)
        print(f"  {name:10s} {total:8.3f}  {'; '.join(hits[:8])}")
    print("board assembly path (board shifted to -X and lifted towards the lid, against the case):")
    for dx, dz in ((-enc.USB_SLIDE, 8.0), (-enc.USB_SLIDE, 4.0), (-enc.USB_SLIDE, 1.0), (-enc.USB_SLIDE, 0.0),
                   (-enc.USB_SLIDE * 0.5, 0.0)):
        moved = Pos(dx, 0, dz) * board
        v = sum(volume(case & s) for s in moved.solids())
        worst = max(worst, v)
        print(f"  dx {dx:5.2f}  dz {dz:4.1f}   {v:8.3f}")
    print("RESULT:", "PASS" if worst < 1e-2 else f"FAIL (worst {worst:.3f} mm3)")


if __name__ == "__main__":
    main()
