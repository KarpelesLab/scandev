#!/usr/bin/env python3
"""Receive front end: board placement and first-pass routing.

Signal runs left to right along one line: probe connector, three
quarter-wave sections, amplifier, switch, amplifier, low-pass, output
connector.  The transmit isolator sits in a column on the left between the
TX and PROBE connectors, as far from the amplifier as the board allows.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
from fe import s                     # noqa: E402
from kipcb import Board              # noqa: E402

W, H = 126, 50
Y = 34                               # the signal line
# the transmit pulse passes through these at about half an amp
b = Board(s, W, H, wide={n: 0.6 for n in ["TX_IN", "TXA", "TXB", "PROBE", "Q1", "Q2", "Q3"]})

# connectors and mounting
b.sma("J1", "L", 10)
b.sma("J2", "L", Y)
b.sma("J3", "R", Y)
b.place("J4", 46, 5, 90)
for ref, (x, y) in zip(["H1", "H2", "H3", "H4"], [(4, 46), (W - 4, 4), (W - 4, 46), (30, 4)]):
    b.place(ref, x, y)

# transmit isolator, top to bottom
for i, (ref, y) in enumerate(zip(["D1", "D2", "D3", "D4", "D5", "D6"], [6, 10, 14.5, 18.5, 23, 27])):
    b.place(ref, 20, y, 0)
b.place("R1", 26, 12, 90)
b.place("R2", 26, 21, 90)

# receive isolator, left to right
x = 19
c = d = 0
for k in range(3):
    b.place(f"C{2*k+1}", x, Y + 3.5, 90)
    b.place(f"L{k+1}", x + 5, Y, 0)
    b.place(f"C{2*k+2}", x + 10, Y + 3.5, 90)
    b.place(f"D{7+2*k}", x + 10, Y - 5, 0)
    b.place(f"D{8+2*k}", x + 14, Y - 5, 0)
    x += 15
b.place("R3", x - 1.5, Y + 3.5, 90)

# amplifier chain
b.place("C7", 65, Y, 0)
b.place("R4", 65, Y + 3, 0)
b.place("U1", 70, Y, 0)
b.place("R5", 70, Y - 3, 0)
b.place("R6", 70, Y + 3, 0)
b.place("C8", 71.5, Y + 6.2, 0)
b.place("C10", 73.5, Y - 3, 90)
b.place("C11", 75.5, Y - 3, 90)
b.place("FB1", 74.5, Y - 7, 0)
b.place("R9", 75, Y, 0)
b.place("C13", 77, Y + 3, 90)
b.place("C12", 79, Y - 1.2, 0)
b.place("R7", 80.5, Y + 4, 90)
b.place("U2", 85.5, Y, 0)
b.place("C9", 85.5, Y - 3.5, 0)
b.place("R8", 88, Y + 4, 90)
b.place("U3", 91, Y, 0)
b.place("R10", 91, Y - 3, 0)
b.place("R11", 91, Y + 3, 0)
b.place("C14", 92.5, Y + 6.2, 0)
b.place("C15", 94.5, Y - 3, 90)
b.place("C16", 96.5, Y - 3, 90)
b.place("FB2", 95.5, Y - 7, 0)
b.place("R12", 96, Y, 0)
b.place("C17", 99.5, Y, 0)
b.place("C18", 102, Y + 4.5, 90)
b.place("L4", 106.5, Y, 0)
b.place("C19", 111, Y + 4.5, 90)

# power and references, along the top
b.place("D13", 68, 5, 0)
b.place("C21", 73, 5, 90)
b.place("U4", 78, 5, 0)
b.place("C22", 82, 7, 90)
b.place("C23", 84.5, 5, 90)
b.place("R15", 80, 14, 0)
b.place("R16", 80, 16.5, 0)
b.place("C24", 85, 15, 90)
b.place("C25", 87.5, 15, 90)
b.place("R13", 56, 12, 0)
b.place("R14", 56, 14.5, 0)
b.place("C20", 56, 17, 0)
b.place("R17", 96, 8, 0)
b.place("D14", 100, 8, 0)

if __name__ == "__main__":
    work = os.path.join(HERE, "..", "..", "build", "hw", "fe")
    b.run(HERE, work, route="--route" in sys.argv)
