"""Placement of the BekantX board (called by bekantx_layout.py).

Fixed positions come from the enclosure (CAD/board_interface.json) or are chosen by hand for the large
parts; everything else is placed by Placer.auto() next to the pads it connects to, in the order below
(order = priority: decoupling and switching loops first).

Sides: F.Cu faces the front panel (buttons, OLED connector, status LEDs). All other parts are on B.Cu,
where the enclosure leaves 7.0 mm.
"""
import math

import pcbnew

from bekantx_layout import LATE_VIA_REFS, P, add_rule_area, add_track, add_zone, drop_plane_vias

WIFI = (0.6, 0.6, 34.0, 37.4)          # region of the ESP32-C3 block on B.Cu


PLACER = None      # set by place(); used by fixed() to check for overlaps


def fixed(part, x, y, side, test, check=True):
    """Put a part at x, y and pick the rotation for which test(part) is true; fail on an overlap."""
    for rot in (0, 90, 180, 270):
        part.put(x, y, rot, side)
        if test(part):
            if check and PLACER is not None:
                from bekantx_layout import overlap
                hit = [b for b in PLACER.boxes(side, skip=part) if overlap(part.box(), b)]
                if hit:
                    raise RuntimeError(f"{part.ref}: fixed position {x}, {y} overlaps {hit[:3]}")
            return part
    raise RuntimeError(f"{part.ref}: no rotation satisfies the constraint")


def best_rot(pl, part, x, y, side, near=None):
    """Put a part at x, y with the rotation that gives the shortest connections."""
    part.cache(side)
    t = pl.targets(part, {k: [v] for k, v in (near or {}).items()})
    best = None
    for rot in (0, 90, 180, 270):
        cost = 0.0
        for net, tp in t.items():
            cost += min(abs(px - qx) + abs(py - qy) for px, py in part.pad_xy(net, x, y, rot) for qx, qy in tp)
        if best is None or cost < best[0]:
            best = (cost, rot)
    return part.put(x, y, best[1])


