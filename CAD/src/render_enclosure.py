"""Renderings of the enclosure alone (case, lid, keypad) for blog posts, offscreen with VTK.

  "%USERPROFILE%/.venvs/bekantx-cad/Scripts/python.exe" CAD/src/render_enclosure.py <out_dir>

Reads the parts in the board frame written by export_board_frame.py (build/blog/asm, build/blog/expl with the lid
lifted). kicad-cli cannot render the enclosure without a board (it frames the camera on the board), so these views
come from VTK; the board views and the board-in-case views come from tools/pcb/blog_renders.py.
Transparent PNG, 2400 x 1350. Board frame: x along the case, y up the sheet, +z = front (keypad, display).
"""
import sys
from pathlib import Path

import vtk

ROOT = Path(__file__).resolve().parents[2]
BLOG = ROOT / "build" / "blog"
W, H = 2400, 1350
GREY = (0.80, 0.80, 0.82)
KEYS = (0.55, 0.57, 0.60)

# name: ([(part, colour)], camera direction (from the focal point towards the camera), view up)
VIEWS = {
    "enclosure_front": ([("asm/case", GREY), ("asm/lid", GREY), ("asm/keypad", KEYS)], (-0.35, 0.55, 1.0), (0, -1, 0)),
    "enclosure_back_open": ([("asm/case", GREY), ("asm/keypad", KEYS)], (-0.35, 0.45, -1.0), (0, -1, 0)),
    "enclosure_exploded": ([("expl/case", GREY), ("expl/lid", GREY), ("expl/keypad", KEYS)], (0.9, -0.9, -0.55), (0, 0, -1)),
}


def render(parts, direction, up, png):
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    ren.SetBackgroundAlpha(0.0)
    for name, col in parts:
        r = vtk.vtkSTLReader()
        r.SetFileName(str(BLOG / f"{name}.stl"))
        n = vtk.vtkPolyDataNormals()
        n.SetInputConnection(r.GetOutputPort())
        n.SetFeatureAngle(30)
        m = vtk.vtkPolyDataMapper()
        m.SetInputConnection(n.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(m)
        a.GetProperty().SetColor(*col)
        a.GetProperty().SetSpecular(0.25)
        a.GetProperty().SetSpecularPower(30)
        ren.AddActor(a)
    kit = vtk.vtkLightKit()
    kit.AddLightsToRenderer(ren)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetAlphaBitPlanes(1)
    win.SetMultiSamples(8)
    win.AddRenderer(ren)
    win.SetSize(W, H)
    ren.ResetCamera()
    cam = ren.GetActiveCamera()
    fp = cam.GetFocalPoint()
    d = cam.GetDistance()
    L = sum(v * v for v in direction) ** 0.5
    cam.SetPosition(*(fp[i] + direction[i] / L * d for i in range(3)))
    cam.SetViewUp(*up)
    ren.ResetCamera()
    cam.Zoom(1.25)
    win.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(win)
    grab.SetInputBufferTypeToRGBA()
    grab.ReadFrontBufferOff()
    grab.Update()
    w = vtk.vtkPNGWriter()
    w.SetFileName(str(png))
    w.SetInputConnection(grab.GetOutputPort())
    w.Write()


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, (parts, direction, up) in VIEWS.items():
        render(parts, direction, up, out / f"{name}.png")
        print(name, "ok")


if __name__ == "__main__":
    main(sys.argv[1])
