"""Simple envelope 3D models (STEP) for the footprints that have no model in the KiCad library.

  %USERPROFILE%/.venvs/bekantx-cad/Scripts/python.exe CAD/src/make_pcb_models.py

Written to Pcb_Controller/3d/ and attached to the footprints by tools/pcb/bekantx_finish.py.
These are boxes with the outer dimensions of the data sheets (or of the enclosure parameters where the
data sheet was not checked: marked ASSUMPTION); they are good for the enclosure fit, not for looks.
Model coordinates: footprint origin, x right, y up, z = 0 on the board surface, millimetres.
"""
from pathlib import Path

from build123d import Axis, Box, Plane, Pos, RectangleRounded, export_step, extrude

OUT = Path(__file__).resolve().parents[2] / "Pcb_Controller" / "3d"

# name: [(size x, size y, size z, centre x, centre y)], bodies stand on the board
MODELS = {
    # HRO TYPE-C-31-M-12: shell 8.94 x 7.35 x 3.26 (ASSUMPTION, same numbers as the enclosure parameters)
    # the shell is a rounded slot 7.3 long (footprint outline), built separately in main()
    "USB_C_HRO_TYPE-C-31-M-12": None,
    # C&K JS102011SAQN: body 9.0 x 3.6 x 3.5; side actuator not modelled
    "SW_CK_JS102011SAQN": [(9.0, 3.6, 3.5, 0, 0)],
    # SK6812MINI 3.5 x 3.5 x 0.95
    "LED_SK6812MINI": [(3.5, 3.5, 0.95, 0, 0)],
    # Cree CLVBA-FKA 3.2 x 2.8 x 1.9 (data sheet CLD-CT1165)
    "LED_Cree_CLVBA-FKA": [(3.2, 2.8, 1.9, 0, 0)],
    # Johanson 2450AT18A100 3.2 x 1.6 x 1.3
    "Johanson_2450AT18A100": [(3.2, 1.6, 1.3, 0, 0)],
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, boxes in MODELS.items():
        part = None
        if boxes is None:      # USB-C shell: rounded profile in the x/z plane, extruded along y
            prof = Plane.XZ * Pos(0, 3.26 / 2) * RectangleRounded(8.94, 3.26, 1.25)
            part = Pos(0, 3.65, 0) * extrude(prof, 7.3)
            boxes = []
        for sx, sy, sz, cx, cy in boxes:
            b = Pos(cx, cy, sz / 2) * Box(sx, sy, sz)
            part = b if part is None else part + b
        export_step(part, str(OUT / f"{name}.step"))
        print("wrote", OUT / f"{name}.step")


if __name__ == "__main__":
    main()
