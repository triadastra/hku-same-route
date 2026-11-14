"""Paper figures for following at real intersections, from the tables following.py writes. PDF and PNG in graphs/.

  graphs/following-models.pdf   chance that a stranger follows you through k intersections, Agent World and Markov chains
  graphs/following-pairs.pdf    two people arriving together: same next k decisions, Agent World and the chains' formula
  graphs/following-roads.pdf    same next road, by how many roads the intersection has
  graphs/following-hours.pdf    chance of being followed through 3 intersections, by hour of day

Run:  python hku-agents/make_following_figures.py --run day1      (needs matplotlib)
"""
import argparse
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from make_figures import save

BLUE, ORANGE, GREEN, YELLOW, PURPLE = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"
INK, MUTED, GRID = "#1f2423", "#6b7370", "#e3e6e4"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.labelcolor": INK})

SERIES = {  # column suffix -> (label, colour, marker)
    "agents": ("Agent World", BLUE, "o"),
    "imitate": ("Markov: counted + imitation", PURPLE, "v"),
    "counted": ("Markov: counted", ORANGE, "s"),
    "momentum": ("Markov: momentum", GREEN, "^"),
    "equal": ("Markov: equal chance", YELLOW, "D"),
}


def table(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def draw(ax, x, series, ticks=None, end_labels=True, ymax=100):
    ax.grid(axis="y", color=GRID, lw=0.5)
    ends = []
    for label, colour, marker, y, ls in series:
        ax.plot(x, y, color=colour, lw=1.6, ls=ls, marker=marker, ms=4, mec="white" if ls == "-" else colour,
                mfc=colour if ls == "-" else "white", mew=0.7, label=label, zorder=3)
        ends.append([y[-1], label])
    if end_labels:
        ends.sort()
        for i in range(1, len(ends)):
            ends[i][0] = max(ends[i][0], ends[i - 1][0] + ymax * 0.055)
        for y, label in ends:
            ax.text(x[-1] + (x[-1] - x[0]) * 0.03, y, label, va="center", fontsize=6.5)
    ax.set_xticks(x if ticks is None else ticks)
    ax.set_ylim(0, ymax)


def models(an):
    rows = table(an / "following_pk.csv")[:6]
    k = [int(r["k"]) for r in rows]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    draw(ax, k, [(lab, col, mk, [100 * float(r[f"p_{key}"]) for r in rows], "-") for key, (lab, col, mk) in SERIES.items()],
         end_labels=False)
    ax.legend(frameon=False, fontsize=6.5, loc="upper right")
    ax.set_xlabel("Intersections in a row, $k$")
    ax.set_ylabel("Trips with a stranger following (%)")
    ax.set_xlim(0.7, 6.3)
    save(fig, "following-models")


def pairs(an):
    rows = table(an / "following_qk.csv")[:5]
    k = [int(r["k"]) for r in rows]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    series = [("Agent World", BLUE, "o", [100 * float(r["agents_observed"]) for r in rows], "-"),
              ("Markov: counted", ORANGE, "s", [100 * float(r["counted_formula_on_agent_pairs"]) for r in rows], "--"),
              ("Markov: momentum", GREEN, "^", [100 * float(r["momentum_formula_on_agent_pairs"]) for r in rows], "--"),
              ("Markov: equal chance", YELLOW, "D", [100 * float(r["equal_formula_on_agent_pairs"]) for r in rows], "--")]
    draw(ax, k, series)
    ax.set_xlabel("Next decisions made the same way, $k$")
    ax.set_ylabel("Pairs arriving together (%)")
    ax.set_xlim(0.7, 5.3)
    save(fig, "following-pairs")


def roads(an):
    rows = table(an / "following_by_roads.csv")
    x = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    series = [(SERIES[key][0], SERIES[key][1], SERIES[key][2], [100 * float(r[key]) for r in rows], "-")
              for key in ("agents", "counted", "momentum", "equal")]
    draw(ax, x, series)
    ax.set_xticklabels([r["roads"] for r in rows])
    ax.set_xlabel("Roads at the intersection")
    ax.set_ylabel("Same next road, pairs arriving together (%)")
    ax.set_xlim(-0.3, len(rows) - 0.7)
    save(fig, "following-roads")


def hours(an):
    rows = [r for r in table(an / "following_by_hour.csv") if int(r["trips"]) >= 200]
    h = [int(r["hour"][:2]) for r in rows]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    draw(ax, h, [(SERIES[key][0], SERIES[key][1], SERIES[key][2], [100 * float(r[f"p3_{key}"]) for r in rows], "-")
                 for key in ("agents", "counted", "momentum", "equal")], ticks=[h0 for h0 in h if h0 % 3 == 0])
    ax.set_xticklabels([f"{h0:02d}:00" for h0 in h if h0 % 3 == 0])
    ax.set_xlabel("Hour of departure (hours with at least 200 trips)")
    ax.set_ylabel("Followed through 3 intersections (%)")
    save(fig, "following-hours")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="day1")
    an = C.OUT / ap.parse_args().run / "analysis"
    models(an); pairs(an); roads(an); hours(an)
    print("wrote graphs/following-models, following-pairs, following-roads, following-hours (.pdf and .png)")
