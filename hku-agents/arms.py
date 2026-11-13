"""Compare the arms of the experiment on one finished run.

Arms
  agents   the Agent World run (out/<run>/trips.jsonl)
  random   random place to random place by the quickest path (random_walk.py), several seeds
  noisy    the agents' own trips re-walked with softmax-noisy turns (the older baseline in analyze.py)
  omni     agents that can see and follow the recorded crowd (out/<omni run>/trips.jsonl), if it exists

What it computes
  1. P_k and S_k for every arm (the paper's shared-turn metrics).
  2. The Markov chain of turns: how often two walkers who meet on a road would go on to make the same
     next k turns if each turn depended only on the road they are on, against what really happens.
  3. Per-junction tests of the agents' turn shares against random walking, with effect sizes, and a
     Diebold-Mariano test of which model predicts the agents' turns better: equal chance or random walking.
  4. Road use in both arms, and how the difference relates to nearby places.

    python arms.py --run day1                 # about 10 minutes
    python arms.py --run day1 --omni omni     # also include the omni run in out/omni/

Writes out/<run>/analysis/: compare.md, arms_shared_turns.csv, arms_markov.csv, junction_tests.csv,
junction_tests_directed.csv, road_usage_compare.csv, road_amenity_regression.csv
"""
import argparse
import bisect
import csv
import json
import math
import random
from collections import Counter, defaultdict

import numpy as np
from scipy import stats

import config as C
from analyze import rewalk
from export_amenity_map import FUNCTIONS, GROUP
from random_walk import random_trips
from world import World, xy

KMAX = 10
TURNS = "LRSB"
END = -1
MIN_PASSES = 30   # a junction is tested only if both arms pass it at least this often
NEAR_M = 60       # a place is "near" a road segment if it is within this many metres of its midpoint


# ---------------------------------------------------------------- shared turns
def index_trips(trips):
    idx = defaultdict(list)
    for g, tr in enumerate(trips):
        for s, seg in enumerate(tr["segments"]):
            idx[(seg["edge"], seg["from"])].append((seg["t"], g, s))
    for v in idx.values():
        v.sort()
    return idx, {k: [x[0] for x in v] for k, v in idx.items()}


def shared_pass(you_trips, crowd, decision, index=None):
    """For each 'you' trip, against every stranger's trip in the crowd.

    rows: one per 'you' trip: the longest run of shared turns with one stranger, and how many
          strangers shared at least k turns (each turn within the time window).
    streaks: {directed segment where two people first walked together: Counter of how many of the next
          turns they both made the same way}. Only the route counts here, not the clock, because this is
          compared with the Markov chain, which has no clock.
    """
    idx, times = index or index_trips(crowd)
    W = C.SHARED_WINDOW
    rows, streaks = [], defaultdict(Counter)
    for you in you_trips:
        prev, best = {}, {}
        ys = you["segments"]
        for s, seg in enumerate(ys):
            key = (seg["edge"], seg["from"])
            lst, ts = idx.get(key, ()), times.get(key, ())
            lo, hi = bisect.bisect_left(ts, seg["t"] - W), bisect.bisect_right(ts, seg["t"] + W)
            cur = {}
            for _, og, os_ in lst[lo:hi]:
                agent = crowd[og]["agent"]
                if agent == you["agent"]:
                    continue
                p = prev.get((og, os_ - 1))
                # a shared turn is a decision junction both passed together, the same way in and out
                turns = (p + (1 if decision[seg["from"]] else 0)) if p is not None else 0
                cur[(og, os_)] = turns
                if turns > best.get(agent, -1):
                    best[agent] = turns
                if p is None:
                    xs = crowd[og]["segments"]
                    if s and os_ and xs[os_ - 1]["edge"] == ys[s - 1]["edge"] and xs[os_ - 1]["from"] == ys[s - 1]["from"]:
                        continue  # they were already on the same route, just outside the time window
                    run, j = 0, 1
                    while (run < KMAX and s + j < len(ys) and os_ + j < len(xs)
                           and xs[os_ + j]["edge"] == ys[s + j]["edge"] and xs[os_ + j]["from"] == ys[s + j]["from"]):
                        run += decision[ys[s + j]["from"]]
                        j += 1
                    streaks[key][run] += 1
            prev = cur
        rows.append({"agent": you["agent"], "kind": you.get("kind"), "max": max(best.values(), default=0),
                     "ge": [sum(1 for v in best.values() if v >= k) for k in range(KMAX + 1)]})
    return rows, streaks


