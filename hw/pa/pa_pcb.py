#!/usr/bin/env python3
"""Transmit amplifier: board placement and first-pass routing.

Logic inputs on the left, output on the right, supply along the top.  The
bridge (Q1, Q2) sits directly under its ceramic bypass capacitors so the
switched current loop stays small.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
from pa import s                     # noqa: E402
from kipcb import Board              # noqa: E402

W, H = 96, 52
POWER = ["VIN", "VSYS", "VPA", "SW", "TANK", "TX_OUT", "VDRV"]
b = Board(s, W, H, wide={n: 0.8 for n in POWER})

b.place("J1", 14.5, 9, 0)
b.place("D1", 24, 6, 0)
b.place("C1", 30, 6, 90)
b.place("J2", 35, 4, 90)
b.place("J7", 43, 4, 90)
b.place("R3", 24, 14, 0)
b.place("D2", 28.5, 14, 0)
b.place("R1", 53, 5, 0)
b.place("R2", 53, 9.5, 0)
b.place("C2", 66, 9, 0)
b.place("C3", 80, 9, 0)

b.sma("J3", "L", 26)
b.sma("J4", "L", 38)
b.place("J5", 24, 47, 90)
b.place("R4", 22, 26, 0)
b.place("R5", 26, 28.5, 90)
b.place("R6", 22, 38, 0)
b.place("R7", 26, 35.5, 90)
b.place("R8", 31, 44, 0)
b.place("R9", 35, 44, 0)
b.place("C7", 39, 44, 0)

b.place("U1", 38, 32, 0)
b.place("R10", 34, 25, 0)
b.place("C8", 38, 26, 0)
b.place("C9", 43, 28, 90)
b.place("R11", 46, 30, 0)
b.place("R12", 46, 35, 0)
b.place("Q1", 51, 29, 0)
b.place("Q2", 51, 36, 0)
b.place("C6", 50.5, 24, 0)
b.place("C4", 55.5, 24, 0)
b.place("C5", 61, 24, 0)
b.place("R13", 55, 38, 90)
b.place("C10", 58, 31, 0)
b.place("C11", 58, 34.5, 0)
b.place("L1", 66, 31, 0)
b.place("C12", 73, 35.5, 90)
b.place("C13", 76.5, 35.5, 90)
b.sma("J6", "R", 31)

for ref, (x, y) in zip(["H1", "H2", "H3", "H4"], [(13, 47), (W - 4, 4), (W - 4, 48), (48, 47)]):
    b.place(ref, x, y)

if __name__ == "__main__":
    work = os.path.join(HERE, "..", "..", "build", "hw", "pa")
    b.run(HERE, work, route="--route" in sys.argv)
