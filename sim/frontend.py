#!/usr/bin/env python3
"""SPICE model of the passive transmit/receive front end.

    PA --[series crossed diodes x N, R to ground between]--+-- Cm -- tank (Ct || L+Rs)
                                                            |
                    LNA --[quarter-wave pi + shunt crossed diodes] x N

Three questions, one ngspice run each:
  tx    transient burst: what reaches the LNA, what the tank sees, how long
        until the LNA node is quiet again
  rx    AC: how much of the coil EMF arrives at the LNA
  leak  AC: how much PA output noise arrives at the LNA while receiving
"""
import argparse
import math
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe import Coil, match  # noqa: E402

# 1N4148-class switching diode (BAV99 halves behave the same)
DIODE = ".model DSW D(IS=2.52n RS=0.568 N=1.752 CJO=4p M=0.4 TT=6n BV=100)"


def netlist(f0, p_tx, t_pulse, coil, stages=3, npar=2, r_bleed=470.0,
            mode="tx", t_stop=None, z0=50.0, f_qw=None):
    """f_qw: frequency the quarter-wave sections were built for (default f0)."""
    f_qw = f_qw or f0
    w = 2 * math.pi * f0
    wq = 2 * math.pi * f_qw
    ct, cm, rs = match(coil, f0, z0)
    L = coil.inductance
    lq, cq = z0 / wq, 1 / (wq * z0)
    v_oc = 2 * math.sqrt(2 * p_tx * z0)      # open-circuit peak for p_tx into z0
    n = [f"* NQR front end, mode={mode}", DIODE]

    # --- transmitter and its series isolator
    if mode == "tx":
        n.append(f"Btx src 0 V = time < {t_pulse} ? {v_oc}*sin({w}*time) : 0")
    else:
        n.append(f"Vtx src 0 DC 0 AC {1 if mode == 'leak' else 0}")
    n.append(f"Rsrc src a0 {z0}")
    for s in range(stages):
        a, b = f"a{s}", (f"a{s+1}" if s < stages - 1 else "p")
        for k in range(npar):
            n.append(f"Dsf{s}_{k} {a} {b} DSW")
            n.append(f"Dsr{s}_{k} {b} {a} DSW")
        if s < stages - 1:
            n.append(f"Rbl{s} {b} 0 {r_bleed}")

    # --- probe
    n.append(f"Cm p t {cm}")
    n.append(f"Ct t 0 {ct}")
    n.append(f"Lc t m {L}")
    n.append(f"Rc m e {rs}")
    n.append(f"Vemf e 0 DC 0 AC {1 if mode == 'rx' else 0}")

    # --- receive path: quarter-wave pi sections, shunt crossed diodes
    for s in range(stages):
        a, b = ("p" if s == 0 else f"r{s}"), f"r{s+1}"
        n.append(f"Cqa{s} {a} 0 {cq}")
        n.append(f"Lq{s} {a} {b} {lq}")
        n.append(f"Cqb{s} {b} 0 {cq}")
        for k in range(npar):
            n.append(f"Dpf{s}_{k} {b} 0 DSW")
            n.append(f"Dpr{s}_{k} 0 {b} DSW")
    n.append(f"Rlna r{stages} 0 {z0}")

    lna = f"r{stages}"
    n.append(".options reltol=1e-4 vntol=1e-10 abstol=1e-14 method=gear")
    n.append(".control")
    n.append("set wr_singlescale")
    n.append("set wr_vecnames")
    if mode == "tx":
        tstep = 1 / f0 / 40
        n.append(f"tran {tstep} {t_stop} 0 {tstep}")
        n.append(f"wrdata OUT v({lna}) v(t) v(p) i(Vemf)")
    else:
        n.append(f"ac lin 801 {f0*0.9} {f0*1.1}")
        n.append(f"wrdata OUT vdb({lna})")
    n.append(".endc")
    n.append(".end")
    return "\n".join(n) + "\n"


