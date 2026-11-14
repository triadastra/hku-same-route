"""A demo of the encoded-junction model on the real map.

  graphs/junction-probabilities.pdf   a window of the map with every node and, for every road out of a node, an
                                      arrow labelled with the share of walkers leaving that node who took it

Roads are drawn in their real shape and nodes at their real positions. Each node is coloured by the number of
roads that meet there (1 = dead end ... 5 = five-way junction); the default window is centred on a five-way
junction so that every kind of node appears. The arrows out of one node sum to 100%.

Run:  python hku-agents/make_junction_graph.py [--run day1] [--centre 2931] [--shift -56 0] [--half-width 70] [--half-height 50]
"""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

import config as C
from world import World, xy

OUT = Path(__file__).resolve().parent.parent / "graphs"
INK = "#1f2a44"
KIND = {1: "Dead end", 2: "Place on a road", 3: "Three-way", 4: "Four-way", 5: "Five-way"}
START, LENGTH, SIDE = 4.0, 12.0, 2.4   # metres: where an arrow starts, how long it is, how far right of the road


def flows(run_dir):
    path = run_dir / "trips.jsonl"
    f = open(path, encoding="utf-8") if path.exists() else gzip.open(str(path) + ".gz", "rt", encoding="utf-8")
    use, leave = Counter(), Counter()
    for line in f:
        for s in json.loads(line)["segments"]:
            use[(s["edge"], s["from"])] += 1
            leave[s["from"]] += 1
    return use, leave


def along(line, d):
    """Point d metres along a polyline, and the unit direction there."""
    seg = np.diff(line, axis=0)
    lens = np.hypot(seg[:, 0], seg[:, 1])
    for s, l in zip(range(len(seg)), lens):
        if d <= l or s == len(seg) - 1:
            u = seg[s] / max(l, 1e-9)
            return line[s] + u * min(d, l), u
        d -= l


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="day1")
    ap.add_argument("--centre", type=int, default=2931, help="node the window is placed around")
    ap.add_argument("--shift", type=float, nargs=2, default=(-56, 0), help="metres east and north to move the window")
    ap.add_argument("--half-width", type=float, default=70)
    ap.add_argument("--half-height", type=float, default=50)
    args = ap.parse_args()

    world = World()
    use, leave = flows(C.OUT / args.run)
    cx, cy = world.xy[args.centre][0] + args.shift[0], world.xy[args.centre][1] + args.shift[1]
    x0, x1, y0, y1 = cx - args.half_width, cx + args.half_width, cy - args.half_height, cy + args.half_height
    inside = [i for i, (x, y) in enumerate(world.xy) if x0 + 4 < x < x1 - 4 and y0 + 4 < y < y1 - 4]
    shape = {i: np.array([xy(la, lo) for la, lo in e["geom"]]) for i, e in enumerate(world.edges)}
    near = [s for s in shape.values() if (s[:, 0] > x0 - 50).any() and (s[:, 0] < x1 + 50).any()
            and (s[:, 1] > y0 - 50).any() and (s[:, 1] < y1 + 50).any()]

    sns.set_theme(style="white", font="DejaVu Sans", font_scale=0.75, rc={"pdf.fonttype": 42})
    colour = dict(zip(KIND, sns.color_palette("colorblind", 5)))
    fig, ax = plt.subplots(figsize=(7.2, 7.2 * args.half_height / args.half_width + 0.5))
    ax.add_collection(LineCollection(near, colors="#d9dcd6", linewidths=5.5, capstyle="round", zorder=1))
    ax.add_collection(LineCollection(near, colors="#f7f7f4", linewidths=3.6, capstyle="round", zorder=1.1))

    drawn = 0
    for a in inside:
        for b, e in world.adj[a]:
            line = shape[e] if world.edges[e]["u"] == a else shape[e][::-1]
            road = world.edges[e]["len"]
            p = use[(e, a)] / leave[a] if leave[a] else 0.0
            d0 = min(START, 0.2 * road)
            d1 = max(min(d0 + LENGTH, 0.47 * road), min(d0 + 7.0, 0.8 * road))
            (pa, ua), (pb, ub) = along(line, d0), along(line, d1)
            right = lambda u: np.array([u[1], -u[0]])
            pa, pb = pa + SIDE * right(ua), pb + SIDE * right(ub)
            ax.annotate("", pb, pa, zorder=3, annotation_clip=True, arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.5 + 2.2 * p,
                                                               alpha=0.35 + 0.65 * p, mutation_scale=5 + 4 * p,
                                                               shrinkA=0, shrinkB=0))
            pl = pa + 0.28 * (pb - pa)
            if x0 + 3 < pl[0] < x1 - 3 and y0 + 2 < pl[1] < y1 - 2:
                ax.text(*pl, f"{100 * p:.0f}", ha="center", va="center", fontsize=5.0, color=INK, zorder=4,
                        fontweight="bold" if p >= 0.5 else "normal",
                        bbox=dict(boxstyle="round,pad=0.1", fc="white", ec=INK, lw=0.3, alpha=0.95))
            drawn += 1
    for a in inside:
        k = len(world.adj[a])
        ax.plot(*world.xy[a], "o", ms=7.5, mfc=colour[k], mec="white", mew=0.7, zorder=5)
        ax.text(*world.xy[a], str(k), ha="center", va="center_baseline", fontsize=5, fontweight="bold", color="white", zorder=6)

    bx, by = x0 + 6, y0 + 6
    ax.plot([bx, bx + 25], [by, by], color="black", lw=1.5, solid_capstyle="butt", zorder=6)
    ax.text(bx + 12.5, by + 2, "25 m", ha="center", va="bottom", fontsize=6.5, zorder=6)
    ax.annotate("N", (x1 - 6, y0 + 20), xytext=(x1 - 6, y0 + 6), ha="center", va="center", fontsize=7, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1), zorder=6)
    counts = Counter(len(world.adj[a]) for a in inside)
    handles = [Line2D([], [], marker="o", ls="", ms=7, mfc=colour[k], mec="white", label=f"{KIND[k]} ({counts[k]})")
               for k in KIND if counts[k]]
    handles.append(Line2D([], [], marker=r"$\rightarrow$", ls="", ms=11, color=INK,
                          label="% of walkers leaving the\nnode who take this road"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=7.5,
              ncol=1, handletextpad=0.4, labelspacing=1.1, title="Roads meeting at the node", title_fontsize=7.5,
              alignment="left")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(0.6)
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "junction-probabilities.pdf", bbox_inches="tight", pad_inches=0.03)
    fig.savefig(OUT / "junction-probabilities.png", dpi=260, bbox_inches="tight", pad_inches=0.03)
    print(f"wrote graphs/junction-probabilities (.pdf and .png): {len(inside)} nodes "
          f"{dict(sorted(counts.items()))}, {drawn} arrows, "
          f"{sum(leave[a] for a in inside)} departures, nodes nobody left: {sum(1 for a in inside if not leave[a])}")


if __name__ == "__main__":
    main()
