"""How likely is it that a stranger makes your route decisions, intersection after intersection?

The project plan's question (sections 2.2 and 5): how the number of intersections, the possible directions and
popular routes change the chance that two people appear to follow each other, at different times of day, and
how that chance changes when route preference or imitation is added.

Everything works on real intersections (decisions.py): a trip is a list of decisions
(intersection, road in, road out, time).

Who walks
  agents     the Agent World run: people with their own plans, walking by the quickest path (out/<run>/trips.jsonl)
  no_llm     the same people following a rule-based timetable instead of the LLM (--control), if given
  random_od  random place to random place by the quickest path (random_walk.py)
  and four Markov chains. A chain walker starts where an agent trip makes its first decision, at the same time
  and pace, and makes as many decisions as that trip, choosing each road out from a table:
  equal      every road out has the same chance, 1/n (turning back only at a dead end)
  momentum   roads closer to straight ahead are likelier: weight exp(kappa * cos(change of direction))
  counted    the shares counted in the agent run at each intersection, per road in and hour of day: what the
             project plan's thermal sensors would record, with no way to follow anyone
  imitate    counted, but with chance rho a walker takes the road the person just in front of them took

Measures
  following  the same stranger, behind you by at most FOLLOW_M metres when you reach each intersection,
             arriving and leaving by your roads at k of your intersections in a row.
             P_k = share of trips with such a stranger (also among trips with at least k decisions);
             S_k = average number of such strangers per trip.
  q_k        two people arrive at an intersection by the same road, one at most FOLLOW_M metres behind the other:
             the chance they make the same next k decisions. For a Markov chain there is a formula,
             q_k(s) = sum over roads a of p(a | s)^2 * q_(k-1)(next(s, a)), with q_0 = 1.
  chi-square at each intersection and road in (at least 30 passes): do the Agent World's counts of each road out
             fit equal chance, or momentum? Turning back is left out (equal chance never turns back). Calibrated on
             the equal-chance walkers, where after the correction the test should reject almost none.

    python following.py --run day1 --control mock_day1      # a few minutes; --control is optional

Writes out/<run>/analysis/following.md, following_*.csv and decision_table.csv, and graphs/following-*.pdf.
"""
import argparse
import bisect
import csv
import heapq
import json
import math
import random
from collections import Counter, defaultdict, deque

from scipy import stats

import config as C
from decisions import Decisions
from groups import GROUPS, LABELS, group_of
from random_walk import random_trips
from world import World, _english

KMAX = 8
FOLLOW_M = 30          # metres behind you that still counts as following
KAPPA = 2.0            # momentum: straight on is e^2 = 7.4 times likelier than a right-angle turn
RHO = 0.3              # imitation: chance of taking the road the person in front took
SEEDS = 3
HOUR_MIN = 30          # passes needed to use an hour's own table in the counted model
SAME_PLACE_M = 150     # "same origin / destination" for explaining who follows whom


def secs_for(metres):
    return metres / C.WALK_SPEED


# ---------------- walkers ----------------
def as_decisions(D, trips):
    """Keep what the measures need, and replace each trip's segments by its decisions."""
    out = []
    for t in trips:
        if t["segments"]:
            out.append({"agent": t["agent"], "from": t["from"], "to": t["to"], "depart": t["depart"],
                        "pace": t.get("pace", 1.0), "kind": t.get("kind", ""), "seq": D.trip_decisions(t),
                        "end": D.trip_end(t)})
    return out


def load_trips(path, D):
    with open(path, encoding="utf-8") as f:
        return as_decisions(D, (json.loads(l) for l in f))


