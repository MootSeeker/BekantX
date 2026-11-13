"""BekantX enclosure, revision 2: one PCB behind the front panel.

Parametric rebuild of the original enclosure style (CAD/BekantX_Case.stl,
CAD/BekantX_Lid.stl): a front block with buttons and display, and an arm
angled by 55 degrees that is screwed under the table top. The front block is
deeper and slightly higher than the original so that the single PCB fits.

The board layout does not exist yet, so this script is the source of the
board outline, mounting holes and UI positions. It writes them to
CAD/board_interface.json for the PCB layout.

Coordinate system (millimetres), same as the original case STL:
    X  along the width, 0 in the middle
    Y  depth, 0 at the free front edge, increasing towards the arm
    Z  0 at the outside of the front face, increasing into the case
Arm frame: s along the arm from the hinge line (Y = block_depth, Z = 0),
t perpendicular to the arm, 0 at the surface that touches the table top.

Run:  %USERPROFILE%/.venvs/bekantx-cad/Scripts/python.exe CAD/src/bekantx_enclosure.py
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from build123d import (
    Align,
    Box,
    Cone,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    export_step,
    export_stl,
    extrude,
)

REVISION = "r2"
CAD_DIR = Path(__file__).resolve().parent.parent
BIG = 300.0  # "infinite" extent for masks


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Params:
    # --- outer shape (original: 140 x 31.5 x 20 block, 55 deg arm, 56.8 long, 11 thick)
    width: float = 140.0
    block_depth: float = 44.0          # original 31.5; deeper for the single PCB
    block_height: float = 23.0         # original 20; higher for C40 (10.2 mm) on the back side
    arm_angle_deg: float = 55.0
    arm_length: float = 57.0
    arm_thickness: float = 11.0
    arm_tab_width: float = 80.0        # narrow end of the arm
    arm_taper_start: float = 37.0      # s where the outer contour starts to narrow
    arm_taper_end: float = 47.0        # s where the outer contour reaches arm_tab_width
    front_chamfer_y: float = 3.0       # chamfer between face and front wall
    front_chamfer_z: float = 5.0
    side_chamfer_x: float = 2.0        # chamfer between face and side walls
    side_chamfer_z: float = 3.0
    plan_chamfer: float = 3.0          # front corners seen from the face
    top_chamfer: float = 0.5           # front wall, lid side

    # --- walls
    face_t: float = 2.0
    wall: float = 5.0                  # front and side walls of the block (rim + ledge)
    rim: float = 2.6                   # outer rim around the lid
    arm_floor_t: float = 2.0           # arm wall on the table side
    arm_ledge: float = 2.0             # lid ledge inside the arm rim
    lid_t: float = 2.0
    lid_clearance: float = 0.25        # lid to rim, per side

    # --- lid contour in the arm
    lid_taper_offset: float = 3.0      # lid starts to narrow this far after the kink
    lid_taper_length: float = 12.0

    # --- PCB (ASSUMPTION: 1.6 mm FR4, no layout yet)
    pcb_width: float = 129.0
    pcb_depth: float = 38.0
    pcb_t: float = 1.6
    pcb_y0: float = 5.5                # front edge of the board
    pcb_top_z: float = 8.0             # component side that faces the front panel
    pcb_edge_clearance: float = 0.5
    boss_d: float = 5.5
    screw_pilot_d: float = 1.9         # self-tapping M2.2, as in the original posts
    screw_clear_d: float = 2.6
    screw_head_d: float = 4.4
    pilot_floor: float = 1.0           # material left under a pilot hole in the face
    pcb_boss_xy: tuple = ((-60.0, 9.0), (0.0, 9.0), (60.0, 9.0),
                          (-52.0, 38.5), (0.0, 38.5), (52.0, 38.5))

    # --- UI row
    ui_y: float = 22.0                 # centre line of buttons and display
    button_x: tuple = (-56.0, -41.0, 11.0, 26.0, 41.0, 56.0)   # original pattern
    button_hole_d: float = 10.6        # original
    cap_d: float = 10.0
    cap_protrusion: float = 1.5
    cap_flange_d: float = 12.6
    cap_flange_t: float = 1.6
    cap_top_chamfer: float = 0.4
    switch_height: float = 4.3         # Omron B3F-1000, plunger top above PCB (not checked against datasheet)
    switch_body: float = 6.2
    switch_body_h: float = 3.5
    cap_preload_gap: float = 0.1

    # --- OLED ER-OLED1.29-2 (Docs/ER-OLED1.29-2_Datasheet.pdf, outline drawing)
    oled_glass_w: float = 35.8
    oled_glass_h: float = 17.1
    oled_glass_t: float = 1.2
    oled_visual_w: float = 30.42
    oled_visual_h: float = 15.7
    oled_visual_x0: float = 1.0        # visual area from the glass edge opposite the FPC
    oled_glass_cx: float = -15.7       # glass centre in X; FPC leaves towards +X
    oled_pocket_clearance: float = 0.2
    oled_bezel_t: float = 0.8          # face left in front of the glass

    # --- status LED windows (thinned face) with light baffles
    led_xy: tuple = ((33.5, 14.5), (33.5, 29.5))   # D5 (STM32), D1 (ESP)
    led_window_d: float = 3.5
    led_skin_t: float = 0.6
    led_tube_od: float = 6.5
    led_tube_id: float = 4.5
    led_tube_end_z: float = 5.5

    # --- USB-C in the +X side wall, connector on the back side of the board
    #     HRO TYPE-C-31-M-12: 8.94 x 7.35 x 3.26 (not checked against datasheet)
    usb_y: float = 31.5
    usb_shell_w: float = 8.94
    usb_shell_h: float = 3.26
    usb_shell_len: float = 7.35
    usb_overhang: float = 1.5          # shell front beyond the board edge
    usb_shell_clearance: float = 0.25
    usb_plug_w: float = 12.6           # recess for the plug overmould
    usb_plug_h: float = 7.0
    usb_web: float = 1.5               # wall left between cavity and plug recess

    # --- lid fastening
    tongue_x: tuple = (-45.0, 45.0)
    tongue_w: float = 12.0
    tongue_len: float = 1.3
    tongue_t: float = 0.8
    tongue_clearance: float = 0.2
    lid_screw_x: float = 28.0
    lid_screw_from_end: float = 7.5
    lid_boss_w: float = 7.0
    lid_boss_len: float = 7.0
    lid_cs_d: float = 4.2
    end_wall: float = 4.0              # arm end wall incl. ledge

    # --- table mounting ears (wood screws)
    ear_t: float = 4.0
    ear_xs: tuple = (63.0, 33.5)       # (|x|, s)
    ear_hole_d: float = 4.5
    ear_cs_d: float = 8.5

    # --- desk cable (ASSUMPTION: diameter and plug not measured)
    cable_d: float = 5.0
    cable_exit_w: float = 9.0          # lets a 3-pin 2.54 mm housing pass
    cable_exit_h: float = 6.0
    tie_slot_w: float = 2.0
    tie_slot_len: float = 4.0
    tie_slot_x: float = 4.0
    tie_from_end: float = 22.0
    tie_groove_depth: float = 1.0

    # --- back side component height used for the fit check
    back_component_h: float = 10.2     # C40 EEE-FK1J101P


P = Params()

A = math.radians(P.arm_angle_deg)
CA, SA = math.cos(A), math.sin(A)
U = (0.0, CA, SA)        # along the arm
N = (0.0, -SA, CA)       # arm normal, pointing away from the table
H = P.block_height
T = P.arm_thickness
HW = P.width / 2


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
def arm_yz(s: float, t: float) -> tuple[float, float]:
    """Arm frame (s, t) to case (Y, Z)."""
    return (P.block_depth + s * CA - t * SA, s * SA + t * CA)


def arm_xyz(x: float, s: float, t: float) -> tuple[float, float, float]:
    y, z = arm_yz(s, t)
    return (x, y, z)


def kink_s(z: float, t: float) -> float:
    """s of the line where the plane Z = z meets the arm plane t = t."""
    return (z - t * CA) / SA


def ccw(poly: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return the polygon with counter-clockwise winding."""
    area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1]))
    return list(poly) if area > 0 else list(poly[::-1])


