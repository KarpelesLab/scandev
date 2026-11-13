#!/usr/bin/env python3
"""Digital board: placement and first-pass routing.

Analogue in the top-left corner (ADC input, 5 V rail, clock), FPGA in the
middle, RP2040 below it with USB on the bottom edge and the card slot on
the right edge, logic supplies top-right.  The FPGA sits with ball A1 at
the top-left, which puts the ADC bus (bank 35) towards the ADC, the
amplifier outputs (bank 34) towards the left edge, the RP2040 link
(bank 14) towards the RP2040 and the PMOD (bank 15) towards the top edge.

Only the first inner layer is a ground plane while routing; the second is
left to the router for supplies and crossings, and poured afterwards.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
from dig import s                    # noqa: E402
from kipcb import Board              # noqa: E402

W, H = 112, 86
SUPPLY = ["VBUS", "+5V", "+3V3", "+1V0", "+1V8", "+5VA", "V12", "V12_F", "SW1", "SW2",
          "RP_1V1", "XO_VDD", "ADC_DRVDD"]
b = Board(s, W, H, track=0.15, clearance=0.127, via=(0.5, 0.3),
          wide={n: 0.3 for n in SUPPLY}, wide_via=(0.5, 0.3), planes=("In1.Cu",))


def row(refs, x, y, dx=0.0, dy=0.0, rot=0, side="F"):
    for i, ref in enumerate(refs):
        b.place(ref, x + dx * i, y + dy * i, rot, side)


# ---------------------------------------------------------------- FPGA
FX, FY = 58, 34
b.place("U10", FX, FY, 0)
# bulk capacitors beside and below the package
row(["C50", "C51", "C52", "C53", "C60", "C61"], 70.5, 24, dy=3.6, rot=90)
row(["C66", "C67", "C68", "C69", "C70", "C71"], 45.5, 46.5, dx=5)
# 100 nF on the back, under the supply balls in the middle of the array
small = [f"C{n}" for n in list(range(54, 60)) + list(range(62, 66)) + list(range(72, 82))]
for i, ref in enumerate(small):
    b.place(ref, FX - 4.8 + 2.4 * (i % 5), FY - 3.6 + 2.4 * (i // 5), 0, "B")
row(["R34", "R35", "R36", "R37", "R38", "R33"], 76, 28, dy=3)
b.place("J6", 107, 36, 0)
b.place("J13", 56, 5, 90)

# ---------------------------------------------------------------- ADC, clock
b.sma("J5", "L", 24)
b.place("U9", 28, 24, 180)
row(["RN1", "RN2", "RN3"], 40, 18.5, dy=4)
b.place("R32", 40, 30.5, 0)
b.place("C34", 10, 24, 0)
b.place("R28", 10, 28, 0)
b.place("R30", 14, 24, 0)
b.place("R29", 14, 28, 0)
b.place("C35", 18, 24, 90)
b.place("R31", 18, 28, 0)
b.place("C36", 18, 31, 0)
b.place("C37", 12, 33, 0)
row(["C38", "C39", "C40"], 16, 34, dx=3.5)
b.place("C41", 28, 34, 0)
b.place("C42", 32, 34, 0)
b.place("C44", 22, 15, 0)
row(["C45", "C46"], 26, 15, dx=3.5)
b.place("FB2", 36, 14.5, 0)
b.place("C43", 36, 17, 0)
b.place("X1", 46, 8, 0)
b.place("FB1", 41, 6, 0)
b.place("C32", 41, 9, 0)
row(["R25", "R26"], 51, 7, dy=2.5)
b.place("U8", 36, 8, 0)
b.place("C33", 32.3, 11, 0)
b.place("R27", 36, 12, 0)

# 12 V in, 5 V analogue rail
b.place("J4", 5, 5, 90)
b.place("R20", 13, 5, 0)
b.place("C28", 18, 5, 90)
b.place("U7", 26, 6, 0)
b.place("C29", 24, 12, 0)
b.place("C30", 28, 12, 0)
row(["R21", "R22", "C31"], 9.6, 10, dx=3.2)
b.place("R24", 5, 14, 0)
b.place("D3", 8.5, 14, 0)

# ---------------------------------------------------------------- logic supplies
for k, (u, cin, ind, rt, rb, c1, c2) in enumerate([("U4", "C19", "L1", "R16", "R17", "C20", "C21"),
                                                    ("U5", "C22", "L2", "R18", "R19", "C23", "C24")]):
    y = 8 + 10 * k
    b.place(cin, 79, y, 90)
    b.place(u, 84, y, 0)
    b.place(ind, 90, y, 0)
    b.place(rt, 95.2, y - 1.6, 0)
    b.place(rb, 95.2, y + 1.6, 0)
    b.place(c1, 99, y, 90)
    b.place(c2, 102, y, 90)
b.place("C25", 80, 27, 90)
b.place("U6", 84, 27, 0)
b.place("C26", 88, 27, 90)
b.place("C27", 91, 27, 90)
b.place("R23", 97, 27, 0)
b.place("D2", 100.5, 27, 0)

# ---------------------------------------------------------------- RP2040
RX, RY = 56, 62
b.place("U2", RX, RY, 270)            # GPIO0-11 side towards the FPGA
rp_caps = [f"C{n}" for n in range(5, 17)]
for i, ref in enumerate(rp_caps):
    b.place(ref, RX - 4.8 + 3.2 * (i % 4), RY - 2.6 + 2.6 * (i // 4), 0, "B")
b.place("Y1", 44, 62, 0)
b.place("C3", 40.5, 59, 0)
b.place("C4", 40.5, 65, 0)
b.place("R8", 48.5, 57.5, 90)
b.place("U3", 71, 60, 0)
b.place("C1", 69, 55, 0)
b.place("R5", 73, 55, 0)
row(["R6", "R7", "C2"], 80, 52, dy=3)
b.place("SW1", 88, 50, 0)
b.place("SW2", 88, 57, 0)
b.place("J2", 30, 70, 90)
b.place("R9", 40, 70, 0)
b.place("D1", 43.5, 70, 0)

# USB
b.place("J1", 72, H - 3.65, 0)
b.edge_refs.add("J1")
b.place("U1", 72, 73.5, 0)
b.place("F1", 80.5, 78, 90)
row(["R3", "R4"], 64, 68, dy=2.5)
row(["R2", "R1"], 64.6, 74.5, dy=2.5)

# card slot
b.place("J3", W - 7, 68, 270)
b.edge_refs.add("J3")
row(["R10", "R11", "R12", "R13", "R14", "R15"], 86, 78.5, dx=3.2)
b.place("C17", 91, 82, 0)
b.place("C18", 95, 82, 0)

# ---------------------------------------------------------------- outputs, headers
b.sma("J7", "L", 50)
b.sma("J8", "L", 60)
b.place("R39", 7, 50, 0)
b.place("R40", 7, 60, 0)
row(["J9", "J10", "J11"], 10, 82, dx=8, rot=90)
b.place("J12", 34, 82, 90)
b.place("J14", 47, 82, 90)
b.place("J15", 58.5, 82, 90)
row(["R41", "R42", "R43", "R44"], 11, 77, dx=8)
b.place("R45", 39, 77, 0)
b.place("R46", 56.5, 78, 0)
b.place("C80", 59.7, 78, 0)
b.place("R47", 10, 68, 0)
b.place("D4", 13.5, 68, 0)
b.place("R48", 10, 71.5, 0)
b.place("D5", 13.5, 71.5, 0)
b.place("SW3", 22, 68, 0)
b.place("R49", 22, 73.5, 0)

for ref, (x, y) in zip(["H1", "H2", "H3", "H4"], [(4, 82), (108, 4), (108, 82), (4, 37)]):
    b.place(ref, x, y)

if __name__ == "__main__":
    work = os.path.join(HERE, "..", "..", "build", "hw", "dig")
    b.run(HERE, work, route="--route" in sys.argv)
