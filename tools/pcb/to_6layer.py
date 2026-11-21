"""Turn the 4-layer BekantX board into 6 layers (user decision 2026-11-21: one track direction per layer; on 4 layers
86 connections stayed open and the directions mixed, see Vault/Offene Punkte).

  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/pcb/to_6layer.py <in.kicad_pcb> <out.kicad_pcb>

  F.Cu   signal, vertical runs            (few parts: keys, OLED connector, LEDs)
  In1.Cu +3V3 plane / VCC area            (unchanged)
  In2.Cu signal, horizontal runs          (new)
  In3.Cu signal, vertical runs            (new)
  In4.Cu GND plane                        (was In2.Cu: the GND plane and its "GND plane only" area move here)
  B.Cu   signal, horizontal runs          (almost all parts; GND stays the next plane)

Text edit of the file (layer table, zone layers, stackup), then one load/save through pcbnew to normalise it.
Stackup ASSUMPTION (JLCPCB 6-layer, 1.6 mm, structure of JLC06161H-2116, values not checked against the order
form): 35 um outer / 15.2 um inner copper, prepreg 0.1164 mm (2116) to the planes, cores 0.2 mm plane to inner
signal, prepreg 0.8164 mm between In2 and In3. In2 sits 0.2 mm over the +3V3 plane, In3 0.2 mm over GND.
Tracks are not touched: route afterwards (hv_route.py).
"""
import re, shutil, sys
from pathlib import Path

import pcbnew

CU = lambda name: f"""			(layer "{name}"
				(type "copper")
				(thickness {0.035 if name in ('F.Cu', 'B.Cu') else 0.0152})
			)
"""
DI = lambda n, kind, t, mat, er: f"""			(layer "dielectric {n}"
				(type "{kind}")
				(thickness {t})
				(material "{mat}")
				(epsilon_r {er})
				(loss_tangent 0.02)
			)
"""
STACK = (CU("F.Cu") + DI(1, "prepreg", 0.1164, "2116", 4.16) + CU("In1.Cu") + DI(2, "core", 0.2, "FR4", 4.6)
         + CU("In2.Cu") + DI(3, "prepreg", 0.8164, "7628", 4.4) + CU("In3.Cu") + DI(4, "core", 0.2, "FR4", 4.6)
         + CU("In4.Cu") + DI(5, "prepreg", 0.1164, "2116", 4.16) + CU("B.Cu"))


def main(src, dst):
    t = Path(src).read_text(encoding="utf-8")
    if '"In4.Cu"' in t:
        sys.exit("already 6 layers")
    old = '\t\t(6 "In2.Cu" power "In2.GND")\n'
    assert old in t, "layer table not as expected"
    t = t.replace(old, '\t\t(6 "In2.Cu" signal)\n\t\t(8 "In3.Cu" signal)\n\t\t(10 "In4.Cu" power "In4.GND")\n')
    # stackup: everything from the F.Cu copper entry to the B.Cu copper entry
    a = t.index('\t\t\t(layer "F.Cu"\n\t\t\t\t(type "copper")')
    b = t.index('\t\t\t(layer "B.Cu"\n\t\t\t\t(type "copper")')
    b = t.index("\t\t\t)\n", b) + len("\t\t\t)\n")
    t = t[:a] + STACK + t[b:]
    # zones / fills / rule areas of the GND plane layer move to In4
    n = t.count('(layer "In2.Cu")')
    t = t.replace('(layer "In2.Cu")', '(layer "In4.Cu")')
    t = t.replace('(layers "F.Cu" "B.Cu" "In1.Cu" "In2.Cu")', '(layers "F.Cu" "B.Cu" "In1.Cu" "In2.Cu" "In3.Cu" "In4.Cu")')
    tmp = Path(dst).with_name(Path(dst).stem + "_text.kicad_pcb")
    tmp.write_text(t, encoding="utf-8", newline="\n")
    pro = Path(src).with_suffix(".kicad_pro")
    for p in (tmp, Path(dst)):
        shutil.copy(pro, p.with_suffix(".kicad_pro"))
    board = pcbnew.LoadBoard(str(tmp))
    assert board.GetCopperLayerCount() == 6, board.GetCopperLayerCount()
    pcbnew.SaveBoard(str(dst), board)
    names = [board.GetLayerName(l) for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu)]
    zones = [(z.GetZoneName(), z.GetNetname(), [board.GetLayerName(l) for l in z.GetLayerSet().Seq()])
             for z in board.Zones() if not z.IsTeardropArea() and z.GetZoneName()]
    print(f"6 layers: {names}; {n} zone layer entries moved In2 -> In4")
    for z in zones:
        print("  zone", z)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
