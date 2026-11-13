#!/usr/bin/env python3
"""Fabrication files for JLCPCB from a routed board.

    python3 hw/lib/fab.py fe pa dig

Writes build/fab/<board>/<board>-gerbers.zip, <board>-cpl.csv and
<board>-bom.csv.  The placement file's rotations are KiCad's; JLCPCB's
convention differs for some packages, so check every polarised part in their
placement preview before paying.
"""
import csv
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"{' '.join(cmd[:4])} failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")


def fab(name):
    pcb = os.path.join(ROOT, "hw", name, name + ".kicad_pcb")
    out = os.path.join(ROOT, "build", "fab", name)
    ger = os.path.join(out, "gerbers")
    os.makedirs(ger, exist_ok=True)
    for f in os.listdir(ger):
        os.remove(os.path.join(ger, f))
    layers = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    run("kicad-cli", "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
        "--no-x2", "--use-drill-file-origin", "-o", ger + "/", pcb)
    run("kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
        "--drill-origin", "plot", "--excellon-units", "mm", "-o", ger + "/", pcb)
    z = os.path.join(out, name + "-gerbers.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(ger)):
            zf.write(os.path.join(ger, f), f)

    pos = os.path.join(out, name + "-pos.csv")
    run("kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
        "--use-drill-file-origin", "-o", pos, pcb)
    # which parts JLCPCB is asked to fit: those with a catalogue number
    numbered = {}
    with open(os.path.join(ROOT, "hw", name, name + "-bom.csv")) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["LCSC"]:
            for ref in r["Designator"].split(","):
                numbered[ref] = r
    placed = 0
    with open(pos) as f, open(os.path.join(out, name + "-cpl.csv"), "w", newline="") as g:
        w = csv.writer(g)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in csv.DictReader(f):
            if r["Ref"] in numbered:
                w.writerow([r["Ref"], r["PosX"] + "mm", r["PosY"] + "mm",
                            "Top" if r["Side"] == "top" else "Bottom", r["Rot"]])
                placed += 1
    with open(os.path.join(out, name + "-bom.csv"), "w", newline="") as g:
        w = csv.writer(g)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for r in rows:
            if r["LCSC"]:
                w.writerow([r["Comment"], r["Designator"], r["Footprint"], r["LCSC"]])
    hand = sorted(ref for r in rows if not r["LCSC"] for ref in r["Designator"].split(",")
                  if not ref.startswith("H"))
    print(f"{name}: {len(os.listdir(ger))} gerber/drill files, {placed} parts for assembly, "
          f"{len(hand)} to fit by hand ({' '.join(hand)})")
    print("  ", os.path.relpath(z, ROOT))


if __name__ == "__main__":
    for n in sys.argv[1:]:
        fab(n)