def run(deck):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out.txt")
        cir = os.path.join(d, "deck.cir")
        with open(cir, "w") as f:
            f.write(deck.replace("OUT", out))
        r = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True)
        if not os.path.exists(out):
            sys.exit("ngspice failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
        return np.loadtxt(out, skiprows=1)


def envelope(t, v, f0):
    """Peak |v| per RF cycle."""
    per = 1 / f0
    idx = ((t - t[0]) / per).astype(int)
    nb = idx.max() + 1
    env = np.zeros(nb)
    np.maximum.at(env, idx, np.abs(v))
    return (np.arange(nb) + 0.5) * per + t[0], env


def analyse(f0=3.6e6, p_tx=25.0, t_pulse=100e-6, coil=Coil(), stages=3,
            npar=2, f_qw=None, quiet=False):
    kw = dict(coil=coil, stages=stages, npar=npar, f_qw=f_qw)
    tx = run(netlist(f0, p_tx, t_pulse, mode="tx", t_stop=t_pulse + 250e-6, **kw))
    t, vlna, vt, vp, icoil = tx.T
    on = (t > t_pulse * 0.6) & (t < t_pulse)
    te, env = envelope(t, vlna, f0)
    after = te > t_pulse
    res = dict(
        lna_pk_tx=np.abs(vlna[on]).max(),
        tank_pk=np.abs(vt[on]).max(),
        coil_i_pk=np.abs(icoil[on]).max(),
        feed_pk=np.abs(vp[on]).max(),
    )
    for lvl in (1e-3, 1e-6, 1e-7):
        below = np.where(after & (env < lvl))[0]
        # first cycle after which the envelope stays below the level
        stay = [i for i in below if (env[i:] < lvl).all()]
        res[f"t_below_{lvl:g}"] = (te[stay[0]] - t_pulse) if stay else float("nan")

    rx = run(netlist(f0, p_tx, t_pulse, mode="rx", **kw))
    leak = run(netlist(f0, p_tx, t_pulse, mode="leak", **kw))
    mid = len(rx) // 2
    res["rx_gain_db"] = rx[mid, 1]
    res["rx_gain_pk_db"] = rx[:, 1].max()
    res["rx_bw_3db"] = np.ptp(rx[rx[:, 1] > rx[:, 1].max() - 3, 0])
    res["leak_db"] = leak[mid, 1]
    if not quiet:
        print(f"f0 {f0/1e6:.2f} MHz  {p_tx:.0f} W  {t_pulse*1e6:.0f} us  "
              f"{stages} stages x {npar} diode pairs"
              + (f"  (quarter-wave built for {f_qw/1e6:.2f} MHz)" if f_qw else ""))
        print(f"  transmit: tank {res['tank_pk']:.0f} V pk, coil {res['coil_i_pk']:.2f} A pk, "
              f"feed {res['feed_pk']:.1f} V pk")
        print(f"            LNA input sees {res['lna_pk_tx']*1e3:.1f} mV pk")
        print(f"  recovery: LNA node < 1 mV after {res['t_below_0.001']*1e6:.0f} us, "
              f"< 1 uV after {res['t_below_1e-06']*1e6:.0f} us, "
              f"< 100 nV after {res['t_below_1e-07']*1e6:.0f} us")
        print(f"  receive:  coil EMF -> LNA {res['rx_gain_db']:+.1f} dB at f0 "
              f"(peak {res['rx_gain_pk_db']:+.1f} dB), -3 dB width {res['rx_bw_3db']/1e3:.0f} kHz")
        print(f"  PA noise -> LNA {res['leak_db']:.1f} dB")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--f0", type=float, default=3.6e6)
    ap.add_argument("--power", type=float, default=25.0)
    ap.add_argument("--pulse", type=float, default=100e-6)
    ap.add_argument("--stages", type=int, default=3)
    ap.add_argument("--npar", type=int, default=2)
    ap.add_argument("--fqw", type=float, default=None)
    a = ap.parse_args()
    analyse(a.f0, a.power, a.pulse, stages=a.stages, npar=a.npar, f_qw=a.fqw)
