"""Measure coincidental "following" in a finished run.

For every trip ("you"), find the stranger who made the most of the same turns as you in a row: same
segments, same direction, each entered within SHARED_WINDOW seconds of you. Then compare with a
baseline where the very same trips (same start, end and departure time) are walked with near-random
turns instead of the quickest path.

    python analyze.py --run pilot
    python analyze.py --run pilot --beta 0.01      # how random the baseline turns are (smaller = more random)

Writes out/<run>/analysis/: summary.md, shared_turns.csv, by_hour.csv, turns_by_junction.csv, segment_usage.csv
"""
import argparse
import bisect
import csv
import json
import random
from collections import Counter, defaultdict

import config as C
from groups import GROUPS, LABELS, TURNS, add_dirs, group_of, road_tables
from world import World

KMAX = 10
SHARE_K = 5  # "following" streak length used for the group tables


def index_trips(trips):
    idx = defaultdict(list)
    for g, tr in enumerate(trips):
        for s, seg in enumerate(tr["segments"]):
            idx[(seg["edge"], seg["from"])].append((seg["t"], g, s))
    for v in idx.values():
        v.sort()
    times = {k: [x[0] for x in v] for k, v in idx.items()}
    return idx, times


def shared_runs(trips, decision, sample=None, seed=0):
    """For each 'you' trip: the most consecutive shared turns with any one stranger, and how many
    strangers shared at least k turns."""
    idx, times = index_trips(trips)
    order = list(range(len(trips)))
    if sample and sample < len(order):
        order = random.Random(seed).sample(order, sample)
    W = C.SHARED_WINDOW
    out = []
    for g in order:
        you = trips[g]
        prev, best = {}, {}
        for s, seg in enumerate(you["segments"]):
            key = (seg["edge"], seg["from"])
            lst, ts = idx.get(key, []), times.get(key, [])
            lo, hi = bisect.bisect_left(ts, seg["t"] - W), bisect.bisect_right(ts, seg["t"] + W)
            cur = {}
            for _, og, os_ in lst[lo:hi]:
                other = trips[og]
                if other["agent"] == you["agent"]:
                    continue
                p = prev.get((og, os_ - 1))
                # a shared turn is a decision junction both of you passed through together, same way in and out
                turns = (p[1] + (1 if decision[seg["from"]] else 0)) if p else 0
                cur[(og, os_)] = (1, turns)
                if turns > best.get(other["agent"], -1):
                    best[other["agent"]] = turns
            prev = cur
        mx = max(best.values(), default=-1)
        top = max(best, key=best.get) if best else None
        out.append({"trip": g, "agent": you["agent"], "hour": you["depart"] // 3600, "turns_in_trip": len(you["turns"]),
                    "max_shared_turns": max(mx, 0), "met_anyone": bool(best), "top_stranger": top,
                    "strangers_ge": [sum(1 for v in best.values() if v >= k) for k in range(KMAX + 1)]})
    return out


def rewalk(trips, world, beta, seed):
    rng = random.Random(seed)
    new = []
    for tr in trips:
        a, b = world.places[tr["from"]]["node"], world.places[tr["to"]]["node"]
        w = world.walk(a, b, tr["depart"], policy="noisy", beta=beta, rng=rng, pace=tr.get("pace", 1.0))
        new.append({**tr, "segments": w["segments"], "turns": w["turns"], "arrive": w["arrive"]})
    return new


def p_at_least(rows, k):
    return sum(r["max_shared_turns"] >= k for r in rows) / len(rows) if rows else 0.0


def load_groups(run_dir):
    group = {}
    for p in (run_dir / "agents").glob("A*.json"):
        a = json.loads(p.read_text(encoding="utf-8"))["agent"]
        group[a["id"]] = group_of(a)
    return group


