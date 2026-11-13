#!/usr/bin/env python3
"""Check every LCSC number in the boards' BOMs against the JLCPCB catalogue.

    python3 hw/lib/checkbom.py hw/*/*-bom.csv

Prints what each number really is, so a wrong number shows up as a part that
does not match its row, and lists the rows that have no number yet.  It does
not report stock.
"""
import csv
import sys

from jlc import search

seen = {}


def lookup(num):
    if num not in seen:
        try:
            hits = [c for c in search(num.lstrip("C"), 5) if str(c["lcsc"]) == num.lstrip("C")]
            seen[num] = hits[0] if hits else None
        except Exception as e:      # noqa: BLE001
            seen[num] = e
    return seen[num]


for path in sys.argv[1:]:
    print("==", path)
    for row in csv.DictReader(open(path)):
        n = len(row["Designator"].split(","))
        what = f"{row['Comment'][:16]:16} x{n:<3} {row['Footprint'][:24]:24}"
        if not row["LCSC"]:
            if not row["Footprint"].startswith(("MountingHole", "PinHeader")):
                print(f"  NO NUMBER   {what} {row['MPN']}")
            continue
        c = lookup(row["LCSC"])
        if c is None:
            print(f"  NOT FOUND   {what} {row['LCSC']}")
        elif isinstance(c, Exception):
            print(f"  LOOKUP ERR  {what} {row['LCSC']} {c}")
        else:
            # a lookup by number does not return stock; one by name does
            print(f"  found       {what} {row['LCSC']:<10} {c['mfr'][:26]:26} {c['package'][:14]}")