def p_k(rows, k):
    return sum(r["max"] >= k for r in rows) / len(rows) if rows else float("nan")


def s_k(rows, k):
    return sum(r["ge"][k] for r in rows) / len(rows) if rows else float("nan")


def sample_of(trips, n, seed):
    """The same sample of 'you' trips that analyze.py uses, so the numbers agree with shared_turns.csv."""
    order = list(range(len(trips)))
    if n and n < len(order):
        order = random.Random(seed).sample(order, n)
    return [trips[g] for g in order]


# ---------------------------------------------------------------- Markov chain of turns
def transitions(trips):
    """T[a][b]: how often a walker on directed segment a went on to directed segment b (or ended, b = END)."""
    T = defaultdict(Counter)
    for tr in trips:
        segs = tr["segments"]
        for s, seg in enumerate(segs):
            a = (seg["edge"], seg["from"])
            T[a][(segs[s + 1]["edge"], segs[s + 1]["from"]) if s + 1 < len(segs) else END] += 1
    return T


def markov_q(T, decision, kmax=KMAX):
    """q[k][a]: the chance that two independent walkers on directed segment a make the same next k turns,
    when each next segment depends only on the current one. Segments joined at a junction with no choice
    (fewer than 3 ways) do not count as a turn, so the count carries along them."""
    P = {a: [(b, n / sum(c.values())) for b, n in c.items() if b != END] for a, c in T.items()}
    q = [dict.fromkeys(P, 1.0)]
    for k in range(1, kmax + 1):
        cur = dict.fromkeys(P, 0.0)
        for _ in range(5000):
            change = 0.0
            for a, outs in P.items():
                v = 0.0
                for b, p in outs:
                    v += p * p * (q[k - 1].get(b, 0.0) if decision[b[1]] else cur.get(b, 0.0))
                change = max(change, abs(v - cur[a]))
                cur[a] = v
            if change < 1e-12:
                break
        q.append(cur)
    return q


def markov_vs_observed(streaks, q):
    """For the pairs that met: the share that went on to share k+ turns, observed and as the chain predicts."""
    n = sum(sum(c.values()) for c in streaks.values())
    obs, pred = [], []
    for k in range(1, KMAX + 1):
        obs.append(sum(v for c in streaks.values() for t, v in c.items() if t >= k) / n)
        pred.append(sum(sum(c.values()) * q[k].get(a, 0.0) for a, c in streaks.items()) / n)
    return n, obs, pred


# ---------------------------------------------------------------- junction turn tests
def decisions_of(trip, decision):
    """(junction, directed segment walked in on, turn, time) for every turn in a trip."""
    segs, turns, out, j = trip["segments"], trip["turns"], [], 0
    for k in range(1, len(segs)):
        if decision[segs[k]["from"]] and j < len(turns):
            out.append((segs[k]["from"], (segs[k - 1]["edge"], segs[k - 1]["from"]), turns[j]["turn"], turns[j]["t"]))
            j += 1
    return out


def turn_counts(trips, decision):
    by_node, by_seg = defaultdict(Counter), defaultdict(Counter)
    for tr in trips:
        for node, seg, turn, _ in decisions_of(tr, decision):
            by_node[node][turn] += 1
            by_seg[seg][turn] += 1
    return by_node, by_seg


def compare_counts(A, B):
    """Chi-square (G) test that two arms turn the same way at each unit, and the size of the difference."""
    out = []
    for u in A.keys() & B.keys():
        a, b = [A[u][t] for t in TURNS], [B[u][t] for t in TURNS]
        na, nb = sum(a), sum(b)
        if na < MIN_PASSES or nb < MIN_PASSES:
            continue
        cols = [i for i in range(4) if a[i] + b[i] > 0]
        if len(cols) < 2:
            p, g = 1.0, 0.0
        else:
            g, p, _, _ = stats.chi2_contingency([[a[i] for i in cols], [b[i] for i in cols]], lambda_="log-likelihood")
        sa, sb = [x / na for x in a], [x / nb for x in b]
        out.append({"unit": u, "n_a": na, "n_b": nb, "share_a": sa, "share_b": sb, "g": g, "p": p,
                    "tvd": 0.5 * sum(abs(x - y) for x, y in zip(sa, sb))})
    if out:
        for r, padj in zip(out, stats.false_discovery_control([r["p"] for r in out], method="bh")):
            r["p_bh"] = padj
    return sorted(out, key=lambda r: -(r["n_a"] + r["n_b"]))


