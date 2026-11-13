#!/usr/bin/env python3
"""Receive front end: transmit/receive isolation and low-noise amplifier.

Three coax ports -- TX from the amplifier, PROBE to the tuned coil, RX to the
ADC -- plus a four-pin header for power and the blanking signal.

Band-setting parts (L1-L3, C1-C6) are fitted for the 3.306 MHz line of
hexamine: 2.2 uH and 1 nF make a 46 ohm quarter-wave section there.  The
capacitors are 50 V parts, enough for the 18 V peak a 5 W pulse puts on the
probe port; a much stronger amplifier needs higher-voltage ones at C1.  For
another line at frequency f: L = 50 / (2 pi f), C = 1 / (2 pi f 50), and
check it with sim/frontend.py before transmitting.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from build import main                                           # noqa: E402
from kisch import Schematic                                      # noqa: E402
from parts import C, FB, L, R, crossed, sma                      # noqa: E402

s = Schematic("fe", "NQR receive front end", paper="A3")
OPA = "Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm"
# a 5 x 5 mm shielded power inductor; its loss at 3.3 MHz is not in the
# datasheet and has to be measured
IND = dict(fp="Inductor_SMD:L_Changjiang_FNR5040S", lcsc="C167957", mpn="FNR5040S2R2MT")

# ---------------------------------------------------------------- transmit side
s.text("TRANSMIT ISOLATOR  series crossed diodes pass the pulse, block amplifier noise afterwards",
       (8, 6))
y = 18
sma(s, "J1", "TX IN", (12, y), "TX_IN")
crossed(s, "D1", (28, y - 6), "TX_IN", "TXA", rot=90)
crossed(s, "D2", (28, y + 6), "TX_IN", "TXA", rot=90)
R(s, "R1", "470", (40, y), "TXA", "GND", pkg="1206")
crossed(s, "D3", (54, y - 6), "TXA", "TXB", rot=90)
crossed(s, "D4", (54, y + 6), "TXA", "TXB", rot=90)
R(s, "R2", "470", (66, y), "TXB", "GND", pkg="1206")
crossed(s, "D5", (80, y - 6), "TXB", "PROBE", rot=90)
crossed(s, "D6", (80, y + 6), "TXB", "PROBE", rot=90)
sma(s, "J2", "PROBE", (96, y), "PROBE")

# ---------------------------------------------------------------- receive side
s.text("RECEIVE ISOLATOR  three lumped quarter-wave sections, each ending in crossed diodes to ground",
       (8, 29))
y = 40
x = 12
nodes = ["PROBE", "Q1", "Q2", "Q3"]
cn = dn = 0
for k in range(3):
    a, b = nodes[k], nodes[k + 1]
    cn += 1
    C(s, f"C{cn}", "1n C0G", (x, y), a, "GND", pkg="0805")
    L(s, f"L{k+1}", "2.2u", (x + 12, y - 4), a, b, **IND)
    cn += 1
    C(s, f"C{cn}", "1n C0G", (x + 22, y), b, "GND", pkg="0805")
    crossed(s, f"D{7+dn}", (x + 33, y - 3), b, "GND")
    crossed(s, f"D{8+dn}", (x + 33, y + 4), b, "GND")
    dn += 2
    x += 46
R(s, "R3", "49.9", (x + 2, y), "Q3", "GND")

# ---------------------------------------------------------------- amplifier
s.text("LOW-NOISE AMPLIFIER  two stages of x21, blanking switch between them, 8 MHz low-pass to the ADC",
       (8, 50))
y = 62
OPK = dict(fp=OPA, lcsc="C1409030", mpn="OPA855IDSGR", ref_off=(2.54, -6.35), val_off=(2.54, 6.35))
C(s, "C7", "100n", (14, y - 7), "Q3", "LNA1_P", rot=90)
R(s, "R4", "1k", (22, y + 7), "LNA1_P", "VMID")
s.add("Amplifier_Operational:OPA855xDSG", "U1", "OPA855", (36, y),
      {"4": "LNA1_P", "3": "LNA1_N", "1": "LNA1_FB", "6": "LNA1_OUT",
       "7": "VA1", "8": "VA1", "5": "GND", "9": "GND", "2": None}, **OPK)
R(s, "R5", "200", (52, y - 7), "LNA1_FB", "LNA1_N", rot=90)
R(s, "R6", "10", (50, y + 8), "LNA1_N", "LNA1_G")
C(s, "C8", "1u", (57, y + 8), "LNA1_G", "GND")
R(s, "R9", "49.9", (70, y - 7), "LNA1_OUT", "LNA1_F", rot=90)
C(s, "C13", "390p C0G", (66, y + 8), "LNA1_F", "GND")
C(s, "C12", "100n", (86, y - 7), "LNA1_F", "SW_SIG", rot=90)
R(s, "R7", "10k", (78, y + 8), "SW_SIG", "VMID")

SW = "Analog_Switch:TS5A3159DCK"
SWP = dict(fp="Package_TO_SOT_SMD:SOT-363_SC-70-6", lcsc="C46388", mpn="TS5A3159DCKR")
# IN low: COM = NC (signal).  IN high: COM = NO (mid-rail), receiver blanked.
s.add(SW, "U2", "TS5A3159", (96, y + 1), {"3": "SW_SIG", "1": "VMID", "4": "LNA2_P", "6": "BLANK_B"},
      unit=1, **SWP)
s.add(SW, "U2", "TS5A3159", (88, y + 14), {"5": "+5VA", "2": "GND"}, unit=2, **SWP)
R(s, "R8", "10k", (106, y + 8), "LNA2_P", "VMID")
s.add("Amplifier_Operational:OPA855xDSG", "U3", "OPA855", (120, y),
      {"4": "LNA2_P", "3": "LNA2_N", "1": "LNA2_FB", "6": "LNA2_OUT",
       "7": "VA2", "8": "VA2", "5": "GND", "9": "GND", "2": None}, **OPK)
R(s, "R10", "200", (136, y - 7), "LNA2_FB", "LNA2_N", rot=90)
R(s, "R11", "10", (134, y + 8), "LNA2_N", "LNA2_G")
C(s, "C14", "1u", (141, y + 8), "LNA2_G", "GND")
R(s, "R12", "49.9", (153, y - 7), "LNA2_OUT", "OUT_A", rot=90)
C(s, "C17", "100n", (153, y), "OUT_A", "OUT_B", rot=90)
C(s, "C18", "390p C0G", (110, y + 20), "OUT_B", "GND")
L(s, "L4", "2.2u", (122, y + 16), "OUT_B", "RX_OUT", **IND)
C(s, "C19", "390p C0G", (134, y + 20), "RX_OUT", "GND")
sma(s, "J3", "RX OUT", (150, y + 18), "RX_OUT")

# ---------------------------------------------------------------- power, control
s.text("POWER AND CONTROL  7-16 V in, 5 V low-noise regulator, mid-rail reference, blanking input",
       (8, 86))
y = 96
s.add("Connector_Generic:Conn_01x04", "J4", "PWR/BLANK", (12, y),
      {"1": "VIN", "2": "GND", "3": "BLANK", "4": "GND"},
      fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")
s.add("Device:D_Schottky", "D13", "B5819W", (26, y - 5), {"2": "VIN", "1": "VIN_P"},
      fp="Diode_SMD:D_SOD-123", lcsc="C8598", mpn="B5819W")
C(s, "C21", "10u 25V", (36, y), "VIN_P", "GND", pkg="0805")
s.add("Regulator_Linear:LP2985-5.0", "U4", "LP2985-5.0", (50, y - 2),
      {"VIN": "VIN_P", "ON/~{OFF}": "VIN_P", "GND": "GND", "BP": "LDO_BP", "VOUT": "+5VA"},
      fp="Package_TO_SOT_SMD:SOT-23-5", lcsc="C74511", mpn="LP2985-50DBVR")
C(s, "C22", "10n", (64, y), "LDO_BP", "GND")
C(s, "C23", "10u", (70, y), "+5VA", "GND", pkg="0805")
FB(s, "FB1", (80, y - 5), "+5VA", "VA1")
C(s, "C10", "100n", (78, y + 2), "VA1", "GND")
C(s, "C11", "1u", (84, y + 2), "VA1", "GND")
FB(s, "FB2", (96, y - 5), "+5VA", "VA2")
C(s, "C15", "100n", (94, y + 2), "VA2", "GND")
C(s, "C16", "1u", (100, y + 2), "VA2", "GND")
C(s, "C9", "100n", (108, y), "+5VA", "GND")          # at U2
R(s, "R15", "10k", (116, y - 6), "+5VA", "VMID")
R(s, "R16", "10k", (123, y - 5), "VMID", "GND")
C(s, "C24", "10u", (130, y - 5), "VMID", "GND", pkg="0805")
C(s, "C25", "100n", (136, y - 5), "VMID", "GND")
R(s, "R17", "2.2k", (144, y - 5), "+5VA", "LED_A")
s.add("Device:LED", "D14", "green", (152, y - 5), {"2": "LED_A", "1": "GND"}, rot=90,
      fp="LED_SMD:LED_0603_1608Metric", lcsc="C72043", ref_off=(3.81, -1.27), val_off=(3.81, 1.27))
R(s, "R13", "100", (26, y + 6), "BLANK", "BLANK_B", rot=90)
R(s, "R14", "10k", (40, y + 10), "BLANK_B", "GND")
C(s, "C20", "100p", (46, y + 10), "BLANK_B", "GND")

for i, net in enumerate(["VIN", "GND", "VIN_P", "VA1", "VA2"]):
    s.flag(net, (112 + 10 * i, 8))
for i in range(4):
    s.add("Mechanical:MountingHole", f"H{i+1}", "M3", (120 + 8 * i, 22), {},
          fp="MountingHole:MountingHole_3.2mm_M3", hide_value=True)

if __name__ == "__main__":
    main(s, __file__)
