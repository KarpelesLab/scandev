#!/usr/bin/env python3
"""Probe, pulse and link-budget numbers for the NQR spectrometer.

Everything downstream (SPICE decks, gateware defaults, part ratings) takes its
numbers from here.  Run it to print the design table.
"""
import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

MU0 = 4e-7 * math.pi
KB = 1.380649e-23
GAMMA_14N = 2 * math.pi * 3.0777e6  # rad/s/T


@dataclass
class Coil:
    turns: int = 25
    dia: float = 0.026      # m, winding diameter (25 mm tube)
    length: float = 0.045   # m
    q_unloaded: float = 100.0

    @property
    def inductance(self):
        r = self.dia / 2
        # Wheeler, accurate to ~1 % for length > 0.8 r
        r_in, l_in = r / 0.0254, self.length / 0.0254
        return (r_in**2 * self.turns**2) / (9 * r_in + 10 * l_in) * 1e-6

    def b1_per_amp(self):
        """On-axis centre field of a finite solenoid, T/A."""
        r, l = self.dia / 2, self.length
        return MU0 * self.turns / math.sqrt(l**2 + 4 * r**2)


def match(coil: Coil, f0: float, z0: float = 50.0):
    """Tune cap across the coil, match cap in series with the feed.

    Returns (c_tune, c_match, r_series).
    """
    w = 2 * math.pi * f0
    L = coil.inductance
    rs = w * L / coil.q_unloaded

    def ztank(ct):
        return 1 / (1j * w * ct + 1 / (rs + 1j * w * L))

    c_res = 1 / (w * w * L)
    # below resonance the tank is inductive; find Ct where Re(Z) = z0
    ct = brentq(lambda c: ztank(c).real - z0, c_res * 0.5, c_res * (1 - 1e-6))
    x = ztank(ct).imag
    cm = 1 / (w * x)
    return ct, cm, rs


def report(f0=3.6e6, p_tx=25.0, z0=50.0, coil=Coil()):
    w = 2 * math.pi * f0
    L = coil.inductance
    ct, cm, rs = match(coil, f0, z0)
    q_l = coil.q_unloaded / 2            # matched: source resistance halves Q
    i_pk = math.sqrt(2 * p_tx / rs)      # all power ends up in rs
    v_pk = i_pk * w * L
    b1 = coil.b1_per_amp() * i_pk        # linear amplitude
    # powder spin-1: optimum nominal flip gamma*B1*tp ~ 119 deg (2.08 rad)
    t119 = 2.08 / (GAMMA_14N * b1)
    tau = 2 * q_l / w                    # voltage ring-down time constant
    # ring-down from v_pk to thermal-noise level in the detection bandwidth
    bw = 10e3
    vn = math.sqrt(4 * KB * 300 * z0 * bw)
    t_dead = tau * math.log(v_pk / vn)
    out = dict(
        f0=f0, L=L, rs=rs, c_tune=ct, c_match=cm, q_loaded=q_l,
        i_coil_pk=i_pk, v_tank_pk=v_pk, b1=b1, t_pulse_119=t119,
        tau_ring=tau, t_ring_to_noise=t_dead, vnoise_10k=vn,
        # same B1 budget turned round: power needed for a 100 us pulse
        p_for_100us=p_tx * (t119 / 100e-6) ** 2,
        qw_L=z0 / w, qw_C=1 / (w * z0),
    )
    return out


if __name__ == "__main__":
    for f0 in (3.6e6, 4.64e6, 1.04e6, 2.56e6):
        r = report(f0)
        print(f"--- f0 = {f0/1e6:.2f} MHz, 25 W ---")
        print(f"  coil L          {r['L']*1e6:7.2f} uH   Rs {r['rs']:.2f} ohm   loaded Q {r['q_loaded']:.0f}")
        print(f"  C tune / match  {r['c_tune']*1e12:7.1f} pF / {r['c_match']*1e12:.1f} pF")
        print(f"  tank V / I pk   {r['v_tank_pk']:7.0f} V  / {r['i_coil_pk']:.1f} A")
        print(f"  B1              {r['b1']*1e3:7.2f} mT   -> 119deg pulse {r['t_pulse_119']*1e6:.0f} us")
        print(f"  power for 100us {r['p_for_100us']:7.2f} W")
        print(f"  ring-down tau   {r['tau_ring']*1e6:7.2f} us   to noise floor {r['t_ring_to_noise']*1e6:.0f} us")
        print(f"  quarter-wave    {r['qw_L']*1e6:7.2f} uH / {r['qw_C']*1e12:.0f} pF per section")
