#!/usr/bin/env python3
"""Digital board: FPGA, ADC, and the RP2040 that looks after them.

  * RP2040 with its own USB-C port, BOOTSEL and reset buttons.  It loads the
    FPGA (slave serial, or JTAG on the same wires as the header), talks to it
    over SPI plus a few spare lines, and keeps bitstreams and scan results on
    a microSD card.
  * XC7A35T-FTG256.  It has no configuration flash: the RP2040 loads it at
    every power-up from the card.
  * AD9226 12-bit ADC clocked at 50 MHz from the same oscillator as the FPGA,
    single-ended 1 V span, 50 ohm SMA input from the receive front end.
  * Outputs to the amplifier (HI, LO on coax; enable on a header) and to the
    front end (blanking).

Logic runs from USB.  The ADC's 5 V analogue rail comes from the 12 V system
supply through a linear regulator, so the converter is off when 12 V is.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from build import main                                           # noqa: E402
from kisch import Schematic, define_symbol                       # noqa: E402
from parts import C, FB, L, R, button, caps, holes, led, sma     # noqa: E402

s = Schematic("dig", "NQR digital board", paper="A1")
HDR = "Connector_PinHeader_2.54mm:PinHeader_"


def header(ref, value, at, nets, cols=1):
    n = len(nets)
    if cols == 1:
        s.add(f"Connector_Generic:Conn_01x{n:02d}", ref, value, at,
              {str(i + 1): v for i, v in enumerate(nets)}, fp=f"{HDR}1x{n:02d}_P2.54mm_Vertical")
    else:
        s.add(f"Connector_Generic:Conn_02x{n//2:02d}_Odd_Even", ref, value, at,
              {str(i + 1): v for i, v in enumerate(nets)},
              fp=f"{HDR}2x{n//2:02d}_P2.54mm_Vertical")


# =========================================================== USB and RP2040
s.text("USB AND RP2040  USB-C for programming and data; BOOTSEL held at reset enters the USB boot loader",
       (8, 8), size=2.5)
s.add("Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C", (18, 30),
      {"VBUS": "VBUS", "GND": "GND", "SHIELD": "GND", "CC1": "CC1", "CC2": "CC2",
       "D+": "USB_DP_C", "D-": "USB_DM_C", "SBU1": None, "SBU2": None},
      fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948",
      mpn="TYPE-C-31-M-12")
R(s, "R1", "5.1k", (34, 18), "CC1", "GND")
R(s, "R2", "5.1k", (40, 18), "CC2", "GND")
s.add("Device:Polyfuse", "F1", "1A hold", (34, 30), {"1": "VBUS", "2": "+5V"}, rot=90,
      fp="Fuse:Fuse_1206_3216Metric", lcsc="C20800", mpn="SMD1206P100TF")
s.add("Power_Protection:USBLC6-2SC6", "U1", "USBLC6-2SC6", (48, 40),
      {"1": "USB_DP_C", "6": "USB_DP_C", "3": "USB_DM_C", "4": "USB_DM_C",
       "5": "VBUS", "2": "GND"},
      fp="Package_TO_SOT_SMD:SOT-23-6", lcsc="C7519", mpn="USBLC6-2SC6")
R(s, "R3", "27", (34, 50), "USB_DP_C", "USB_DP", rot=90)
R(s, "R4", "27", (34, 56), "USB_DM_C", "USB_DM", rot=90)

GP = {
    0: "FPGA_CCLK_R", 1: "FPGA_DIN", 2: "FPGA_PROG_B", 3: "FPGA_INIT_B", 4: "FPGA_DONE",
    5: "JTAG_TCK", 6: "JTAG_TMS", 7: "JTAG_TDI", 8: "JTAG_TDO",
    9: "FL_IO2", 10: "FL_SCK", 11: "FL_MOSI", 12: "FL_MISO", 13: "FL_CS", 14: "FL_IRQ",
    15: "FL_IO1", 16: "FL_IO3", 17: "SD_DET", 18: "SD_CLK", 19: "SD_CMD",
    20: "SD_DAT0", 21: "SD_DAT1", 22: "SD_DAT2", 23: "SD_DAT3", 24: "EXP_GP24",
    25: "LED_RP", 26: "TEMP", 27: "V12_SENSE", 28: "EXP_GP28", 29: "EXP_GP29",
}
rp = {"IOVDD": "+3V3", "DVDD": "RP_1V1", "VREG_VIN": "+3V3", "VREG_VOUT": "RP_1V1",
      "USB_VDD": "+3V3", "ADC_AVDD": "+3V3", "TESTEN": "GND", "GND": "GND",
      "XIN": "XIN", "XOUT": "XOUT", "SWCLK": "SWCLK", "SWDIO": "SWDIO", "RUN": "RP_RUN",
      "USB_DP": "USB_DP", "USB_DM": "USB_DM",
      "QSPI_SD0": "QSPI_SD0", "QSPI_SD1": "QSPI_SD1", "QSPI_SD2": "QSPI_SD2",
      "QSPI_SD3": "QSPI_SD3", "QSPI_SCLK": "QSPI_SCLK", "~{QSPI_SS}": "QSPI_SS"}
for g, net in GP.items():
    rp[f"GPIO{g}" + (f"/ADC{g-26}" if g >= 26 else "")] = net
s.add("MCU_RaspberryPi:RP2040", "U2", "RP2040", (84, 46), rp, stub=2,
      fp="Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm", lcsc="C2040", mpn="RP2040",
      ref_off=(-25.4, -50.8), val_off=(-15.24, -50.8))

s.add("Memory_Flash:W25Q16JVSS", "U3", "W25Q16JV", (132, 22),
      {"~{CS}": "QSPI_SS", "DO/IO_{1}": "QSPI_SD1", "~{WP}/IO_{2}": "QSPI_SD2", "GND": "GND",
       "DI/IO_{0}": "QSPI_SD0", "CLK": "QSPI_SCLK", "~{HOLD}/~{RESET}/IO_{3}": "QSPI_SD3",
       "VCC": "+3V3"},
      fp="Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", lcsc="C131025", mpn="W25Q16JVSSIQ")
C(s, "C1", "100n", (150, 22), "+3V3", "GND")
R(s, "R5", "10k", (158, 22), "+3V3", "QSPI_SS")
R(s, "R6", "1k", (166, 20), "QSPI_SS", "BOOT_SW", rot=90)
button(s, "SW1", "BOOTSEL", (178, 20), "BOOT_SW")
R(s, "R7", "10k", (158, 36), "+3V3", "RP_RUN")
button(s, "SW2", "RESET", (178, 34), "RP_RUN")
C(s, "C2", "100n", (166, 38), "RP_RUN", "GND")

s.add("Device:Crystal_GND24", "Y1", "12MHz", (132, 46), {"1": "XIN", "3": "XTAL_O", "2": "GND",
                                                        "4": "GND"},
      fp="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", lcsc="C9002", mpn="X322512MSB4SI")
C(s, "C3", "15p", (122, 54), "XIN", "GND")
C(s, "C4", "15p", (142, 54), "XTAL_O", "GND")
R(s, "R8", "1k", (150, 46), "XOUT", "XTAL_O", rot=90)
header("J2", "SWD", (164, 50), ["SWCLK", "GND", "SWDIO"])
led(s, "D1", (178, 50), "LED_RP", "R9", r_value="1k", net="LED_RP_A")

n = caps(s, "C", 5, "+3V3", ["100n"] * 8 + ["1u"], (122, 66))
n = caps(s, "C", n, "RP_1V1", ["100n", "100n", "1u"], (180, 66))

# =========================================================== microSD
s.text("microSD  SPI or 4-bit SDIO; holds FPGA bitstreams and scan results", (200, 8), size=2.5)
# the detect switch is between pins 9 and 10: one side grounded, the other pulled up
s.add("Connector:Micro_SD_Card_Det2", "J3", "microSD", (228, 26),
      {"DAT2": "SD_DAT2", "DAT3/CD": "SD_DAT3", "CMD": "SD_CMD", "VDD": "+3V3",
       "CLK": "SD_CLK", "VSS": "GND", "DAT0": "SD_DAT0", "DAT1": "SD_DAT1", "9": "SD_DET", "10": "GND",
       "SHIELD": "GND"},
      fp="Connector_Card:microSD_HC_Molex_104031-0811", lcsc="C585350", mpn="104031-0811")
for i, net in enumerate(["SD_CMD", "SD_DAT0", "SD_DAT1", "SD_DAT2", "SD_DAT3", "SD_DET"]):
    R(s, f"R{10+i}", "10k", (202 + 6 * i, 44), "+3V3", net)
C(s, "C17", "10u", (244, 44), "+3V3", "GND", pkg="0805")
C(s, "C18", "100n", (250, 44), "+3V3", "GND")

# =========================================================== power
s.text("POWER  logic from USB 5 V; ADC analogue rail from the 12 V system supply", (262, 8), size=2.5)
BUCK = dict(fp="Package_TO_SOT_SMD:SOT-23-5", lcsc="C141836", mpn="TLV62569DBVR")
IND = dict(fp="Inductor_SMD:L_Taiyo-Yuden_NR-50xx", lcsc="C167957", mpn="FNR5040S2R2MT")
for k, (rail, rtop, rbot, x) in enumerate([("+3V3", "100k", "22k", 270), ("+1V0", "100k", "150k", 270)]):
    y = 22 + 26 * k
    u = f"U{4+k}"
    s.add("Regulator_Switching:TLV62569DBV", u, "TLV62569", (x, y),
          {"VIN": "+5V", "EN": "+5V", "GND": "GND", "SW": f"SW{k+1}", "FB": f"FB{k+1}"}, **BUCK)
    C(s, f"C{19+3*k}", "10u", (x - 14, y + 4), "+5V", "GND", pkg="0805")
    L(s, f"L{k+1}", "2.2u", (x + 16, y - 6), f"SW{k+1}", rail, **IND)
    R(s, f"R{16+2*k}", rtop, (x + 28, y - 2), rail, f"FB{k+1}")
    R(s, f"R{17+2*k}", rbot, (x + 28, y + 8), f"FB{k+1}", "GND")
    C(s, f"C{20+3*k}", "22u", (x + 36, y + 2), rail, "GND", pkg="0805")
    C(s, f"C{21+3*k}", "22u", (x + 42, y + 2), rail, "GND", pkg="0805")
s.add("Regulator_Linear:XC6206PxxxMR", "U6", "XC6206P182", (270, 76),
      {"VI": "+3V3", "GND": "GND", "VO": "+1V8"},
      fp="Package_TO_SOT_SMD:SOT-23", lcsc="C51886219", mpn="XC6206P182MR")
C(s, "C25", "1u", (256, 80), "+3V3", "GND")
C(s, "C26", "1u", (286, 80), "+1V8", "GND")
C(s, "C27", "10u", (292, 80), "+1V8", "GND", pkg="0805")

header("J4", "12V IN", (262, 98), ["V12", "GND"])
R(s, "R20", "10", (274, 94), "V12", "V12_F", pkg="1206", rot=90)
C(s, "C28", "10u 25V", (284, 100), "V12_F", "GND", pkg="1206")
s.add("Regulator_Linear:AMS1117-5.0", "U7", "AMS1117-5.0", (296, 96),
      {"VI": "V12_F", "GND": "GND", "VO": "+5VA"},
      fp="Package_TO_SOT_SMD:SOT-223-3_TabPin2", lcsc="C6187", mpn="AMS1117-5.0")
C(s, "C29", "22u", (308, 100), "+5VA", "GND", pkg="0805")
C(s, "C30", "100n", (314, 100), "+5VA", "GND")
R(s, "R21", "100k", (262, 112), "V12", "V12_SENSE")
R(s, "R22", "22k", (270, 112), "V12_SENSE", "GND")
C(s, "C31", "100n", (278, 112), "V12_SENSE", "GND")
led(s, "D2", (290, 112), "+3V3", "R23", r_value="1k", net="LED_PWR_A")
led(s, "D3", (308, 112), "+5VA", "R24", r_value="2.2k", net="LED_5VA_A")

# =========================================================== clock and ADC
s.text("CLOCK AND ADC  one 50 MHz oscillator for FPGA and converter; 1 V span, single-ended",
       (200, 60), size=2.5)
s.add("Oscillator:ASE-xxxMHz", "X1", "50MHz", (208, 76),
      {"EN": "XO_VDD", "GND": "GND", "OUT": "CLK_XO", "Vdd": "XO_VDD"},
      fp="Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm",
      lcsc="C26267", mpn="SiT8008BI-22-33E-50.000000")
FB(s, "FB1", (204, 66), "+3V3", "XO_VDD")
C(s, "C32", "100n", (216, 66), "XO_VDD", "GND")
R(s, "R25", "33", (222, 74), "CLK_XO", "CLK50", rot=90)
R(s, "R26", "33", (222, 80), "CLK_XO", "CLKBUF_IN", rot=90)
# 5 V buffer: the converter's clock input wants 3.5 V for a high
s.add("74xGxx:74AHCT1G125", "U8", "74AHCT1G125", (236, 82),
      {"1": "GND", "2": "CLKBUF_IN", "3": "GND", "4": "CLKBUF_OUT", "5": "+5VA"},
      fp="Package_TO_SOT_SMD:SOT-23-5", lcsc="C7484", mpn="SN74AHCT1G125DBVR")
C(s, "C33", "100n", (246, 74), "+5VA", "GND")
R(s, "R27", "33", (250, 84), "CLKBUF_OUT", "ADC_CLK", rot=90)

ADC = define_symbol("scandev:AD9226ARS", [
    ("23", "VINA", "L", "input"), ("24", "VINB", "L", "input"), ("", "", "L", ""),
    ("18", "VREF", "L", "passive"), ("17", "SENSE", "L", "input"), ("21", "CAPT", "L", "passive"),
    ("20", "CAPB", "L", "passive"), ("", "", "L", ""), ("22", "MODE", "L", "input"),
    ("1", "CLK", "L", "input"),
    ("13", "BIT1", "R", "output"), ("12", "BIT2", "R", "output"), ("11", "BIT3", "R", "output"),
    ("10", "BIT4", "R", "output"), ("9", "BIT5", "R", "output"), ("8", "BIT6", "R", "output"),
    ("7", "BIT7", "R", "output"), ("6", "BIT8", "R", "output"), ("5", "BIT9", "R", "output"),
    ("4", "BIT10", "R", "output"), ("3", "BIT11", "R", "output"), ("2", "BIT12", "R", "output"),
    ("14", "OTR", "R", "output"),
    ("15", "AVDD", "T", "power_in"), ("26", "AVDD", "T", "power_in"),
    ("28", "DRVDD", "T", "power_in"),
    ("16", "AVSS", "B", "power_in"), ("25", "AVSS", "B", "power_in"),
    ("19", "REFCOM", "B", "power_in"), ("27", "DRVSS", "B", "power_in"),
])
adc = {"23": "ADC_INP", "24": "ADC_INN", "18": "ADC_VREF", "17": "ADC_VREF", "21": "ADC_CAPT",
       "20": "ADC_CAPB", "22": "GND", "1": "ADC_CLK", "14": "ADC_OTR_A",
       "15": "+5VA", "26": "+5VA", "28": "ADC_DRVDD", "16": "GND", "25": "GND", "19": "GND",
       "27": "GND"}
for bit in range(1, 13):                       # BIT1 is the MSB
    adc[str(14 - bit)] = f"ADC_D{12-bit}_A"
s.add(ADC, "U9", "AD9226ARSZ", (246, 108), adc, stub=2,
      fp="Package_SO:SSOP-28_5.3x10.2mm_P0.65mm", lcsc="C730053", mpn="AD9226ARSZ")
sma(s, "J5", "RX IN", (204, 96), "RX_IN")
R(s, "R28", "49.9", (212, 104), "RX_IN", "GND")
C(s, "C34", "100n", (218, 94), "RX_IN", "ADC_AC", rot=90)
R(s, "R29", "1k", (224, 104), "ADC_AC", "ADC_VREF")
R(s, "R30", "33", (228, 94), "ADC_AC", "ADC_INP", rot=90)
C(s, "C35", "22p", (204, 114), "ADC_INP", "ADC_INN")
R(s, "R31", "33", (212, 118), "ADC_VREF", "ADC_INN", rot=90)
C(s, "C36", "100n", (218, 124), "ADC_INN", "GND")
C(s, "C37", "10u", (204, 128), "ADC_VREF", "GND", pkg="0805")
C(s, "C38", "100n", (210, 128), "ADC_VREF", "GND")
C(s, "C39", "100n", (224, 128), "ADC_CAPT", "GND")
C(s, "C40", "100n", (230, 128), "ADC_CAPB", "GND")
C(s, "C41", "10u", (238, 132), "ADC_CAPT", "ADC_CAPB", pkg="0805", rot=90)
C(s, "C42", "100n", (238, 138), "ADC_CAPT", "ADC_CAPB", rot=90)
FB(s, "FB2", (266, 124), "+3V3", "ADC_DRVDD")
C(s, "C43", "100n", (276, 128), "ADC_DRVDD", "GND")
n = caps(s, "C", 44, "+5VA", ["10u", "100n", "100n"], (284, 128))
# series resistors on the data bus keep its edges out of the analogue side
for k in range(3):
    nets = {}
    for j in range(4):
        b = 4 * k + j
        nets[str(j + 1)] = f"ADC_D{b}_A"
        nets[str(8 - j)] = f"ADC_D{b}"
    s.add("Device:R_Pack04", f"RN{k+1}", "33", (286 + 12 * k, 144), nets,
          fp="Resistor_SMD:R_Array_Convex_4x0603", lcsc="C25508", mpn="4D03WGJ0330T5E")
R(s, "R32", "33", (322, 142), "ADC_OTR_A", "ADC_OTR", rot=90)

# =========================================================== FPGA
s.text("FPGA  XC7A35T-FTG256; loaded by the RP2040 (slave serial, M[2:0] = 111) or over JTAG",
       (8, 84), size=2.5)
F = "FPGA_Xilinx_Artix7:XC7A35T-FTG256"
FK = dict(fp="Package_BGA:Xilinx_FTG256", lcsc="C181716", mpn="XC7A35T-2FTG256C", rest_open=True)
b14_15 = {"VCCO_14": "+3V3", "VCCO_15": "+3V3",
          "J14": "FPGA_DIN", "L15": "PUDC_B",
          "T5": "FL_SCK", "T7": "FL_MOSI", "T8": "FL_MISO", "T9": "FL_CS", "T10": "FL_IRQ",
          "R5": "FL_IO1", "R6": "FL_IO2", "R7": "FL_IO3",
          "A8": "PM1", "A9": "PM2", "A10": "PM3", "A12": "PM4",
          "A13": "PM5", "A14": "PM6", "A15": "PM7", "B16": "PM8"}
s.add(F, "U10", "XC7A35T-FTG256", (60, 160), b14_15, unit=1, **FK)
b34_35 = {"VCCO_34": "+3V3", "VCCO_35": "+3V3", "D4": "CLK50",
          "M1": "TX_HI_F", "N1": "TX_LO_F", "P1": "PA_EN_F", "R1": "BLANK_F", "T2": "QDAMP_F",
          "T3": "TRIG_OUT_F", "T4": "TRIG_IN_F", "M2": "LED_F1", "N2": "LED_F2", "R2": "BTN_F",
          "C2": "ADC_OTR"}
for bit, ball in enumerate(["A2", "A3", "A4", "A5", "A7", "B1", "B2", "B4", "B5", "B6", "B7", "C1"]):
    b34_35[ball] = f"ADC_D{bit}"
s.add(F, "U10", "XC7A35T-FTG256", (140, 160), b34_35, unit=2, **FK)
s.add(F, "U10", "XC7A35T-FTG256", (190, 160),
      {"CFGBVS_0": "+3V3", "VCCO_0": "+3V3", "CCLK_0": "FPGA_CCLK", "DONE_0": "FPGA_DONE",
       "INIT_B_0": "FPGA_INIT_B", "PROGRAM_B_0": "FPGA_PROG_B",
       "M0_0": "CFG_M", "M1_0": "CFG_M", "M2_0": "CFG_M",
       "TCK_0": "JTAG_TCK", "TMS_0": "JTAG_TMS", "TDI_0": "JTAG_TDI", "TDO_0": "JTAG_TDO",
       "VREFN_0": "GND", "VREFP_0": "GND", "VP_0": "GND", "VN_0": "GND",
       "DXP_0": "GND", "DXN_0": "GND"}, unit=3, **FK)
s.add(F, "U10", "XC7A35T-FTG256", (250, 170),
      {"GND": "GND", "VCCINT": "+1V0", "VCCBRAM": "+1V0", "VCCAUX": "+1V8",
       "VCCADC_0": "+1V8", "GNDADC_0": "GND", "VCCBATT_0": "GND"}, unit=4, **FK)

R(s, "R33", "33", (306, 172), "FPGA_CCLK_R", "FPGA_CCLK", rot=90)
for i, (net, val, rail) in enumerate([("FPGA_PROG_B", "4.7k", "+3V3"), ("FPGA_INIT_B", "4.7k", "+3V3"),
                                      ("FPGA_DONE", "4.7k", "+3V3"), ("CFG_M", "1k", "+3V3"),
                                      ("PUDC_B", "1k", "GND")]):
    if rail == "GND":
        R(s, f"R{34+i}", val, (298 + 7 * i, 182), net, rail)
    else:
        R(s, f"R{34+i}", val, (298 + 7 * i, 182), rail, net)
header("J6", "JTAG", (296, 160), ["+3V3", "GND", "JTAG_TCK", "JTAG_TMS", "JTAG_TDI", "JTAG_TDO"])

s.text("FPGA decoupling (0402 under the package)", (200, 193), size=2.0)
n = caps(s, "C", 50, "+1V0", ["22u", "22u", "4.7u", "4.7u"] + ["100n"] * 6, (204, 199), pkg="0402")
n = caps(s, "C", n, "+1V8", ["22u", "4.7u"] + ["100n"] * 4, (270, 199), pkg="0402")
n = caps(s, "C", n, "+3V3", ["22u", "22u", "4.7u", "4.7u", "4.7u", "4.7u"] + ["100n"] * 10,
         (204, 210), pkg="0402")

# =========================================================== connectors
s.text("OUTPUTS, HEADERS, INDICATORS", (8, 196), size=2.5)
R(s, "R39", "49.9", (16, 204), "TX_HI_F", "TX_HI", rot=90)
sma(s, "J7", "TX HI", (30, 204), "TX_HI")
R(s, "R40", "49.9", (16, 214), "TX_LO_F", "TX_LO", rot=90)
sma(s, "J8", "TX LO", (30, 214), "TX_LO")
for i, sig in enumerate(["PA_EN", "BLANK", "QDAMP", "TRIG_OUT"]):
    R(s, f"R{41+i}", "100", (48, 202 + 5 * i), f"{sig}_F", sig, rot=90)
R(s, "R45", "1k", (48, 222), "TRIG_IN", "TRIG_IN_F", rot=90)
header("J9", "PA EN", (66, 202), ["PA_EN", "GND"])
header("J10", "BLANK", (78, 202), ["BLANK", "GND"])
header("J11", "QDAMP", (90, 202), ["QDAMP", "GND"])
header("J12", "TRIG", (104, 204), ["TRIG_OUT", "GND", "TRIG_IN", "GND"])
header("J13", "PMOD", (124, 206), ["PM1", "PM5", "PM2", "PM6", "PM3", "PM7", "PM4", "PM8",
                                   "GND", "GND", "+3V3", "+3V3"], cols=2)
header("J14", "EXP", (146, 204), ["EXP_GP24", "EXP_GP28", "EXP_GP29", "GND"])
header("J15", "TEMP", (160, 202), ["TEMP", "GND"])
R(s, "R46", "10k", (170, 204), "+3V3", "TEMP")
C(s, "C80", "100n", (176, 204), "TEMP", "GND")
led(s, "D4", (66, 216), "LED_F1", "R47", r_value="1k", net="LED_F1_A")
led(s, "D5", (84, 216), "LED_F2", "R48", r_value="1k", net="LED_F2_A")
R(s, "R49", "10k", (104, 218), "+3V3", "BTN_F")
button(s, "SW3", "USER", (116, 218), "BTN_F")

for i, net in enumerate(["VBUS", "GND", "+5V", "V12", "V12_F", "+3V3", "+1V0", "XO_VDD", "ADC_DRVDD"]):
    s.flag(net, (12 + 9 * i, 72))
holes(s, (150, 222))

if __name__ == "__main__":
    main(s, __file__)
