"""BekantX enclosure, revision 3: one PCB behind the front panel.

Parametric rebuild of the original enclosure style (CAD/BekantX_Case.stl,
CAD/BekantX_Lid.stl, removed 2026-11-19, kept in git tag archive/pre-cleanup): a front block with buttons and display, and an arm
angled by 55 degrees that is screwed under the table top. The front block is
deeper than the original so that the single PCB fits.

Revision 3 (after the first test print of r2, whose lid was captive):
  * Lid: hinges on two tongues at the arm end and snaps under two lips of the
    front wall. All lid edges and rebate walls are prisms along the direction
    in which the front edge swings, so the lid can rotate in and out. Two
    screws in the arm secure the snap, a tab at the front opens it.
  * Keypad: the six button caps hang on thin arms from one spine (one part).
  * USB-C: the receptacle mouth sits in the outer wall surface. The board has
    a tab under the connector and is slid sideways into the wall pocket.
  * Front block 19.5 mm high instead of 23 mm.

Print orientation: case with the front face on the bed, lid with the inner
side of the block part on the bed, keypad with the spine on the bed.

Screws: eight M2.5 x 6 pan head (ISO 7045 / ISO 14583) straight into the
plastic, six for the board and two for the lid. Wood screws for the table.

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
    Axis,
    Box,
    Cone,
    Cylinder,
    FontStyle,
    Plane,
    Polygon,
    Pos,
    Rot,
    Text,
    export_step,
    export_stl,
    extrude,
)

REVISION = "r3"
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
    block_height: float = 19.5         # original 20, r2 23; back side parts are limited to back_component_h
    arm_angle_deg: float = 55.0
    arm_length: float = 57.0
    arm_thickness: float = 11.0
    arm_tab_width: float = 80.0        # narrow end of the arm
    arm_taper_start: float = 37.0      # s where the outer contour starts to narrow
    arm_taper_end: float = 47.0        # s where the outer contour reaches arm_tab_width
    chamfer: float = 3.0               # one 45 deg chamfer: face to front wall, face to side walls, front corners
    top_chamfer: float = 0.8           # 45 deg chamfer of the outer edges on the lid side

    # --- walls
    face_t: float = 2.0
    wall: float = 5.0                  # front wall of the block at the lid (rim + ledge)
    wall_lower: float = 3.8            # front wall below the ledge; widens at 45 deg up to `wall`
    side_wall: float = 3.8             # side walls of the block (rim + ledge)
    rim: float = 2.6                   # outer rim around the lid, at the lid surface
    arm_floor_t: float = 2.0           # arm wall on the table side
    arm_ledge: float = 1.2             # lid ledge inside the arm rim (plan view)
    lid_t: float = 2.4
    lid_clearance: float = 0.3         # lid to rim, per side (horizontal)

    # --- lid contour in the arm
    lid_taper_offset: float = 3.0      # lid starts to narrow this far after the kink
    lid_taper_length: float = 12.0

    # --- PCB (ASSUMPTION: 1.6 mm FR4, no layout yet)
    pcb_width: float = 129.0
    pcb_depth: float = 38.0
    pcb_t: float = 1.6
    pcb_corner_r: float = 2.5          # rounded outer corners of the board (look; the case pocket stays square)
    pcb_tab_corner_r: float = 0.5      # corners of the USB tab (outer: rounded, inner: milling radius)
    pcb_y0: float = 5.5                # front edge of the board
    pcb_top_z: float = 8.0             # component side that faces the front panel
    pcb_edge_clearance: float = 0.5
    boss_d: float = 5.5
    screw_pilot_d: float = 2.25        # M2.5 machine screw straight into the plastic (0.9 x thread)
    screw_clear_d: float = 2.9
    screw_head_d: float = 5.0          # pan head ISO 7045, 2.1 high
    screw_len: float = 6.0
    pilot_floor: float = 1.0           # material left under a pilot hole in the face
    pcb_boss_xy: tuple = ((-61.0, 10.5), (0.0, 10.5), (61.0, 10.5),
                          (-52.0, 38.5), (0.0, 38.5), (52.0, 38.5))

    # --- UI row
    ui_y: float = 22.0                 # centre line of buttons and display
    button_x: tuple = (-56.0, -41.0, 11.0, 26.0, 41.0, 56.0)   # original pattern
    button_hole_d: float = 10.6        # original
    cap_d: float = 9.8                 # 0.4 radial play in the hole (r2: 0.3)
    cap_protrusion: float = 1.5
    cap_flange_d: float = 12.0
    cap_top_chamfer: float = 0.4
    # symbols on the caps, in the order of button_x. Seen from the front the row reads
    # M1 M2 M3 M4 [display] up down (the user's right is -X). ASSUMPTION: no assignment is specified yet.
    button_labels: tuple = ("down", "up", "M4", "M3", "M2", "M1")
    label_depth: float = 0.4           # engraved, two layers
    label_font: str = "Arial"
    label_font_size: float = 4.4
    label_arrow_w: float = 5.2
    label_arrow_h: float = 4.2
    # keypad: all caps hang on thin arms from one spine in front of the buttons
    keypad_arm_t: float = 0.4          # two layers of 0.2 mm
    keypad_arm_w: float = 2.5
    keypad_spine_t: float = 0.8
    keypad_spine_w: float = 1.6
    keypad_spine_gap: float = 0.6      # spine to the front wall
    keypad_spine_overhang: float = 2.0 # spine beyond the outer arms
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
    oled_window_margin: float = 0.3    # window smaller than the visual area, per side

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
    usb_overhang: float = 1.5          # shell front beyond the edge of the board tab (ASSUMPTION, check footprint)
    usb_shell_clearance: float = 0.3
    usb_recess: float = 0.2            # shell front behind the outer wall surface
    usb_wall_t: float = 1.2            # wall left in front of the board tab
    usb_slide_margin: float = 0.3      # board to the -X wall while it is lowered
    usb_tab_w: float = 11.0            # board tab that carries the connector
    usb_pocket_w: float = 12.0         # pocket in the side wall for tab and shell

    # --- lid: hinge tongues at the arm end
    hinge_x: tuple = (-22.0, 22.0)
    hinge_w: float = 14.0
    hinge_len: float = 2.0             # tongue beyond the rebate wall
    hinge_t: float = 1.0
    hinge_tip_gap: float = 0.15        # tongue tip to slot end; this takes the snap force
    hinge_clearance: float = 0.25      # above the tongue
    hinge_side_clearance: float = 0.3

    # --- lid: snap lips on the front wall (see the snap section below)
    snap_x: tuple = ((-52.0, -16.0), (16.0, 52.0))
    snap_compress: float = 0.25        # how far the lid is squeezed when it passes the lip
    snap_retention_deg: float = 40.0   # catch face against the direction of motion (90 = locked)
    snap_lead_deg: float = 30.0        # lead-in face on top of the lip, from the lid surface
    snap_lead_margin: float = 0.2
    snap_land: float = 0.1
    snap_gap: float = 0.2              # lid nose to lip underside when closed
    snap_tip_clearance: float = 0.25
    snap_side_clearance: float = 0.5

    # --- lid: tab at the front to open it
    tab_w: float = 16.0
    tab_overhang: float = 1.0          # beyond the front wall
    tab_side_clearance: float = 0.3
    tab_scoop: float = 1.8             # chamfer of the front wall below the tab (finger nail)

    # --- lid: two securing screws in the arm
    lid_screw_x: float = 30.0
    lid_screw_s_from_kink: float = 8.0
    lid_boss_w: float = 7.0
    lid_boss_margin: float = 2.75
    lid_screw_depth: float = 5.5
    lid_cbore_d: float = 5.6           # counterbore for the pan head
    lid_cbore_depth: float = 1.2

    # --- table mounting ears (wood screws)
    ear_t: float = 4.0
    ear_xs: tuple = (63.0, 33.5)       # (|x|, s)
    ear_hole_d: float = 4.5
    ear_cs_d: float = 8.5

    # --- desk cable (ASSUMPTION: diameter and plug not measured)
    cable_d: float = 5.0
    cable_exit_w: float = 9.0          # lets a 3-pin 2.54 mm housing pass
    arm_wall_overhang_deg: float = 45.0   # inner arm walls lean out towards the floor to save plastic
    cable_exit_h: float = 5.0
    tie_slot_w: float = 3.2
    tie_slot_len: float = 4.0
    tie_slot_x: float = 4.0
    tie_from_end: float = 22.0
    tie_groove_depth: float = 1.0

    # --- back side component height used for the fit check.
    #     C40 (EEE-FK1J101P, 10.2 mm) does NOT fit any more, see Vault/Offene Punkte.md
    back_component_h: float = 7.0


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


def prism_shear(pts):
    """Polygon given in the plane Z = 0, extruded both ways along the lid draft
    direction (0, -K, 1). All lid edges and rebate walls are made this way."""
    return extrude(Plane.XY * Polygon(*ccw(pts), align=None), amount=BIG, dir=(0, -K, 1), both=True)


def q_of(y: float, z: float) -> float:
    """Y in the plane Z = 0 of the draft line through (y, z)."""
    return y + K * z


def prism_arm(pts, t0=-BIG, t1=BIG):
    """Polygon in the arm plan (x, s), extruded along the arm normal."""
    pl = Plane(origin=arm_xyz(0, 0, t0), x_dir=(1, 0, 0), z_dir=N)
    return extrude(pl * Polygon(*ccw(pts), align=None), amount=t1 - t0)


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def xslot(x0, x1, y, z, w, h):
    """Stadium (w x h, round ends) in the Y-Z plane, extruded along X: USB-C shell and its opening."""
    half = (w - h) / 2
    shape = box(x0, x1, y - half, y + half, z - h / 2, z + h / 2)
    for sy in (-1, 1):
        shape += Plane(origin=(x0, y + sy * half, z), x_dir=(0, 1, 0), z_dir=(1, 0, 0)) * Cylinder(
            h / 2, x1 - x0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return shape


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

# Lid draft. The lid hinges at the arm end, so its front edge swings on an arc
# around the hinge. K is the slope (-dY/dZ) of that arc at the front edge; every
# lid edge and rebate wall is a prism along (0, -K, 1). Walls that face the
# hinge side then only move away from the lid when it opens.
_hinge_nominal = arm_yz(P.arm_length - P.rim, LEDGE_T)
K = (_hinge_nominal[1] - LEDGE_Z) / (_hinge_nominal[0] - P.rim)
KK = math.hypot(1.0, K)
RHO = (-1 / KK, -K / KK)       # out of the lid into the front wall, in (Y, Z)
TAU = (-K / KK, 1 / KK)        # along the front wall, the way the lid edge opens
FRONT_BASE_Y = P.rim + K * P.lid_t                 # rebate front wall at ledge level

# side profiles in (Y, Z)
OUTER_PROFILE = [
    (P.chamfer, 0), (P.block_depth, 0), arm_yz(P.arm_length, 0), arm_yz(P.arm_length, T),
    arm_yz(S_KINK, T), (P.top_chamfer, H), (0, H - P.top_chamfer), (0, P.chamfer),
]
S_FAR = P.arm_length + 50.0
CAVITY_PROFILE = [
    (P.wall_lower, P.face_t), arm_yz(kink_s(P.face_t, P.arm_floor_t), P.arm_floor_t),
    arm_yz(S_FAR, P.arm_floor_t), arm_yz(S_FAR, LEDGE_T),
    arm_yz(S_KINK_IN, LEDGE_T), (P.wall, LEDGE_Z), (P.wall_lower, LEDGE_Z - (P.wall - P.wall_lower)),
]
# everything below the lid underside
BELOW_LID_PROFILE = [
    (-BIG, LEDGE_Z), arm_yz(S_KINK_IN, LEDGE_T), arm_yz(BIG, LEDGE_T), arm_yz(BIG, -BIG), (-BIG, -BIG),
]

# plan contours of the block in (X, Y)
BLOCK_OUTER = [
    (-HW + P.chamfer, 0), (HW - P.chamfer, 0), (HW, P.chamfer),
    (HW, BIG), (-HW, BIG), (-HW, P.chamfer),
]
BLOCK_CAVITY = offset_polygon(BLOCK_OUTER, P.side_wall)
CAVITY_HW = HW - P.side_wall

# front view in (X, Z): chamfer between face and side walls
FRONT_VIEW = [
    (-HW + P.chamfer, 0), (HW - P.chamfer, 0), (HW, P.chamfer),
    (HW, BIG), (-HW, BIG), (-HW, P.chamfer),
]

# plan contours of the arm in (x, s), valid at the arm surface t = T
ARM_OUTER = [
    (-HW, -BIG), (HW, -BIG), (HW, P.arm_taper_start), (TAB_HW, P.arm_taper_end),
    (TAB_HW, P.arm_length), (-TAB_HW, P.arm_length), (-TAB_HW, P.arm_taper_end), (-HW, P.arm_taper_start),
]
ARM_REBATE = [
    (-(HW - P.rim), -BIG), (HW - P.rim, -BIG), (HW - P.rim, LID_TAPER_S0), (TAB_HW - P.rim, LID_TAPER_S1),
    (TAB_HW - P.rim, P.arm_length - P.rim), (-(TAB_HW - P.rim), P.arm_length - P.rim),
    (-(TAB_HW - P.rim), LID_TAPER_S1), (-(HW - P.rim), LID_TAPER_S0),
]
ARM_RIM_OUTLINE = offset_polygon(ARM_REBATE, -P.rim)     # lid rebate plus rim, ears lie outside


def ledge_point(qy: float) -> tuple[float, float]:
    """(s, plan Y) where the draft line with the Z = 0 coordinate qy meets the arm ledge."""
    z = (LEDGE_T + SA * (qy - P.block_depth)) / (SA * K + CA)
    return (kink_s(z, LEDGE_T), qy - K * z)


# The same contours as draft prisms: coordinates in the plane Z = 0 ("Q").
# The block contour is the rebate at the lid surface Z = H, the arm contour the
# rebate at the arm surface t = T.
BLOCK_REBATE_Q = [(x, q_of(y, H)) for x, y in offset_polygon(BLOCK_OUTER, P.rim)]
ARM_REBATE_Q = [(x, q_of(*arm_yz(s_, T))) for x, s_ in ARM_REBATE]
BLOCK_LID_Q = offset_polygon(BLOCK_REBATE_Q, P.lid_clearance)
ARM_LID_Q = offset_polygon(ARM_REBATE_Q, P.lid_clearance)
# cavity in the arm: plan view of the rebate at ledge level, moved in by the ledge; walls parallel to Z
ARM_CAVITY_PLAN = offset_polygon([(x, ledge_point(qy)[1]) for x, qy in ARM_REBATE_Q], P.arm_ledge)

Q_END_WALL = q_of(*arm_yz(P.arm_length - P.rim, T))
S_END_WALL = ledge_point(Q_END_WALL)[0]                  # rebate end wall at ledge level
S_END_LID = ledge_point(Q_END_WALL - P.lid_clearance)[0]
S_HINGE_TIP = S_END_WALL + P.hinge_len
PIVOT = arm_yz(S_HINGE_TIP, LEDGE_T)                     # the lid turns about the tongue tips

# USB pocket: the board tab is lowered through a notch in the rim, then the board
# is slid towards +X. The notch is longer by the draft so that a vertical path is free.
USB_POCKET_X = HW - P.usb_wall_t
USB_NOTCH_Y0 = P.usb_y - P.usb_pocket_w / 2
USB_NOTCH_Y1 = P.usb_y + P.usb_pocket_w / 2 + K * P.lid_t
USB_NOTCH_Q = [
    (HW - P.rim - 0.5, q_of(USB_NOTCH_Y0, LEDGE_Z)), (USB_POCKET_X, q_of(USB_NOTCH_Y0, LEDGE_Z)),
    (USB_POCKET_X, q_of(USB_NOTCH_Y1, LEDGE_Z)), (HW - P.rim - 0.5, q_of(USB_NOTCH_Y1, LEDGE_Z)),
]
# the lid ear that fills the notch; its front needs room because the ear swings forward
EAR_FRONT_GAP = (abs(PIVOT[1] - LEDGE_Z) / abs(PIVOT[0] - USB_NOTCH_Y0) - K) * P.lid_t + 0.3
LID_EAR_Q = [
    (HW - P.rim - P.lid_clearance - 0.5, q_of(USB_NOTCH_Y0 + EAR_FRONT_GAP, LEDGE_Z)),
    (USB_POCKET_X - P.lid_clearance, q_of(USB_NOTCH_Y0 + EAR_FRONT_GAP, LEDGE_Z)),
    (USB_POCKET_X - P.lid_clearance, q_of(USB_NOTCH_Y1 - P.lid_clearance, LEDGE_Z)),
    (HW - P.rim - P.lid_clearance - 0.5, q_of(USB_NOTCH_Y1 - P.lid_clearance, LEDGE_Z)),
]


# --------------------------------------------------------------------------
# Snap at the front wall, drawn in (rho, tau): rho out of the lid into the wall,
# tau along the wall in the direction in which the lid edge opens. The lid edge
# moves along tau only, so this is an ordinary snap profile:
#
#   tau ^        wall (rho > 0)
#       |    \  lead-in
#       |   |   land           lip of the case, sticks out to rho = -SNAP_P
#       |    /  catch face
#       |     | nose of the lid, face at rho = -C_RHO
#       +---------> rho
# --------------------------------------------------------------------------
def front_yz(rho: float, tau: float) -> tuple[float, float]:
    return (FRONT_BASE_Y + rho * RHO[0] + tau * TAU[0], LEDGE_Z + rho * RHO[1] + tau * TAU[1])


C_RHO = P.lid_clearance / KK                             # lid to wall, perpendicular to the wall
SNAP_P = P.snap_compress + C_RHO + P.hinge_tip_gap       # lip height above the wall
TAN_PSI = 1 / math.tan(math.radians(P.snap_retention_deg))
_lead = (-math.cos(math.radians(P.snap_lead_deg)), math.sin(math.radians(P.snap_lead_deg)))   # in (Y, Z)
LEAD_RHO = _lead[0] * RHO[0] + _lead[1] * RHO[1]
LEAD_TAU = _lead[0] * TAU[0] + _lead[1] * TAU[1]
TAN_LEAD = LEAD_RHO / LEAD_TAU
TAU_MAX = P.lid_t * KK
# the lead-in must reach from the lip tip to beyond the lid nose before it meets the lid surface
SNAP_TAU_LAND1 = (TAU_MAX - SNAP_P * K
                  - (SNAP_P - C_RHO + P.snap_lead_margin) / TAN_LEAD * (1 - K * TAN_LEAD))
SNAP_TAU_LAND0 = SNAP_TAU_LAND1 - P.snap_land
SNAP_TAU_ROOT = SNAP_TAU_LAND0 - SNAP_P * TAN_PSI        # catch face meets the wall
SNAP_TAU_NOSE = SNAP_TAU_ROOT + C_RHO * TAN_PSI - P.snap_gap   # top of the lid nose
assert SNAP_TAU_NOSE > 0.7 and SNAP_TAU_ROOT > 0.3, "snap profile does not fit into the lid thickness"
_far = 6.0
SNAP_LIP_PROFILE = [
    front_yz(0.6, SNAP_TAU_ROOT - 0.6 * TAN_PSI), front_yz(-SNAP_P, SNAP_TAU_LAND0),
    front_yz(-SNAP_P, SNAP_TAU_LAND1),
    front_yz(-SNAP_P + _far * LEAD_RHO, SNAP_TAU_LAND1 + _far * LEAD_TAU),
]
SNAP_LID_CUT = [
    front_yz(1.0, SNAP_TAU_NOSE - (1.0 + C_RHO) * TAN_PSI),
    front_yz(-SNAP_P - P.snap_tip_clearance, SNAP_TAU_NOSE + (SNAP_P + P.snap_tip_clearance - C_RHO) * TAN_PSI),
    front_yz(-SNAP_P - P.snap_tip_clearance, _far), front_yz(1.0, _far),
]

PCB_X0, PCB_X1 = -P.pcb_width / 2, P.pcb_width / 2
PCB_Y0, PCB_Y1 = P.pcb_y0, P.pcb_y0 + P.pcb_depth
PCB_BOTTOM_Z = P.pcb_top_z + P.pcb_t

OLED_X0 = P.oled_glass_cx - P.oled_glass_w / 2
OLED_X1 = P.oled_glass_cx + P.oled_glass_w / 2
OLED_Y0 = P.ui_y - P.oled_glass_h / 2
OLED_Y1 = P.ui_y + P.oled_glass_h / 2
WINDOW_X0 = OLED_X0 + P.oled_visual_x0 + P.oled_window_margin
WINDOW_X1 = OLED_X0 + P.oled_visual_x0 + P.oled_visual_w - P.oled_window_margin
WINDOW_Y0 = P.ui_y - P.oled_visual_h / 2 + P.oled_window_margin
WINDOW_Y1 = P.ui_y + P.oled_visual_h / 2 - P.oled_window_margin

USB_Z = PCB_BOTTOM_Z + P.usb_shell_h / 2
USB_FRONT_X = HW - P.usb_recess
USB_TAB_X1 = USB_FRONT_X - P.usb_overhang              # end of the board tab
USB_SLIDE = CAVITY_HW - PCB_X1 - P.usb_slide_margin                   # sideways travel of the board during assembly
assert USB_FRONT_X - USB_SLIDE < USB_POCKET_X - 0.2, "USB shell does not pass the wall when the board is lowered"
LID_SCREW_S = S_KINK + P.lid_screw_s_from_kink
TIE_S = P.arm_length - P.tie_from_end
CAP_PLUNGER_Z = P.pcb_top_z - P.switch_height
KEYPAD_BASE_Z = CAP_PLUNGER_Z - P.cap_preload_gap      # underside of the keypad = print bed
SPINE_Y0 = P.wall + P.keypad_spine_gap
SPINE_Y1 = SPINE_Y0 + P.keypad_spine_w


# --------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------
def half_space(origin, x_dir, normal):
    """Everything on the side of the plane to which `normal` points."""
    return Plane(origin=origin, x_dir=x_dir, z_dir=normal) * Box(
        2 * BIG, 2 * BIG, BIG, align=(Align.CENTER, Align.CENTER, Align.MIN))


def top_chamfer_cut():
    """Material to remove for the chamfer of the outer edges on the lid side: front
    corners and side walls of the block, continued along the sides of the arm."""
    c = P.top_chamfer
    r2 = math.sqrt(0.5)
    cut = None
    below_arm = prism_yz([arm_yz(-BIG, T), arm_yz(BIG, T), arm_yz(BIG, -BIG), arm_yz(-BIG, -BIG)])
    below_block = box(-BIG, BIG, -BIG, BIG, -BIG, H)
    for sx in (-1, 1):
        # side wall of the block and side of the arm; they meet at the kink
        block_side = half_space((sx * (HW - c), 0, H), (0, 1, 0), (sx * r2, 0, r2))
        arm_side = half_space(arm_xyz(sx * (HW - c), 0, T), U, (sx * r2, N[1] * r2, N[2] * r2))
        part = (block_side - below_arm) + (arm_side - below_block) + (block_side & arm_side)
        # front corner
        corner = half_space((sx * (HW - P.chamfer / 2), P.chamfer / 2 + c * r2, H), (sx * r2, r2, 0),
                            (sx * 0.5, -0.5, r2))
        part += corner
        cut = part if cut is None else cut + part
    return cut


def arm_wall_relief():
    """Extra cavity behind the taper and end walls of the arm. Below the lid ledge
    these walls lean outwards by arm_wall_overhang_deg instead of standing parallel
    to Z, which removes the solid wedges and still prints without support."""
    sin_o = math.sin(math.radians(P.arm_wall_overhang_deg))
    poly = ccw(ARM_CAVITY_PLAN)

    def on_ledge(pt):
        return (pt[0], pt[1], (LEDGE_T + SA * (pt[1] - P.block_depth)) / CA)

    xmax = max(abs(x) for x, _ in poly)
    s_start = kink_s(P.face_t, P.arm_floor_t) + 1.0
    slab = prism_yz([arm_yz(s_start, P.arm_floor_t), arm_yz(S_FAR, P.arm_floor_t),
                     arm_yz(S_FAR, LEDGE_T), arm_yz(s_start, LEDGE_T)], -xmax, xmax)

    def lean_out(a, b):
        """Half space behind the wall over the plan edge a-b, leaning out from the ledge."""
        pa, pb = on_ledge(a), on_ledge(b)
        e = [pb[i] - pa[i] for i in range(3)]
        ln = math.sqrt(sum(v * v for v in e))
        e = [v / ln for v in e]
        hn = math.hypot(e[0], e[1])
        u1 = (-e[1] / hn, e[0] / hn, 0.0)                        # horizontal, into the cavity
        u2 = (e[1] * u1[2] - e[2] * u1[1], e[2] * u1[0] - e[0] * u1[2], e[0] * u1[1] - e[1] * u1[0])
        sin_p = -sin_o / u2[2]
        n = tuple(math.sqrt(1 - sin_p * sin_p) * u1[i] + sin_p * u2[i] for i in range(3))
        return half_space(pa, tuple(e), n)

    # the plan contour is not convex (wide part, tapers, narrow tab), so two convex pieces:
    # the tapers up to where the narrow tab starts, and the tab with the end wall
    edges = [(a, b) for a, b in zip(poly, poly[1:] + poly[:1]) if min(a[1], b[1]) > 0]
    tapers = [(a, b) for a, b in edges if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6]
    ends = [(a, b) for a, b in edges if abs(a[1] - b[1]) < 1e-6]
    y_tab = max(max(a[1], b[1]) for a, b in tapers)
    x_tab = min(min(abs(a[0]), abs(b[0])) for a, b in tapers)
    wide = slab & box(-BIG, BIG, -BIG, y_tab, -BIG, BIG)
    for a, b in tapers:
        wide &= lean_out(a, b)
    tab = slab & box(-x_tab, x_tab, y_tab, BIG, -BIG, BIG)
    for a, b in ends:
        tab &= lean_out(a, b)
    return wide + tab


def build_case(snap: bool = True):
    outer = prism_yz(OUTER_PROFILE) & prism_xy(BLOCK_OUTER) & prism_xz(FRONT_VIEW) & prism_arm(ARM_OUTER)
    rebate = (prism_shear(BLOCK_REBATE_Q) & prism_shear(ARM_REBATE_Q)) + prism_shear(USB_NOTCH_Q)
    rebate -= prism_yz(BELOW_LID_PROFILE)
    cavity = prism_yz(CAVITY_PROFILE) & prism_xy(BLOCK_CAVITY) & prism_xy(ARM_CAVITY_PLAN)
    case = outer - top_chamfer_cut() - rebate - cavity - arm_wall_relief()

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

    # USB-C: pocket for the board tab and the shell (open towards the lid, the rim
    # notch above it is part of the rebate) and an opening of the size of the shell
    sc = P.usb_shell_clearance
    case -= box(CAVITY_HW - 0.01, USB_POCKET_X, P.usb_y - P.usb_pocket_w / 2, P.usb_y + P.usb_pocket_w / 2,
                P.pcb_top_z - sc, LEDGE_Z + 0.01)
    case -= xslot(USB_POCKET_X - 0.01, HW + 1, P.usb_y, USB_Z, P.usb_shell_w + 2 * sc, P.usb_shell_h + 2 * sc)

    # hinge: slots for the lid tongues in the arm end wall, floor = ledge
    for x in P.hinge_x:
        hw = P.hinge_w / 2 + P.hinge_side_clearance
        case -= arm_box(x - hw, x + hw, S_END_WALL - 1.0, S_HINGE_TIP + P.hinge_tip_gap,
                        LEDGE_T, LEDGE_T + P.hinge_t + P.hinge_clearance)

    # snap lips on the front wall
    if snap:
        for x0, x1 in P.snap_x:
            case += prism_yz(SNAP_LIP_PROFILE, x0, x1) & outer

    # notch in the front rim for the lid tab, front wall chamfered below it
    tw = P.tab_w / 2 + P.tab_side_clearance
    case -= box(-tw, tw, -1, FRONT_BASE_Y + 0.01, LEDGE_Z, H + 1)
    case -= prism_yz([(-1, LEDGE_Z + 0.01), (P.tab_scoop, LEDGE_Z + 0.01), (-1, LEDGE_Z - P.tab_scoop - 1)], -tw, tw)

    # lid screw bosses in the arm: columns with print-vertical sides
    shift = (LEDGE_T - P.arm_floor_t) * SA / CA
    s0 = LID_SCREW_S - P.lid_boss_margin
    s1 = LID_SCREW_S + P.lid_boss_margin + P.lid_screw_depth * SA / CA
    column = [arm_yz(s0 - shift, P.arm_floor_t - 0.01), arm_yz(s1 - shift, P.arm_floor_t - 0.01),
              arm_yz(s1, LEDGE_T), arm_yz(s0, LEDGE_T)]
    for sx in (-1, 1):
        x = sx * P.lid_screw_x
        case += prism_yz(column, x - P.lid_boss_w / 2, x + P.lid_boss_w / 2)
    for sx in (-1, 1):
        case -= arm_cyl(sx * P.lid_screw_x, LID_SCREW_S, P.screw_pilot_d, LEDGE_T - P.lid_screw_depth, LEDGE_T + 1)

    # desk cable: exit window in the arm end wall, slots and groove for a cable tie
    case -= arm_box(-P.cable_exit_w / 2, P.cable_exit_w / 2, TIE_S, P.arm_length + 1,
                    P.arm_floor_t, P.arm_floor_t + P.cable_exit_h)
    for sx in (-1, 1):
        x = sx * P.tie_slot_x
        case -= arm_box(x - P.tie_slot_w / 2, x + P.tie_slot_w / 2, TIE_S - P.tie_slot_len / 2,
                        TIE_S + P.tie_slot_len / 2, -1, P.arm_floor_t + 1)
    case -= arm_box(-P.tie_slot_x - P.tie_slot_w / 2, P.tie_slot_x + P.tie_slot_w / 2,
                    TIE_S - P.tie_slot_len / 2, TIE_S + P.tie_slot_len / 2, -1, P.tie_groove_depth)
    return case


def build_lid():
    top = prism_yz(OUTER_PROFILE)
    below = prism_yz(BELOW_LID_PROFILE)
    lid = (prism_shear(BLOCK_LID_Q) & prism_shear(ARM_LID_Q) & top) - below
    lid += (prism_shear(LID_EAR_Q) & top) - below

    # room for the snap lips: only the nose at the inner side stays
    for x0, x1 in P.snap_x:
        lid -= prism_yz(SNAP_LID_CUT, x0 - P.snap_side_clearance, x1 + P.snap_side_clearance)

    # tab to open the lid
    lid += box(-P.tab_w / 2, P.tab_w / 2, -P.tab_overhang, FRONT_BASE_Y + P.lid_clearance + 0.5, LEDGE_Z, H)

    # hinge tongues at the arm end
    for x in P.hinge_x:
        lid += arm_box(x - P.hinge_w / 2, x + P.hinge_w / 2, S_END_LID - 3.0, S_HINGE_TIP,
                       LEDGE_T, LEDGE_T + P.hinge_t)

    for sx in (-1, 1):
        x = sx * P.lid_screw_x
        lid -= arm_cyl(x, LID_SCREW_S, P.screw_clear_d, LEDGE_T - 1, T + 1)
        lid -= arm_cyl(x, LID_SCREW_S, P.lid_cbore_d, T - P.lid_cbore_depth, T + 1)
    return lid


def build_keypad():
    """All six caps on one spine, at the assembly position (caps at rest)."""
    arm_y1 = P.ui_y - P.cap_flange_d / 2 + 0.5
    xs = sorted(P.button_x)
    pad = box(xs[0] - P.keypad_spine_overhang, xs[-1] + P.keypad_spine_overhang, SPINE_Y0, SPINE_Y1,
              KEYPAD_BASE_Z - P.keypad_spine_t, KEYPAD_BASE_Z)
    ch = P.cap_top_chamfer
    for x in xs:
        pad += box(x - P.keypad_arm_w / 2, x + P.keypad_arm_w / 2, SPINE_Y0, arm_y1,
                   KEYPAD_BASE_Z - P.keypad_arm_t, KEYPAD_BASE_Z)
        pad += zcyl(x, P.ui_y, P.cap_flange_d, P.face_t, KEYPAD_BASE_Z)
        pad += zcyl(x, P.ui_y, P.cap_d, -P.cap_protrusion + ch, P.face_t + 0.01)
        pad += Pos(x, P.ui_y, -P.cap_protrusion) * Cone(P.cap_d / 2 - ch, P.cap_d / 2, ch,
                                                        align=(Align.CENTER, Align.CENTER, Align.MIN))
    for x, label in zip(P.button_x, P.button_labels):
        pad -= cap_label(x, label)
    return pad


def cap_label(x, label):
    """Engraving in the cap top. The plane is seen from the front: its x axis is the
    user's right (-X), its y axis is up (+Y, towards the table), its normal points at the user."""
    front = Plane(origin=(x, P.ui_y, -P.cap_protrusion), x_dir=(-1, 0, 0), z_dir=(0, 0, -1))
    if label in ("up", "down"):
        w, h = P.label_arrow_w / 2, P.label_arrow_h / 2
        sy = 1 if label == "up" else -1
        sketch = Polygon(*ccw([(-w, -sy * h), (w, -sy * h), (0, sy * h)]), align=None)
    else:
        sketch = Text(label, font_size=P.label_font_size, font=P.label_font, font_style=FontStyle.BOLD,
                      align=(Align.CENTER, Align.CENTER))
    return extrude(front * sketch, amount=-P.label_depth)


