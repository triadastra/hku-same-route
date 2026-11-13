"""Two paper figures from the map in web.json, written as vector PDF (and PNG previews) to graphs/.

  graphs/amenity-density.pdf    how many places per hectare, as a smoothed multi-colour heat map
  graphs/amenity-functions.pdf  the most common function in each one-hectare block, one colour per function

Run:  python hku-agents/make_figures.py      (needs matplotlib, numpy, scipy)
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Patch
from scipy.ndimage import gaussian_filter

from export_amenity_map import FUNCTIONS, GROUP, R, hex_centre, hex_of

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "graphs"
BANDWIDTH = 60   # metres, standard deviation of the smoothing kernel
CELL = 5         # metres per raster cell
COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TIE = "#a7b0aa"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42, "axes.linewidth": 0.6})


def load():
    web = json.loads((ROOT / "web.json").read_text())
    lines = [np.array(e["p"]).reshape(-1, 2) for e in web["edges"]]
    return web["places"], lines


def frame(ax, places, lines, street_colour):
    xs, ys = [p["x"] for p in places], [p["y"] for p in places]
    x0, x1, y0, y1 = min(xs) - 120, max(xs) + 120, min(ys) - 120, max(ys) + 120
    ax.add_collection(LineCollection(lines, colors=street_colour, linewidths=0.3, zorder=3))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for name in ("Kennedy Town", "HKU", "Sai Ying Pun"):
        m = [p for p in places if p["cat"] == "mtr" and name in p["name"]]
        x, y = np.mean([p["x"] for p in m]), np.mean([p["y"] for p in m])
        label = name if name != "HKU" else "HKU station"
        ax.annotate(label, (x, y), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=7, fontweight="bold",
                    zorder=6, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.3", lw=0.4))
        ax.plot(x, y, "o", ms=3, mfc="white", mec="black", mew=0.8, zorder=6)
    # 500 m scale bar and north arrow
    bx, by = x0 + 60, y0 + 60
    ax.plot([bx, bx + 500], [by, by], color="black", lw=1.5, solid_capstyle="butt", zorder=6)
    ax.text(bx + 250, by + 22, "500 m", ha="center", va="bottom", fontsize=7, zorder=6,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    ax.annotate("N", (x1 - 70, y0 + 170), xytext=(x1 - 70, y0 + 50), ha="center", va="center", fontsize=8, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1), zorder=6)
    return x0, x1, y0, y1


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.03)
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", pad_inches=0.03, dpi=220)
    plt.close(fig)


def density(places, lines):
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    x0, x1, y0, y1 = frame(ax, places, lines, "#00000055")
    xe, ye = np.arange(x0, x1 + CELL, CELL), np.arange(y0, y1 + CELL, CELL)
    h, _, _ = np.histogram2d([p["y"] for p in places], [p["x"] for p in places], bins=[ye, xe])
    per_ha = gaussian_filter(h, BANDWIDTH / CELL, mode="constant") / CELL ** 2 * 10_000
    shown = np.ma.masked_less(per_ha, 1.0)  # under one place per hectare stays white
    im = ax.imshow(shown, extent=[xe[0], xe[-1], ye[0], ye[-1]], origin="lower", cmap="turbo", vmin=1, vmax=per_ha.max(),
                   interpolation="bilinear", zorder=2, rasterized=True)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.015)
    cb.set_label("Places per hectare")
    cb.outline.set_linewidth(0.5)
    save(fig, "amenity-density")
    return per_ha.max()


def functions(places, lines):
    cells = {}
    for p in places:
        cells.setdefault(hex_of(p["x"], p["y"]), [0] * len(FUNCTIONS))[GROUP[p["cat"]]] += 1
    angles = np.radians(30 + 60 * np.arange(6))
    polys, cols, tally = [], [], [0] * (len(FUNCTIONS) + 1)
    for (q, r), counts in cells.items():
        cx, cy = hex_centre(q, r)
        top = [i for i, v in enumerate(counts) if v == max(counts)]
        k = top[0] if len(top) == 1 else len(FUNCTIONS)
        tally[k] += 1
        polys.append(np.c_[cx + (R - 2) * np.cos(angles), cy + (R - 2) * np.sin(angles)])
        cols.append(COLOURS[k] if k < len(FUNCTIONS) else TIE)
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    frame(ax, places, lines, "#00000066")
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors="white", linewidths=0.4, zorder=2))
    handles = [Patch(fc=COLOURS[i], label=f"{name} ({tally[i]})") for i, (name, _) in enumerate(FUNCTIONS)]
    handles.append(Patch(fc=TIE, label=f"Tie ({tally[-1]})"))
    ax.legend(handles=handles, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.02), frameon=False, fontsize=7.5,
              handlelength=1.2, handleheight=1.0, columnspacing=1.6, title="Most common function in the block (number of blocks)",
              title_fontsize=7.5)
    save(fig, "amenity-functions")
    return len(cells), tally


if __name__ == "__main__":
    places, lines = load()
    print("peak density, places per hectare:", round(density(places, lines), 1))
    print("blocks, tally:", functions(places, lines))
