# scandev

A self-contained nuclear quadrupole resonance (NQR) spectrometer: put a
sample in a coil, send a short radio-frequency pulse, and listen for the
faint signal the nuclei send back. The frequency of that signal identifies
the compound, through a sealed container and with no magnet.

The project follows Applied Science's video
[Identify chemicals with radio frequencies - Nuclear Quadrupole Resonance (MRI without magnets)](https://www.youtube.com/watch?v=JO_EHceV9sk),
which builds one around an oscilloscope, a bench amplifier and a passive
transmit/receive network. Here the oscilloscope is replaced by an FPGA, an
ADC and purpose-built boards.

## Status

Early. Nothing has been built or run on hardware yet.

| Part | State |
|------|-------|
| Probe and pulse numbers (`sim/probe.py`) | done |
| Transmit/receive front end in SPICE (`sim/frontend.py`) | passive network modelled |
| Gateware core (`gateware/rtl`) | passes simulation, synthesises for `xc7a35t-ftg256`; not placed or routed |
| Host link, pin-level top, host software | not started |
| Boards (KiCad) | not started |

## Plan

Three boards joined by SMA cables, plus the probe in its own shielded box:

- **Digital**: Xilinx Artix-7 (XC7A35T-FTG256), 12-bit ADC, one 50 MHz
  clock, FT2232H for JTAG and a serial link to the host.
- **Amplifier**: a 5-10 W switching stage driven from FPGA pins. About 3 W
  is enough for a 100 µs pulse at 3.6 MHz, and a switching stage is silent
  when it is off.
- **Receive front end**: quarter-wave sections with crossed diodes, an
  FPGA-controlled blanking switch, and the low-noise amplifier.

The first target is sodium nitrite at 3.6 MHz, the strong line the video
uses to prove the instrument works.

## Layout

```
sim/        design numbers and the ngspice front-end model
gateware/   Verilog (rtl/), testbench and its Python judge (tb/)
video/      script used to transcribe the reference video for study
```

## Running the checks

```sh
python3 sim/probe.py          # coil, matching, pulse length, ring-down
python3 sim/frontend.py       # needs ngspice
python3 gateware/tb/run_core.py
```

The gateware is simulated and synthesised with
[reticle](https://github.com/KarpelesLab/reticle). `run_core.py` looks for
the binary at `tools/reticle-target/release/reticle`, or wherever the
`RETICLE` environment variable points.

## Safety

The probe coil carries several hundred volts of RF during a pulse. Sodium
nitrite is toxic in gram quantities: keep it in a sealed tube.
