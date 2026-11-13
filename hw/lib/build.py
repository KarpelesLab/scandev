"""Write a board's schematic, check it, and export the PDF and BOM."""
import csv
import os
import sys

IGNORED_ERC = {"lib_symbol_issues", "footprint_link_issues", "lib_symbol_mismatch"}


def build(sch, here):
    root = os.path.dirname(os.path.dirname(os.path.abspath(here)))
    work = os.path.join(os.path.dirname(root), "build", "hw", sch.name)
    path = sch.write(os.path.dirname(os.path.abspath(here)))
    bad = sch.verify(work)
    erc = [e for e in sch.erc(work) if e[1] not in IGNORED_ERC]
    pdf = sch.pdf(os.path.dirname(os.path.abspath(here)))
    bom = os.path.join(os.path.dirname(os.path.abspath(here)), sch.name + "-bom.csv")
    with open(bom, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC", "MPN"])
        for (value, fp, lcsc, mpn), refs in sch.bom().items():
            w.writerow([value, ",".join(refs), fp.split(":")[-1], lcsc, mpn])
    print(f"{sch.name}: {len(sch.parts)} parts, {len(set(v for v in sch.want.values() if v))} nets")
    print("  netlist:", "matches" if not bad else f"{len(bad)} MISMATCHES")
    for b in bad[:20]:
        print("    ", b)
    print("  rule check:", "clean" if not erc else f"{len(erc)} findings")
    for e in erc[:30]:
        print("    ", e[0], e[1], "-", e[2], "|", e[3][:90])
    print("  wrote", os.path.relpath(path), os.path.relpath(pdf), os.path.relpath(bom))
    return not bad and not [e for e in erc if e[0] == "error"]


def main(sch, here):
    sys.exit(0 if build(sch, here) else 1)
