#!/usr/bin/env python3
"""Simulate one NQR experiment on nqr_core and judge the result.

Two runs of the same pulse program against a synthetic free-induction decay
20 kHz off the carrier:

  clean   no noise: the captured samples must have the right frequency (and
          its sign), amplitude and decay, and the transmit drive the right
          number of cycles
  noisy   noise three times the signal on every ADC sample, different in each
          shot: the summed capture must still show the line, with the noise
          the size that four coherently added shots should leave

What this would not catch: anything about pins, timing closure, or analogue
behaviour, and an error common to the model here and the RTL (both take the
carrier as freq * f_clk / 2^32).
"""
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RETICLE = os.environ.get("RETICLE", os.path.join(ROOT, "tools/reticle-target/release/reticle"))
BUILD = os.path.join(ROOT, "build/sim_core")

F_CLK = 50e6
F0 = 3.6e6
DELTA = 20e3            # line sits this far above the carrier
T2S = 100e-6
AMP = 100.0             # ADC LSB
R = 50
SHIFT = 8
NSHOTS = 4
SHOTLEN = 16384
T_TX, T_DEAD, N_ACQ, T_IDLE = 500, 250, 256, 16

TX, BLANK, QDAMP, ACQ, SYNC, LAST = 1, 8, 16, 32, 64, 128
FREQ = round(F0 / F_CLK * 2**32)
PROGRAM = [
    (SYNC | TX | BLANK, T_TX),
    (BLANK | QDAMP, T_DEAD),
    (ACQ, N_ACQ * R),
    (LAST, T_IDLE),
]


def stimulus(sigma, rng):
    k = np.arange(SHOTLEN)
    t = k / F_CLK
    f_car = FREQ * F_CLK / 2**32
    shots = []
    for _ in range(NSHOTS):
        s = np.zeros(SHOTLEN)
        fid = k >= T_TX
        s[fid] = AMP * np.exp(-(t[fid] - T_TX / F_CLK) / T2S) * np.cos(
            2 * np.pi * (f_car + DELTA) * t[fid])
        # transmit leakage: a full-scale carrier while the pulse is on
        s[~fid] = 2000 * np.cos(2 * np.pi * f_car * t[~fid] + 0.7)
        s += rng.normal(0, sigma, SHOTLEN)
        shots.append(np.clip(np.round(s), -2048, 2047).astype(int))
    return np.concatenate(shots)


def simulate(name, sigma, seed):
    d = os.path.join(BUILD, name)
    os.makedirs(d, exist_ok=True)
    stim = stimulus(sigma, np.random.default_rng(seed))
    with open(os.path.join(d, "stim.hex"), "w") as f:
        f.write("\n".join(f"{v & 0xFFF:03x}" for v in stim) + "\n")
    regs = [(1, FREQ), (2, R), (3, SHIFT), (4, NSHOTS)]
    for a, (ctrl, dur) in enumerate(PROGRAM):
        regs += [(5, a), (6, dur), (7, ctrl)]
    regs.append((0xFF, 0))
    with open(os.path.join(d, "cfg.hex"), "w") as f:
        f.write("\n".join(f"{a:02x}{v:08x}" for a, v in regs) + "\n")
    shutil.copy(os.path.join(ROOT, "gateware/rtl/sine1024.hex"), d)
    srcs = [os.path.join(ROOT, "gateware/tb/nqr_core_tb.v")] + [
        os.path.join(ROOT, "gateware/rtl", m + ".v")
        for m in ("nqr_core", "pulse_seq", "nco", "ddc", "capture")]
    cmd = [RETICLE, "sim", "--top", "nqr_core_tb",
           "--param", f"SHOTLEN={SHOTLEN}", "--param", f"NSHOTS={NSHOTS}"] + srcs
    r = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
    out = {"D": []}
    for line in r.stdout.splitlines():
        w = line.split()
        if not w:
            continue
        if w[0] == "D":
            out["D"].append((int(w[2]), int(w[3])))
        elif w[0] in ("ID", "SHOTS", "NSAMP", "TX", "FAIL"):
            out[w[0]] = w[1:]
    if r.returncode or "FAIL" in out or not out["D"]:
        sys.exit(f"simulation {name} failed (exit {r.returncode}):\n"
                 + r.stdout[-1500:] + r.stderr[-1500:])
    d_ = np.array(out["D"], dtype=float)
    out["z"] = d_[:, 0] + 1j * d_[:, 1]
    return out