def test_summary(rows):
    if not rows:
        return {}
    w = np.array([r["n_a"] for r in rows], float)
    tvd = np.array([r["tvd"] for r in rows])
    d = np.array([[r["share_a"][i] - r["share_b"][i] for i in range(4)] for r in rows])
    paired = {}
    for i, t in enumerate(TURNS):
        x = d[:, i]
        paired[t] = {"mean": float(x.mean()), "mean_abs": float(np.abs(x).mean()),
                     "wilcoxon_p": float(stats.wilcoxon(x).pvalue) if np.any(x != 0) else 1.0}
    return {"units": len(rows), "significant": sum(r["p_bh"] < 0.05 for r in rows) / len(rows),
            "tvd_median": float(np.median(tvd)), "tvd_weighted": float((tvd * w).sum() / w.sum()), "paired": paired}


# ---------------------------------------------------------------- Diebold-Mariano
def uniform_shares(world, seg):
    """Equal chance for every way out of the junction at the end of a directed segment (turning back
    included), as shares of left, right, straight, back."""
    edge, frm = seg
    e = world.edges[edge]
    n = e["v"] if e["u"] == frm else e["u"]
    c = Counter(world.turn(n, edge, None, e_out) for _, e_out in world.adj[n])
    tot = sum(c.values())
    return [c[t] / tot for t in TURNS]


