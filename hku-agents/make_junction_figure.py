"""Paper figure: how people split at a junction, as a connected diagram with a share on each path.

For each path into a junction, the share of people leaving by each of the junction's paths (and the share who
stop there), counted from the Agent World run. This is the table a sensor at the junction would record
(time, junction, path in, path out), drawn for two busy junctions near HKU station: a 3-path and a 4-path one.

  graphs/junction-shares.pdf

Run:  python hku-agents/make_junction_figure.py --run day1      (needs matplotlib)
"""
import argparse
import json
import math
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

import config as C
from decisions import Decisions
from make_figures import save
from world import World, _english, xy

BLUE, INK, MUTED, STREET = "#2a78d6", "#1f2423", "#6b7370", "#d5d9d7"
REACH_M = 30
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "pdf.fonttype": 42, "text.color": INK})


def compass(angle):
    return ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"][round(math.degrees(angle) / 45) % 8]


def arm_line(w, D, c, k, reach=REACH_M):
    """The first `reach` metres of path k out of junction c, as points from the junction outward."""
    br = D.arms[c][k]["main"]
    node = br["node"]
    pts, total = [w.xy[node]], 0.0
    for e in br["edges"]:
        E = w.edges[e]
        g = [xy(*p) for p in (E["geom"] if E["u"] == node else E["geom"][::-1])]
        for p in g[1:]:
            d = math.dist(pts[-1], p)
            if total + d >= reach:
                f = (reach - total) / d
                pts.append((pts[-1][0] + f * (p[0] - pts[-1][0]), pts[-1][1] + f * (p[1] - pts[-1][1])))
                return pts
            total += d
            pts.append(p)
        node = E["v"] if E["u"] == node else E["u"]
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="day1")
    args = ap.parse_args()
    w = World()
    D = Decisions(w)
    cnt, stops = defaultdict(Counter), Counter()
    with open(C.OUT / args.run / "trips.jsonl", encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            if t["segments"]:
                for c, ai, ao, _ in D.trip_decisions(t):
                    cnt[(c, ai)][ao] += 1
                end = D.trip_end(t)
                if end:
                    stops[end] += 1
    passes = Counter()
    for (c, ai), cc in cnt.items():
        passes[c] += sum(cc.values())
    hku = xy(22.28320, 114.13690)
    near = [c for c in passes if math.dist(D.centre[c], hku) < 250]
    picks = [max((c for c in near if len(D.arms[c]) == n), key=lambda c: passes[c]) for n in (3, 4)]

    lines = [[xy(*p) for p in E["geom"]] for E in w.edges]
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 4.4))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.86, bottom=0.01, hspace=0.42, wspace=0.04)
    for row, c in enumerate(picks):
        cx, cy = D.centre[c]
        names = sorted({_english(A["name"]) for A in D.arms[c]} - {""})
        fig.text(0.01, 0.955 if row == 0 else 0.475, f"({'ab'[row]}) Junction with {len(D.arms[c])} paths"
                 + (f" on {', '.join(names)}" if names else "") + f": {passes[c]:,} people passed",
                 fontsize=7.5, fontweight="bold", ha="left")
        for ai in range(4):
            ax = axes[row][ai]
            ax.set_xlim(cx - 45, cx + 45); ax.set_ylim(cy - 45, cy + 45); ax.set_aspect("equal")
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
            if ai >= len(D.arms[c]):
                ax.axis("off")
                continue
            ax.add_collection(LineCollection(lines, colors=STREET, linewidths=0.8, zorder=1))
            got = cnt.get((c, ai), Counter())
            tot = sum(got.values()) + stops[(c, ai)]
            for k, A in enumerate(D.arms[c]):
                h = A["heading"]
                ex, ey = cx + 26 * math.cos(h), cy + 26 * math.sin(h)
                lx, ly = cx + 37 * math.cos(h), cy + 37 * math.sin(h)
                share = got[k] / tot if tot else 0.0
                if k == ai:   # the path people arrive by: an arrow toward the junction
                    ax.annotate("", xy=(cx + 3 * math.cos(h), cy + 3 * math.sin(h)), xytext=(ex, ey),
                                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3, mutation_scale=9), zorder=4)
                    label = "in" + (f"\n{100 * share:.0f}% back" if share >= 0.005 else "")
                else:
                    ax.plot([cx, ex], [cy, ey], color=BLUE, lw=0.6 + 7 * share, solid_capstyle="round", alpha=0.9, zorder=3)
                    label = f"{100 * share:.0f}%"
                ax.text(lx, ly, label, fontsize=7, ha="center", va="center", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))
            ax.plot(cx, cy, "o", ms=3.5, mfc="white", mec=INK, mew=0.8, zorder=6)
            stop = stops[(c, ai)] / tot if tot else 0.0
            ax.set_title(f"From the {compass(D.arms[c][ai]['heading'])} path ({tot:,} people)"
                         + (f", {100 * stop:.0f}% stop here" if stop >= 0.005 else ""), fontsize=6.3, color=MUTED, pad=2)
    save(fig, "junction-shares")
    for c in picks:
        print(f"junction {c}: {len(D.arms[c])} paths, {passes[c]} passes")


if __name__ == "__main__":
    main()
