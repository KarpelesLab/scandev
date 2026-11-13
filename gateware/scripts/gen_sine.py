#!/usr/bin/env python3
"""Sine table for the NCO: 1024 entries, 12-bit two's complement, half-sample
offset so the table is symmetric and has no DC term."""
import math
import sys

N, AMP = 1024, 2047
with open(sys.argv[1], "w") as f:
    for i in range(N):
        v = round(AMP * math.sin(2 * math.pi * (i + 0.5) / N))
        f.write(f"{v & 0xFFF:03x}\n")
