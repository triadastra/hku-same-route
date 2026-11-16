"""One results table and its figure: shared turns (P_k, mean S_k) for the four conditions, window W = 90 s.

Conditions (names as in the paper)
  Agent World          the Agent World run itself (runs/<run>/trips.jsonl), one run
  Random Walking       Markov chain, equal chance at every junction (sameroute/analysis/following.py, model "equal")
  Momentum Chain       Markov chain, straight on likelier (sameroute/analysis/following.py, model "momentum", kappa 2)
  Random Init and End  random place to random place by the quickest path (sameroute/sim/random_walk.py)

The three baselines are not stored runs: they are walked again here from the Agent World trips with the
repository's own walkers and seeds (chains: seeds 100, 101, 102 as in sameroute/analysis/following.py; random places: seeds 1 to 5
as in sameroute/analysis/arms.py). A chain walker replaces one agent trip: same start junction, start time, pace and number of
decisions. Every condition is scored with sameroute/analysis/arms.py's shared_pass (the paper's metric): a stranger shares a turn
when both pass the same junction, in and out by the same segments, each within W seconds of the other.
Every trip is scored as "you" against every other person's trips in the same condition and repeat.

    python -m sameroute analyse shared-turns-table --run census_run            # compute, then table and figure
    python -m sameroute analyse shared-turns-table --from-csv                  # table, figure and printed values from the CSV

Writes results/shared_turns.csv, results/shared_turns.tex, graphs/shared-turns-three-arms.pdf and .png.
"""
import argparse
import csv
import json
import multiprocessing as mp
import statistics
from pathlib import Path

from sameroute import config as C

RESULTS = C.RESULTS
CSV_PATH = RESULTS / "shared_turns.csv"
TEX_PATH = RESULTS / "shared_turns.tex"
KMAX = 10
CONDITIONS = ["Agent World", "Random Walking", "Momentum Chain", "Random Init and End"]
SEEDS = {"Agent World": [None], "Random Walking": [100, 101, 102], "Momentum Chain": [100, 101, 102],
         "Random Init and End": [1, 2, 3, 4, 5]}
MODEL = {"Random Walking": "equal", "Momentum Chain": "momentum"}
G = {}   # world, trips and decisions, loaded once and shared with the worker processes


# ---------------------------------------------------------------- walkers
def chain_trips(walkers):
    """Markov-chain walkers (following.chain_walk: a list of decisions) as trips made of segments, so that
    arms.shared_pass can score them. A walker walks in by the road of its first decision, then out of every
    junction by the road it chose, through bends, to the next junction (a dead end is walked there and back)."""
    D, world = G["D"], G["world"]
    out = []
    for w in walkers:
        seq = w["seq"]
        if not seq:
            continue
        pace, segs = w["pace"], []

        def walk(node, edges, t):
            for e in edges:
                E = world.edges[e]
                nxt = E["v"] if E["u"] == node else E["u"]
                segs.append({"edge": e, "from": node, "to": nxt, "t": t})
                t += E["secs"] / pace
                node = nxt
            return node, t

        c, ai, _, t0 = seq[0]
        br = D.arms[c][ai]["main"]
        node, back = br["node"], []
        for e in br["edges"]:                       # the road in, walked towards the junction
            E = world.edges[e]
            nxt = E["v"] if E["u"] == node else E["u"]
            back.append((e, nxt, node, E["secs"] / pace))
            node = nxt
        t = t0 - sum(b[3] for b in back)
        for e, a, b, secs in reversed(back):
            segs.append({"edge": e, "from": a, "to": b, "t": t})
            t += secs
        for m, (c, ai, ao, t) in enumerate(seq):
            cur_c, cur_arm = c, ao
            for _ in range(60):                     # as Decisions.step
                br = D.arms[cur_c][cur_arm]["main"]
                end, t = walk(br["node"], br["edges"], t)
                if m == len(seq) - 1:
                    break
                nxt = D.branch_arm.get((end, br["last"]))
                if nxt is None:                     # dead end: back the same way
                    _, t = walk(end, br["edges"][::-1], t)
                    nxt = (cur_c, cur_arm)
                c2, a2 = nxt
                if D.is_decision[c2]:
                    break
                others = [k for k in range(len(D.arms[c2])) if k != a2]
                cur_c, cur_arm = c2, (others[0] if others else a2)
        for s in segs:
            s["t"] = round(s["t"])
        out.append({"agent": w["agent"], "kind": "chain", "segments": segs, "arrive": round(t)})
    return out


