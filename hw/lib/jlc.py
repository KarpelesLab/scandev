#!/usr/bin/env python3
"""Look parts up in the JLCPCB assembly catalogue (via jlcsearch.tscircuit.com).

    python3 hw/lib/jlc.py LTC6228 "TPS7A4901"
"""
import json
import sys
import urllib.parse
import urllib.request


def search(term, limit=6):
    url = "https://jlcsearch.tscircuit.com/components/list.json?search=" + urllib.parse.quote(term)
    req = urllib.request.Request(url, headers={"User-Agent": "jlc-lookup"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("components", [])[:limit]


if __name__ == "__main__":
    for term in sys.argv[1:]:
        print("==", term)
        try:
            for c in search(term):
                price = str(c.get("price", "")).split(",")[0]
                print(f"  C{c['lcsc']:<9} {c['mfr']:<26} {c['package']:<20} stock {c['stock']:<8}"
                      f" {price} {'basic' if c.get('basic') else ''}")
        except Exception as e:  # network trouble is not worth a traceback
            print("  lookup failed:", e)