def diebold_mariano(world, agent_trips, rw_by_seg, decision):
    """Which model forecasts the agents' turns better: equal chance per exit, or the random-walk shares?

    Loss is the Brier score of each observed turn. The loss differential is averaged within each hour of
    the day; the DM statistic is its mean over hours divided by a Newey-West standard error. A positive
    statistic means random walking predicts the agents better than equal chance.
    """
    uni, rwp = {}, {}
    loss = defaultdict(lambda: [0.0, 0.0, 0])   # hour -> [sum loss uniform, sum loss random walk, turns]
    per_seg = defaultdict(lambda: [0.0, 0.0, 0])
    for tr in agent_trips:
        for _, seg, turn, t in decisions_of(tr, decision):
            if seg not in uni:
                uni[seg] = uniform_shares(world, seg)
                c = rw_by_seg.get(seg, {})
                n = sum(c.values())
                # random-walk shares, shrunk toward equal chance by one pseudo-pass (so unseen roads fall back to it)
                rwp[seg] = [(c.get(x, 0) + uni[seg][i]) / (n + 1) for i, x in enumerate(TURNS)]
            lu = sum(((x == turn) - uni[seg][i]) ** 2 for i, x in enumerate(TURNS))
            lr = sum(((x == turn) - rwp[seg][i]) ** 2 for i, x in enumerate(TURNS))
            for acc in (loss[int(t // 3600) % 24], per_seg[seg]):
                acc[0] += lu; acc[1] += lr; acc[2] += 1
    hours = sorted(h for h, v in loss.items() if v[2] >= 500)
    d = np.array([(loss[h][0] - loss[h][1]) / loss[h][2] for h in hours])
    n = len(d)
    lag = int(n ** (1 / 3))
    dc = d - d.mean()
    lrv = (dc @ dc) / n + 2 * sum((1 - j / (lag + 1)) * (dc[j:] @ dc[:-j]) / n for j in range(1, lag + 1))
    dm = d.mean() / math.sqrt(lrv / n)
    tot = [sum(v[i] for v in loss.values()) for i in range(3)]
    seg_d = np.array([(v[0] - v[1]) / v[2] for v in per_seg.values() if v[2] >= MIN_PASSES])
    t_seg = stats.ttest_1samp(seg_d, 0.0)
    return {"hours": [f"{h:02d}:00" for h in hours], "d_by_hour": d.tolist(), "dm": float(dm), "lag": lag,
            "p": float(2 * stats.t.sf(abs(dm), n - 1)), "brier_uniform": tot[0] / tot[2], "brier_random_walk": tot[1] / tot[2],
            "turns": tot[2], "segments_tested": len(seg_d), "t_across_segments": float(t_seg.statistic),
            "p_across_segments": float(t_seg.pvalue), "share_segments_rw_better": float((seg_d > 0).mean())}


# ---------------------------------------------------------------- road use
def road_use(trips):
    return Counter(s["edge"] for tr in trips for s in tr["segments"])


def top_share(use, world, frac=0.05):
    """Share of all metres walked that fall on the busiest `frac` of segments."""
    wm = sorted((n * world.edges[e]["len"] for e, n in use.items()), reverse=True)
    wm += [0.0] * (len(world.edges) - len(wm))
    return sum(wm[: max(1, int(frac * len(world.edges)))]) / sum(wm)


def amenity_regression(world, ua, ur):
    """log(agent share of walking / random-walk share) on the number of places of each function near the road."""
    mids = np.array([xy(*e["geom"][len(e["geom"]) // 2]) for e in world.edges])
    X = np.zeros((len(world.edges), len(FUNCTIONS)))
    for p in world.places.values():
        near = np.hypot(mids[:, 0] - p["xy"][0], mids[:, 1] - p["xy"][1]) <= NEAR_M
        X[near, GROUP[p["category"]]] += 1
    ta, tr = sum(ua.values()), sum(ur.values())
    keep = np.array([ua[e] + ur[e] >= 20 for e in range(len(world.edges))])
    y = np.array([math.log(((ua[e] + 1) / ta) / ((ur[e] + 1) / tr)) for e in range(len(world.edges))])[keep]
    A = np.c_[np.ones(keep.sum()), X[keep]]
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = y - A @ beta
    bread = np.linalg.inv(A.T @ A)
    cov = bread @ (A.T * res ** 2) @ A @ bread * len(y) / (len(y) - A.shape[1])  # robust (HC1) errors
    se = np.sqrt(np.diag(cov))
    r2 = 1 - (res @ res) / ((y - y.mean()) @ (y - y.mean()))
    names = ["(intercept)"] + [f[0] for f in FUNCTIONS]
    return [{"term": n, "coef": float(b), "se": float(s), "p": float(2 * stats.norm.sf(abs(b / s)))}
            for n, b, s in zip(names, beta, se)], float(r2), int(keep.sum())


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="day1")
    ap.add_argument("--omni", default="", help="name of an omni run in out/ to include")
    ap.add_argument("--seeds", type=int, default=5, help="random-walk repeats")
    ap.add_argument("--sample", type=int, default=5000, help="max trips used as 'you'")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--beta", type=float, default=0.01, help="randomness of the noisy re-walk")
    args = ap.parse_args()

    world = World()
    run_dir = C.OUT / args.run
    out = run_dir / "analysis"
    trips = [json.loads(l) for l in open(run_dir / "trips.jsonl", encoding="utf-8")]
    trips = [t for t in trips if t["segments"]]
    decision = [len(a) >= 3 for a in world.adj]
    print(f"{len(trips)} agent trips")

    # ---- the arms
    arms, streaks, metres = {}, {}, {}
    rows, streaks["agents"] = shared_pass(sample_of(trips, args.sample, args.seed), trips, decision)
    arms["agents"] = [rows]
    metres["agents"] = sum(t["metres"] for t in trips) / len(trips)
    print("agents done")

    rw_sets = []
    arms["random"] = []
    for i in range(args.seeds):
        rw = random_trips(world, trips, args.seed + i)
        rows, st = shared_pass(sample_of(rw, args.sample, args.seed), rw, decision)
        arms["random"].append(rows)
        if i < 2:
            rw_sets.append(rw)   # the first is the arm we report; the second is the noise check
        if i == 0:
            streaks["random"] = st
            metres["random"] = sum(t["metres"] for t in rw) / len(rw)
        print(f"random walk seed {args.seed + i} done")
    rw = rw_sets[0]

    noisy = rewalk(trips, world, args.beta, args.seed)
    rows, streaks["noisy"] = shared_pass(sample_of(noisy, args.sample, args.seed), noisy, decision)
    arms["noisy"] = [rows]
    metres["noisy"] = sum(sum(world.edges[s["edge"]]["len"] for s in t["segments"]) for t in noisy) / len(noisy)
    print("noisy re-walk done")

    omni = None
    if args.omni:
        omni = [json.loads(l) for l in open(C.OUT / args.omni / "trips.jsonl", encoding="utf-8")]
        omni = [t for t in omni if t["segments"]]
        # an omni agent walks through the recorded crowd; its own recorded self is skipped as "the same person"
        rows, streaks["omni"] = shared_pass(sample_of(omni, args.sample, args.seed), trips, decision)
        arms["omni"] = [rows]
        metres["omni"] = sum(t["metres"] for t in omni) / len(omni)

    def stat(arm, f, k):
        v = [f(r, k) for r in arms[arm]]
        return float(np.mean(v)), (float(np.std(v, ddof=1)) if len(v) > 1 else 0.0)

    names = list(arms)
    with open(out / "arms_shared_turns.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["k_turns_in_a_row"] + [f"p_{a}" for a in names] + ["p_random_sd"] + [f"s_{a}" for a in names] + ["s_random_sd"])
        for k in range(1, KMAX + 1):
            w.writerow([k] + [round(stat(a, p_k, k)[0], 4) for a in names] + [round(stat("random", p_k, k)[1], 4)]
                       + [round(stat(a, s_k, k)[0], 3) for a in names] + [round(stat("random", s_k, k)[1], 3)])
    kinds = {kind: [r for r in arms["agents"][0] if r["kind"] == kind] for kind in ("go", "stroll")}

    # ---- Markov chain
    q_rw = markov_q(transitions(rw), decision)
    q_ag = markov_q(transitions(trips), decision)
    mk = {"random": markov_vs_observed(streaks["random"], q_rw), "agents": markov_vs_observed(streaks["agents"], q_ag),
          "agents_rw_chain": markov_vs_observed(streaks["agents"], q_rw)}
    if omni:
        mk["omni"] = markov_vs_observed(streaks["omni"], q_ag)
    with open(out / "arms_markov.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["k_more_turns", "random_observed", "random_markov", "agents_observed", "agents_markov",
                    "agents_markov_random_walk_chain"] + (["omni_observed"] if omni else []))
        for k in range(1, KMAX + 1):
            w.writerow([k] + [round(x, 5) for x in (mk["random"][1][k - 1], mk["random"][2][k - 1], mk["agents"][1][k - 1],
                                                    mk["agents"][2][k - 1], mk["agents_rw_chain"][2][k - 1])]
                       + ([round(mk["omni"][1][k - 1], 5)] if omni else []))
    print("Markov chain done")

    # ---- junction tests
    ag_node, ag_seg = turn_counts(trips, decision)
    rw_node, rw_seg = turn_counts(rw, decision)
    rw2_node, rw2_seg = turn_counts(rw_sets[1], decision) if len(rw_sets) > 1 else ({}, {})
    t_node, t_seg = compare_counts(ag_node, rw_node), compare_counts(ag_seg, rw_seg)
    null_node, null_seg = compare_counts(rw_node, rw2_node), compare_counts(rw_seg, rw2_seg)
    with open(out / "junction_tests.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["junction", "lat", "lon", "passes_agents", "passes_random"] + [f"agents_{t}_%" for t in TURNS]
                   + [f"random_{t}_%" for t in TURNS] + ["g_statistic", "p", "p_bh", "tvd"])
        for r in t_node:
            n = world.nodes[r["unit"]]
            w.writerow([r["unit"], n["lat"], n["lon"], r["n_a"], r["n_b"]] + [round(100 * x, 1) for x in r["share_a"] + r["share_b"]]
                       + [round(r["g"], 2), f"{r['p']:.3g}", f"{r['p_bh']:.3g}", round(r["tvd"], 4)])
    with open(out / "junction_tests_directed.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["segment", "name", "from_junction", "passes_agents", "passes_random"] + [f"agents_{t}_%" for t in TURNS]
                   + [f"random_{t}_%" for t in TURNS] + ["g_statistic", "p", "p_bh", "tvd"])
        for r in t_seg:
            e, frm = r["unit"]
            w.writerow([e, world.edges[e]["name"], frm, r["n_a"], r["n_b"]] + [round(100 * x, 1) for x in r["share_a"] + r["share_b"]]
                       + [round(r["g"], 2), f"{r['p']:.3g}", f"{r['p_bh']:.3g}", round(r["tvd"], 4)])
    dm = diebold_mariano(world, trips, rw_seg, decision)
    print("junction tests done")

    # ---- road use
    ua, ur = road_use(trips), road_use(rw)
    ta, tr = sum(ua.values()), sum(ur.values())
    used = [e for e in range(len(world.edges)) if ua[e] + ur[e] > 0]
    rho = stats.spearmanr([ua[e] for e in used], [ur[e] for e in used])
    with open(out / "road_usage_compare.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["segment", "name", "walkers_agents", "walkers_random", "share_agents_%", "share_random_%", "ratio", "metres", "lat", "lon"])
        for e in sorted(used, key=lambda e: -(ua[e] + ur[e])):
            E = world.edges[e]
            mid = E["geom"][len(E["geom"]) // 2]
            w.writerow([e, E["name"], ua[e], ur[e], round(100 * ua[e] / ta, 4), round(100 * ur[e] / tr, 4),
                        round(((ua[e] + 1) / ta) / ((ur[e] + 1) / tr), 3), E["len"], mid[0], mid[1]])
    reg, r2, n_reg = amenity_regression(world, ua, ur)
    with open(out / "road_amenity_regression.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["term", "coef", "se", "p"])
        for r in reg:
            w.writerow([r["term"], round(r["coef"], 4), round(r["se"], 4), f"{r['p']:.3g}"])

    # ---- summary
    label = {"agents": "Agent World", "random": "Random walk", "noisy": "Same trips, noisy turns", "omni": "Omni agents"}
    L = [f"# Comparison of the arms: {args.run}", "",
         f"{len(trips)} trips in each arm ({len(arms['agents'][0])} used as 'you'); a turn is shared within {C.SHARED_WINDOW} s. "
         f"Random walk: {args.seeds} repeats, mean ± standard deviation.", "",
         "## Chance that a stranger makes your same k turns in a row", "",
         "| k | " + " | ".join(label[a] for a in names) + " |", "|---|" + "---|" * len(names)]
    for k in range(1, KMAX + 1):
        cells = []
        for a in names:
            m, sd = stat(a, p_k, k)
            cells.append(f"{m:.1%} ± {sd:.1%}" if a == "random" else f"{m:.1%}")
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L += ["", "Average trip length: " + ", ".join(f"{label[a]} {metres[a]:.0f} m" for a in names) + ". "
          "Longer trips give more chances to share turns, so the arms differ in exposure as well as in route choice.", "",
          f"Within the Agent World arm: `go_to` trips ({len(kinds['go'])}) share 5+ turns {p_k(kinds['go'], 5):.1%} of the time, "
          f"`stroll` trips ({len(kinds['stroll'])}) {p_k(kinds['stroll'], 5):.1%}.", "",
          "## Markov chain of turns", "",
          "Two people start walking the same road together. Chance that they then make the same next k turns: what "
          "happened, and what a chain predicts in which every turn depends only on the current road.", "",
          "| k more turns | Random walk, observed | Random walk, Markov chain | Agents, observed | Agents, Markov chain (fitted on agents) | Agents, Markov chain (fitted on random walk) |",
          "|---|---|---|---|---|---|"]
    for k in (1, 2, 3, 4, 5):
        L.append(f"| {k} | {mk['random'][1][k - 1]:.1%} | {mk['random'][2][k - 1]:.1%} | {mk['agents'][1][k - 1]:.1%} | "
                 f"{mk['agents'][2][k - 1]:.1%} | {mk['agents_rw_chain'][2][k - 1]:.1%} |")
    L += ["", f"Pairs that met: random walk {mk['random'][0]:,}, agents {mk['agents'][0]:,}."]
    if omni:
        L.append(f"Omni agents, observed, 3 more turns: {mk['omni'][1][2]:.1%} ({mk['omni'][0]:,} pairs).")

    L += ["", "## Do agents turn differently from random walkers?", "",
          f"G-test of the left/right/straight/back counts, agents against random walk, where both arms have at least "
          f"{MIN_PASSES} passes. p-values corrected over all units (Benjamini-Hochberg). 'Noise check' is one random-walk "
          "repeat against another: what the same test gives when there is no real difference.", "",
          "| Unit | Tested | Significant at 5% | Median difference (TVD) | Pass-weighted TVD | Noise check: significant | Noise check: median TVD |",
          "|---|---|---|---|---|---|---|"]
    for name, t, nul in (("Junction", t_node, null_node), ("Road and direction", t_seg, null_seg)):
        a, b = test_summary(t), test_summary(nul)
        L.append(f"| {name} | {a['units']} | {a['significant']:.1%} | {a['tvd_median']:.3f} | {a['tvd_weighted']:.3f} | "
                 f"{b.get('significant', float('nan')):.1%} | {b.get('tvd_median', float('nan')):.3f} |")
    L += ["", "TVD (total variation distance) is the share of turns that would have to change for the two arms to agree: "
          "0 = identical, 1 = completely different.", "",
          "Paired differences, agents minus random walk, per road and direction:", "",
          "| Turn | Mean difference | Mean absolute difference | Wilcoxon p |", "|---|---|---|---|"]
    pr = test_summary(t_seg)["paired"]
    for t, nm in zip(TURNS, ("Left", "Right", "Straight", "Back")):
        L.append(f"| {nm} | {pr[t]['mean']:+.1%} | {pr[t]['mean_abs']:.1%} | {pr[t]['wilcoxon_p']:.3g} |")
    L += ["", "## Diebold-Mariano: which model predicts the agents' turns better?", "",
          f"Brier score over {dm['turns']:,} agent turns (lower is better): equal chance per exit {dm['brier_uniform']:.4f}, "
          f"random-walk shares {dm['brier_random_walk']:.4f}.",
          f"DM statistic over {len(dm['hours'])} hours of the day (Newey-West, lag {dm['lag']}): {dm['dm']:.2f}, p = {dm['p']:.3g}. "
          "Positive means random walking predicts the agents better than equal chance.",
          f"Across {dm['segments_tested']} roads and directions: random walking is the better predictor on "
          f"{dm['share_segments_rw_better']:.1%} of them (paired t = {dm['t_across_segments']:.2f}, p = {dm['p_across_segments']:.3g}).", "",
          "## Road use", "",
          f"Spearman rank correlation of walkers per segment, agents against random walk: {rho.statistic:.3f} "
          f"({len(used)} segments used by either arm).",
          f"Share of all metres walked on the busiest 5% of segments: agents {top_share(ua, world):.1%}, random walk {top_share(ur, world):.1%}.",
          f"Segments never walked: agents {sum(1 for e in range(len(world.edges)) if not ua[e])}, "
          f"random walk {sum(1 for e in range(len(world.edges)) if not ur[e])} of {len(world.edges)}.", "",
          f"Regression of log(agent share / random-walk share) on places within {NEAR_M} m of the segment "
          f"({n_reg} segments, R² = {r2:.3f}, robust standard errors):", "",
          "| Places nearby | Coefficient | Std. error | p |", "|---|---|---|---|"]
    for r in reg:
        L.append(f"| {r['term']} | {r['coef']:+.3f} | {r['se']:.3f} | {r['p']:.3g} |")
    L += ["", "A coefficient of +0.10 means each extra place of that kind nearby goes with about 10% more agent "
          "walking on the segment than random walking would put there.", "",
          "Tables: arms_shared_turns.csv, arms_markov.csv, junction_tests.csv, junction_tests_directed.csv, "
          "road_usage_compare.csv, road_amenity_regression.csv."]
    (out / "compare.md").write_text("\n".join(L), encoding="utf-8")
    (out / "dm_by_hour.csv").write_text("hour,loss_equal_chance_minus_loss_random_walk\n"
                                        + "\n".join(f"{h},{d:.5f}" for h, d in zip(dm["hours"], dm["d_by_hour"])) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