def place(board, pl, parts, iface):
    global PLACER
    PLACER = pl
    p = parts
    W, H = pl.W, pl.H

    # ------------------------------------------------------------ front side, given by the enclosure
    for b in iface["buttons"]:
        sw = p[b["ref_hint"]]
        # footprint origin is pad 1; the body centre is at (3.25, 2.25)
        sw.put(b["x"] - 3.25, b["y"] - 2.25, 0, "F")
    for led in iface["status_leds"]:
        p[led["ref_hint"]].put(led["x"], led["y"], 0, "F")
        d = led["baffle_keepout_d"] / 2
        pl.keepout("F", (led["x"] - d, led["y"] - d, led["x"] + d, led["y"] + d), "light baffle")
    # OLED: the FPC leaves the glass at x = 66.7, is folded back under the glass (22 mm tail) and enters
    # the connector from +x with the contacts facing the board. Pin 1 of the FPC is on the +y side.
    oled = iface["oled"]
    fixed(p["J3"], 50.0, oled["fpc_exit_centre_y"], "F",
          lambda q: q.pad(1)[1] > q.pad(16)[1] and q.pad_xy("GND")[0][0] > q.pad(1)[0] - 10 and
          max(x for x, _ in q.pad_xy("GND")) > q.pad(1)[0] + 2)
    assert abs(p["J3"].pad(1)[1] - (oled["fpc_exit_centre_y"] + 3.75)) < 0.01
    # FPC tail lies on the board in front of the connector: keep the front side free there
    pl.keepout("F", (54.5, 11.5, 68.5, 21.5), "OLED FPC")

    # ------------------------------------------------------------ back side, large parts
    usb = iface["usb_c"]
    # shell front 1.5 mm beyond the end of the tab (footprint: shell front at +3.65 from the origin)
    fixed(p["J1"], usb["shell_front_x"] - 3.65, usb["centre_y"], "B", lambda q: q.pad("A6")[0] < q.x - 3)
    # desk connector: angled header, pins and the cable housing point to +x and stay above the board
    j10 = fixed(p["J10"], 68.6, 30.0, "B", lambda q: q.box()[2] > q.x + 8, check=False)   # moved below
    j10.put(68.6, 30.0 + (22.0 - min(j10.pad(1)[1], j10.pad(3)[1])), j10.rot)     # pads span y = 22.0 .. 27.08
    pl.keepout("B", (70.2, 20.3, 90.0, 28.8), "J10 housing and cable")
    # input protection directly at the VDESK pin, on the side away from the STM32: fuse, TVS, then D4
    inp = (67.4, 29.2, 82.0, 37.4)
    pl.auto("F1", side="B", near=(70.8, 30.6), radius=3, region=inp)
    pl.auto("C28", side="B", radius=6, region=inp)
    pl.auto("D6", side="B", radius=8, region=inp)
    # input electrolytics along the front edge
    for i, ref in enumerate(("C40", "C50", "C51", "C52")):
        fixed(p[ref], 86.0 + 9.6 * i, 6.7, "B", lambda q: q.pad(1)[1] > q.pad(2)[1] and abs(q.pad(1)[0] - q.x) < 0.1)
    # USB mux selector (slide switch, only reachable with the lid off)
    fixed(p["SW2"], 74.6, 6.6, "B", lambda q: q.box()[2] - q.box()[0] > q.box()[3] - q.box()[1])
    # antenna in the board corner (x = 0, y = H), 6.5 x 6.5 mm free of copper, feed towards the ground
    fixed(p["AE1"], 2.5, H - 4.05, "B", lambda q: q.pad(1)[1] < q.pad(2)[1] and abs(q.pad(1)[0] - q.x) < 0.1)
    fx, fy = p["AE1"].pad(1)
    add_rule_area(board, [(0, H - 6.5), (fx - 0.9, H - 6.5), (fx - 0.9, fy + 0.95), (fx + 0.9, fy + 0.95),
                          (fx + 0.9, H - 6.5), (6.5, H - 6.5), (6.5, H), (0, H)], "antenna clearance",
                  [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu], footprints=False)
    pl.keepout("FB", (0, H - 6.5, 6.5, H), "antenna")
    # ICs with a hand-picked position; the rotation follows from their connections
    best_rot(pl, p["U7"], 57.0, 13.6, "B", near={"LINBUS": p["J10"].pad(3)})
    pl.auto("C70", side="B", near={"+12V": p["U7"].pad(7)}, radius=5)          # VSUP decoupling at the pin
    best_rot(pl, p["U9"], 100.5, 24.0, "B", near={"VCC": (97.0, 21.0), "Net-(U9-SW)": (104.0, 24.0)})
    # 12 V buck (LV2862, asynchronous) between the cable housing (y < 28.8) and the board edge, as one compact
    # cell (review 2026-11-15, Majors 1 and 2; AN-1149): VIN, SW and SHDN on the upper pin row (pins 4-6),
    # CB, GND and FB on the lower row (1-3).
    #   C25 (input) right above VIN pin 5, its GND pad next to it -> short loop C25 - VIN - switch
    #   C26 (boot) between pin 1 (CB) and pin 6 (SW), directly beside the IC
    #   D20 (catch diode) right of C26, cathode at the top towards SW, anode (GND) at the bottom
    #   L20 right of D20; output capacitors right of L20
    fixed(p["U20"], 83.0, 33.4, "B", lambda q: q.pad(5)[1] < q.y and q.pad(6)[0] > q.x)
    fixed(p["C25"], 83.0, 30.05, "B", lambda q: q.pad(1)[0] < q.x and abs(q.pad(1)[1] - q.y) < 0.1)
    fixed(p["C26"], 85.78, 33.4, "B", lambda q: q.pad(1)[1] > q.y and abs(q.pad(1)[0] - q.x) < 0.1)
    fixed(p["D20"], 88.65, 33.4, "B", lambda q: q.pad(1)[1] < q.y and abs(q.pad(1)[0] - q.x) < 0.1)
    fixed(p["L20"], 94.05, 33.4, "B", lambda q: q.pad(1)[0] < q.x and abs(q.pad(1)[1] - q.y) < 0.1)
    best_rot(pl, p["U4"], 121.3, 26.0, "B")
    best_rot(pl, p["U8"], 115.3, 25.6, "B")

    a = lambda ref, **k: pl.auto(ref, **k)
    pin = lambda u, n: p[u].pad(n)
    inflate = lambda b, m: (b[0] - m, b[1] - m, b[2] + m, b[3] + m)

    # ------------------------------------------------------------ 12 V buck (U20) and 3.3 V buck (U9): compact loops first
    a("R22", side="B", radius=6, near={"U2_FB": pin("U20", 3)})              # feedback divider at the FB pin
    a("R21", side="B", radius=6, near={"U2_FB": pin("U20", 3)})
    a("R20", side="B", radius=8)
    # U9 (LMR51610 data sheet 8.4.1): input capacitor as close as possible to VIN/GND, both feedback resistors
    # close to FB. Placed before anything else around U9 (review 2026-11-15, Major 3 and Minor 5).
    a("C15", side="B", near={"VCC": pin("U9", 5), "GND": pin("U9", 2)}, radius=4)
    a("C49", side="B", near={"VCC": pin("U9", 5)}, radius=5)
    a("C16", side="B", radius=6)
    a("R42", side="B", near={"U9_FB": pin("U9", 3)}, radius=5)
    a("R41", side="B", near={"U9_FB": pin("U9", 3)}, radius=5)
    # D4 (VIN -> VCC) between the TVS and the regulators, right of the cable housing
    a("D4", side="B", near={"VIN": (90.5, 24.5), "VCC": (95.0, 24.5)}, radius=6)
    a("C24", side="B", near={"VCC": pin("D4", 1)})
    a("C27", side="B", near={"+12V": pin("L20", 2)}); a("C34", side="B", near={"+12V": pin("L20", 2)})
    a("L4", side="B", radius=12, step=0.5)
    a("R40", side="B")
    a("C17", side="B", near={"+3V3": pin("L4", 2)})
    a("C18", side="B", near={"+3V3": pin("L4", 2)})

    # ------------------------------------------------------------ ESP32-C3 block
    # U2 sits between the pin columns of SW3 and SW4. Seen on this side: pins 1-8 on the left (pin 1 lowest),
    # 9-16 on top (GPIOs to the STM32), 17-24 on the right (flash), 25-32 at the bottom (USB, UART, crystal, VDDA).
    # its courtyard corners touch the 0.3 mm margin around the THT pads of SW3/SW4 (no copper conflict, DRC clean)
    fixed(p["U2"], 16.0, 22.3, "B", lambda q: q.pad(1)[0] < q.x - 2 and q.pad(1)[1] > q.y + 1, check=False)
    w = dict(side="B", region=WIFI)
    # matching network (C8 | L2 | C9) at the antenna, 50 ohm line from U2 pin 1 to it
    a("C9", **w, near={"Net-(AE1-FEED)": (fx + 2.8, fy - 2.3)}, radius=3)
    a("L2", **w, radius=4)
    a("C8", **w, near={"Net-(U2-LNA_IN)": pin("L2", 1)}, radius=4)
    pl.keepout("B", (0.6, pin("C9", 1)[1] - 0.6, pin("C9", 1)[0] + 0.3, H - 6.5), "antenna feed")
    (x1, y1), (x2, y2) = pin("U2", 1), pin("C8", 1)
    dg = min(x1 - 0.7 - x2, y2 - y1)
    rf_line = [(x1, y1), (x1 - 0.7, y1), (x1 - 0.7 - dg, y1 + dg), (x2, y2)]
    for (ax, ay), (bx, by) in zip(rf_line, rf_line[1:]):
        n = max(1, int((abs(bx - ax) + abs(by - ay)) / 0.4))
        for i in range(n + 1):
            qx, qy = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
            pl.keepout("B", (qx - 0.75, qy - 0.75, qx + 0.75, qy + 0.75), "RF line")
    # VDD3P3 (pins 2, 3): C7 right above the RF line keep-out, its +3.3VA pad about 2 mm from pin 3; L1 behind it
    fixed(p["C7"], 10.9, 22.0, "B", lambda q: q.pad(1)[0] > q.x and abs(q.pad(1)[1] - q.y) < 0.1)
    a("L1", **w, near={"+3.3VA": pin("C7", 1)}, radius=4)
    # VDDA decoupling and crystal below the bottom pin row; 1.6 mm stay free under U2 for the escape of
    # USB and UART (pins 25-28); everything else keeps 1.2 mm distance to U2
    fixed(p["C1"], 14.2, 27.3, "B", lambda q: abs(q.pad(1)[0] - q.x) < 0.1 and q.pad(1)[1] < q.pad(2)[1])
    best_rot(pl, p["Y1"], 17.5, 28.4, "B")
    pl.keepout("B", inflate(p["U2"].box(), 1.2), "U2 escape ring")
    a("R1", **w, near={"Net-(U2-XTAL_P)": pin("U2", 30)}, radius=4)          # series resistor at the XTAL_P pin
    a("C11", **w); a("C10", **w)
    a("C3", **w, near={"+3V3": pin("U2", 11)})
    a("C14", **w)                                                            # VDD_SPI
    a("C2", **w, near={"+3V3": pin("U2", 17)})
    best_rot(pl, p["U3"], 29.0, 25.6, "B")                                   # flash: 4 mm to U2 for the six SPI lines
    pl.keepout("B", (21.6, 21.2, 24.6, 28.2), "flash lines")
    a("C13", **w)
    a("C6", **w, near={"+3V3": pin("U2", 32)})
    a("C4", **w, near={"+3V3": pin("U2", 31)})
    a("C5", **w, near={"+3V3": pin("U2", 17)})
    for r in ("R2", "C12", "R6", "R4", "R5", "R3", "R7", "R8", "R43"):
        a(r, **w)
    a("SW1", **w); a("SW9", **w)
    for r in ("TP14", "TP15", "TP16"):
        a(r, **w)

    # ------------------------------------------------------------ STM32 and what belongs to it
    mid = (30.0, 0.6, 68.0, 37.4)
    # not behind the pads of J3: the display signals come through vias next to those pads
    best_rot(pl, p["U1"], 56.5, 27.5, "B", near={"DISP_SCK": p["J3"].pad(15), "LINBUS": (70, 30)})
    a("C72", side="B", near={"+3V3": pin("U1", 4)})
    a("C73", side="B", near={"+3V3": pin("U1", 4)})
    pl.keepout("B", inflate(p["U1"].box(), 3.0), "U1 escape ring")      # 32 pins, all leave: 3 mm for the fan-out
    a("C41", side="B", region=mid)
    pl.keepout("B", p["J3"].box(), "J3 pads: no holes of J2 here")
    a("J2", side="B", region=mid, near=(46.5, 30.5), margin=0.8)
    a("U5", side="B", region=mid)
    a("C38", side="B", near={"+3V3": pin("U5", 4)})
    for r in ("R31", "R32", "R33", "R46", "TP17", "TP18"):
        a(r, side="B", region=mid)

    # OLED support parts on the front side, next to the connector pads (short charge-pump loops)
    of = dict(side="F", region=(33.0, 4.0, 46.4, 29.0))      # leaves a channel for vias at the J3 pads
    a("C45", **of); a("C46", **of); a("C47", **of); a("C48", **of)
    a("C43", **of, near={"+3V3": pin("J3", 14)})
    a("C44", **of, near={"+3V3": pin("J3", 5)})
    a("R44", **of)

    # ------------------------------------------------------------ buttons: RC filter at each switch
    for sw, r, c, rp, tp in (("SW3", "R17", "C30", "R19", "TP19"), ("SW4", "R18", "C31", "R23", "TP20"),
                             ("SW5", "R24", "C32", "R26", "TP22"), ("SW6", "R25", "C33", "R27", "TP21"),
                             ("SW7", "R34", "C36", "R35", "TP23"), ("SW8", "R36", "C37", "R37", "TP24")):
        ctr = (p[sw].x + 3.25, p[sw].y + 2.25)
        net = [n for n in p[sw].nets if n != "GND"][0]
        a(c, side="B", near={net: ctr}, radius=6)
        a(r, side="B", radius=6)
        a(rp, side="B", radius=8)
        a(tp, side="B", radius=8)

    # ------------------------------------------------------------ desk input, protection, LIN
    a("D7", side="B", radius=8, near={"LINBUS": p["J10"].pad(3)})    # ESD diode right at the connector
    # (C28, F1 and D6 are placed right after J10, see above)
    a("C71", side="B"); a("R71", side="B"); a("D70", side="B")
    a("R45", side="B"); a("R70", side="B")

    # ------------------------------------------------------------ USB
    usbr = (108.0, 12.5, 128.4, 37.4)
    a("R13", side="B", region=usbr); a("R12", side="B", region=usbr)
    a("C35", side="B", region=usbr)
    a("L3", side="B", region=usbr)
    a("D3", side="B", near={"VBUS": pin("U4", 5), "VCC": pin("U9", 5)}, radius=16)
    a("C29", side="B", near={"+3V3": pin("U8", 10)})

    # ------------------------------------------------------------ status LEDs (front) and their parts
    a("R14", side="B"); a("R15", side="B"); a("R16", side="B")
    a("C42", side="B", near={"+3V3": pin("D1", 4)})
    for r in ("TP8", "TP10", "TP12"):
        a(r, side="B", near={"VCC": pin("D4", 1)}, radius=16)
    a("TP11", side="B", near={"+3V3": pin("L4", 2)}); a("TP9", side="B"); a("TP13", side="B")

    for pad in p["J1"].fp.Pads():          # short, wide pads: connect them solidly to the pour
        if pad.GetNetname() == "GND":
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    # ------------------------------------------------------------ hand-routed, locked tracks
    # RF: U2.1 - C8 (shunt) - L2 (series) - C9 (shunt) - antenna feed, all on B.Cu over the GND plane.
    # 0.35 mm is about 50 ohm on the 0.21 mm prepreg of JLC04161H-7628 (estimate, not field-solved).
    rf = lambda net, pts, w=0.35: add_track(board, net, pts, w, pcbnew.B_Cu)
    l2a, l2b, c9 = p["L2"].pad(1), p["L2"].pad(2), p["C9"].pad(1)
    rf("Net-(U2-LNA_IN)", rf_line[:2], 0.25)          # leaves the 0.5 mm pitch pad at pad width
    rf("Net-(U2-LNA_IN)", rf_line[1:])
    rf("Net-(U2-LNA_IN)", [rf_line[-1], l2a])
    gnd9 = p["C9"].pad(2)                  # approach C9 pad 1 on the side away from its GND pad
    seg_d = lambda a, b: min(math.dist(gnd9, (a[0] + (b[0] - a[0]) * i / 20, a[1] + (b[1] - a[1]) * i / 20)) for i in range(21))
    ways = [[l2b, c9], [l2b, (l2b[0], c9[1]), c9], [l2b, (c9[0], l2b[1]), c9]]
    rf("Net-(AE1-FEED)", max(ways, key=lambda wy: min(seg_d(a, b) for a, b in zip(wy, wy[1:]))))
    rf("Net-(AE1-FEED)", [c9, (fx + 1.5, c9[1]), (fx, c9[1] + 1.5), (fx, fy)])

    # No fan-out for the QFNs here. Tried and measured (open connections after the signal stage):
    # free pins 13, locked exit stubs 23, alternating fan-out vias 30. Freerouting cannot move fixed
    # items, so the pins stay free and the touch-up router does the rest.

    # plane connections: one via per SMD pad of GND and +3V3, via arrays in the exposed pads
    n, failed = drop_plane_vias(board, iface, ep_grid={"U1": (33, 3), "U2": (33, 3)}, skip=LATE_VIA_REFS)
    print(f"plane vias: {n}, pads without via: {failed}")

    # ------------------------------------------------------------ zones
    ol = [tuple(q) for q in iface["board"]["outline"]]
    # Both inner layers are planes; the router treats planes as obstacles and puts no tracks there.
    # Tried: In1 as a mixed layer without the +3V3 plane during routing. The router then moved 1.1 m of
    # track onto In1 (more than on B.Cu) and left as many signals open, so the plane stays.
    add_zone(board, "+3V3", pcbnew.In1_Cu, ol, "+3V3 plane", solid=True)
    add_zone(board, "GND", pcbnew.In2_Cu, ol, "GND plane", solid=True)
    # inner layers are planes only: no tracks there (vias and fills are allowed)
    # The outer GND pours and the "no tracks on inner layers" rule are added after routing
    # (bekantx_finish.py): Freerouting places no vias through a wire keep-out, and it treats pours as planes.
