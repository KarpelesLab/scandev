"""Common parts with their footprints and JLCPCB (LCSC) numbers."""
FP_R = {"0603": "Resistor_SMD:R_0603_1608Metric", "1206": "Resistor_SMD:R_1206_3216Metric",
        "2512": "Resistor_SMD:R_2512_6332Metric"}
FP_C = {"0402": "Capacitor_SMD:C_0402_1005Metric", "0603": "Capacitor_SMD:C_0603_1608Metric", "0805": "Capacitor_SMD:C_0805_2012Metric",
        "1206": "Capacitor_SMD:C_1206_3216Metric"}

# (value, package) -> LCSC.  Every number here was looked up in the JLCPCB
# catalogue and matches the value and package it is listed under
# (hw/lib/checkbom.py repeats the check).
R_LCSC = {
    ("4.7", "0603"): "C844794", ("10", "0603"): "C22859", ("27", "0603"): "C25190",
    ("33", "0603"): "C23140", ("49.9", "0603"): "C23185", ("100", "0603"): "C22775",
    ("200", "0603"): "C8218", ("1k", "0603"): "C21190", ("2.2k", "0603"): "C844925",
    ("4.7k", "0603"): "C116693", ("5.1k", "0603"): "C2907044", ("10k", "0603"): "C25804",
    ("22k", "0603"): "C114065", ("100k", "0603"): "C115320", ("150k", "0603"): "C402995",
    ("10", "1206"): "C2828881", ("470", "1206"): "C4502", ("220 1W", "2512"): "C38808",
}
C_LCSC = {
    ("100n", "0402"): "C1525",
    ("15p", "0603"): "C107037", ("22p", "0603"): "C525244", ("100p", "0603"): "C14858",
    ("390p C0G", "0603"): "C1667", ("1n", "0603"): "C106247", ("10n", "0603"): "C57112",
    ("100n", "0603"): "C14663", ("100n 50V", "0603"): "C88219", ("1u", "0603"): "C15849",
    ("1u 25V", "0603"): "C92848",
    ("470p C0G", "0805"): "C575439", ("1n C0G", "0805"): "C62774", ("2.2n C0G", "0805"): "C513663",
    ("3.9n C0G", "0805"): "C97901", ("4.7u", "0805"): "C1779", ("10u", "0805"): "C15850",
    ("10u 25V", "0805"): "C84416", ("22u", "0805"): "C98190",
    ("10u 25V", "1206"): "C9807",
}


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


def caps(sch, prefix, start, rail, values, at, pkg="0603", pitch=6, gnd="GND"):
    """A row of decoupling capacitors on one rail; returns the next number."""
    n = start
    for i, v in enumerate(values):
        C(sch, f"{prefix}{n}", v, (at[0] + pitch * i, at[1]), rail, gnd,
          pkg=pkg if not v.startswith(("22u", "10u", "4.7u")) else "0805")
        n += 1
    return n


def button(sch, ref, value, at, a, b="GND"):
    sch.add("Switch:SW_Push", ref, value, at, {"1": a, "2": b},
            fp="Button_Switch_SMD:SW_SPST_TL3342", mpn="TL3342 / 1TS005 class 5x5 tact")
