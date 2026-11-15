"""Shared turns in the live world: the figure in the style of graphs/shared-turns-three-arms, with the live world.

For each trip: the longest run of turns shared with one stranger, where a turn is shared if both people make
the same decision (same junction, road in and road out) within config.SHARED_WINDOW seconds of each other.
All lines are on the same 1,000 people and the hours the live world covers:

  Live World            out/live_census trips
  Agent World           the same people's trips in out/census_run that finished by the same time
  Random Init and End   random place to random place by the quickest path (random_walk.py), on the live trips
  Momentum Chain        Markov chain exp(kappa cos turn) started from the live trips (following.chain_walk)
  Random Walking        Markov chain with equal chance of each road, started from the live trips

Chains and random trips are the mean of --seeds repeats. Writes ../graphs/live-shared-turns.pdf/.png and
out/live_census/analysis/live_shared_turns_models.csv.

    python live_shared_turns.py
"""
import argparse
import bisect
import csv
import gzip
import itertools
import json
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
import following as F
from decisions import Decisions
from random_walk import random_trips
from world import World

KMAX = 10
BLUE, ORANGE, GREEN, YELLOW, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"
INK, MUTED = "#1f2423", "#6b7370"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.labelcolor": INK})


def shared_scan(trips, window=C.SHARED_WINDOW):
    """Longest run of consecutive decisions shared with one stranger, per trip."""
    idx = defaultdict(list)
    for g, t in enumerate(trips):
        for m, (c, ai, ao, tt) in enumerate(t["seq"]):
            idx[(c, ai, ao)].append((tt, g, m))
    for v in idx.values():
        v.sort()
    times = {k: [x[0] for x in v] for k, v in idx.items()}
    out = []
    for t in trips:
        me, prev, best = t["agent"], {}, 0
        for c, ai, ao, tt in t["seq"]:
            key = (c, ai, ao)
            lst, ts = idx[key], times[key]
            cur = {}
            for _, g, mm in lst[bisect.bisect_left(ts, tt - window): bisect.bisect_right(ts, tt + window)]:
                if trips[g]["agent"] == me:
                    continue
                s = prev.get((g, mm - 1), 0) + 1
                cur[(g, mm)] = s
                best = max(best, s)
            prev = cur
        out.append(best)
    return out


def p_curve(sets):
    """Mean over repeats of the share of trips with a run of at least k, k = 1..KMAX, in percent."""
    cur = []
    for k in range(1, KMAX + 1):
        v = [100 * sum(b >= k for b in rows) / len(rows) for rows in sets]
        cur.append(sum(v) / len(v))
    return cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()
    live_dir, aw_dir = C.OUT / "live_census", C.OUT / "census_run"
    summary = json.loads((live_dir / "run_summary.json").read_text())
    clock = summary.get("clock_reached", "24:00")
    cut = int(clock[:2]) * 3600 + int(clock[3:]) * 60
    world = World()
    D = F.D_GLOBAL = Decisions(world)

    raw_live = [t for t in (json.loads(l) for l in gzip.open(live_dir / "trips.jsonl.gz", "rt", encoding="utf-8")) if t["segments"]]
    ids = {json.loads(l)["id"] for l in itertools.islice(open(aw_dir / "people.jsonl", encoding="utf-8"), summary["agents"])}
    raw_aw = [t for t in (json.loads(l) for l in gzip.open(aw_dir / "trips.jsonl.gz", "rt", encoding="utf-8"))
              if t["agent"] in ids and t["segments"] and t.get("arrive") is not None and t["arrive"] <= cut]
    live, aw = F.as_decisions(D, raw_live), F.as_decisions(D, raw_aw)
    print(f"{len(live)} live trips, {len(aw)} Agent World trips, to {clock}", flush=True)

    models = {"equal": F.Model(D, "equal"), "momentum": F.Model(D, "momentum")}
    curves = {
        "live": p_curve([shared_scan(live)]),
        "agents": p_curve([shared_scan(aw)]),
        "random_od": p_curve([shared_scan(F.as_decisions(D, random_trips(world, raw_live, 1 + s))) for s in range(args.seeds)]),
        "momentum": p_curve([shared_scan(F.chain_walk(D, live, models["momentum"], 100 + s)) for s in range(args.seeds)]),
        "equal": p_curve([shared_scan(F.chain_walk(D, live, models["equal"], 100 + s)) for s in range(args.seeds)]),
    }
    with open(live_dir / "analysis" / "live_shared_turns_models.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["k_turns_in_a_row"] + [f"p_{n}" for n in curves])
        for k in range(KMAX):
            w.writerow([k + 1] + [round(curves[n][k] / 100, 4) for n in curves])

    series = [("live", "Live World", VIOLET, "v"), ("agents", "Agent World", BLUE, "o"),
              ("equal", "Random Walking", YELLOW, "D"), ("momentum", "Momentum Chain", GREEN, "^"),
              ("random_od", "Random Init and End", ORANGE, "s")]
    k = list(range(1, KMAX + 1))
    fig, ax = plt.subplots(figsize=(3.5, 2.9))
    ax.grid(axis="y", color="#e3e6e4", lw=0.5)
    ax.set_axisbelow(True)
    for name, label, colour, marker in series:
        ax.plot(k, curves[name], color=colour, lw=1.6, marker=marker, ms=4, mec="white", mew=0.6, label=label, zorder=3)
    ax.set_xticks(k)
    ax.set_xlim(0.7, KMAX + 0.3)
    ax.set_ylim(0, 115)
    ax.set_yticks(range(0, 101, 20))
    ax.legend(frameon=False, fontsize=7, loc="upper right", ncol=2, columnspacing=1.0, handlelength=2.2)
    ax.set_xlabel("Same turns in a row, $k$")
    ax.set_ylabel("Trips where a stranger shares $k$ turns (%)")
    graphs = C.ROOT.parent / "graphs"
    fig.savefig(graphs / "live-shared-turns.pdf", bbox_inches="tight")
    fig.savefig(graphs / "live-shared-turns.png", dpi=220, bbox_inches="tight")
    for n in curves:
        print(n, " ".join(f"{v:.1f}" for v in curves[n]))


if __name__ == "__main__":
    main()
