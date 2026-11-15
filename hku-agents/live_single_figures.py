"""The three panels of graphs/live-vs-agent-world as separate graphs, in the style of graphs/live-shared-turns.

Same data as live_figures.py (the same 1,000 people, trips finished by the time the live world reached).
Writes ../graphs/live-following.pdf/.png, live-pairs.pdf/.png and live-hours.pdf/.png.

    python live_single_figures.py
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from live_figures import A_AW, A_LIVE, LIVE, pct, rows

BLUE, ORANGE, GREEN, YELLOW, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6", "#e34948"
INK, MUTED = "#1f2423", "#6b7370"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.labelcolor": INK})
GRAPHS = C.ROOT.parent / "graphs"


def draw(name, x, series, xlabel, ylabel, top, xticklabels=None, ncol=2):
    fig, ax = plt.subplots(figsize=(3.5, 2.9))
    ax.grid(axis="y", color="#e3e6e4", lw=0.5)
    ax.set_axisbelow(True)
    for label, colour, marker, y in series:
        ax.plot(x, y, color=colour, lw=1.6, marker=marker, ms=4, mec="white", mew=0.6, label=label, zorder=3)
    ax.set_xticks(x)
    if xticklabels:
        ax.set_xticklabels(xticklabels)
    ax.set_xlim(x[0] - 0.3, x[-1] + 0.3)
    ax.set_ylim(0, top)
    ax.legend(frameon=False, fontsize=7, loc="upper right", ncol=ncol, columnspacing=1.0, handlelength=2.2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.savefig(GRAPHS / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(GRAPHS / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    clock = json.loads((LIVE / "run_summary.json").read_text()).get("clock_reached", "24:00")
    pk_l, pk_a = rows(A_LIVE / "following_pk.csv"), rows(A_AW / "following_pk.csv")
    qk_l, qk_a = rows(A_LIVE / "following_qk.csv"), rows(A_AW / "following_qk.csv")
    hr_l = {r["hour"]: r for r in rows(A_LIVE / "following_by_hour.csv")}
    hr_a = {r["hour"]: r for r in rows(A_AW / "following_by_hour.csv")}

    k = [int(r["k"]) for r in pk_l]
    draw("live-following", k,
         [("Live World", VIOLET, "v", [pct(r["p_agents"]) for r in pk_l]),
          ("Agent World", BLUE, "o", [pct(r["p_agents"]) for r in pk_a]),
          ("Random Walking", YELLOW, "D", [pct(r["p_equal"]) for r in pk_l]),
          ("Momentum Chain", GREEN, "^", [pct(r["p_momentum"]) for r in pk_l]),
          ("Result Based Chain", RED, "P", [pct(r["p_counted"]) for r in pk_l]),
          ("Random Init and End", ORANGE, "s", [pct(r["p_random_od"]) for r in pk_l])],
         "Junctions in a row, $k$", "Trips where a stranger follows for $k$ junctions (%)", 48)

    k = [int(r["k"]) for r in qk_l if int(r["k"]) <= 5]
    q = lambda t, c: [pct(r[c]) for r in t if int(r["k"]) <= 5]
    draw("live-pairs", k,
         [("Live World", VIOLET, "v", q(qk_l, "agents_observed")),
          ("Agent World", BLUE, "o", q(qk_a, "agents_observed")),
          ("Random Walking", YELLOW, "D", q(qk_l, "equal_observed")),
          ("Momentum Chain", GREEN, "^", q(qk_l, "momentum_observed")),
          ("Result Based Chain", RED, "P", q(qk_l, "counted_observed"))],
         "Next decisions, $k$", "Pairs making the same $k$ decisions (%)", 110)

    last = int(clock[:2]) - 1
    hours = [f"{h:02d}:00" for h in range(6, last + 1) if f"{h:02d}:00" in hr_l and f"{h:02d}:00" in hr_a]
    x = [int(h[:2]) for h in hours]
    draw("live-hours", x,
         [("Live World", VIOLET, "v", [pct(hr_l[h]["p3_agents"]) for h in hours]),
          ("Agent World", BLUE, "o", [pct(hr_a[h]["p3_agents"]) for h in hours]),
          ("Random Walking", YELLOW, "D", [pct(hr_l[h]["p3_equal"]) for h in hours]),
          ("Momentum Chain", GREEN, "^", [pct(hr_l[h]["p3_momentum"]) for h in hours])],
         "Hour the trip starts", "Trips followed for 3 junctions (%)", 27, [f"{h:02d}" for h in x])
    print("wrote graphs/live-following, live-pairs, live-hours (.pdf and .png)")


if __name__ == "__main__":
    main()
