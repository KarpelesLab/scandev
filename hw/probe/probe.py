#!/usr/bin/env python3
"""Probe board: tuning and matching capacitors for the sample coil.

    SMA --+-- Cm --+---------+--- coil
                   |         |
                   Ct       (coil, wound on the sample tube, on J2)
                   |         |
                  gnd -------+

The coil resonates with the tuning capacitance Ct, and the series matching
capacitance Cm brings the tank to 50 ohm.  For the 25-turn, 7.3 uH coil at
3.306 MHz: Ct = 245-270 pF and Cm = 45-70 pF, depending on the coil's Q
(sim/probe.py).  The tank reaches 350-400 V peak at 4 W, so the fixed parts
are 1 kV C0G; each has spare positions, and CV1 and CV2 are pads for
variable capacitors rated for that voltage, fitted by hand.

RT1 is a thermistor for the sample's temperature (the line moves with it),
read by the digital board through J3.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from build import main                                           # noqa: E402
from kisch import Schematic                                      # noqa: E402
from parts import C, holes, sma                                  # noqa: E402

s = Schematic("probe", "NQR probe tuning board", paper="A4")
s.text("PROBE  fixed 1 kV capacitors plus hand-fitted variables; coil on J2", (8, 8))

sma(s, "J1", "TO FRONT END", (14, 24), "PROBE")
for i, v in enumerate(["22p 1kV C0G", "22p 1kV C0G", "DNP", "DNP"]):
    C(s, f"CM{i+1}", v, (30, 16 + 6 * i), "PROBE", "TANK", pkg="1206", rot=90)
s.add("Device:C_Variable", "CV2", "MATCH 5-30p", (30, 42), {"1": "PROBE", "2": "TANK"}, rot=90,
      fp="Connector_Wire:SolderWire-0.75sqmm_1x02_P7mm_D1.25mm_OD3.5mm",
      mpn="variable capacitor, >=500 V")
for i, v in enumerate(["100p 1kV C0G", "100p 1kV C0G", "22p 1kV C0G", "22p 1kV C0G", "DNP", "DNP"]):
    C(s, f"CT{i+1}", v, (46 + 8 * i, 30), "TANK", "GND", pkg="1206")
s.add("Device:C_Variable", "CV1", "TUNE 5-40p", (96, 30), {"1": "TANK", "2": "GND"},
      fp="Connector_Wire:SolderWire-0.75sqmm_1x02_P7mm_D1.25mm_OD3.5mm",
      mpn="variable capacitor, >=500 V")
s.add("Connector:Screw_Terminal_01x02", "J2", "COIL", (110, 26), {"1": "TANK", "2": "GND"},
      fp="TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal")

s.add("Device:Thermistor_NTC", "RT1", "10k NTC", (30, 58), {"1": "TEMP", "2": "GND"},
      fp="Resistor_SMD:R_0603_1608Metric", mpn="10k B3950 NTC 0603")
s.add("Connector_Generic:Conn_01x02", "J3", "TEMP", (14, 56), {"1": "TEMP", "2": "GND"},
      fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
s.flag("GND", (60, 52))
holes(s, (76, 58))

if __name__ == "__main__":
    main(s, __file__)