def score(task):
    """P_k and mean S_k (k = 1..KMAX) of one condition and seed, every trip scored."""
    from sameroute.analysis.arms import p_k, s_k, shared_pass
    name, seed = task
    if name == "Agent World":
        trips = G["trips"]
    elif name == "Random Init and End":
        from sameroute.sim.random_walk import random_trips
        trips = random_trips(G["world"], G["trips"], seed)
    else:
        from sameroute.analysis.following import Model, chain_walk
        trips = chain_trips(chain_walk(G["D"], G["agents"], Model(G["D"], MODEL[name]), seed))
    rows, _ = shared_pass(trips, trips, G["decision"])
    return (name, seed, len(trips), [p_k(rows, k) for k in range(1, KMAX + 1)],
            [s_k(rows, k) for k in range(1, KMAX + 1)])


def compute(run):
    from sameroute.world.decisions import Decisions
    from sameroute.analysis.following import as_decisions
    from sameroute.world.world import World
    run_dir = C.OUT / run
    src = run_dir / "trips.jsonl"
    world = World()
    trips = [json.loads(l) for l in open(src, encoding="utf-8")]
    trips = [t for t in trips if t["segments"]]
    D = Decisions(world)
    G.update(world=world, trips=trips, D=D, agents=as_decisions(D, trips),
             decision=[len(a) >= 3 for a in world.adj])
    tasks = [(name, seed) for name in CONDITIONS for seed in SEEDS[name]]
    print(f"{len(trips)} Agent World trips; {len(tasks)} passes", flush=True)
    res = {}
    with mp.get_context("fork").Pool(min(4, mp.cpu_count())) as pool:
        for name, seed, n, p, s in pool.imap_unordered(score, tasks):
            res.setdefault(name, []).append((seed, n, p, s))
            print(f"  done: {name}, seed {seed}, {n} trips", flush=True)
    RESULTS.mkdir(exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["condition", "k", "P_k", "P_k_sd", "S_k_bar", "S_k_bar_sd", "repeats", "trips", "W_s",
                    "run", "seeds"])
        for name in CONDITIONS:
            reps = sorted(res[name], key=lambda r: (r[0] is None, r[0]))
            n = sorted({r[1] for r in reps})
            for k in range(KMAX):
                p, s = [r[2][k] for r in reps], [r[3][k] for r in reps]
                sd = (lambda v: f"{statistics.stdev(v):.6f}") if len(reps) > 1 else (lambda v: "")
                w.writerow([name, k + 1, f"{statistics.mean(p):.6f}", sd(p), f"{statistics.mean(s):.6f}", sd(s),
                            len(reps), n[0] if len(n) == 1 else f"{n[0]}-{n[-1]}", C.SHARED_WINDOW, run,
                            " ".join(str(r[0]) for r in reps if r[0] is not None)])
    print(f"wrote {CSV_PATH}")


# ---------------------------------------------------------------- table, figure, values to quote
def read_csv():
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    names = [c for c in CONDITIONS if any(r["condition"] == c for r in rows)]
    by = {c: sorted((r for r in rows if r["condition"] == c), key=lambda r: int(r["k"])) for c in names}
    return names, by


def header(name):
    words = name.split()
    cut = 2 if len(words) > 2 else 1
    return r"\shortstack{" + " ".join(words[:cut]) + r"\\" + " ".join(words[cut:]) + "}"


def fmt_s(v):
    return f"{v:.2f}" if v >= 0.095 else f"{v:.3f}"   # small values keep a third decimal


