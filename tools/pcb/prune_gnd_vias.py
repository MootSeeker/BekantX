"""Remove GND vias that connect nothing on the outer layers (after gnd_trim.py bared most of the board).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/prune_gnd_vias.py <in.kicad_pcb> <out.kicad_pcb>

A GND via stays when a track or a pad of the net touches it, or when it lies in the filled GND pour of F.Cu or
B.Cu (it stitches that piece to the In2 plane). Every other GND via only tied the outer copper that is no longer
there. Zones must be filled in the input (gnd_trim.py saves them filled). Vias are removed at the very end in one go
(pcbnew proxies break after Remove()).
"""
import sys

import pcbnew

from bekantx_layout import P, unP
from pcb_geom import OUTER, uid

sys.stdout.reconfigure(line_buffering=True)


def main(src, dst):
    board = pcbnew.LoadBoard(str(src))
    fills = {}
    for z in board.Zones():
        if z.GetZoneName().startswith(("GND top", "GND bottom")) and not z.GetIsRuleArea():
            lay = z.GetFirstLayer()
            fills.setdefault(lay, []).append(z.GetFilledPolysList(lay))
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND" and t.GetLayer() in OUTER]
    pads = [(p, lay) for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == "GND" for lay in OUTER if p.IsOnLayer(lay)]
    drop, kept = [], 0
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]:
        pt = v.GetPosition()
        used = any(v.HitTest(t.GetStart()) or v.HitTest(t.GetEnd()) for t in tracks)
        used = used or any(p.HitTest(pt) or v.HitTest(p.GetPosition()) for p, _l in pads)
        used = used or any(f.Contains(pt) for lst in fills.values() for f in lst)
        if used:
            kept += 1
        else:
            drop.append(v)
    where = [unP(v.GetPosition()) for v in drop]
    for v in drop:
        board.Remove(v)
    pcbnew.SaveBoard(str(dst), board)
    print(f"GND vias kept {kept}, removed {len(where)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
