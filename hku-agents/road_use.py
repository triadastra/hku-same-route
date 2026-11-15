"""How much each road is used under each method.

For every segment of the walking network: how many of 1,000 walkers pass along it, under
  equal chance      Markov chain, every road out equally likely
  momentum          Markov chain, roads closer to straight on likelier
  counted shares    Markov chain with the shares counted in the Agent World run
  imitation         counted shares, plus a chance of taking the road of the person in front
  random start/end  a random place to a random place by the quickest path
  Agent World       the people's own trips
  Q-learning        followers trained to follow one Agent World person (follower_rl.py; test half of the people)

To compare like with like, every method is counted the same way: a walk is its list of junction choices, and
each choice adds one pass to every segment between that junction and the next. (So the stretch from a trip's
start to its first junction is not counted for any method, and the stretch after its last choice runs on to the
next junction.) Chain walkers and random trips are one draw each, with a fixed seed.

    python road_use.py --run census_run

Writes out/<run>/analysis/road_use.csv (every segment) and road_use.md (summary), and graphs/road-use-methods.pdf.
"""
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from functools import lru_cache

import numpy as np
from scipy import stats

import config as C
from decisions import Decisions
from following import RHO, Model, as_decisions, chain_walk
from random_walk import random_trips
from world import World, xy

METHODS = [("equal", "Markov: equal chance"), ("momentum", "Markov: momentum"), ("counted", "Markov: counted shares"),
           ("imitate", "Markov: imitation"), ("random_od", "Random start and end"), ("agents", "Agent World"),
           ("q", "Q-learning follower")]
ON_MAP = ("equal", "random_od", "agents", "q")      # the four branches of the study, side by side


def use_of(D, walks):
    """Passes per segment, and the number of walks, from walks given as junction choices."""
    @lru_cache(maxsize=None)
    def stretch(c, arm):                      # the segments from a junction, by one road, to the next junction
        edges, cur_c, cur_arm = [], c, arm
        for _ in range(60):
            br = D.arms[cur_c][cur_arm]["main"]
            edges += br["edges"]
            nxt = D.branch_arm.get((br["end"], br["last"]))
            if nxt is None:                   # a dead end is walked to the end and back
                edges += br["edges"]
                nxt = (cur_c, cur_arm)
            c2, a2 = nxt
            if D.is_decision[c2]:
                break
            others = [k for k in range(len(D.arms[c2])) if k != a2]
            cur_c, cur_arm = c2, others[0] if others else a2
        return tuple(edges)

    use, n = Counter(), 0
    for w in walks:
        if w["seq"]:
            n += 1
            for c, _, ao, _ in w["seq"]:
                use.update(stretch(c, ao))
    return use, n


def summary(world, per_1000):
    """For one method: how unevenly the walking is spread over the network."""
    length = np.array([e["len"] for e in world.edges])
    stairs = np.array([e["steps"] for e in world.edges])
    metres = per_1000 * length
    order = np.sort(metres)
    cum = np.cumsum(order)
    gini = float(1 - 2 * (cum.sum() / cum[-1]) / len(order) + 1 / len(order))
    top = np.sort(metres)[::-1][: max(1, int(0.05 * len(metres)))].sum() / metres.sum()
    return {"gini": gini, "top5": float(top), "unused": float((per_1000 == 0).mean()),
            "stairs": float((per_1000 * stairs).sum() / metres.sum()), "km_per_walk": float(metres.sum() / 1e6)}


