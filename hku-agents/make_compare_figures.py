"""Paper figures for the comparison of the arms, from the tables arms.py writes. Vector PDF and PNG in graphs/.

  graphs/shared-turns-three-arms.pdf  P_k against k, one line per arm
  graphs/markov-turns.pdf             after two people meet: observed against the Markov chain
  graphs/road-use-ratio.pdf           where agents walk more, and less, than random walkers

Run:  python hku-agents/make_compare_figures.py --run day1      (needs matplotlib, numpy)
"""
import argparse
import csv
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.collections import LineCollection

import config as C
from make_figures import save
from world import World, xy

BLUE, ORANGE, GREEN, YELLOW, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#1f2423", "#6b7370"
ARMS = [("agents", "Agent World", BLUE, "o"), ("random", "Random walk", ORANGE, "s"),
        ("noisy", "Same trips, noisy turns", YELLOW, "D")]
LIVE_ARMS = [("live", "Live world", GREEN, "^"), ("agents", "Agent World", BLUE, "o"), ("random", "Random walk", ORANGE, "s")]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.labelcolor": INK})


def table(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def lines(ax, k, series):
    """series: (label, colour, marker, values). Each line gets a marker shape and a label at its end."""
    ax.grid(axis="y", color="#e3e6e4", lw=0.5)
    ends = []
    for label, colour, marker, y in series:
        ax.plot(k, y, color=colour, lw=1.6, marker=marker, ms=4, mec="white", mew=0.6, label=label, zorder=3)
        ends.append([y[-1], label])
    ends.sort()
    for i in range(1, len(ends)):   # keep end labels from overlapping
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 4.5)
    for y, label in ends:
        ax.text(k[-1] + 0.25, y, label, va="center", fontsize=7)
    ax.set_xticks(k)
    ax.set_xlim(k[0] - 0.3, k[-1] + 0.3)
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=7, loc="lower left")


def shared_turns(an):
    """With a live run: the three arms on the same people (live_shared_turns.csv). Without: the 10,000-person
    arms (arms_shared_turns.csv), with the spread of the random-walk repeats."""
    live = an / "live_shared_turns.csv"
    rows = table(live if live.exists() else an / "arms_shared_turns.csv")
    k = [int(r["k_turns_in_a_row"]) for r in rows]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    arms = LIVE_ARMS if live.exists() else ARMS
    series = [(label, colour, marker, [100 * float(r[f"p_{arm}"]) for r in rows])
              for arm, label, colour, marker in arms if f"p_{arm}" in rows[0]]
    if "p_random_sd" in rows[0]:
        m = np.array([100 * float(r["p_random"]) for r in rows])
        sd = np.array([100 * float(r["p_random_sd"]) for r in rows])
        ax.fill_between(k, m - sd, m + sd, color=ORANGE, alpha=0.2, lw=0)
    lines(ax, k, series)
    ax.set_xlabel("Same turns in a row, $k$")
    ax.set_ylabel("Trips where a stranger shares $k$ turns (%)")
    save(fig, "shared-turns-three-arms")


def markov(an):
    rows = table(an / "arms_markov.csv")
    k = [int(r["k_more_turns"]) for r in rows]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    get = lambda c: [100 * float(r[c]) for r in rows]
    for label, colour, marker, y, ls in (("Agents, observed", BLUE, "o", get("agents_observed"), "-"),
                                         ("Agents, Markov chain", BLUE, "o", get("agents_markov"), "--"),
                                         ("Random walk, observed", ORANGE, "s", get("random_observed"), "-"),
                                         ("Random walk, Markov chain", ORANGE, "s", get("random_markov"), "--")):
        ax.plot(k, y, color=colour, lw=1.6, ls=ls, marker=marker, ms=4, mec="white", mew=0.6,
                mfc=colour if ls == "-" else "white", label=label, zorder=3)
        if ls == "--":
            ax.lines[-1].set_markeredgecolor(colour)
    ax.grid(axis="y", color="#e3e6e4", lw=0.5)
    ax.set_xticks(k); ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    ax.set_xlabel("Further turns made the same way, $k$")
    ax.set_ylabel("Pairs that met on a road (%)")
    save(fig, "markov-turns")


def road_ratio(an):
    world = World()
    rows = {int(r["segment"]): r for r in table(an / "road_usage_compare.csv")}
    segs, vals, widths = [], [], []
    for e, E in enumerate(world.edges):
        r = rows.get(e)
        if not r or int(r["walkers_agents"]) + int(r["walkers_random"]) < 20:
            continue
        segs.append([xy(*p) for p in E["geom"]])
        vals.append(math.log2(float(r["ratio"])))
        widths.append(0.4 + 1.6 * min(1.0, (int(r["walkers_agents"]) + int(r["walkers_random"])) / 4000))
    order = np.argsort(np.abs(vals))   # strongest differences drawn on top
    cmap = LinearSegmentedColormap.from_list("div", [ORANGE, "#c9cecb", BLUE])
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.add_collection(LineCollection([[xy(*p) for p in E["geom"]] for E in world.edges], colors="#e3e6e4", linewidths=0.3))
    lc = LineCollection([segs[i] for i in order], cmap=cmap, norm=TwoSlopeNorm(0, -4, 4), linewidths=[widths[i] for i in order])
    lc.set_array(np.array(vals)[order])
    ax.add_collection(lc)
    for name in ("Kennedy Town", "HKU", "Sai Ying Pun"):
        m = [p["xy"] for p in world.places.values() if p["category"] == "mtr" and name in p["name"]]
        x, y = np.mean([p[0] for p in m]), np.mean([p[1] for p in m])
        ax.annotate(name if name != "HKU" else "HKU station", (x, y), xytext=(0, 9), textcoords="offset points", ha="center",
                    fontsize=7, fontweight="bold", zorder=6, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.3", lw=0.4))
        ax.plot(x, y, "o", ms=3, mfc="white", mec="black", mew=0.8, zorder=6)
    ax.autoscale(); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(lc, ax=ax, fraction=0.03, pad=0.015, ticks=[-4, -2, 0, 2, 4])
    cb.ax.set_yticklabels(["16× less", "4× less", "same", "4× more", "16× more"])
    cb.set_label("Agents' share of walking against random walk")
    cb.outline.set_linewidth(0.5)
    save(fig, "road-use-ratio")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="day1")
    an = C.OUT / ap.parse_args().run / "analysis"
    shared_turns(an); markov(an); road_ratio(an)
    print("wrote graphs/shared-turns-three-arms, markov-turns, road-use-ratio (.pdf and .png)")
