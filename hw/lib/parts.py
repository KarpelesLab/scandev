"""Common parts with their footprints and JLCPCB (LCSC) numbers.

LCSC numbers marked `?` in LCSC_UNVERIFIED were written from memory and have
not been checked against the catalogue; check them before ordering.
"""
FP_R = {"0603": "Resistor_SMD:R_0603_1608Metric", "1206": "Resistor_SMD:R_1206_3216Metric",
        "2512": "Resistor_SMD:R_2512_6332Metric"}
FP_C = {"0603": "Capacitor_SMD:C_0603_1608Metric", "0805": "Capacitor_SMD:C_0805_2012Metric",
        "1206": "Capacitor_SMD:C_1206_3216Metric"}

# (value, package) -> LCSC
R_LCSC = {
    ("49.9", "0603"): "C23185", ("200", "0603"): "C8218", ("10", "0603"): "C22859",
    ("100", "0603"): "C22775", ("1k", "0603"): "C21190", ("10k", "0603"): "C25804",
    ("2.2k", "0603"): "C4190",
}
C_LCSC = {
    ("100n", "0603"): "C14663", ("1u", "0603"): "C15849", ("10u", "0805"): "C15850",
    ("10n", "0603"): "C57112", ("100p", "0603"): "C14858",
}
LCSC_VERIFIED = {"C23185", "C8218"}


def R(sch, ref, value, at, a, b, pkg="0603", rot=0, **kw):
    sch.add("Device:R", ref, value, at, {"1": a, "2": b}, rot=rot, fp=FP_R[pkg],
            lcsc=kw.pop("lcsc", R_LCSC.get((value, pkg), "")), **kw)


def C(sch, ref, value, at, a, b, pkg="0603", rot=0, **kw):
    sch.add("Device:C", ref, value, at, {"1": a, "2": b}, rot=rot, fp=FP_C[pkg],
            lcsc=kw.pop("lcsc", C_LCSC.get((value, pkg), "")), **kw)


def L(sch, ref, value, at, a, b, fp="Inductor_SMD:L_1210_3225Metric", rot=90, **kw):
    sch.add("Device:L", ref, value, at, {"1": a, "2": b}, rot=rot, fp=fp, **kw)


def FB(sch, ref, at, a, b, rot=90):
    sch.add("Device:FerriteBead", ref, "600R", at, {"1": a, "2": b}, rot=rot,
            fp="Inductor_SMD:L_0603_1608Metric", lcsc="C1002", mpn="GZ1608D601TF")


def crossed(sch, ref, at, x, y, rot=0):
    """One BAV99 as an anti-parallel pair between nets x and y.

    The package is two diodes in series, 1 -> 3 -> 2; tying 1 and 2 together
    leaves one diode each way between that node and pin 3.
    """
    off = {0: (-1.27, -3.81), 90: (-6.35, 0), 180: (-1.27, 3.81), 270: (3.81, 0)}[rot]
    sch.add("Diode:BAV99", ref, "BAV99", at, {"1": x, "2": x, "3": y}, rot=rot,
            fp="Package_TO_SOT_SMD:SOT-23", lcsc="C82480", mpn="BAV99LT1G",
            ref_off=off, hide_value=True)


def sma(sch, ref, value, at, net, rot=0):
    sch.add("Connector:Conn_Coaxial", ref, value, at, {"1": net, "2": "GND"}, rot=rot,
            ref_off=(3.81, -2.54), val_off=(3.81, 0),
            fp="Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount")


def led(sch, ref, at, rail, r_ref, r_value="2.2k", colour="green", net=None):
    """Indicator: resistor from `rail`, LED to ground."""
    net = net or f"{ref}_A"
    R(sch, r_ref, r_value, at, rail, net)
    sch.add("Device:LED", ref, colour, (at[0] + 8, at[1]), {"2": net, "1": "GND"}, rot=90,
            fp="LED_SMD:LED_0603_1608Metric", lcsc="C72043",
            ref_off=(3.81, -1.27), val_off=(3.81, 1.27))


def holes(sch, at, n=4):
    for i in range(n):
        sch.add("Mechanical:MountingHole", f"H{i+1}", "M3", (at[0] + 8 * i, at[1]), {},
                fp="MountingHole:MountingHole_3.2mm_M3", hide_value=True)
