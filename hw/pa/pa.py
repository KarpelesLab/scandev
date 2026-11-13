#!/usr/bin/env python3
"""Transmit amplifier: a half-bridge switching at the carrier frequency.

Two logic inputs from the FPGA (HI and LO, one coax each) drive a UCC27282
half-bridge driver and two MOSFETs.  A series capacitor and inductor and a
shunt capacitor turn the 50 ohm line into the ~6 ohm load the bridge needs
and remove the harmonics of the square wave: 3.8 W at 12 V, 6.0 W at 15 V
(sim/pa.py).  When the bridge is not switching it adds no noise, which the
passive receive isolation depends on.

The bridge is fed through 110 ohm from a large capacitor.  A pulse train
draws from the capacitor; a transmitter stuck on by a fault collapses the
rail instead of cooking the probe.

Band-setting parts: C10 (+C11), L1, C12 + C13: 3.9 nF, 1.5 uH and 2.2 nF + 470 pF
for 3.306 MHz.  They see under 50 V.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from build import main                                           # noqa: E402
from kisch import Schematic, define_symbol                       # noqa: E402
from parts import C, L, R, holes, led, sma                       # noqa: E402

s = Schematic("pa", "NQR transmit amplifier", paper="A3")

DRV = define_symbol("scandev:UCC27282DRC", [
    ("7", "HI", "L", "input"), ("8", "LI", "L", "input"), ("6", "EN", "L", "input"),
    ("3", "HB", "R", "passive"), ("4", "HO", "R", "output"), ("5", "HS", "R", "passive"),
    ("10", "LO", "R", "output"),
    ("1", "VDD", "T", "power_in"), ("2", "NC", "T", "no_connect"),
    ("9", "VSS", "B", "power_in"), ("11", "PAD", "B", "passive"),
])
FET = dict(fp="Package_TO_SOT_SMD:SOT-23", lcsc="C5122025", mpn="IRLML0060TRPBF",
           ref_off=(5.08, -2.54), val_off=(5.08, 2.54))

# ---------------------------------------------------------------- supply
s.text("SUPPLY  12 V in (9-15 V), passed on to the receive front end; bridge rail fed through 110 ohm",
       (8, 6))
y = 18
s.add("Connector:Barrel_Jack_Switch", "J1", "12V IN", (14, y), {"1": "VIN", "2": "GND", "3": "GND"},
      fp="Connector_BarrelJack:BarrelJack_Horizontal", lcsc="C431532", mpn="DC005-T")
s.add("Device:D_Schottky", "D1", "SS34", (30, y - 4), {"2": "VIN", "1": "VSYS"},
      fp="Diode_SMD:D_SMA", lcsc="C8678", mpn="SS34")
C(s, "C1", "10u 25V", (40, y + 2), "VSYS", "GND", pkg="1206")
# one 12 V feed each for the receive front end and the digital board's ADC rail
s.add("Connector_Generic:Conn_01x02", "J2", "12V OUT A", (50, y - 3), {"1": "VSYS", "2": "GND"},
      fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
s.add("Connector_Generic:Conn_01x02", "J7", "12V OUT B", (50, y + 5), {"1": "VSYS", "2": "GND"},
      fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
R(s, "R1", "220 1W", (66, y - 4), "VSYS", "VPA", pkg="2512", rot=90)
R(s, "R2", "220 1W", (66, y + 3), "VSYS", "VPA", pkg="2512", rot=90)
for i, ref in enumerate(["C2", "C3"]):
    s.add("Device:C_Polarized", ref, "1000u 25V", (80 + 8 * i, y), {"1": "VPA", "2": "GND"},
          fp="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm")
C(s, "C4", "10u 25V", (96, y), "VPA", "GND", pkg="1206")
C(s, "C5", "10u 25V", (104, y), "VPA", "GND", pkg="1206")
C(s, "C6", "100n 50V", (112, y), "VPA", "GND")
led(s, "D2", (124, y), "VSYS", "R3", r_value="4.7k")

# ---------------------------------------------------------------- driver
s.text("DRIVER  inputs idle low and the driver is disabled unless EN is driven high", (8, 34))
y = 52
sma(s, "J3", "HI IN", (12, y - 8), "HI_IN")
sma(s, "J4", "LO IN", (12, y + 2), "LO_IN")
s.add("Connector_Generic:Conn_01x02", "J5", "EN", (12, y + 14), {"1": "EN_IN", "2": "GND"},
      fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
R(s, "R4", "100", (28, y - 10), "HI_IN", "HI", rot=90)
R(s, "R5", "10k", (38, y - 4), "HI", "GND")
R(s, "R6", "100", (28, y + 2), "LO_IN", "LI", rot=90)
R(s, "R7", "10k", (38, y + 8), "LI", "GND")
R(s, "R8", "1k", (28, y + 14), "EN_IN", "EN", rot=90)
R(s, "R9", "100k", (38, y + 20), "EN", "GND")
C(s, "C7", "1n", (46, y + 20), "EN", "GND")
s.add(DRV, "U1", "UCC27282", (62, y),
      {"7": "HI", "8": "LI", "6": "EN", "3": "HB", "4": "HO", "5": "SW", "10": "LO",
       "1": "VDRV", "2": None, "9": "GND", "11": "GND"},
      fp="Package_SON:Texas_DRC0010J", lcsc="C2677035", mpn="UCC27282DRCR")
R(s, "R10", "10", (52, y - 14), "VSYS", "VDRV", rot=90)
C(s, "C8", "1u 25V", (62, y - 16), "VDRV", "GND")
C(s, "C9", "100n 50V", (78, y - 10), "HB", "SW", rot=90)

# ---------------------------------------------------------------- bridge, output
s.text("BRIDGE AND OUTPUT NETWORK", (88, 34))
R(s, "R11", "4.7", (92, y - 4), "HO", "GH", rot=90)
R(s, "R12", "4.7", (92, y + 10), "LO", "GL", rot=90)
s.add("Transistor_FET:IRLML0030", "Q1", "IRLML0060", (106, y - 4),
      {"1": "GH", "3": "VPA", "2": "SW"}, **FET)
s.add("Transistor_FET:IRLML0030", "Q2", "IRLML0060", (106, y + 10),
      {"1": "GL", "3": "SW", "2": "GND"}, **FET)
R(s, "R13", "10k", (118, y + 8), "SW", "GND")
C(s, "C10", "3.9n C0G", (128, y - 4), "SW", "TANK", pkg="0805", rot=90)
C(s, "C11", "DNP", (128, y + 4), "SW", "TANK", pkg="0805", rot=90)
L(s, "L1", "1.5u", (142, y - 4), "TANK", "TX_OUT", fp="Inductor_SMD:L_Bourns_SRP5030T",
  mpn="1.5uH >=3A")
C(s, "C12", "2.2n C0G", (134, y + 14), "TX_OUT", "GND", pkg="0805")
C(s, "C13", "470p C0G", (144, y + 14), "TX_OUT", "GND", pkg="0805")
sma(s, "J6", "TX OUT", (156, y), "TX_OUT")

for i, net in enumerate(["VIN", "GND", "VSYS", "VPA", "VDRV"]):
    s.flag(net, (112 + 10 * i, 84))
holes(s, (20, 90))

if __name__ == "__main__":
    main(s, __file__)
