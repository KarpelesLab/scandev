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
| Amplifier output network (`sim/pa.py`) | done |
| Schematics of the three boards (`hw/`) | written; KiCad's netlist matches and the rule check passes |
| Board layouts | not started |
| Parts | ICs chosen and checked against JLCPCB stock; most passive part numbers unchecked, inductors and oscillator not chosen |
| Gateware core (`gateware/rtl`) | passes simulation, synthesises for `xc7a35t-ftg256`; on hold until a board exists |
| RP2040 firmware, host software | not started |

## Boards

Three boards joined by SMA cables, plus the probe in its own shielded box.
Each is a Python script in `hw/` that writes the KiCad schematic, a PDF of
it and a BOM, and checks KiCad's reading of the netlist against the script.

- **Digital** (`hw/dig`): Xilinx Artix-7 (XC7A35T-FTG256) and an AD9226
  12-bit ADC on one 50 MHz oscillator. An RP2040 with its own USB-C port,
  BOOTSEL and reset buttons loads the FPGA (there is no configuration
  flash) and keeps bitstreams and scan results on a microSD card.
- **Amplifier** (`hw/pa`): a half-bridge switching at the carrier, 3.8 W
  at 12 V into 50 ohm. It is silent when it is not switching, and its rail
  collapses if it is left transmitting. Takes the 12 V input for the system.
- **Receive front end** (`hw/fe`): series crossed diodes towards the
  amplifier, three quarter-wave sections with shunt diodes towards the
  receiver, two low-noise stages with a blanking switch between them.

The amplifier's output network and the front end's quarter-wave sections
are fitted to one frequency. They are fitted for hexamine.

## Samples

The video's sodium nitrite is not something to buy casually, so the first
target is **hexamine** (solid camping-fuel tablets): a nitrogen line at
3.306 MHz at room temperature whose signal lasts about 1.5 ms, long enough
that the receiver's dead time after the pulse costs little.

## Layout

```
sim/        design numbers and the ngspice front-end model
hw/         board scripts, generated schematics, PDFs and BOMs
gateware/   Verilog (rtl/), testbench and its Python judge (tb/)
video/      script used to transcribe the reference video for study
```

## Running the checks

```sh
python3 sim/probe.py          # coil, matching, pulse length, ring-down
python3 sim/frontend.py       # needs ngspice
python3 gateware/tb/run_core.py
python3 hw/fe/fe.py           # likewise hw/pa/pa.py, hw/dig/dig.py; needs KiCad 9+
```

The gateware is simulated and synthesised with
[reticle](https://github.com/KarpelesLab/reticle). `run_core.py` looks for
the binary at `tools/reticle-target/release/reticle`, or wherever the
`RETICLE` environment variable points.

## Safety

The probe coil carries several hundred volts of RF during a pulse. Sodium
nitrite is toxic in gram quantities: keep it in a sealed tube.
