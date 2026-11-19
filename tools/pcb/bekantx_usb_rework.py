"""Re-route the USB-C connector J1: VBUS moves to F.Cu, D+ / D- / CC1 / CC2 run straight on B.Cu (PR #5 feedback).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/bekantx_usb_rework.py <in.kicad_pcb> <out.kicad_pcb>

Feedback (owner, 2026-11-18): the two Y-shaped VBUS tracks on B.Cu lay between the connector pads and the ESD
protection U4. D+ and D- had to go around them (D+ 25 mm round the connector, D- over two vias and F.Cu, CC1/CC2
over F.Cu hops). "Take VBUS to another layer and route D+/D- straight from the signal lines."

New routing (board mm, J1 pads at x 125.88..127.33, pitch 0.5, on B.Cu):
- VBUS: both J1 VBUS pad groups leave to the left by a 0.4 mm stub to a via (125.3, y); on F.Cu a 0.4 mm bar joins
  them, a branch goes to a via 1.2 mm in front of U4 pin 5 and a second branch to a via in front of C35 pin 1
  (R13 stands in the way on B.Cu). On B.Cu only the short stubs from these vias to the pads remain.
- D+: pad B6 runs straight to U4 pin 6; A6 is joined to B6 behind the pad ends (x 127.65), where no other pad sits.
- D-: pad B7 runs straight to U4 pin 4; A7 is joined to B7 in front of the pad ends (x 125.5), around nothing.
  Both end with a 45 degree jog 0.25 mm in front of the U4 pad so that they enter its pad on the centre line.
- CC1 / CC2: straight L shapes to R13 / R12 on B.Cu.
The old tracks and vias of the four signal nets and the VBUS segments east of x 122 are removed; the rest of the
VBUS chain (C35, TP13, D3) is kept. Afterwards: bekantx_finish.py (zones), DRC.
"""
import sys

import pcbnew

from bekantx_layout import P, add_track, add_via, unP

B, F = pcbnew.B_Cu, pcbnew.F_Cu
SIGNAL_NETS = ("Net-(J1-D+-PadA6)", "Net-(J1-D--PadA7)", "Net-(J1-CC1)", "Net-(J1-CC2)")
VBUS_VIA = (0.5, 0.3)
X_PAD = 126.605                               # centre of the J1 pads
X_DPLUS_JOIN = 127.65                         # A6/B6 joint behind the pad ends (0.195 mm from the A7 pad)
X_DMINUS_JOIN = 125.5                         # A7/B7 joint in front of the pad ends (0.255 mm from the A6 pad)
X_VIA = 125.3                                 # VBUS vias of the connector
U4 = {"D-": (122.438, 25.05), "VBUS": (122.438, 26.0), "D+": (122.438, 26.95)}


def pad(board, ref, num):
    p = board.FindFootprintByReference(ref).FindPadByNumber(num)
    return unP(p.GetPosition())


def main(src, dst):
    board = pcbnew.LoadBoard(str(src))
    for num, (x, y) in {"B7": (X_PAD, 25.25), "A6": (X_PAD, 25.75), "A7": (X_PAD, 26.25), "B6": (X_PAD, 26.75),
                        "A5": (X_PAD, 24.75), "B5": (X_PAD, 27.75), "A4": (X_PAD, 23.55), "A9": (X_PAD, 28.45)}.items():
        p = pad(board, "J1", num)
        assert abs(p[0] - x) < 0.01 and abs(p[1] - y) < 0.01, (num, p)
    for ref, num, xy in (("U4", "4", U4["D-"]), ("U4", "5", U4["VBUS"]), ("U4", "6", U4["D+"]),
                         ("R13", "1", None), ("R12", "1", None), ("C35", "1", None)):
        p = pad(board, ref, num)
        assert xy is None or (abs(p[0] - xy[0]) < 0.01 and abs(p[1] - xy[1]) < 0.01), (ref, num, p)
    r13, r12, c35 = pad(board, "R13", "1"), pad(board, "R12", "1"), pad(board, "C35", "1")

    # ---- what goes: all tracks and vias of the four signal nets, the VBUS tracks east of x 122
    old = []
    for t in board.GetTracks():
        if t.GetNetname() in SIGNAL_NETS:
            old.append(t)
        elif t.GetNetname() == "VBUS" and t.GetClass() == "PCB_TRACK" and max(unP(t.GetStart())[0], unP(t.GetEnd())[0]) > 122.0:
            old.append(t)
    n_old = len(old)

    # ---- D-: B7 straight on, A7 joined to it in front of the pads
    dm = U4["D-"]
    add_track(board, "Net-(J1-D--PadA7)", [(X_PAD, 25.25), (123.55, 25.25), (123.35, dm[1]), dm], 0.25, B, False)
    add_track(board, "Net-(J1-D--PadA7)", [(X_PAD, 26.25), (X_DMINUS_JOIN + 0.25, 26.25), (X_DMINUS_JOIN, 26.0),
                                           (X_DMINUS_JOIN, 25.5), (X_DMINUS_JOIN + 0.25, 25.25)], 0.25, B, False)
    # ---- D+: B6 straight on, A6 joined to it behind the pad ends
    dp = U4["D+"]
    add_track(board, "Net-(J1-D+-PadA6)", [(X_PAD, 26.75), (123.55, 26.75), (123.35, dp[1]), dp], 0.25, B, False)
    add_track(board, "Net-(J1-D+-PadA6)", [(X_PAD, 25.75), (X_DPLUS_JOIN, 25.75), (X_DPLUS_JOIN, 26.75), (X_PAD, 26.75)],
              0.25, B, False)
    # ---- CC1 / CC2
    add_track(board, "Net-(J1-CC1)", [(X_PAD, 24.75), (r13[0], 24.75), r13], 0.15, B, False)
    add_track(board, "Net-(J1-CC2)", [(X_PAD, 27.75), (r12[0], 27.75), r12], 0.15, B, False)
    # ---- VBUS on F.Cu
    vu = (123.7, U4["VBUS"][1])               # via in front of U4 pin 5
    vc = (122.8, c35[1])                      # via in front of C35 pin 1 (R13 pad starts at x 123.3)
    for xy in ((X_VIA, 23.55), (X_VIA, 28.45), vu, vc):
        add_via(board, "VBUS", xy, *VBUS_VIA, locked=False)
    add_track(board, "VBUS", [(X_PAD, 23.55), (X_VIA, 23.55)], 0.4, B, False)
    add_track(board, "VBUS", [(X_PAD, 28.45), (X_VIA, 28.45)], 0.4, B, False)
    add_track(board, "VBUS", [(X_VIA, 23.55), (X_VIA, 28.45)], 0.4, F, False)                    # bar
    add_track(board, "VBUS", [(X_VIA, 23.55), (vc[0] + 0.35, 23.55), vc], 0.4, F, False)         # to C35
    add_track(board, "VBUS", [(X_VIA, U4["VBUS"][1]), vu], 0.4, F, False)                        # to U4
    add_track(board, "VBUS", [vu, U4["VBUS"]], 0.4, B, False)
    add_track(board, "VBUS", [c35, vc], 0.4, B, False)

    for t in old:                              # removals last: pcbnew proxies break after Remove()
        board.Remove(t)
    pcbnew.SaveBoard(str(dst), board)
    print(f"J1 re-routed: {n_old} old tracks/vias removed, VBUS on F.Cu with 4 vias, D+/D-/CC1/CC2 straight on B.Cu")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