def figure(world, use, run):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LogNorm
    from make_figures import save

    geom = [[xy(*p) for p in e["geom"]] for e in world.edges]
    names = dict(METHODS)
    norm = LogNorm(vmin=1, vmax=300)                          # walkers in 1,000; the same scale in every panel
    cmap = sns.color_palette("rocket_r", as_cmap=True)
    with sns.axes_style("white"), sns.plotting_context("paper", font_scale=0.85):
        fig, axes = plt.subplots(1, len(ON_MAP), figsize=(7.2, 1.95))
        for ax, key in zip(axes.ravel(), ON_MAP):
            v = use[key]
            ax.add_collection(LineCollection(geom, colors="#e3e6e4", linewidths=0.25))
            idx = np.argsort(v)                               # the busiest segments drawn last, on top
            idx = idx[v[idx] >= 1]
            lc = LineCollection([geom[i] for i in idx], cmap=cmap, norm=norm,
                                linewidths=0.35 + 1.5 * np.clip(np.log10(v[idx]) / np.log10(300), 0, 1))
            lc.set_array(np.clip(v[idx], 1, 300))
            ax.add_collection(lc)
            ax.autoscale()
            ax.set_aspect("equal")
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(names[key], fontsize=8, loc="left", pad=3)
            sns.despine(ax=ax, left=True, bottom=True)
        fig.tight_layout(w_pad=0.3, rect=(0, 0.17, 1, 1))
        cb = fig.colorbar(lc, cax=fig.add_axes([0.3, 0.17, 0.4, 0.04]), orientation="horizontal", ticks=[1, 3, 10, 30, 100, 300])
        cb.ax.set_xticklabels(["1", "3", "10", "30", "100", "300+"])
        cb.set_label("Walkers in 1,000 who pass along the segment", fontsize=7.5)
        cb.outline.set_linewidth(0.4)
    save(fig, "road-use-methods" if run == "census_run" else f"road-use-methods-{run}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="census_run")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-figure", action="store_true")
    ap.add_argument("--figure-only", action="store_true", help="redraw the figure from road_use.csv")
    args = ap.parse_args()
    run_dir = C.OUT / args.run
    out = run_dir / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    world = World()
    if args.figure_only:
        with open(out / "road_use.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        figure(world, {k: np.array([float(r[f"per_1000_{k}"]) for r in rows]) for k in ON_MAP}, args.run)
        return
    D = Decisions(world)

    print("loading the Agent World trips", flush=True)
    with open(run_dir / "trips.jsonl", encoding="utf-8") as f:
        raw = [t for t in map(json.loads, f) if t["segments"]]
    agents = [t for t in as_decisions(D, raw) if t["seq"]]
    walks = {"agents": agents, "random_od": as_decisions(D, random_trips(world, raw, args.seed))}
    del raw

    print("walking the Markov chains", flush=True)
    counts, hourly = defaultdict(Counter), defaultdict(Counter)
    for t in agents:
        for c, ai, ao, tt in t["seq"]:
            counts[(c, ai)][ao] += 1
            hourly[(c, ai, int(tt // 3600) % 24)][ao] += 1
    counted = Model(D, "counted", counts=counts, hourly=hourly)
    walks["equal"] = chain_walk(D, agents, Model(D, "equal"), args.seed)
    walks["momentum"] = chain_walk(D, agents, Model(D, "momentum"), args.seed)
    walks["counted"] = chain_walk(D, agents, counted, args.seed)
    walks["imitate"] = chain_walk(D, agents, counted, args.seed, rho=RHO)

    saved = out / "follower_rl_q.npy"
    if saved.exists():
        print("walking the Q-learning followers", flush=True)
        import torch
        import follower_rl as F
        env = F.Env(D, agents, torch.device("cpu"))
        _, te = F.split_people(agents, seed=7)
        L, Dn = env.episodes(te, random.Random(7))
        walks["q"] = env.run(L, Dn, "q", Q=torch.as_tensor(np.load(saved)), record=True)["walks"]
    else:
        print("no trained follower found (run follower_rl.py first): left out", flush=True)

    n_edges = len(world.edges)
    use, n_walks = {}, {}
    for key, _ in METHODS:
        if key in walks:
            u, n_walks[key] = use_of(D, walks[key])
            use[key] = np.array([u.get(e, 0) for e in range(n_edges)]) * 1000.0 / n_walks[key]
    keys = [k for k, _ in METHODS if k in use]

    with open(out / "road_use.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["segment", "name", "metres", "stairs_metres"] + [f"per_1000_{k}" for k in keys])
        for e, E in enumerate(world.edges):
            w.writerow([e, E["name"], E["len"], E["steps"]] + [round(float(use[k][e]), 2) for k in keys])

    names = dict(METHODS)
    pct = lambda x: f"{100 * x:.1f}%"
    M = [f"# Road use under each method: {args.run}", "",
         f"{n_edges:,} segments. A walk is its list of junction choices; each choice adds one pass to every segment "
         f"between that junction and the next, for every method alike. Use is given as walkers in 1,000.", "",
         "| Method | Walks | Walking on the busiest 5% of segments | Unevenness (Gini) | Segments never used | Walking on stairs "
         "| Km per walk | Rank correlation with the Agent World |", "|---|---|---|---|---|---|---|---|"]
    for k in keys:
        s = summary(world, use[k])
        rho = 1.0 if k == "agents" else float(stats.spearmanr(use[k], use["agents"]).statistic)
        M.append(f"| {names[k]} | {n_walks[k]:,} | {pct(s['top5'])} | {s['gini']:.2f} | {pct(s['unused'])} | {pct(s['stairs'])} | "
                 f"{s['km_per_walk']:.2f} | {rho:.2f} |")
    M += ["", "Unevenness is the Gini coefficient of metres walked per segment: 0 if every segment carried the same, 1 if one "
              "segment carried everything. The rank correlation (Spearman) compares each method's use of every segment with "
              "the Agent World's.", "",
          "## The busiest segments in the Agent World", "",
          "| Street | " + " | ".join(names[k] for k in keys) + " |", "|---|" + "---|" * len(keys)]
    by_street = defaultdict(lambda: np.zeros(len(keys)))
    metres = defaultdict(float)
    for e, E in enumerate(world.edges):
        by_street[E["name"] or "(unnamed path)"] += np.array([use[k][e] * E["len"] for k in keys])
        metres[E["name"] or "(unnamed path)"] += E["len"]
    a = keys.index("agents")
    for street in sorted((s for s in by_street if s != "(unnamed path)"), key=lambda s: -by_street[s][a])[:12]:
        M.append(f"| {street} | " + " | ".join(f"{v / metres[street]:.0f}" for v in by_street[street]) + " |")
    M += ["", "Walkers in 1,000 on an average metre of the street.", "",
          "Table: road_use.csv (every segment). Figure: graphs/road-use-methods.pdf."]
    (out / "road_use.md").write_text("\n".join(M) + "\n", encoding="utf-8")
    if not args.no_figure:
        figure(world, use, args.run)
    print(f"wrote {out / 'road_use.md'}")


if __name__ == "__main__":
    main()
