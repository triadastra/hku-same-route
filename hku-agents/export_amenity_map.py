"""Build amenity-heat-map.html: the places on our map, binned into one-hectare blocks by what they are for.

Reads web.json (the footpaths and the 1,538 places) and writes one self-contained page next to it.
Run from the repository root or from hku-agents/:  python hku-agents/export_amenity_map.py
"""
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = 60.0  # hexagon radius in metres: 104 m across, 0.94 ha
PAD = 40

# Eight functions, in the fixed colour order used by the page
FUNCTIONS = [
    ("Food and drink", ["food"]),
    ("Shops", ["shop"]),
    ("University", ["hku", "hall", "library"]),
    ("Named buildings", ["building"]),
    ("Transport stops", ["bus", "mtr"]),
    ("Parks and sights", ["park", "sight"]),
    ("Schools", ["school"]),
    ("Everyday services", ["health", "money", "service", "toilet", "vending", "worship"]),
]
NOTES = [
    "Restaurants, cafes, bars and canteens",
    "Shops, supermarkets and markets",
    "HKU teaching buildings, halls and libraries",
    "Residential towers, offices and hotels that carry a name",
    "Bus stops and MTR exits",
    "Parks, playgrounds, sports grounds, viewpoints and historic sites",
    "Schools, kindergartens and tutoring centres",
    "Clinics, pharmacies, banks, toilets, water points and places of worship",
]
GROUP = {cat: i for i, (_, cats) in enumerate(FUNCTIONS) for cat in cats}


def hex_of(x, y):
    q = (math.sqrt(3) / 3 * x - y / 3) / R
    r = (2 / 3 * y) / R
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def hex_centre(q, r):
    return R * math.sqrt(3) * (q + r / 2), R * 1.5 * r


def main():
    web = json.loads((ROOT / "web.json").read_text())
    places, edges = web["places"], web["edges"]
    xs = [v for e in edges for v in e["p"][0::2]] + [p["x"] for p in places]
    ys = [v for e in edges for v in e["p"][1::2]] + [p["y"] for p in places]
    min_x, max_y = min(xs) - PAD - R, max(ys) + PAD + R
    width, height = max(xs) + PAD + R - min_x, max_y - (min(ys) - PAD - R)

    def sx(x):
        return round(x - min_x, 1)

    def sy(y):  # north is up
        return round(max_y - y, 1)

    streets = []
    for e in edges:
        p = e["p"]
        pts = [f"{sx(p[i]):g} {sy(p[i + 1]):g}" for i in range(0, len(p), 2)]
        streets.append("M" + "L".join(pts))

    named = [(sum(e["p"][0::2]) / (len(e["p"]) / 2), sum(e["p"][1::2]) / (len(e["p"]) / 2), e["n"])
             for e in edges if e.get("n")]

    cells = {}
    for p in places:
        key = hex_of(p["x"], p["y"])
        cells.setdefault(key, []).append(p)
    out = []
    for (q, r), ps in cells.items():
        cx, cy = hex_centre(q, r)
        near = sorted(named, key=lambda n: (n[0] - cx) ** 2 + (n[1] - cy) ** 2)[:6]
        street = Counter(n[2] for n in near).most_common(1)[0][0] if near else ""
        counts = [0] * len(FUNCTIONS)
        for p in ps:
            counts[GROUP[p["cat"]]] += 1
        ps.sort(key=lambda p: (GROUP[p["cat"]], p["name"]))
        out.append({"x": sx(cx), "y": sy(cy), "c": counts, "n": street,
                    "p": [[p["name"], GROUP[p["cat"]]] for p in ps]})
    out.sort(key=lambda c: (c["y"], c["x"]))

    def centre(word):
        m = [p for p in places if p["cat"] == "mtr" and word in p["name"]]
        return [sx(sum(p["x"] for p in m) / len(m)), sy(sum(p["y"] for p in m) / len(m))]

    data = {
        "w": round(width), "h": round(height), "R": R,
        "streets": "".join(streets), "cells": out,
        "fn": [name for name, _ in FUNCTIONS], "notes": NOTES,
        "labels": [["Kennedy Town", *centre("Kennedy Town")], ["HKU", *centre("HKU")],
                   ["Sai Ying Pun", *centre("Sai Ying Pun")]],
        "meta": {"places": len(places), "km": web["meta"]["graph"]["km"], "segments": len(edges)},
    }
    template = (Path(__file__).parent / "amenity_map_template.html").read_text()
    page = template.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    (ROOT / "amenity-heat-map.html").write_text(page)
    print(f"{len(out)} blocks, {len(places)} places, {len(page) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
