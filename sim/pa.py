#!/usr/bin/env python3
"""Output network of the switching amplifier.

A half-bridge switching between 0 and Vdd drives the 50 ohm line through a
series capacitor and inductor and a shunt capacitor:

    bridge --Cs--L--+-- 50 ohm
                    Cp
                    |
                   gnd

The network turns 50 ohm into the few ohms the bridge needs to deliver the
power wanted from a low supply, and leaves the bridge a slightly inductive
load so the switches turn on with little voltage across them.  It is fitted
to one frequency, like the quarter-wave sections of the receive front end.
"""
import argparse
import cmath
import math


def zin(f, cs, l, cp, rl=50.0, r_sw=0.1, r_l=0.15):
    w = 2 * math.pi * f
    zp = 1 / (1 / rl + 1j * w * cp)
    return r_sw + r_l + 1 / (1j * w * cs) + 1j * w * l + zp, zp


def report(f0, vdd, cs, l, cp):
    print(f"f0 {f0/1e6:.3f} MHz, Vdd {vdd:.0f} V, Cs {cs*1e9:.2f} nF, L {l*1e6:.2f} uH, Cp {cp*1e9:.2f} nF")
    p1 = None
    for n in (1, 3, 5):
        v = 2 * vdd / (math.pi * n)              # harmonic amplitude of the square wave
        z, zp = zin(n * f0, cs, l, cp)
        i = v / z
        vout = i * zp
        p = abs(vout) ** 2 / (2 * 50)
        if n == 1:
            p1 = p
            w = 2 * math.pi * f0
            print(f"  load on the bridge {z.real:.2f} {z.imag:+.2f}j ohm "
                  f"({math.degrees(cmath.phase(z)):+.0f} deg, inductive is wanted)")
            print(f"  output {p:.2f} W into 50 ohm, {abs(vout):.1f} V pk")
            print(f"  switch current {abs(i):.2f} A pk; Cs sees {abs(i)/(w*cs):.0f} V pk, "
                  f"L sees {abs(i)*w*l:.0f} V pk")
        else:
            print(f"  harmonic {n}: {10*math.log10(p/p1):.0f} dBc")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--f0", type=float, default=3.306e6)
    ap.add_argument("--vdd", type=float, default=12.0)
    ap.add_argument("--cs", type=float, default=3.9e-9)
    ap.add_argument("--l", type=float, default=1.5e-6)
    ap.add_argument("--cp", type=float, default=2.7e-9)
    a = ap.parse_args()
    report(a.f0, a.vdd, a.cs, a.l, a.cp)
