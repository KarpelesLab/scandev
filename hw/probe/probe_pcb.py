#!/usr/bin/env python3
"""Probe tuning board: two layers, 1.5 mm between the tank and everything else."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
from probe import s                  # noqa: E402
from kipcb import Board              # noqa: E402

W, H = 76, 40
b = Board(s, W, H, layers=2, planes=("B.Cu",), track=0.4, via=(0.8, 0.4),
          wide={"TANK": (1.5, 1.5), "PROBE": 1.0}, wide_via=(1.2, 0.6), zone_clearance=1.5)
b.sma("J1", "L", 16)
for i in range(4):
    b.place(f"CM{i+1}", 12 + 5 * i, 16, 90)
b.place("CV2", 13, 6, 0)
for i in range(6):
    b.place(f"CT{i+1}", 36 + 4.5 * i, 20, 90)
b.place("CV1", 40, 8, 0)
b.place("J2", W - 7, 17.5, 270)
b.place("J3", 8, 34, 90)
b.place("RT1", 62, 34, 0)
for ref, (x, y) in zip(["H1", "H2", "H3", "H4"], [(4, 4), (W - 4, 4), (W - 4, H - 4), (24, H - 4)]):
    b.place(ref, x, y)

if __name__ == "__main__":
    b.run(HERE, os.path.join(HERE, "..", "..", "build", "hw", "probe"), route="--route" in sys.argv)