class Model:
    """Probabilities of each road out, given the intersection, the road in and (counted only) the hour."""

    def __init__(self, D, kind, kappa=KAPPA, counts=None, hourly=None):
        self.D, self.kind, self.kappa = D, kind, kappa
        self.counts, self.hourly = counts, hourly
        self.cache = {}

    def probs(self, c, ai, hour=None):
        key = (c, ai, hour if self.kind == "counted" else None)
        if key in self.cache:
            return self.cache[key]
        D = self.D
        if self.kind == "counted":
            cnt = self.hourly.get((c, ai, hour)) if hour is not None else None
            if not cnt or sum(cnt.values()) < HOUR_MIN:
                cnt = self.counts.get((c, ai))
            if cnt:
                tot = sum(cnt.values())
                res = [(a, n / tot) for a, n in sorted(cnt.items())]
            else:
                opts = D.options(c, ai)
                res = [(a, 1 / len(opts)) for a in opts]
        elif self.kind == "momentum":
            opts = D.options(c, ai)
            w = [math.exp(self.kappa * math.cos(math.radians(D.turn_angle(c, ai, a)))) for a in opts]
            res = [(a, x / sum(w)) for a, x in zip(opts, w)]
        else:  # equal
            opts = D.options(c, ai)
            res = [(a, 1 / len(opts)) for a in opts]
        self.cache[key] = res
        return res

    def choose(self, c, ai, t, rng):
        p = self.probs(c, ai, int(t // 3600) % 24)
        r, acc = rng.random(), 0.0
        for a, x in p:
            acc += x
            if r < acc:
                return a
        return p[-1][0]


def chain_walk(D, trips, model, seed, rho=0.0):
    """Markov-chain walkers: one per agent trip, starting at its first decision, same time, pace and number of
    decisions. Walkers move on one clock, so with rho > 0 one can copy the person just in front of them."""
    rng = random.Random(seed)
    follow_s = secs_for(FOLLOW_M)
    heap = [(t["seq"][0][3], g, t["seq"][0][0], t["seq"][0][1], 0) for g, t in enumerate(trips) if t["seq"]]
    heapq.heapify(heap)
    seqs = [[] for _ in trips]
    recent = defaultdict(deque)   # (intersection, road in) -> arrivals (time, road out), oldest first
    while heap:
        t, g, c, ai, k = heapq.heappop(heap)
        ao = None
        if rho > 0:
            q = recent[(c, ai)]
            while q and q[0][0] < t - follow_s:
                q.popleft()
            if q and rng.random() < rho:
                ao = q[-1][1]            # the person just in front of you
        if ao is None:
            ao = model.choose(c, ai, t, rng)
        if rho > 0:
            recent[(c, ai)].append((t, ao))
        seqs[g].append((c, ai, ao, t))
        if k + 1 < len(trips[g]["seq"]):
            nxt = D.step(c, ao)
            if nxt is not None:
                c2, a2, secs, _ = nxt
                heapq.heappush(heap, (t + (D.through_secs(c, ai, ao) + secs) / trips[g]["pace"], g, c2, a2, k + 1))
    return [{**t, "seq": s} for t, s in zip(trips, seqs)]


# ---------------- measures ----------------
def follow_scan(trips, follow_m=FOLLOW_M):
    """For each trip: (decisions, longest following run by one stranger, strangers with a run >= k, that
    stranger's trip)."""
    follow_s = secs_for(follow_m)
    idx = defaultdict(list)
    for g, t in enumerate(trips):
        for m, (c, ai, ao, tt) in enumerate(t["seq"]):
            idx[(c, ai, ao)].append((tt, g, m))
    for v in idx.values():
        v.sort()
    times = {k: [x[0] for x in v] for k, v in idx.items()}
    rows = []
    for i, t in enumerate(trips):
        me = t["agent"]
        prev, best, best_g = {}, {}, {}
        for c, ai, ao, tt in t["seq"]:
            key = (c, ai, ao)
            lst, ts = idx[key], times[key]
            cur = {}
            for _, g, mm in lst[bisect.bisect_right(ts, tt): bisect.bisect_right(ts, tt + follow_s)]:
                a = trips[g]["agent"]
                if a == me:
                    continue
                s = prev.get((g, mm - 1), 0) + 1
                cur[(g, mm)] = s
                if s > best.get(a, 0):
                    best[a], best_g[a] = s, g
            prev = cur
        top = max(best, key=best.get) if best else None
        rows.append({"n": len(t["seq"]), "max": best[top] if top else 0, "top": best_g[top] if top else None,
                     "ge": [sum(1 for v in best.values() if v >= k) for k in range(KMAX + 1)],
                     "hour": int(t["depart"] // 3600) % 24})
    return rows


def p_k(rows, k, need_k=False):
    rs = [r for r in rows if r["n"] >= k] if need_k else rows
    return sum(r["max"] >= k for r in rs) / len(rs) if rs else float("nan")


def s_k(rows, k):
    return sum(r["ge"][k] for r in rows) / len(rows) if rows else float("nan")


def q_scan(trips, kmax=6, follow_m=FOLLOW_M):
    """Pairs arriving at an intersection by the same road, one close behind the other: how many then make the
    same next k decisions (route only). Also, for each k, the starting state and hour of the pairs counted."""
    follow_s = secs_for(follow_m)
    idx = defaultdict(list)
    for g, t in enumerate(trips):
        for m, (c, ai, ao, tt) in enumerate(t["seq"]):
            idx[(c, ai)].append((tt, g, m))
    for v in idx.values():
        v.sort()
    times = {k: [x[0] for x in v] for k, v in idx.items()}
    pairs, same = [0] * (kmax + 1), [0] * (kmax + 1)
    states = [Counter() for _ in range(kmax + 1)]
    by_roads = defaultdict(lambda: [0, 0])          # number of roads -> [pairs, same next road]
    for i, t in enumerate(trips):
        seq = t["seq"]
        for m, (c, ai, ao, tt) in enumerate(seq):
            lst, ts = idx[(c, ai)], times[(c, ai)]
            for _, g, mm in lst[bisect.bisect_right(ts, tt): bisect.bisect_right(ts, tt + follow_s)]:
                if trips[g]["agent"] == t["agent"]:
                    continue
                other = trips[g]["seq"]
                rem = min(len(seq) - m, len(other) - mm, kmax)
                r = 0
                while r < rem and seq[m + r][:3] == other[mm + r][:3]:
                    r += 1
                hour = int(tt // 3600) % 24
                for k in range(1, rem + 1):
                    pairs[k] += 1
                    same[k] += r >= k
                    states[k][(c, ai, hour)] += 1
                br = by_roads[min(len(D_GLOBAL.arms[c]), 6)]
                br[0] += 1
                br[1] += ao == other[mm][2]
    return pairs, same, states, by_roads


def q_formula(D, model, kmax=6, hour=None):
    """q_k(s) for every state s = (intersection, road in) of a Markov chain (for the counted chain: that hour's
    table where it has enough passes)."""
    states = [(c, ai) for c in range(len(D.arms)) if D.is_decision[c] for ai in range(len(D.arms[c]))]
    nxt = {}
    for c, ai in states:
        for a, _ in model.probs(c, ai, hour):
            st = D.step(c, a)
            nxt[(c, a)] = (st[0], st[1]) if st else None
    q = [dict.fromkeys(states, 1.0)]
    for k in range(1, kmax + 1):
        cur = {}
        for c, ai in states:
            v = 0.0
            for a, p in model.probs(c, ai, hour):
                n = nxt[(c, a)]
                v += p * p * (q[k - 1].get(n, 0.0) if n else 0.0)
            cur[(c, ai)] = v
        q.append(cur)
    return q


D_GLOBAL = None


def chi_square(D, counts, models, min_passes=30):
    """Goodness of fit, per (intersection, road in), of the counts of each road out (turning back left out) to the
    equal-chance and momentum probabilities. Returns rows, and per model the share rejected at 5% after
    Benjamini-Hochberg correction and the median effect size w = sqrt(chi2 / n)."""
    rows = []
    for (c, ai), cnt in sorted(counts.items()):
        opts = [a for a in D.options(c, ai) if a != ai]
        obs = [cnt.get(a, 0) for a in opts]
        n = sum(obs)
        if n < min_passes or len(opts) < 2:
            continue
        row = {"c": c, "ai": ai, "n": n, "roads": len(D.arms[c])}
        for name in ("equal", "momentum"):
            p = dict(models[name].probs(c, ai))
            tot = sum(p[a] for a in opts)
            exp = [n * p[a] / tot for a in opts]
            chi2, pv = stats.chisquare(obs, exp)
            row[name] = (chi2, pv, math.sqrt(chi2 / n))
        rows.append(row)
    summary = {}
    for name in ("equal", "momentum"):
        if rows:
            adj = stats.false_discovery_control([r[name][1] for r in rows], method="bh")
            for r, a in zip(rows, adj):
                r[name] = r[name] + (a,)
            ws = sorted(r[name][2] for r in rows)
            summary[name] = (len(rows), sum(r[name][3] < 0.05 for r in rows) / len(rows), ws[len(ws) // 2])
    return rows, summary


# ---------------- report ----------------
def compass(angle):
    return ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"][round(math.degrees(angle) / 45) % 8]


def road_name(D, c, a):
    A = D.arms[c][a]
    return f"{_english(A['name']) or 'footpath'} ({compass(A['heading'])})"


def main():
    global D_GLOBAL
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="day1")
    ap.add_argument("--control", default="", help="a run of the same people without the LLM (e.g. mock_day1)")
    ap.add_argument("--seeds", type=int, default=SEEDS)
    args = ap.parse_args()

    world = World()
    D = D_GLOBAL = Decisions(world)
    run_dir = C.OUT / args.run
    out = run_dir / "analysis"
    out.mkdir(exist_ok=True)
    people = {}
    if (run_dir / "people.jsonl").exists():
        people = {a["id"]: a for a in (json.loads(l) for l in open(run_dir / "people.jsonl", encoding="utf-8"))}

    print("loading and converting trips", flush=True)
    raw = [json.loads(l) for l in open(run_dir / "trips.jsonl", encoding="utf-8")]
    raw = [t for t in raw if t["segments"]]
    agents = as_decisions(D, raw)
    rod = []
    for s in range(args.seeds):
        rod.append(as_decisions(D, random_trips(world, raw, 1 + s)))
    del raw
    control = load_trips(C.OUT / args.control / "trips.jsonl", D) if args.control else None

    counts, hourly = defaultdict(Counter), defaultdict(Counter)
    for t in agents:
        for c, ai, ao, tt in t["seq"]:
            counts[(c, ai)][ao] += 1
            hourly[(c, ai, int(tt // 3600) % 24)][ao] += 1
    models = {"equal": Model(D, "equal"), "momentum": Model(D, "momentum"),
              "counted": Model(D, "counted", counts=counts, hourly=hourly)}

    print("walking the Markov chains", flush=True)
    walkers = {"agents": [agents], "random_od": rod}
    if control:
        walkers["no_llm"] = [control]
    for name in ("equal", "momentum", "counted"):
        walkers[name] = [chain_walk(D, agents, models[name], 100 + s) for s in range(args.seeds)]
    walkers["imitate"] = [chain_walk(D, agents, models["counted"], 200 + s, rho=RHO) for s in range(args.seeds)]

    print("measuring following", flush=True)
    rows = {k: [follow_scan(ts) for ts in v] for k, v in walkers.items()}

    def mean_sd(name, f):
        v = [f(r) for r in rows[name]]
        m = sum(v) / len(v)
        sd = (sum((x - m) ** 2 for x in v) / (len(v) - 1)) ** 0.5 if len(v) > 1 else 0.0
        return m, sd

    label = {"agents": "Agent World", "no_llm": "Same people, no LLM", "random_od": "Random place to place",
             "equal": "Markov: equal chance", "momentum": f"Markov: momentum (kappa {KAPPA:g})",
             "counted": "Markov: counted", "imitate": f"Markov: counted + imitation (rho {RHO:g})"}
    names = [n for n in label if n in walkers]
    with open(out / "following_pk.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["k"] + [f"p_{n}" for n in names] + [f"p_{n}_sd" for n in names]
                   + [f"p_{n}_given_k_decisions" for n in names] + [f"s_{n}" for n in names])
        for k in range(1, KMAX + 1):
            w.writerow([k] + [round(mean_sd(n, lambda r: p_k(r, k))[0], 4) for n in names]
                       + [round(mean_sd(n, lambda r: p_k(r, k))[1], 4) for n in names]
                       + [round(mean_sd(n, lambda r: p_k(r, k, True))[0], 4) for n in names]
                       + [round(mean_sd(n, lambda r: s_k(r, k))[0], 3) for n in names])

    print("pairs and the Markov formula", flush=True)
    qmeas = {n: q_scan(walkers[n][0]) for n in ("agents", "equal", "momentum", "counted", "imitate", "random_od")}
    qform = {n: q_formula(D, models[n]) for n in ("equal", "momentum")}
    q_hourly = {h: q_formula(D, models["counted"], hour=h) for h in range(24)}

    def predicted(meas, model_name, k):
        st = meas[2][k]
        tot = sum(st.values())
        if not tot:
            return float("nan")
        if model_name == "counted":
            return sum(n * q_hourly[h][k].get((c, ai), 0.0) for (c, ai, h), n in st.items()) / tot
        return sum(n * qform[model_name][k].get((c, ai), 0.0) for (c, ai, h), n in st.items()) / tot

    with open(out / "following_qk.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["k", "pairs_agents", "agents_observed", "counted_formula_on_agent_pairs", "momentum_formula_on_agent_pairs",
                    "equal_formula_on_agent_pairs", "equal_observed", "equal_formula", "momentum_observed",
                    "momentum_formula", "counted_observed", "counted_formula", "imitate_observed", "random_od_observed"])
        for k in range(1, 7):
            obs = lambda n: qmeas[n][1][k] / qmeas[n][0][k] if qmeas[n][0][k] else float("nan")
            w.writerow([k, qmeas["agents"][0][k], round(obs("agents"), 4), round(predicted(qmeas["agents"], "counted", k), 4),
                        round(predicted(qmeas["agents"], "momentum", k), 4), round(predicted(qmeas["agents"], "equal", k), 4),
                        round(obs("equal"), 4), round(predicted(qmeas["equal"], "equal", k), 4),
                        round(obs("momentum"), 4), round(predicted(qmeas["momentum"], "momentum", k), 4),
                        round(obs("counted"), 4), round(predicted(qmeas["counted"], "counted", k), 4),
                        round(obs("imitate"), 4), round(obs("random_od"), 4)])

    # same next decision, by how many roads the intersection has
    with open(out / "following_by_roads.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["roads", "pairs_agents", "agents", "equal", "momentum", "counted", "imitate", "random_od"])
        for n_roads in (3, 4, 5, 6):
            cells = []
            for n in ("agents", "equal", "momentum", "counted", "imitate", "random_od"):
                p, s = qmeas[n][3].get(n_roads, [0, 0])
                cells.append(round(s / p, 4) if p else "")
            w.writerow([n_roads if n_roads < 6 else "6+", qmeas["agents"][3].get(n_roads, [0, 0])[0]] + cells)

    # by hour of day
    hours = sorted({r["hour"] for r in rows["agents"][0]})
    with open(out / "following_by_hour.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hour", "trips"] + [f"p3_{n}" for n in names])
        for h in hours:
            line = [f"{h:02d}:00", sum(r["hour"] == h for r in rows["agents"][0])]
            for n in names:
                line.append(round(mean_sd(n, lambda r: p_k([x for x in r if x["hour"] == h], 3))[0], 4))
            w.writerow(line)

    # chi-square: Agent World counts, and the equal-chance walkers' own counts as a calibration
    chi_rows, chi = chi_square(D, counts, models)
    eq_counts = defaultdict(Counter)
    for t in walkers["equal"][0]:
        for c, ai, ao, tt in t["seq"]:
            eq_counts[(c, ai)][ao] += 1
    _, chi_cal = chi_square(D, eq_counts, models)
    with open(out / "following_chi2.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["intersection", "road_in", "roads", "passes", "chi2_equal", "p_equal", "p_equal_bh", "w_equal",
                    "chi2_momentum", "p_momentum", "p_momentum_bh", "w_momentum"])
        for r in chi_rows:
            w.writerow([r["c"], road_name(D, r["c"], r["ai"]), r["roads"], r["n"]]
                       + [round(r["equal"][0], 2), f"{r['equal'][1]:.3g}", f"{r['equal'][3]:.3g}", round(r["equal"][2], 3)]
                       + [round(r["momentum"][0], 2), f"{r['momentum'][1]:.3g}", f"{r['momentum'][3]:.3g}", round(r["momentum"][2], 3)])

    # sweeps: momentum strength, imitation, following distance
    sweep = []
    for kappa in (0.5, 1.0, 2.0, 4.0):
        m = Model(D, "momentum", kappa=kappa)
        r = follow_scan(chain_walk(D, agents, m, 300))
        q = q_formula(D, m)
        st = qmeas["agents"][2][3]
        tot = sum(st.values())
        sweep.append(("momentum, kappa", kappa, p_k(r, 3), p_k(r, 5), sum(n * q[3].get((c, ai), 0) for (c, ai, h), n in st.items()) / tot))
    for rho in (0.0, 0.1, 0.3, 0.5):
        r = follow_scan(chain_walk(D, agents, models["counted"], 400, rho=rho))
        sweep.append(("imitation, rho", rho, p_k(r, 3), p_k(r, 5), None))
    for fm in (15, 30, 60):
        for n in ("agents", "counted"):
            r = follow_scan(walkers[n][0], follow_m=fm)
            sweep.append((f"following distance, {label[n]}", fm, p_k(r, 3), p_k(r, 5), None))
    with open(out / "following_sweeps.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["what", "value", "p3", "p5", "q3_formula_on_agent_pairs"])
        for row in sweep:
            w.writerow([row[0], row[1], round(row[2], 4), round(row[3], 4), "" if row[4] is None else round(row[4], 4)])

    # who follows whom in the Agent World
    ag, ar = agents, rows["agents"][0]
    hits = [(ag[i], ag[r["top"]]) for i, r in enumerate(ar) if r["max"] >= 3]
    def near(a, b):
        return math.dist(world.places[a]["xy"], world.places[b]["xy"]) <= SAME_PLACE_M
    same_od = sum(near(a["from"], b["from"]) and near(a["to"], b["to"]) for a, b in hits)
    same_o = sum(near(a["from"], b["from"]) for a, b in hits)
    same_d = sum(near(a["to"], b["to"]) for a, b in hits)
    same_group = sum(group_of(people[a["agent"]]) == group_of(people[b["agent"]]) for a, b in hits) if people else 0

    # the project plan's table: shares of each road out, per intersection and road in
    with open(out / "decision_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["intersection", "lat", "lon", "roads", "road_in", "road_out", "turn", "passes", "share_%",
                    "equal_%", "momentum_%"])
        stops = Counter(t["end"] for t in agents if t["end"])
        for (c, ai), cnt in sorted(counts.items(), key=lambda kv: -sum(kv[1].values())):
            tot = sum(cnt.values()) + stops[(c, ai)]
            if tot < 20:
                continue
            ms = D.members[c]
            lat = sum(world.nodes[n]["lat"] for n in ms) / len(ms)
            lon = sum(world.nodes[n]["lon"] for n in ms) / len(ms)
            eq = dict(models["equal"].probs(c, ai))
            mo = dict(models["momentum"].probs(c, ai))
            for ao in range(len(D.arms[c])):
                w.writerow([c, round(lat, 6), round(lon, 6), len(D.arms[c]), road_name(D, c, ai), road_name(D, c, ao),
                            D.label(c, ai, ao), tot, round(100 * cnt[ao] / tot, 1), round(100 * eq.get(ao, 0), 1),
                            round(100 * mo.get(ao, 0), 1)])
            w.writerow([c, round(lat, 6), round(lon, 6), len(D.arms[c]), road_name(D, c, ai), "stops here", "S", tot,
                        round(100 * stops[(c, ai)] / tot, 1), "", ""])

    # ---------------- summary ----------------
    def pct(x):
        return f"{100 * x:.1f}%"

    L = [f"# Following at real intersections: {args.run}", "",
         f"{len(agents):,} trips, {sum(len(t['seq']) for t in agents):,} decisions at {sum(D.is_decision)} decision points. "
         f"A stranger is following you for k decisions if the same person, at most {FOLLOW_M} m behind you each time "
         f"(about {secs_for(FOLLOW_M):.0f} s), arrives at and leaves k of your intersections in a row by your roads. "
         f"Chain walkers and random trips: {args.seeds} repeats, mean (± standard deviation).", "",
         "## Chance that a stranger follows you through k intersections", "",
         "| k | " + " | ".join(label[n] for n in names) + " |", "|---|" + "---|" * len(names)]
    for k in range(1, 7):
        cells = []
        for n in names:
            m, sd = mean_sd(n, lambda r: p_k(r, k))
            cells.append(pct(m) + (f" ± {100 * sd:.1f}" if len(rows[n]) > 1 else ""))
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L += ["", "Among trips that make at least k decisions:", "",
          "| k | " + " | ".join(label[n] for n in names) + " |", "|---|" + "---|" * len(names)]
    for k in (3, 5):
        L.append(f"| {k} | " + " | ".join(pct(mean_sd(n, lambda r: p_k(r, k, True))[0]) for n in names) + " |")
    L += ["", "## Two people arriving together: same next k decisions", "",
          f"Pairs who arrive at an intersection by the same road, one at most {FOLLOW_M} m behind the other. "
          "The formula is the Markov chain's prediction for the same pairs (the counted chain uses the table of the hour "
          "they arrive in); for the chain walkers it checks the code.", "",
          "| k | Agent World | Counted chain, formula | Momentum, formula | Equal chance, formula | Equal: walkers / formula | Momentum: walkers / formula | Counted: walkers / formula | Imitation: walkers |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k in range(1, 6):
        o = lambda n: qmeas[n][1][k] / qmeas[n][0][k] if qmeas[n][0][k] else float("nan")
        L.append(f"| {k} | {pct(o('agents'))} | {pct(predicted(qmeas['agents'], 'counted', k))} | "
                 f"{pct(predicted(qmeas['agents'], 'momentum', k))} | {pct(predicted(qmeas['agents'], 'equal', k))} | "
                 f"{pct(o('equal'))} / {pct(predicted(qmeas['equal'], 'equal', k))} | "
                 f"{pct(o('momentum'))} / {pct(predicted(qmeas['momentum'], 'momentum', k))} | "
                 f"{pct(o('counted'))} / {pct(predicted(qmeas['counted'], 'counted', k))} | {pct(o('imitate'))} |")
    L += ["", f"Agent pairs counted at k = 1: {qmeas['agents'][0][1]:,}.", "",
          "## Same next road, by how many roads the intersection has", "",
          "| Roads | Agent pairs | Agent World | Equal chance | Momentum | Counted | Imitation | Random place to place |",
          "|---|---|---|---|---|---|---|---|"]
    with open(out / "following_by_roads.csv") as f:
        for r in csv.DictReader(f):
            L.append(f"| {r['roads']} | {int(r['pairs_agents']):,} | " + " | ".join(
                pct(float(r[n])) if r[n] else "" for n in ("agents", "equal", "momentum", "counted", "imitate", "random_od")) + " |")
    L += ["", "## Is the choice at each intersection equal chance? (chi-square)", "",
          "Goodness of fit of the Agent World's counts of each road out, at each intersection and road in with at least 30 "
          "passes (turning back left out), to equal chance and to momentum. p-values corrected over all of them "
          "(Benjamini-Hochberg). Calibration: the same test on the equal-chance walkers' counts, which do follow equal chance, so after the correction it should reject almost none.", "",
          "| Counts tested against | Intersection and road-in pairs | Rejected at 5% | Median effect size w | Calibration: rejected |",
          "|---|---|---|---|---|"]
    for name, lab in (("equal", "Equal chance"), ("momentum", f"Momentum (kappa {KAPPA:g})")):
        n_t, rej, med = chi[name]
        L.append(f"| {lab} | {n_t:,} | {pct(rej)} | {med:.2f} | " + (pct(chi_cal["equal"][1]) if name == "equal" else "") + " |")
    L += ["", "w = sqrt(chi-square / passes): about 0.1 is a small difference, 0.3 medium, 0.5 large. Passes by the same "
          "person on different trips are not independent, so p-values are too small; the effect size does not have that problem."]
    L += ["", "## Sweeps", "", "| What | Value | P_3 | P_5 | q_3 formula on agent pairs |", "|---|---|---|---|---|"]
    for row in sweep:
        L.append(f"| {row[0]} | {row[1]:g} | {pct(row[2])} | {pct(row[3])} | {'' if row[4] is None else pct(row[4])} |")
    L += ["", "## Who follows whom in the Agent World", "",
          f"Of {len(hits):,} trips with a stranger following for 3+ intersections, the stranger started within "
          f"{SAME_PLACE_M} m of where you started on {pct(same_o / len(hits))}, was going to within {SAME_PLACE_M} m of "
          f"your destination on {pct(same_d / len(hits))}, both on {pct(same_od / len(hits))}"
          + (f", and was in your group on {pct(same_group / len(hits))}" if people else "") + ".", "",
          "Tables: following_pk.csv, following_qk.csv, following_by_roads.csv, following_by_hour.csv, following_sweeps.csv, following_chi2.csv, "
          "decision_table.csv (shares of each road out per intersection and road in, with equal-chance and momentum "
          "probabilities, and the share that stop there)."]
    (out / "following.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
