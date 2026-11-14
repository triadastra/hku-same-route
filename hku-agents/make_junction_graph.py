"""A small worked example of the encoded-junction model: a piece of the real map drawn as a directed graph.

  graphs/junction-probabilities.pdf   every road drawn twice, once per direction; the number on arrow A -> B
                                      is the share of walkers leaving A who took the road to B

The layout is schematic (roads are evened out in length so the numbers fit); the connections and the
percentages are the real ones from the run.

Run:  python hku-agents/make_junction_graph.py [--run day1] [--centre 1662] [--hops 2]
"""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import seaborn as sns
from matplotlib.patches import FancyArrowPatch

import config as C
from world import World

OUT = Path(__file__).resolve().parent.parent / "graphs"
RAD = 0.16   # bend of each arrow, so A -> B and B -> A do not overlap


def flows(run_dir):
    path = run_dir / "trips.jsonl"
    f = open(path, encoding="utf-8") if path.exists() else gzip.open(str(path) + ".gz", "rt", encoding="utf-8")
    pair, leave = Counter(), Counter()
    for line in f:
        for s in json.loads(line)["segments"]:
            pair[(s["from"], s["to"])] += 1
            leave[s["from"]] += 1
    return pair, leave


def arc_point(a, b, t, rad):
    """Point at fraction t along the quadratic curve matplotlib draws for arc3 with this bend."""
    a, b = np.array(a), np.array(b)
    d = b - a
    ctrl = (a + b) / 2 + rad * np.array([d[1], -d[0]])
    return (1 - t) ** 2 * a + 2 * (1 - t) * t * ctrl + t ** 2 * b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="day1")
    ap.add_argument("--centre", type=int, default=1662, help="node the example is built around")
    ap.add_argument("--hops", type=int, default=2)
    args = ap.parse_args()

    world = World()
    pair, leave = flows(C.OUT / args.run)
    inside = {args.centre}
    for _ in range(args.hops):
        inside |= {n for i in list(inside) for n, _ in world.adj[i]}
    G = nx.Graph()
    for i in inside:
        for n, _ in world.adj[i]:
            if n in inside and n != i:
                G.add_edge(i, n)
    start = {i: world.xy[i] for i in G}
    pos = nx.kamada_kawai_layout(G, pos=start)
    order = sorted(G, key=lambda i: (-pos[i][1], pos[i][0]))
    name = {i: chr(65 + k) for k, i in enumerate(order)}
    degree = {i: len(world.adj[i]) for i in G}
    cut = {i: degree[i] - G.degree(i) for i in G}   # roads of this node that leave the figure

    sns.set_theme(style="white", font="DejaVu Sans", font_scale=0.75, rc={"pdf.fonttype": 42})
    cmap = sns.color_palette("flare", as_cmap=True)
    fig, ax = plt.subplots(figsize=(7.0, 5.6))
    for u, v in G.edges:
        for a, b in ((u, v), (v, u)):
            p = pair[(a, b)] / leave[a] if leave[a] else 0.0
            ax.add_patch(FancyArrowPatch(pos[a], pos[b], connectionstyle=f"arc3,rad={RAD}", arrowstyle="-|>",
                                         mutation_scale=9, lw=0.6 + 2.6 * p, color=cmap(p), shrinkA=15, shrinkB=15,
                                         zorder=2))
            x, y = arc_point(pos[a], pos[b], 0.38, RAD)
            ax.text(x, y, f"{100 * p:.0f}%", ha="center", va="center", fontsize=6.5, color="#222", zorder=4,
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec=cmap(p), lw=0.6))
    for i in G:
        whole = cut[i] == 0
        ink = "white" if whole else "#1f2a44"
        ax.plot(*pos[i], "o", ms=25, mfc="#1f2a44" if whole else "white", mec="#1f2a44", mew=1.2, zorder=5)
        ax.annotate(name[i], pos[i], xytext=(0, 3), textcoords="offset points", ha="center", va="center", fontsize=8.5,
                    fontweight="bold", color=ink, zorder=6)
        ax.annotate(f"{degree[i]}-way", pos[i], xytext=(0, -6), textcoords="offset points", ha="center", va="center",
                    fontsize=5, color=ink, zorder=6)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 100))
    cb = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.01, shrink=0.6)
    cb.set_label("Share of walkers leaving the first node (%)", fontsize=7)
    cb.outline.set_visible(False)
    ax.plot([], [], "o", ms=8, mfc="#1f2a44", mec="#1f2a44", label="All roads of the node shown (shares sum to 100%)")
    ax.plot([], [], "o", ms=8, mfc="white", mec="#1f2a44", mew=1.2, label="Some roads leave the figure (shares sum to less)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 0.0), frameon=False, fontsize=7, ncol=2, handletextpad=0.3)
    ax.margins(0.08)
    ax.set_aspect("equal")
    ax.axis("off")
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "junction-probabilities.pdf", bbox_inches="tight", pad_inches=0.03)
    fig.savefig(OUT / "junction-probabilities.png", dpi=220, bbox_inches="tight", pad_inches=0.03)

    print(f"wrote graphs/junction-probabilities (.pdf and .png): {G.number_of_nodes()} nodes, {G.number_of_edges()} roads")
    for i in order:
        outs = ", ".join(f"{name[i]}->{name[n]} {100 * pair[(i, n)] / leave[i]:.1f}%" for n in sorted(G[i], key=name.get))
        print(f"  {name[i]} (node {i}, {degree[i]}-way, {leave[i]} leaving, {cut[i]} roads off-figure): {outs}")


if __name__ == "__main__":
    main()