def keypad_for_print(pad):
    """Spine and arms on the bed (Z = 0), caps up."""
    return Pos(0, 2 * P.ui_y, KEYPAD_BASE_Z) * Rot(180, 0, 0) * pad


def build_board_envelope():
    """Stand-in for the PCB until a layout exists: board, UI parts, USB shell and
    a slab of the tallest back side part over the whole board."""
    parts = {
        "pcb": box(PCB_X0, PCB_X1, PCB_Y0, PCB_Y1, P.pcb_top_z, PCB_BOTTOM_Z)
        + box(PCB_X1 - 0.01, USB_TAB_X1, P.usb_y - P.usb_tab_w / 2, P.usb_y + P.usb_tab_w / 2,
              P.pcb_top_z, PCB_BOTTOM_Z),
        "back_components": box(PCB_X0, PCB_X1, PCB_Y0, PCB_Y1, PCB_BOTTOM_Z, PCB_BOTTOM_Z + P.back_component_h),
        "oled": box(OLED_X0, OLED_X1, OLED_Y0, OLED_Y1, P.oled_bezel_t, P.oled_bezel_t + P.oled_glass_t),
        "usb": xslot(USB_FRONT_X - P.usb_shell_len, USB_FRONT_X, P.usb_y, USB_Z, P.usb_shell_w, P.usb_shell_h),
    }
    sw = None
    for x in P.button_x:
        b = P.switch_body / 2
        one = box(x - b, x + b, P.ui_y - b, P.ui_y + b, P.pcb_top_z - P.switch_body_h, P.pcb_top_z)
        one += zcyl(x, P.ui_y, 3.5, CAP_PLUNGER_Z, P.pcb_top_z - P.switch_body_h + 0.01)
        sw = one if sw is None else sw + one
    parts["switches"] = sw
    parts["keypad"] = build_keypad()
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
                  "outline": [[bx(x), by(y)] for x, y in (
                      (PCB_X0, PCB_Y0), (PCB_X1, PCB_Y0), (PCB_X1, P.usb_y - P.usb_tab_w / 2),
                      (USB_TAB_X1, P.usb_y - P.usb_tab_w / 2), (USB_TAB_X1, P.usb_y + P.usb_tab_w / 2),
                      (PCB_X1, P.usb_y + P.usb_tab_w / 2), (PCB_X1, PCB_Y1), (PCB_X0, PCB_Y1))],
                  "outline_note": "rectangle plus a tab under the USB-C connector; the four outer corners of the "
                                  "rectangle are rounded with corner_radius, the corners of the tab (outer and inner) "
                                  "with tab_corner_radius",
                  "corner_radius": P.pcb_corner_r, "tab_corner_radius": P.pcb_tab_corner_r,
                  "side_clearance_to_case": round(CAVITY_HW - PCB_X1, 2),
                  "assembly": f"lower the board shifted by {USB_SLIDE:.1f} mm towards -x, then slide it towards +x "
                              "into the USB pocket; nothing may reach beyond the outline on the +x edge"},
        "screws": f"8 x M2.5 x {P.screw_len:g} pan head (ISO 7045 or ISO 14583), 6 for the board, 2 for the lid, "
                  "straight into the plastic",
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
        "usb_c": {"ref_hint": "J1", "side": "B", "edge": "end of the tab on the edge x = board width",
                  "centre_y": by(P.usb_y), "tab_end_x": bx(USB_TAB_X1), "tab_width": P.usb_tab_w,
                  "shell_front_x": bx(USB_FRONT_X), "shell_front_beyond_tab_edge": P.usb_overhang},
        "keypad_keepout_front": {"note": "printed keypad between front panel and board: spine along the front "
                                         "edge, one arm from the spine to every button",
                                 "spine": {"x0": bx(min(P.button_x) - P.keypad_spine_overhang),
                                           "x1": bx(max(P.button_x) + P.keypad_spine_overhang),
                                           "y0": by(SPINE_Y0), "y1": by(SPINE_Y1)},
                                 "arm_width": P.keypad_arm_w,
                                 "max_part_height": round(P.pcb_top_z - KEYPAD_BASE_Z - 0.5, 2)},
        "height_limits": {
            "front_side_general": round(P.pcb_top_z - P.face_t, 2),
            "front_side_at_back_edge": front_height_limit(PCB_Y1),
            "front_side_full_height_until_y": by(P.block_depth - (P.arm_floor_t - P.face_t * CA) / SA) ,
            "back_side_free": round(LEDGE_Z - PCB_BOTTOM_Z, 2),
            "back_side_max_part": P.back_component_h,
        },
    }