def write_tex(names, by):
    one = by[names[0]][0]
    reps = ", ".join(f"{c}: {by[c][0]['repeats']}" for c in names)
    trips = ", ".join(f"{c}: {int(str(by[c][0]['trips']).split('-')[0]):,}".replace(",", "{,}") for c in names)
    sd_p = max((100 * float(r["P_k_sd"]) for c in names for r in by[c] if r["P_k_sd"]), default=0.0)
    sd_s = max((float(r["S_k_bar_sd"]) for c in names for r in by[c] if r["S_k_bar_sd"]), default=0.0)
    cols = "".join("r" for _ in names)
    L = [r"% Written by sameroute/analysis/shared_turns_table.py from results/shared_turns.csv. Do not edit by hand.",
         r"% Needs \usepackage{booktabs}.",
         r"\begin{table}[t]", r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{4pt}",
         r"\caption{Shared turns by condition, window $W = \SI{" + one["W_s"] + r"}{\second}$ (run \texttt{"
         + one["run"].replace("_", r"\_") + r"}). $P_k$: share of trips on which at least one stranger makes the "
         r"same $k$ turns in a row. $\bar{S}_k$: mean number of such strangers per trip. Trips per condition: "
         + trips + ". Repeats: " + reps + r"; values are means over repeats. Largest standard deviation across "
         f"repeats: {sd_p:.2f} percentage points for $P_k$ and {sd_s:.3f} for " + r"$\bar{S}_k$.}",
         r"\label{tab:shared-turns}",
         r"\begin{tabular}{@{}r" + cols + r"@{}}", r"\toprule",
         "$k$ & " + " & ".join(header(c) for c in names) + r" \\", r"\midrule",
         r"\multicolumn{" + str(len(names) + 1) + r"}{@{}l}{$P_k$ (\%)} \\"]
    for i in range(KMAX):
        L.append(f"{i + 1} & " + " & ".join(f"{100 * float(by[c][i]['P_k']):.1f}" for c in names) + r" \\")
    L += [r"\midrule", r"\multicolumn{" + str(len(names) + 1) + r"}{@{}l}{$\bar{S}_k$ (strangers per trip)} \\"]
    for i in range(KMAX):
        L.append(f"{i + 1} & " + " & ".join(fmt_s(float(by[c][i]['S_k_bar'])) for c in names) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    TEX_PATH.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {TEX_PATH}")


def write_figure(names, by):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from sameroute.figures.arms import BLUE, GREEN, ORANGE, YELLOW, lines   # also sets the paper's plot style
    from sameroute.figures.amenity import save
    style = {"Agent World": (BLUE, "o"), "Random Walking": (YELLOW, "D"), "Momentum Chain": (GREEN, "^"),
             "Random Init and End": (ORANGE, "s")}
    k = list(range(1, KMAX + 1))
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    series = []
    for c in names:
        y = np.array([100 * float(r["P_k"]) for r in by[c]])
        if by[c][0]["P_k_sd"]:
            sd = np.array([100 * float(r["P_k_sd"]) for r in by[c]])
            ax.fill_between(k, y - sd, y + sd, color=style[c][0], alpha=0.2, lw=0)
        series.append((c, style[c][0], style[c][1], list(y)))
    lines(ax, k, series)
    for t in list(ax.texts):       # the legend names the lines; end labels would repeat it and collide
        t.remove()
    ax.legend(frameon=False, fontsize=6.5, loc="upper right", ncol=2, columnspacing=1.0, handlelength=1.6)
    ax.set_ylim(0, 115)
    ax.set_yticks(range(0, 101, 20))
    ax.set_xlabel("Same turns in a row, $k$")
    ax.set_ylabel("Trips where a stranger shares $k$ turns (%)")
    save(fig, "shared-turns-three-arms")
    print("wrote graphs/shared-turns-three-arms.pdf and .png")


def print_values(names, by):
    print("\nValues to quote (from results/shared_turns.csv)")
    for c in names:
        r = by[c][KMAX - 1]
        print(f"  {c}: P_10 = {100 * float(r['P_k']):.2f}%, mean S_10 = {float(r['S_k_bar']):.3f}")
    if "Agent World" in by:
        for c in names:
            if c == "Agent World":
                continue
            ks = [i + 1 for i in range(KMAX) if float(by["Agent World"][i]["S_k_bar"]) > float(by[c][i]["S_k_bar"])]
            print(f"  smallest k where Agent World's mean S_k exceeds {c}'s: "
                  + (f"{ks[0]} (it exceeds at k = {', '.join(map(str, ks))})" if ks else "none in k = 1..10"))
    for c in names:
        p9, p10 = float(by[c][8]["P_k"]), float(by[c][9]["P_k"])
        print(f"  {c}: P_10 / P_9 = {p10 / p9:.3f}" if p9 else f"  {c}: P_10 / P_9 undefined (P_9 = 0)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="census_run")
    ap.add_argument("--from-csv", action="store_true", help="skip the computing; use results/shared_turns.csv")
    args = ap.parse_args()
    if not args.from_csv:
        compute(args.run)
    names, by = read_csv()
    write_tex(names, by)
    write_figure(names, by)
    print_values(names, by)


if __name__ == "__main__":
    main()