FAILED = []


def check(what, ok, detail):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}: {detail}")
    if not ok:
        FAILED.append(what)


def main():
    fs = F_CLK / R
    gain = 2047 / 2 * R**3 / 2**SHIFT * NSHOTS      # per LSB of input amplitude

    print("clean run")
    c = simulate("clean", 0.0, 1)
    z = c["z"]
    check("identity", c["ID"] == ["4e515231"], c["ID"][0])
    check("shots", c["SHOTS"] == [str(NSHOTS)], c["SHOTS"][0])
    check("samples per shot", c["NSAMP"] == [str(N_ACQ)], c["NSAMP"][0])
    txc, hic, edges = map(int, c["TX"])
    want_edges = NSHOTS * T_TX * F0 / F_CLK
    check("transmit cycles on", txc == NSHOTS * T_TX, f"{txc} (want {NSHOTS*T_TX})")
    check("transmit RF periods", abs(edges - want_edges) <= NSHOTS,
          f"{edges} (want {want_edges:.0f})")
    check("transmit duty", abs(hic / txc - 0.5) < 0.02, f"{hic/txc:.3f}")

    n = np.arange(len(z))
    use = slice(4, 200)
    ph = np.unwrap(np.angle(z[use]))
    f_meas = np.polyfit(n[use], ph, 1)[0] * fs / (2 * np.pi)
    check("line frequency and sign", abs(f_meas - DELTA) < 0.005 * DELTA,
          f"{f_meas/1e3:+.3f} kHz (want {DELTA/1e3:+.3f})")
    slope, icpt = np.polyfit(n[use] / fs, np.log(np.abs(z[use])), 1)
    check("decay time", abs(-1 / slope - T2S) < 0.03 * T2S,
          f"{-1/slope*1e6:.1f} us (want {T2S*1e6:.0f})")
    # sample n is centred a CIC group delay before the tick that produced it
    t0 = (T_DEAD + R - 3 * (R - 1) / 2) / F_CLK
    a0 = np.exp(icpt) * np.exp(t0 / T2S) / gain
    check("amplitude", abs(a0 - AMP) < 0.05 * AMP, f"{a0:.1f} LSB (want {AMP:.0f})")
    check("leakage kept out", np.abs(z[0]) < 1.3 * gain * AMP,
          f"first sample {np.abs(z[0])/gain:.1f} LSB-equivalent")

    print("noisy run (noise 3x the signal on every sample)")
    sigma = 300.0
    m = simulate("noisy", sigma, 2)
    resid = m["z"] - z
    # CIC impulse response is three boxcars convolved; LO power is 2047^2/2
    h = np.convolve(np.convolve(np.ones(R), np.ones(R)), np.ones(R))
    want = sigma * np.sqrt((h**2).sum() * 2047**2 / 2 * NSHOTS) / 2**SHIFT
    got = np.sqrt((resid.real**2).mean()), np.sqrt((resid.imag**2).mean())
    check("noise after 4 shots, I", abs(got[0] / want - 1) < 0.15,
          f"{got[0]:.3g} (want {want:.3g})")
    check("noise after 4 shots, Q", abs(got[1] / want - 1) < 0.15,
          f"{got[1]:.3g} (want {want:.3g})")
    spec = np.abs(np.fft.fft(m["z"] * np.hanning(len(z))))
    freqs = np.fft.fftfreq(len(z), 1 / fs)
    pk = freqs[spec.argmax()]
    check("line found in the noisy spectrum", abs(pk - DELTA) <= fs / len(z),
          f"peak at {pk/1e3:+.1f} kHz, {spec.max()/np.median(spec):.0f}x the median bin")

    print("FAILED: " + ", ".join(FAILED) if FAILED else "all checks passed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