# --------------------------------------------------------------------------
# Checks and export
# --------------------------------------------------------------------------
def volume(shape) -> float:
    return 0.0 if shape is None else float(shape.volume)


def main() -> None:
    case, lid, keypad = build_case(), build_lid(), build_keypad()
    env = build_board_envelope()

    print(f"BekantX enclosure {REVISION}")
    for name, part in (("case", case), ("lid", lid), ("keypad", keypad)):
        bb = part.bounding_box()
        print(f"  {name:11s} size {bb.size.X:7.2f} x {bb.size.Y:6.2f} x {bb.size.Z:6.2f}  "
              f"volume {part.volume / 1000:6.1f} cm3  valid {part.is_valid}  solids {len(part.solids())}")

    print("fit check (intersection volume in mm3, must be 0):")
    worst = 0.0
    for a_name, a in (("case", case), ("lid", lid)):
        for b_name, b in env.items():
            v = volume(a & b)
            worst = max(worst, v)
            print(f"  {a_name:6s} x {b_name:16s} {v:8.3f}")
    for b_name in ("switches", "pcb", "oled"):
        v = volume(env["keypad"] & env[b_name])
        worst = max(worst, v)
        print(f"  keypad x {b_name:16s} {v:8.3f}")
    v = volume(case & lid)
    worst = max(worst, v)
    print(f"  case   x lid              {v:8.3f}")

    # the lid must swing in and out: rotate it about the tongue tips
    print("lid motion (rotation about the hinge, intersection with the case in mm3):")
    hinge = Axis((0, PIVOT[0], PIVOT[1]), (1, 0, 0))
    case_plain = build_case(snap=False)
    lift_per_deg = math.radians(1) * math.hypot(PIVOT[0] - FRONT_BASE_Y, PIVOT[1] - LEDGE_Z)
    for deg in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
        moved = lid.rotate(hinge, -deg)
        v_plain, v_snap = volume(case_plain & moved), volume(case & moved)
        worst = max(worst, v_plain)
        print(f"  {deg:4.1f} deg (front edge lifted {deg * lift_per_deg:4.1f})  without lips {v_plain:7.3f}"
              f"   with lips {v_snap:7.3f}")
    # then it is pulled out of the hinge slots along the tilted arm, opening further on the way
    for deg, d in ((6.0, 1.0), (6.0, 2.5), (10.0, 4.0), (15.0, 8.0)):
        ang = A - math.radians(deg)
        moved = Pos(0, -d * math.cos(ang), -d * math.sin(ang)) * lid.rotate(hinge, -deg)
        v = volume(case & moved)
        worst = max(worst, v)
        print(f"  {deg:4.1f} deg, pulled out of the hinge by {d:3.1f}            {v:7.3f}")

    # the board must reach its place: lowered with an offset to -X, then slid to +X
    print("board assembly (board with USB shell against the case, mm3):")
    board = env["pcb"] + env["usb"]
    for dx, dz in ((-USB_SLIDE, 12.0), (-USB_SLIDE, 8.0), (-USB_SLIDE, 4.0), (-USB_SLIDE, 1.0), (-USB_SLIDE, 0.0),
                   (-USB_SLIDE * 0.5, 0.0)):
        v = volume(case & (Pos(dx, 0, dz) * board))
        worst = max(worst, v)
        print(f"  dx {dx:5.2f}  dz {dz:5.1f}   {v:7.3f}")

    print("clearances:")
    print(f"  pcb to side walls        {CAVITY_HW - PCB_X1:.2f}")
    print(f"  pcb to front wall        {PCB_Y0 - P.wall:.2f}")
    y_arm = P.block_depth + (P.pcb_top_z * CA - P.arm_floor_t) / SA
    print(f"  pcb back edge to arm     {y_arm - PCB_Y1:.2f} (at the board front side)")
    print(f"  back side free height    {LEDGE_Z - PCB_BOTTOM_Z:.2f} (parts up to {P.back_component_h})")
    print(f"  front side free height   {P.pcb_top_z - P.face_t:.2f}")
    print(f"  usb shell front          {HW - USB_FRONT_X:.2f} behind the wall surface, "
          f"wall in front of the tab {P.usb_wall_t:.2f}")
    engage_board = P.screw_len - P.pcb_t
    engage_lid = P.screw_len - (P.lid_t - P.lid_cbore_depth)
    print(f"screws M2.5 x {P.screw_len:g}: {engage_board:.1f} in the board bosses (hole "
          f"{P.pcb_top_z - P.pilot_floor:.1f} deep), {engage_lid:.1f} in the lid columns (hole {P.lid_screw_depth:.1f} deep)")
    assert engage_board < P.pcb_top_z - P.pilot_floor - 0.5 and engage_lid < P.lid_screw_depth - 0.5
    print("lid snap:")
    print(f"  draft of the lid edges   {math.degrees(math.atan(K)):.1f} deg from Z")
    print(f"  lip beyond the wall      {SNAP_P:.2f}, overlap with the lid nose {SNAP_P - C_RHO:.2f}, "
          f"squeeze {P.snap_compress:.2f}")
    print(f"  lid nose height          {SNAP_TAU_NOSE / KK:.2f} in Z, lip root {SNAP_TAU_ROOT / KK:.2f} above the ledge")
    cy, cz = RHO[0] - TAN_PSI * TAU[0], RHO[1] - TAN_PSI * TAU[1]
    print(f"  catch face overhang      {math.degrees(math.atan2(abs(cy), abs(cz))):.1f} deg from vertical "
          "when printed face down")

    # case in assembly coordinates (= print position); lid and keypad lowered onto the bed
    exports = (("Case", case), ("Lid", Pos(0, 0, -LEDGE_Z) * lid), ("Keypad", keypad_for_print(keypad)))
    for name, part in exports:
        base = CAD_DIR / f"BekantX_{name}_{REVISION}"
        export_step(part, str(base.with_suffix(".step")))
        export_stl(part, str(base.with_suffix(".stl")), tolerance=0.02, angular_tolerance=0.1)
    build = CAD_DIR.parent / "build" / "cad"
    build.mkdir(parents=True, exist_ok=True)
    board = None
    for part in env.values():
        board = part if board is None else board + part
    export_stl(board, str(build / "board_envelope.stl"), tolerance=0.05)
    export_stl(keypad, str(build / "keypad_in_place.stl"), tolerance=0.05)
    export_stl(lid, str(build / "lid_in_place.stl"), tolerance=0.05)

    (CAD_DIR / "board_interface.json").write_text(json.dumps(board_interface(), indent=2) + "\n", encoding="utf-8")
    (build / "params.json").write_text(json.dumps(asdict(P), indent=2) + "\n", encoding="utf-8")
    if worst > 1e-3:
        raise SystemExit(f"FIT CHECK FAILED: interference {worst:.3f} mm3")
    print("fit check passed")


if __name__ == "__main__":
    main()