def group_tables(run_dir, out, world, trips, model, decision):
    """groups.csv, share_matrix.csv, road_usage.csv and road_decisions.csv."""
    group = load_groups(run_dir)
    degree = [len(a) for a in world.adj]
    add_dirs(trips, world.edges)
    usage, turns = road_tables(trips, group, degree)

    people = Counter(group.values())
    by_g = defaultdict(list)
    for tr in trips:
        by_g[group[tr["agent"]]].append(tr)
    rows_by_g = defaultdict(list)
    for r in model:
        rows_by_g[group[r["agent"]]].append(r)
    edge_g = defaultdict(Counter)  # group -> edge -> walkers
    for (g, h), c in usage.items():
        edge_g[g].update(c)

    def road_name(e):
        return world.edges[e]["name"] or f"path #{e}"

    with open(out / "groups.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "label", "people", "trips", "trips_per_person", "walk_min_per_person", "turns_per_trip",
                    "left_%", "right_%", "straight_%", "back_%", "p_shares_3", f"p_shares_{SHARE_K}", "busiest_road"])
        for g in GROUPS:
            trs, n = by_g[g], people[g]
            if not n:
                continue
            tc = Counter(x["turn"] for tr in trs for x in tr["turns"])
            tt = sum(tc.values()) or 1
            walk = sum(tr["arrive"] - tr["depart"] for tr in trs) / 60
            top = edge_g[g].most_common(1)
            w.writerow([g, LABELS[g], n, len(trs), round(len(trs) / n, 2), round(walk / n, 1),
                        round(sum(len(tr["turns"]) for tr in trs) / max(1, len(trs)), 1)]
                       + [round(100 * tc[d] / tt, 1) for d in TURNS]
                       + [round(p_at_least(rows_by_g[g], 3), 4), round(p_at_least(rows_by_g[g], SHARE_K), 4),
                          road_name(top[0][0]) if top else ""])

    # Who makes your turns: for trips with a stranger sharing SHARE_K+ turns, which group was that stranger in?
    mat = defaultdict(Counter)
    for r in model:
        if r["max_shared_turns"] >= SHARE_K and r["top_stranger"]:
            mat[group[r["agent"]]][group[r["top_stranger"]]] += 1
    with open(out / "share_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["you"] + GROUPS + ["trips"])
        for g in GROUPS:
            tot = sum(mat[g].values())
            if tot:
                w.writerow([g] + [round(mat[g][h] / tot, 4) for h in GROUPS] + [tot])

    total = Counter()
    for c in edge_g.values():
        total.update(c)
    hours = defaultdict(Counter)
    for (g, h), c in usage.items():
        for e, n in c.items():
            hours[e][h] += n
    with open(out / "road_usage.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["segment", "name", "walkers"] + GROUPS + ["peak_hour", "metres", "steps_m", "lift"])
        for e, n in total.most_common():
            E = world.edges[e]
            w.writerow([e, E["name"], n] + [edge_g[g][e] for g in GROUPS]
                       + [f"{hours[e].most_common(1)[0][0]:02d}:00", E["len"], E["steps"], E["lift"]])

    with open(out / "road_decisions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["segment", "name", "from_junction", "to_junction", "group", "people", "left_%", "right_%", "straight_%", "back_%"])
        for (code, g), c in sorted(turns.items(), key=lambda kv: -sum(kv[1].values())):
            n = sum(c.values())
            if n < 5:
                continue
            e = code // 2
            a, b = (world.edges[e]["u"], world.edges[e]["v"]) if code % 2 == 0 else (world.edges[e]["v"], world.edges[e]["u"])
            w.writerow([e, world.edges[e]["name"], a, b, g, n] + [round(100 * c[d] / n, 1) for d in TURNS])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="pilot")
    ap.add_argument("--beta", type=float, default=0.01, help="baseline randomness; smaller is more random")
    ap.add_argument("--sample", type=int, default=0, help="score only this many random trips as 'you' (faster); 0 = every trip")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    world = World()
    run_dir = C.OUT / args.run
    trips = [json.loads(l) for l in open(run_dir / "trips.jsonl", encoding="utf-8")]
    trips = [t for t in trips if t["segments"]]
    decision = [len(a) >= 3 for a in world.adj]
    agents = len({t["agent"] for t in trips})
    print(f"{len(trips)} trips by {agents} agents")

    model = shared_runs(trips, decision, args.sample, args.seed)
    base_trips = rewalk(trips, world, args.beta, args.seed)
    base = shared_runs(base_trips, decision, args.sample, args.seed)

    out = run_dir / "analysis"
    out.mkdir(exist_ok=True)
    with open(out / "shared_turns.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["k_turns_in_a_row", "p_someone_shares_k_quickest", "p_someone_shares_k_random_turns",
                    "avg_strangers_sharing_k_quickest", "avg_strangers_sharing_k_random_turns"])
        for k in range(1, KMAX + 1):
            w.writerow([k, round(p_at_least(model, k), 4), round(p_at_least(base, k), 4),
                        round(sum(r["strangers_ge"][k] for r in model) / len(model), 3),
                        round(sum(r["strangers_ge"][k] for r in base) / len(base), 3)])
    by_hour = defaultdict(list)
    for r in model:
        by_hour[r["hour"]].append(r)
    with open(out / "by_hour.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hour", "trips", "p_shares_3", "p_shares_5"])
        for h in sorted(by_hour):
            w.writerow([f"{h:02d}:00", len(by_hour[h]), round(p_at_least(by_hour[h], 3), 4), round(p_at_least(by_hour[h], 5), 4)])

    # The Plan's turn-probability table: how people turn at each junction
    jt = defaultdict(Counter)
    for tr in trips:
        for x in tr["turns"]:
            jt[x["node"]][x["turn"]] += 1
    with open(out / "turns_by_junction.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["junction", "lat", "lon", "passes", "left_%", "right_%", "straight_%", "back_%"])
        for n, c in sorted(jt.items(), key=lambda kv: -sum(kv[1].values()))[:200]:
            tot = sum(c.values())
            w.writerow([n, world.nodes[n]["lat"], world.nodes[n]["lon"], tot] + [round(100 * c[d] / tot, 1) for d in "LRSB"])
    use = Counter(s["edge"] for tr in trips for s in tr["segments"])
    with open(out / "segment_usage.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["segment", "name", "walkers", "metres", "steps_m", "lift", "lat", "lon"])
        for e, n in use.most_common():
            E = world.edges[e]
            mid = E["geom"][len(E["geom"]) // 2]
            w.writerow([e, E["name"], n, E["len"], E["steps"], E["lift"], mid[0], mid[1]])

    group_tables(run_dir, out, world, trips, model, decision)

    total = Counter(x["turn"] for tr in trips for x in tr["turns"])
    tt = sum(total.values()) or 1
    lines = [f"# Same-route analysis: {args.run}", "",
             f"{len(trips)} trips by {agents} agents; {len(model)} trips used as 'you'. "
             f"A stranger shares a turn with you when you both pass the same junction the same way in and out, "
             f"each within {C.SHARED_WINDOW} s of the other.", "",
             "| Same turns in a row (k) | Quickest path (this run) | Random turns (baseline) |", "|---|---|---|"]
    for k in (1, 2, 3, 4, 5, 6, 8, 10):
        lines.append(f"| {k} | {p_at_least(model, k):.1%} | {p_at_least(base, k):.1%} |")
    lines += ["", f"All turns recorded: left {total['L'] / tt:.0%}, right {total['R'] / tt:.0%}, "
              f"straight {total['S'] / tt:.0%}, back {total['B'] / tt:.0%}.",
              f"Baseline: the same {len(trips)} trips re-walked with softmax turns (beta={args.beta} per second of detour).", "",
              "Busiest segments are in segment_usage.csv; per-junction turn shares are in turns_by_junction.csv.", "",
              "## By group", "",
              f"| Group | People | Trips each | Walking min each | Left | Right | Straight | Stranger shares {SHARE_K}+ turns |",
              "|---|---|---|---|---|---|---|---|"]
    with open(out / "groups.csv", encoding="utf-8") as f:
        for g in csv.DictReader(f):
            lines.append(f"| {g['label']} | {g['people']} | {g['trips_per_person']} | {g['walk_min_per_person']} | "
                         f"{g['left_%']}% | {g['right_%']}% | {g['straight_%']}% | {float(g[f'p_shares_{SHARE_K}']):.0%} |")
    lines += ["", "Per road: road_usage.csv (walkers by group, peak hour) and road_decisions.csv (what each group "
              "did at the end of each road, by direction). Who shares your turns: share_matrix.csv."]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
