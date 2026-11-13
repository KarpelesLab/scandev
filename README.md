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
| Schematics of the four boards (`hw/`) | written; KiCad's netlist matches and the rule check passes |
| Layout: front end, amplifier, probe | placed and autorouted; no rule violations, nothing unconnected; not reviewed |
| Layout: digital board | placed and autorouted, **not complete**: 11 nets unrouted, 7 isolated patches of ground pour |
| Parts | every catalogue number checked against JLCPCB; connectors, inductors, oscillator and buttons not chosen |
| Fabrication files (`hw/lib/fab.py`) | generated for the routed boards; placement rotations unchecked |
| Gateware core (`gateware/rtl`) | passes simulation, synthesises for `xc7a35t-ftg256`; on hold until a board exists |
| RP2040 firmware, host software | not started |

## Boards

Four boards joined by SMA cables. Each is a pair of Python scripts in
`hw/`: one writes the KiCad schematic, a PDF of it and a BOM, and checks
KiCad's reading of the netlist against the script; the other places the
footprints, routes the board and runs the design rule check.

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
- **Probe** (`hw/probe`): the tuning and matching capacitors for the
  sample coil, 1 kV parts with pads for hand-fitted variable capacitors,
  and a thermistor for the sample's temperature. Goes in a shielded box
  with the coil.

The amplifier's output network and the front end's quarter-wave sections
are fitted to one frequency. They are fitted for hexamine.

### Wiring

| From | To | Cable |
|------|----|-------|
| digital `TX HI`, `TX LO` | amplifier `HI IN`, `LO IN` | SMA |
| digital `PA EN` | amplifier `EN` | 2-pin |
| amplifier `TX OUT` | front end `TX IN` | SMA |
| front end `PROBE` | probe `TO FRONT END` | SMA |
| front end `RX OUT` | digital `RX IN` | SMA |
| digital `BLANK` | front end `PWR/BLANK` pins 3-4 | 2-pin |
| amplifier `12V OUT A` | front end `PWR/BLANK` pins 1-2 | 2-pin |
| amplifier `12V OUT B` | digital `12V IN` | 2-pin |
| probe `TEMP` | digital `TEMP` | 2-pin |

The digital board's logic runs from its USB port; 12 V only feeds its ADC.

### Known weak points

- The layouts are autorouted first passes. Nobody has looked at the
  amplifier feedback loops, return paths or the FPGA's supply routing.
- The OPA855 stages are fast enough to oscillate on a careless layout.
- The gateware drives the two bridge inputs as exact complements. The
  driver blocks both-on but adds no dead time; the gateware should.
- The FPGA's supplies come up in no particular order.
- The ADC's 5 V regulator drops 7 V at about 100 mA and will run warm.

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
python3 hw/fe/fe.py           # schematic; likewise pa, dig, probe; needs KiCad 9+
python3 hw/fe/fe_pcb.py --route   # layout; needs freerouting under tools/
python3 hw/lib/checkbom.py hw/*/*-bom.csv
python3 hw/lib/fab.py fe pa probe
```

The gateware is simulated and synthesised with
[reticle](https://github.com/KarpelesLab/reticle). `run_core.py` looks for
the binary at `tools/reticle-target/release/reticle`, or wherever the
`RETICLE` environment variable points.

## Safety

The probe coil and the probe board carry several hundred volts of RF
during a pulse. Sodium
nitrite is toxic in gram quantities: keep it in a sealed tube.