def offset_polygon(poly: list[tuple[float, float]], d: float) -> list[tuple[float, float]]:
    """Offset a simple polygon inwards by d (outwards for d < 0) with mitred corners.
    Valid as long as no edge vanishes; that is asserted."""
    poly = ccw(poly)
    n = len(poly)
    lines = []
    for p, q in zip(poly, poly[1:] + poly[:1]):
        ex, ey = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(ex, ey)
        nx, ny = -ey / ln, ex / ln                       # inward normal of a CCW polygon
        lines.append((nx, ny, nx * p[0] + ny * p[1] + d, ex / ln, ey / ln))
    out = []
    for i in range(n):
        a1, b1, c1, *_ = lines[i - 1]
        a2, b2, c2, *_ = lines[i]
        det = a1 * b2 - a2 * b1
        out.append(((c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det))
    for i in range(n):                                   # every edge keeps its direction
        p, q = out[i], out[(i + 1) % n]
        assert (q[0] - p[0]) * lines[i][3] + (q[1] - p[1]) * lines[i][4] > 1e-6, "offset too large"
    return out


def prism_yz(pts, x0=-BIG, x1=BIG):
    """Polygon in (Y, Z), extruded along X."""
    pl = Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    return extrude(pl * Polygon(*ccw(pts), align=None), amount=x1 - x0)


def prism_xy(pts, z0=-BIG, z1=BIG):
    """Polygon in (X, Y), extruded along Z."""
    return extrude(Plane.XY.offset(z0) * Polygon(*ccw(pts), align=None), amount=z1 - z0)


def prism_xz(pts, y0=-BIG, y1=BIG):
    """Polygon in (X, Z), extruded along Y."""
    pl = Plane(origin=(0, y1, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
    return extrude(pl * Polygon(*ccw(pts), align=None), amount=y1 - y0)


def prism_arm(pts, t0=-BIG, t1=BIG):
    """Polygon in the arm plan (x, s), extruded along the arm normal."""
    pl = Plane(origin=arm_xyz(0, 0, t0), x_dir=(1, 0, 0), z_dir=N)
    return extrude(pl * Polygon(*ccw(pts), align=None), amount=t1 - t0)


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def zcyl(x, y, d, z0, z1):
    return Pos(x, y, z0) * Cylinder(d / 2, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def arm_plane(x, s, t):
    return Plane(origin=arm_xyz(x, s, t), x_dir=(1, 0, 0), z_dir=N)


def arm_cyl(x, s, d, t0, t1):
    return arm_plane(x, s, t0) * Cylinder(d / 2, t1 - t0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def arm_box(x0, x1, s0, s1, t0, t1):
    return arm_plane((x0 + x1) / 2, (s0 + s1) / 2, (t0 + t1) / 2) * Box(x1 - x0, s1 - s0, t1 - t0)


# --------------------------------------------------------------------------
# Derived contours
# --------------------------------------------------------------------------
S_KINK = kink_s(H, T)                              # outer kink between block top and arm top
S_KINK_IN = kink_s(H - P.lid_t, T - P.lid_t)       # kink of the lid underside
LID_TAPER_S0 = S_KINK + P.lid_taper_offset
LID_TAPER_S1 = LID_TAPER_S0 + P.lid_taper_length
TAB_HW = P.arm_tab_width / 2
LEDGE_Z = H - P.lid_t
LEDGE_T = T - P.lid_t

# side profiles in (Y, Z)
OUTER_PROFILE = [
    (P.front_chamfer_y, 0), (P.block_depth, 0), arm_yz(P.arm_length, 0), arm_yz(P.arm_length, T),
    arm_yz(S_KINK, T), (P.top_chamfer, H), (0, H - P.top_chamfer), (0, P.front_chamfer_z),
]
CAVITY_PROFILE = [
    (P.wall, P.face_t), arm_yz(kink_s(P.face_t, P.arm_floor_t), P.arm_floor_t),
    arm_yz(P.arm_length - P.end_wall, P.arm_floor_t), arm_yz(P.arm_length - P.end_wall, LEDGE_T),
    arm_yz(S_KINK_IN, LEDGE_T), (P.wall, LEDGE_Z),
]
# everything below the lid underside
BELOW_LID_PROFILE = [
    (-BIG, LEDGE_Z), arm_yz(S_KINK_IN, LEDGE_T), arm_yz(BIG, LEDGE_T), arm_yz(BIG, -BIG), (-BIG, -BIG),
]

# plan contours of the block in (X, Y)
BLOCK_OUTER = [
    (-HW + P.plan_chamfer, 0), (HW - P.plan_chamfer, 0), (HW, P.plan_chamfer),
    (HW, BIG), (-HW, BIG), (-HW, P.plan_chamfer),
]
BLOCK_REBATE = offset_polygon(BLOCK_OUTER, P.rim)
BLOCK_CAVITY = offset_polygon(BLOCK_OUTER, P.wall)
BLOCK_LID = offset_polygon(BLOCK_OUTER, P.rim + P.lid_clearance)

# front view in (X, Z): chamfer between face and side walls
FRONT_VIEW = [
    (-HW + P.side_chamfer_x, 0), (HW - P.side_chamfer_x, 0), (HW, P.side_chamfer_z),
    (HW, BIG), (-HW, BIG), (-HW, P.side_chamfer_z),
]

# plan contours of the arm in (x, s)
ARM_OUTER = [
    (-HW, -BIG), (HW, -BIG), (HW, P.arm_taper_start), (TAB_HW, P.arm_taper_end),
    (TAB_HW, P.arm_length), (-TAB_HW, P.arm_length), (-TAB_HW, P.arm_taper_end), (-HW, P.arm_taper_start),
]
ARM_REBATE = [
    (-(HW - P.rim), -BIG), (HW - P.rim, -BIG), (HW - P.rim, LID_TAPER_S0), (TAB_HW - P.rim, LID_TAPER_S1),
    (TAB_HW - P.rim, P.arm_length - P.rim), (-(TAB_HW - P.rim), P.arm_length - P.rim),
    (-(TAB_HW - P.rim), LID_TAPER_S1), (-(HW - P.rim), LID_TAPER_S0),
]
ARM_CAVITY = offset_polygon(ARM_REBATE, P.arm_ledge)
ARM_LID = offset_polygon(ARM_REBATE, P.lid_clearance)
ARM_RIM_OUTLINE = offset_polygon(ARM_REBATE, -P.rim)     # lid rebate plus rim, ears lie outside

PCB_X0, PCB_X1 = -P.pcb_width / 2, P.pcb_width / 2
PCB_Y0, PCB_Y1 = P.pcb_y0, P.pcb_y0 + P.pcb_depth
PCB_BOTTOM_Z = P.pcb_top_z + P.pcb_t

OLED_X0 = P.oled_glass_cx - P.oled_glass_w / 2
OLED_X1 = P.oled_glass_cx + P.oled_glass_w / 2
OLED_Y0 = P.ui_y - P.oled_glass_h / 2
OLED_Y1 = P.ui_y + P.oled_glass_h / 2
WINDOW_X0 = OLED_X0 + P.oled_visual_x0
WINDOW_X1 = WINDOW_X0 + P.oled_visual_w
WINDOW_Y0 = P.ui_y - P.oled_visual_h / 2
WINDOW_Y1 = P.ui_y + P.oled_visual_h / 2

USB_Z = PCB_BOTTOM_Z + P.usb_shell_h / 2
USB_FRONT_X = PCB_X1 + P.usb_overhang
LID_SCREW_S = P.arm_length - P.lid_screw_from_end
TIE_S = P.arm_length - P.tie_from_end
CAP_PLUNGER_Z = P.pcb_top_z - P.switch_height


# --------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------
def build_case():
    outer = prism_yz(OUTER_PROFILE) & prism_xy(BLOCK_OUTER) & prism_xz(FRONT_VIEW) & prism_arm(ARM_OUTER)
    rebate = (prism_xy(BLOCK_REBATE) & prism_arm(ARM_REBATE)) - prism_yz(BELOW_LID_PROFILE)
    cavity = prism_yz(CAVITY_PROFILE) & prism_xy(BLOCK_CAVITY) & prism_arm(ARM_CAVITY)
    case = outer - rebate - cavity

    # mounting ears: lower everything outside the lid rim to ear thickness
    ear_zone = prism_yz([arm_yz(LID_TAPER_S0, P.ear_t), arm_yz(P.arm_length + 5, P.ear_t),
                         arm_yz(P.arm_length + 5, T + 5), arm_yz(LID_TAPER_S0, T + 5)])
    case -= ear_zone - prism_arm(ARM_RIM_OUTLINE)
    cs_depth = (P.ear_cs_d - P.ear_hole_d) / 2
    for sx in (-1, 1):
        x, s = sx * P.ear_xs[0], P.ear_xs[1]
        case -= arm_cyl(x, s, P.ear_hole_d, -1, P.ear_t + 1)
        case -= arm_plane(x, s, P.ear_t - cs_depth) * Cone(
            P.ear_hole_d / 2, P.ear_cs_d / 2, cs_depth, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # PCB bosses with pilot holes
    for x, y in P.pcb_boss_xy:
        case += zcyl(x, y, P.boss_d, P.face_t - 0.01, P.pcb_top_z)
    for x, y in P.pcb_boss_xy:
        case -= zcyl(x, y, P.screw_pilot_d, P.pilot_floor, P.pcb_top_z + 1)

    # LED light baffles and thinned windows
    for x, y in P.led_xy:
        case += zcyl(x, y, P.led_tube_od, P.face_t - 0.01, P.led_tube_end_z)
    for x, y in P.led_xy:
        case -= zcyl(x, y, P.led_tube_id, P.face_t, P.led_tube_end_z + 1)
        case -= zcyl(x, y, P.led_window_d, P.led_skin_t, P.face_t + 0.01)

    # button holes
    for x in P.button_x:
        case -= zcyl(x, P.ui_y, P.button_hole_d, -1, P.face_t + 1)

    # OLED pocket (glass glued in from the inside) and window
    c = P.oled_pocket_clearance
    case -= box(OLED_X0 - c, OLED_X1 + c, OLED_Y0 - c, OLED_Y1 + c, P.oled_bezel_t, P.face_t + 0.01)
    case -= box(WINDOW_X0, WINDOW_X1, WINDOW_Y0, WINDOW_Y1, -1, P.face_t)

    # USB-C: recess for the plug from outside, slot for the shell open towards the lid
    recess_x = HW - P.wall + P.usb_web
    sc = P.usb_shell_clearance
    case -= box(recess_x, HW + 1, P.usb_y - P.usb_plug_w / 2, P.usb_y + P.usb_plug_w / 2,
                USB_Z - P.usb_plug_h / 2, USB_Z + P.usb_plug_h / 2)
    case -= box(HW - P.wall - 0.5, recess_x + 0.01, P.usb_y - P.usb_shell_w / 2 - sc,
                P.usb_y + P.usb_shell_w / 2 + sc, PCB_BOTTOM_Z - sc, LEDGE_Z + 0.01)

    # slots for the lid tongues in the front wall
    tc = P.tongue_clearance
    for x in P.tongue_x:
        case -= box(x - P.tongue_w / 2 - 0.3, x + P.tongue_w / 2 + 0.3, P.rim - P.tongue_len - tc, P.rim + 0.01,
                    LEDGE_Z - 0.1, LEDGE_Z + P.tongue_t + tc)

    # lid screw bosses in the arm: gussets with a print-vertical face towards the block
    s_end = P.arm_length - P.end_wall
    s_top = s_end - P.lid_boss_len
    s_foot = s_top - (LEDGE_T - P.arm_floor_t) * SA / CA
    gusset = [arm_yz(s_end + 0.01, P.arm_floor_t - 0.01), arm_yz(s_end + 0.01, LEDGE_T),
              arm_yz(s_top, LEDGE_T), arm_yz(s_foot, P.arm_floor_t - 0.01)]
    for sx in (-1, 1):
        x = sx * P.lid_screw_x
        case += prism_yz(gusset, x - P.lid_boss_w / 2, x + P.lid_boss_w / 2)
    for sx in (-1, 1):
        case -= arm_cyl(sx * P.lid_screw_x, LID_SCREW_S, P.screw_pilot_d, P.arm_floor_t + 0.6, LEDGE_T + 1)

    # desk cable: exit window in the arm end wall, slots and groove for a cable tie
    case -= arm_box(-P.cable_exit_w / 2, P.cable_exit_w / 2, s_end - 1, P.arm_length + 1,
                    P.arm_floor_t, P.arm_floor_t + P.cable_exit_h)
    for sx in (-1, 1):
        x = sx * P.tie_slot_x
        case -= arm_box(x - P.tie_slot_w / 2, x + P.tie_slot_w / 2, TIE_S - P.tie_slot_len / 2,
                        TIE_S + P.tie_slot_len / 2, -1, P.arm_floor_t + 1)
    case -= arm_box(-P.tie_slot_x - P.tie_slot_w / 2, P.tie_slot_x + P.tie_slot_w / 2,
                    TIE_S - P.tie_slot_len / 2, TIE_S + P.tie_slot_len / 2, -1, P.tie_groove_depth)
    return case


def build_lid():
    lid = (prism_xy(BLOCK_LID) & prism_arm(ARM_LID) & prism_yz(OUTER_PROFILE)) - prism_yz(BELOW_LID_PROFILE)
    y_edge = P.rim + P.lid_clearance
    for x in P.tongue_x:
        lid += box(x - P.tongue_w / 2, x + P.tongue_w / 2, P.rim - P.tongue_len, y_edge + 0.5,
                   LEDGE_Z, LEDGE_Z + P.tongue_t)
    cs_depth = (P.lid_cs_d - P.screw_clear_d) / 2
    for sx in (-1, 1):
        x = sx * P.lid_screw_x
        lid -= arm_cyl(x, LID_SCREW_S, P.screw_clear_d, LEDGE_T - 1, T + 1)
        lid -= arm_plane(x, LID_SCREW_S, T - cs_depth) * Cone(
            P.screw_clear_d / 2, P.lid_cs_d / 2, cs_depth + 0.01, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return lid


def build_button_cap():
    """One cap in print orientation: flange on the bed, visible top up."""
    flange_bottom = CAP_PLUNGER_Z - P.cap_preload_gap
    flange_t = flange_bottom - P.face_t
    body_h = flange_t + P.face_t + P.cap_protrusion
    ch = P.cap_top_chamfer
    cap = Cylinder(P.cap_flange_d / 2, flange_t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cap += Cylinder(P.cap_d / 2, body_h - ch, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cap += Pos(0, 0, body_h - ch) * Cone(P.cap_d / 2, P.cap_d / 2 - ch, ch,
                                         align=(Align.CENTER, Align.CENTER, Align.MIN))
    return cap


def cap_in_place(x):
    """Button cap at its assembly position (rest position, flange at the face)."""
    flange_bottom = CAP_PLUNGER_Z - P.cap_preload_gap
    return (zcyl(x, P.ui_y, P.cap_flange_d, P.face_t, flange_bottom)
            + zcyl(x, P.ui_y, P.cap_d, -P.cap_protrusion, P.face_t + 0.01))


def build_board_envelope():
    """Stand-in for the PCB until a layout exists: board, UI parts, USB shell and
    a slab of the tallest back side part over the whole board."""
    parts = {
        "pcb": box(PCB_X0, PCB_X1, PCB_Y0, PCB_Y1, P.pcb_top_z, PCB_BOTTOM_Z),
        "back_components": box(PCB_X0, PCB_X1, PCB_Y0, PCB_Y1, PCB_BOTTOM_Z, PCB_BOTTOM_Z + P.back_component_h),
        "oled": box(OLED_X0, OLED_X1, OLED_Y0, OLED_Y1, P.oled_bezel_t, P.oled_bezel_t + P.oled_glass_t),
        "usb": box(USB_FRONT_X - P.usb_shell_len, USB_FRONT_X, P.usb_y - P.usb_shell_w / 2,
                   P.usb_y + P.usb_shell_w / 2, PCB_BOTTOM_Z, PCB_BOTTOM_Z + P.usb_shell_h),
    }
    sw = None
    caps = None
    for x in P.button_x:
        b = P.switch_body / 2
        one = box(x - b, x + b, P.ui_y - b, P.ui_y + b, P.pcb_top_z - P.switch_body_h, P.pcb_top_z)
        one += zcyl(x, P.ui_y, 3.5, CAP_PLUNGER_Z, P.pcb_top_z - P.switch_body_h + 0.01)
        sw = one if sw is None else sw + one
        caps = cap_in_place(x) if caps is None else caps + cap_in_place(x)
    parts["switches"] = sw
    parts["button_caps"] = caps
    return parts


# --------------------------------------------------------------------------
# Board interface for the PCB layout
# --------------------------------------------------------------------------
def board_interface() -> dict:
    """Positions in board coordinates as KiCad shows them: origin at the board
    corner (case X min, Y min), x to the right, y down, seen on the front side
    (F.Cu = the side with buttons and display connector, facing the front panel)."""
    def bx(x):
        return round(x - PCB_X0, 3)

    def by(y):
        return round(y - PCB_Y0, 3)

    def front_height_limit(y):
        """Free height above F.Cu at case Y, limited by the face and the arm wall."""
        z_min = max(P.face_t, (P.arm_floor_t + (y - P.block_depth) * SA) / CA)
        return round(P.pcb_top_z - z_min, 2)

    return {
        "revision": REVISION,
        "note": "Generated by CAD/src/bekantx_enclosure.py. Do not edit by hand.",
        "board": {"width": P.pcb_width, "depth": P.pcb_depth, "thickness": P.pcb_t,
                  "edge_clearance_to_case": P.pcb_edge_clearance},
        "mounting_holes": [{"x": bx(x), "y": by(y), "drill": P.screw_clear_d,
                            "keepout_d_front": P.boss_d + 0.5, "keepout_d_back": P.screw_head_d + 0.6}
                           for x, y in P.pcb_boss_xy],
        "buttons": [{"ref_hint": f"SW{3 + i}", "x": bx(x), "y": by(P.ui_y), "side": "F",
                     "cap_keepout_d": P.cap_flange_d + 0.6, "cap_keepout_height_above_board":
                     round(P.pcb_top_z - CAP_PLUNGER_Z + P.cap_preload_gap + 0.5, 2)}
                    for i, x in enumerate(P.button_x)],
        "oled": {"glass": {"x0": bx(OLED_X0), "x1": bx(OLED_X1), "y0": by(OLED_Y0), "y1": by(OLED_Y1)},
                 "fpc_exit_edge_x": bx(OLED_X1), "fpc_exit_centre_y": by(P.ui_y),
                 "glass_back_above_board": round(P.pcb_top_z - P.oled_bezel_t - P.oled_glass_t, 2),
                 "connector_side": "F"},
        "status_leds": [{"ref_hint": r, "x": bx(x), "y": by(y), "side": "F",
                         "baffle_keepout_d": P.led_tube_od + 0.5,
                         "max_part_height": round(P.pcb_top_z - P.led_tube_end_z - 0.3, 2)}
                        for r, (x, y) in zip(("D5", "D1"), P.led_xy)],
        "usb_c": {"ref_hint": "J1", "side": "B", "edge": "x = board width",
                  "centre_y": by(P.usb_y), "shell_front_beyond_edge": P.usb_overhang},
        "height_limits": {
            "front_side_general": round(P.pcb_top_z - P.face_t, 2),
            "front_side_at_back_edge": front_height_limit(PCB_Y1),
            "front_side_full_height_until_y": by(P.block_depth - (P.arm_floor_t - P.face_t * CA) / SA) ,
            "back_side": round(LEDGE_Z - PCB_BOTTOM_Z, 2),
        },
    }


# --------------------------------------------------------------------------
# Checks and export
# --------------------------------------------------------------------------
def volume(shape) -> float:
    return 0.0 if shape is None else float(shape.volume)


def main() -> None:
    case, lid, cap = build_case(), build_lid(), build_button_cap()
    env = build_board_envelope()

    print(f"BekantX enclosure {REVISION}")
    for name, part in (("case", case), ("lid", lid), ("button_cap", cap)):
        bb = part.bounding_box()
        print(f"  {name:11s} size {bb.size.X:7.2f} x {bb.size.Y:6.2f} x {bb.size.Z:6.2f}  "
              f"volume {part.volume / 1000:6.1f} cm3  valid {part.is_valid}  solids {len(part.solids())}")

    print("fit check (intersection volume in mm3, must be 0):")
    worst = 0.0
    for a_name, a in (("case", case), ("lid", lid)):
        for b_name, b in env.items():
            v = volume(a & b)
            worst = max(worst, v)
            print(f"  {a_name:5s} x {b_name:16s} {v:8.3f}")
    v = volume(case & lid)
    worst = max(worst, v)
    print(f"  case  x lid              {v:8.3f}")

    print("clearances:")
    print(f"  pcb to side walls        {HW - P.wall - PCB_X1:.2f}")
    print(f"  pcb to front wall        {PCB_Y0 - P.wall:.2f}")
    y_arm = P.block_depth + (P.pcb_top_z * CA - P.arm_floor_t) / SA
    print(f"  pcb back edge to arm     {y_arm - PCB_Y1:.2f} (at the board front side)")
    print(f"  back side free height    {LEDGE_Z - PCB_BOTTOM_Z:.2f} (C40 needs {P.back_component_h})")
    print(f"  front side free height   {P.pcb_top_z - P.face_t:.2f}")
    print(f"  usb shell front to recess{HW - P.wall + P.usb_web - USB_FRONT_X:6.2f}")

    for name, part in (("Case", case), ("Lid", lid), ("ButtonCap", cap)):
        base = CAD_DIR / f"BekantX_{name}_{REVISION}"
        export_step(part, str(base.with_suffix(".step")))
        export_stl(part, str(base.with_suffix(".stl")), tolerance=0.02, angular_tolerance=0.1)
    build = CAD_DIR.parent / "build" / "cad"
    build.mkdir(parents=True, exist_ok=True)
    board = None
    for part in env.values():
        board = part if board is None else board + part
    export_stl(board, str(build / "board_envelope.stl"), tolerance=0.05)

    (CAD_DIR / "board_interface.json").write_text(json.dumps(board_interface(), indent=2) + "\n", encoding="utf-8")
    (build / "params.json").write_text(json.dumps(asdict(P), indent=2) + "\n", encoding="utf-8")
    if worst > 1e-3:
        raise SystemExit(f"FIT CHECK FAILED: interference {worst:.3f} mm3")
    print("fit check passed")


if __name__ == "__main__":
    main()
