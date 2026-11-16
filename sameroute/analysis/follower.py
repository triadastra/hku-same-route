"""The deliberate follower: what the following measure reads when someone follows on purpose.

SUPERSEDED for results by sameroute/analysis/follower_rl.py (method.md, section 6b). This walker takes a new target when it loses
one and keeps its own trip's destination, both of which the authors ruled out. It is kept because sameroute/analysis/follower_rl.py
uses the measure defined here (Leaders, trail_scan, t_k, interval).

Every other walker in the study follows nobody on purpose. This one does, by a fixed rule with no personality,
so it marks the top of the scale: the Agent World shows how much following happens by coincidence, and the
deliberate follower shows how much happens when it is intended, on the same streets, among the same people.

The world
  The Agent World run is replayed unchanged. Its people (the leaders) walk exactly as they did. Followers are
  added one at a time: they see the leaders, the leaders do not see them, and followers do not see each other.
  So a follower can only follow a real person living their day, never another follower.

One follower per Agent World trip
  It starts at that trip's first junction, by the same road, at the same time and pace, and it keeps that trip's
  destination. At each junction it scores every road out (never the road it came by, unless at a dead end) and
  takes the best:

      score(road) = R * [road is the one its target took, and the target is in view] - 0.5 * x(road)^2

  Penalty. The follower remembers d_min, the shortest walking distance to its destination over every junction
      it has passed. If a road would leave it at distance d, then x = max(0, d - d_min) / L. A road that brings
      it closer costs nothing; a little farther costs almost nothing, so a road that has to go round is
      accepted; walking away is punished more and more.
  Reward. R for taking the road its target took, only while the target is in view: the target came to this
      junction by the follower's own road at most V seconds before it. The map has no buildings, so a true
      line of sight cannot be computed; "same road, at most V seconds in front" stands in for it.
  Target. The person nearest in front who is in view (never the follower's own person). The follower keeps its
      target from junction to junction while it stays in view, and takes a new one when it is lost.
  Together: the follower takes its target's road until that would leave it more than L * sqrt(2R) beyond the
      closest it has been to its destination. With no target, or R = 0, it takes the quickest road (of two
      equally quick roads, the one its own trip took), so with R = 0 it repeats its trip.
  Pace. It walks at its trip's pace, never overtakes its target (it reaches the next junction at least 1 s
      after them) and does not speed up to keep one.
  End. It stops when it takes the road its destination is on, or after three times its trip's number of
      junctions (counted and reported as "did not arrive").
  Nothing is trained and nothing is drawn by chance, so one run is the whole result.

The measure
  T_k: the share of walkers who trail the same stranger through k junctions in a row. At each of those
  junctions the stranger arrives and leaves by the walker's roads, and the walker is at most FOLLOW_M metres
  behind along the road when the stranger reaches it. This is the study's following rule (sameroute/analysis/following.py), seen
  from the person behind. It is computed for the Agent World people themselves (coincidence) and for the
  followers (intent), against the same leaders. Intervals are 95% bootstrap intervals that resample people,
  not trips, because one person's trips are not independent.

    python -m sameroute analyse follower --run census_run
    python -m sameroute analyse follower --run census_run --people-from live_census   # only the people of another run
    python -m sameroute analyse follower --run census_run --limit 2000                # a quick look at the first 2,000 trips
    python -m sameroute analyse follower --check                                      # test the code; needs no run and no API key

Writes runs/<run>/analysis/follower.md, follower_tk.csv and follower_sweep.csv, and graphs/follower-trailing.pdf.
"""
import argparse
import bisect
import csv
import json
import math
import time
from collections import defaultdict

import numpy as np

from sameroute import config as C
from sameroute.world.decisions import Decisions
from sameroute.analysis.following import FOLLOW_M, KMAX, MAX_GAP_S, as_decisions, walked_by
from sameroute.world.world import World

REWARD = 1.0                       # R: reward for taking the road the target took
SCALE_M = 100.0                    # L: the unit of x in the penalty 0.5 * x^2, metres
VIEW_S = 30.0                      # V: the target must have passed at most this many seconds before
REWARDS = (0.0, 0.25, 1.0, 4.0, 16.0)   # the sweep: with L = 100 m, up to 0, 71, 141, 283 and 566 m off course
CAP_FACTOR, CAP_EXTRA = 3, 10      # a follower gives up after CAP_FACTOR * (its trip's junctions) + CAP_EXTRA
BOOT = 500                         # bootstrap resamples of people
BOOT_SEED = 7


def tolerance_m(reward, scale_m=SCALE_M):
    """How far beyond its closest point a follower will go for its target."""
    return scale_m * math.sqrt(2 * reward)


class Leaders:
    """The Agent World trips, indexed by junction and road in, to answer: who came this way just before me?"""

    def __init__(self, trips):
        self.trips = trips
        by_state = defaultdict(list)
        for g, t in enumerate(trips):
            for m, (c, ai, ao, tt) in enumerate(t["seq"]):
                by_state[(c, ai)].append((tt, ao, g, m))
        self.arrivals = {k: sorted(v) for k, v in by_state.items()}
        self.times = {k: [x[0] for x in v] for k, v in self.arrivals.items()}

    def in_view(self, c, ai, t, view_s, me):
        """People who came to junction c by road ai in the last view_s seconds, nearest in front first."""
        lst = self.arrivals.get((c, ai))
        if not lst:
            return []
        ts = self.times[(c, ai)]
        seen = lst[bisect.bisect_left(ts, t - view_s): bisect.bisect_right(ts, t)]
        return [x for x in reversed(seen) if self.trips[x[2]]["agent"] != me]


def follow(D, leaders, trip, reward=REWARD, view_s=VIEW_S, scale_m=SCALE_M):
    """Walk one follower, paired with one Agent World trip. Returns the walk in the form the measures use, with
    how many of its decisions followed a target and whether it arrived."""
    w = D.w
    speed = C.WALK_SPEED

    def node_at(c, arm):                      # the map node where a road meets its junction
        return D.arms[c][arm]["main"]["node"]

    night = trip["depart"] >= 19 * 3600 or trip["depart"] < 6.5 * 3600   # the Agent World's rule for unlit paths
    secs_to_dest = w.times_from(w.places[trip["to"]]["node"], night)     # walking time at the map's speed

    def dist(c, arm):                         # walking distance to the destination, in flat metres
        return secs_to_dest[node_at(c, arm)] * speed

    def via(c, arm):                          # walking time to the destination if it sets off along this road
        br = D.arms[c][arm]["main"]
        e = w.edges[br["edge"]]
        return w.seg_cost(br["edge"], night) + secs_to_dest[e["v"] if e["u"] == br["node"] else e["u"]]

    seq0 = trip["seq"]
    own = {(c, ai): ao for c, ai, ao, _ in seq0}             # the road its trip took, to settle exact ties
    c, ai, _, t = seq0[0]
    cap = CAP_FACTOR * len(seq0) + CAP_EXTRA
    metres = walked_by(trip, t)               # the follower shares its trip's walk up to the first junction
    first = bisect.bisect_left(trip["tt"], t)
    tt, dd = list(trip["tt"][:first]), list(trip["dd"][:first])
    seq, target, d_min, followed, arrived, left = [], None, math.inf, 0, False, 0.0
    while True:
        tt.append(t)
        dd.append(metres)
        here = dist(c, ai)
        d_min = min(d_min, here)
        if here <= 1e-6:                      # the destination is this junction
            arrived = True
            break
        lead = None
        if reward > 0:
            seen = leaders.in_view(c, ai, t, view_s, trip["agent"])
            lead = next((x for x in seen if x[2] == target), seen[0] if seen else None)
        best = None
        for ao in D.options(c, ai):
            nxt = D.step(c, ao)
            if nxt is None:
                continue
            leg = D.through_secs(c, ai, ao) + nxt[2]
            ends_here = via(c, ao) < leg - 1e-6          # the destination is on this road, before the next junction
            after = 0.0 if ends_here else dist(nxt[0], nxt[1])
            x = max(0.0, after - d_min) / scale_m
            with_target = lead is not None and ao == lead[1]
            score = (reward if with_target else 0.0) - 0.5 * x * x
            # ties: the target's road first, then the quicker way to the destination, then the road its own trip
            # took (pairs of sidewalks are often exactly as quick), then the lower road number
            key = (-score, not with_target, round(via(c, ao), 3), ao != own.get((c, ai)), ao)
            if best is None or key < best[0]:
                best = (key, ao, nxt, with_target, ends_here)
        if best is None:                      # a junction with no way on: cannot happen on a connected map
            break
        _, ao, (c2, a2, secs, m), with_target, ends_here = best
        target = lead[2] if with_target else None
        followed += with_target
        seq.append((c, ai, ao, t))
        left = via(c, ao) * speed             # flat metres still to walk if it went straight there from here
        if ends_here:
            arrived = True
            break
        if len(seq) >= cap:
            break
        cross = D.through_secs(c, ai, ao)
        t2 = t + (cross + secs) / trip["pace"]
        if with_target:                       # never overtake the target
            ls, lm = leaders.trips[lead[2]]["seq"], lead[3]
            if lm + 1 < len(ls) and ls[lm + 1][0] == c2 and ls[lm + 1][1] == a2:
                t2 = max(t2, ls[lm + 1][3] + 1.0)
        metres += m + cross * speed
        left = 0.0
        c, ai, t = c2, a2, t2
    return {**trip, "seq": seq, "tt": tt, "dd": dd, "followed": followed, "arrived": arrived,
            "metres_from_first_junction": dd[-1] - dd[first] + left}


def trail_scan(walkers, leaders, follow_m=FOLLOW_M):
    """For each walker: its number of decisions, and the longest run of junctions in a row at which it was close
    behind the same stranger among the leaders, arriving and leaving by the same roads."""
    idx = defaultdict(list)
    for g, t in enumerate(leaders.trips):
        for m, (c, ai, ao, tt) in enumerate(t["seq"]):
            idx[(c, ai, ao)].append((tt, g, m))
    for v in idx.values():
        v.sort()
    times = {k: [x[0] for x in v] for k, v in idx.items()}
    rows = []
    for wk in walkers:
        me, prev, best = wk["agent"], {}, 0
        for c, ai, ao, t_me in wk["seq"]:
            key = (c, ai, ao)
            cur = {}
            if key in idx:
                lst, ts = idx[key], times[key]
                for t_lead, g, m in lst[bisect.bisect_left(ts, t_me - MAX_GAP_S): bisect.bisect_right(ts, t_me)]:
                    if leaders.trips[g]["agent"] == me:
                        continue
                    was = walked_by(wk, t_lead)              # where the walker was when the stranger got here
                    if was is None or walked_by(wk, t_me) - was > follow_m:
                        continue
                    run = prev.get((g, m - 1), 0) + 1
                    cur[(g, m)] = run
                    best = max(best, run)
            prev = cur
        rows.append({"agent": me, "n": len(wk["seq"]), "max": best})
    return rows


def t_k(rows, k, need_k=False):
    rs = [r for r in rows if r["n"] >= k] if need_k else rows
    return sum(r["max"] >= k for r in rs) / len(rs) if rs else float("nan")


def interval(rows, k, boot=BOOT, seed=BOOT_SEED):
    """95% bootstrap interval of T_k, resampling people (all of a person's trips together)."""
    people = sorted({r["agent"] for r in rows})
    at = {a: i for i, a in enumerate(people)}
    n, hit = np.zeros(len(people)), np.zeros(len(people))
    for r in rows:
        n[at[r["agent"]]] += 1
        hit[at[r["agent"]]] += r["max"] >= k
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(people), size=(boot, len(people)))
    share = hit[draws].sum(axis=1) / n[draws].sum(axis=1)
    return float(np.percentile(share, 2.5)), float(np.percentile(share, 97.5))


def describe(walks, agents):
    """How the followers walked, against the trips they were paired with."""
    dec = sum(len(x["seq"]) for x in walks)
    base_m = sum(a["dd"][-1] - a["dd"][bisect.bisect_left(a["tt"], a["seq"][0][3])] for a in agents)
    return {"decisions": dec,
            "followed_share": sum(x["followed"] for x in walks) / dec,
            "trips_that_followed": sum(x["followed"] > 0 for x in walks) / len(walks),
            "arrived": sum(x["arrived"] for x in walks) / len(walks),
            "same_route": sum([s[:3] for s in x["seq"]] == [s[:3] for s in a["seq"]] for x, a in zip(walks, agents)) / len(walks),
            "extra_metres": (sum(x["metres_from_first_junction"] for x in walks) - base_m) / len(walks)}


def figure(tk_rows, sweep, run):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sameroute.figures.amenity import save
    from sameroute.figures.following import BLUE, GRID, MUTED, PURPLE

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.7))
    k = [r["k"] for r in tk_rows]
    for key, lab, col, mk in (("agents", "Agent World (coincidence)", BLUE, "o"),
                              ("follower", "Deliberate follower", PURPLE, "v")):
        a.fill_between(k, [100 * r[f"{key}_lo"] for r in tk_rows], [100 * r[f"{key}_hi"] for r in tk_rows],
                       color=col, alpha=0.18, lw=0)
        a.plot(k, [100 * r[key] for r in tk_rows], color=col, lw=1.6, marker=mk, ms=4, mec="white", mew=0.7, label=lab)
    a.set_xlabel("Junctions in a row, $k$")
    a.set_ylabel("Walkers trailing the same stranger (%)")
    a.set_xticks(k)
    a.legend(frameon=False, fontsize=6.5)
    x = [s["tolerance_m"] for s in sweep]
    for kk, col, mk in ((3, PURPLE, "v"), (5, MUTED, "s")):
        b.plot(x, [100 * s[f"t{kk}"] for s in sweep], color=col, lw=1.6, marker=mk, ms=4, mec="white", mew=0.7,
               label=f"$k$ = {kk}")
    b.set_xlabel("Distance a follower will go off course (m)")
    b.set_ylabel("Followers trailing the same stranger (%)")
    b.legend(frameon=False, fontsize=6.5)
    for ax in (a, b):
        ax.grid(axis="y", color=GRID, lw=0.5)
        ax.set_ylim(0, 100)
    fig.tight_layout()
    save(fig, "follower-trailing" if run == "census_run" else f"follower-trailing-{run}")


def check(D, n=3000, seed=7):
    """Test the walker on trips made here, with no run needed: n trips from a random place to a random place by
    the quickest path. A follower with no reward must repeat its trip exactly and follow nobody; with a reward
    it must stay within its limit, and every follower must arrive."""
    import random
    w = D.w
    rng = random.Random(seed)
    codes = sorted(w.places)
    raw = []
    while len(raw) < n:
        a, b = rng.choice(codes), rng.choice(codes)
        if w.places[a]["node"] == w.places[b]["node"]:
            continue
        depart = rng.randrange(7 * 3600, 22 * 3600)
        night = depart >= 19 * 3600 or depart < 6.5 * 3600
        walk = w.walk(w.places[a]["node"], w.places[b]["node"], depart, night)
        raw.append({"agent": f"T{len(raw) % 500:05d}", "from": a, "to": b, "depart": depart, "pace": 1.0, "kind": "go",
                    "arrive": walk["arrive"], "segments": walk["segments"]})
    trips = [t for t in as_decisions(D, raw) if t["seq"]]
    leaders = Leaders(trips)
    plain = [follow(D, leaders, t, reward=0) for t in trips]
    # A follower may record a few junctions more than its trip near the destination: the trip's record leaves out
    # a junction it cannot name both roads of. So the trip's decisions must open the follower's, not equal them.
    starts = sum([x[:3] for x in p["seq"]][:len(t["seq"])] == [x[:3] for x in t["seq"]] for p, t in zip(plain, trips))
    same = sum([x[:3] for x in p["seq"]] == [x[:3] for x in t["seq"]] for p, t in zip(plain, trips))
    assert starts == len(trips), f"with no reward, {len(trips) - starts} of {len(trips)} followers left the quickest path"
    assert same >= 0.99 * len(trips), f"with no reward, only {same} of {len(trips)} followers repeat their trip exactly"
    assert not any(p["followed"] for p in plain), "with no reward, a follower followed someone"
    assert all(p["arrived"] for p in plain), "with no reward, a follower did not arrive"
    assert abs(t_k(trail_scan(plain, leaders), 3) - t_k(trail_scan(trips, leaders), 3)) < 0.005, "the measure differs on equal routes"
    keen = [follow(D, leaders, t, reward=1.0) for t in trips]
    assert sum(k["followed"] for k in keen) > 0, "with a reward, nobody followed anyone"
    assert all(k["tt"] == sorted(k["tt"]) and k["dd"] == sorted(k["dd"]) for k in keen), "a walk goes back in time"
    assert t_k(trail_scan(keen, leaders), 3) >= t_k(trail_scan(plain, leaders), 3), "following lowered the measure"
    again = [follow(D, leaders, t, reward=1.0) for t in trips]
    assert [k["seq"] for k in keen] == [k["seq"] for k in again], "two runs differ"
    print(f"checks passed on {len(trips):,} quickest-path trips: no reward repeats the trip ({same:,} exactly, the "
          f"rest with extra junctions recorded at the end), a reward makes followers "
          f"follow ({100 * sum(k['followed'] for k in keen) / sum(len(k['seq']) for k in keen):.1f}% of decisions), "
          f"all arrive without it, two runs agree.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="test the code on trips made here, then stop")
    ap.add_argument("--run", default="census_run", help="the Agent World run whose people are followed")
    ap.add_argument("--people-from", default="", help="only the people of this other run; results go to "
                                                      "analysis/same_people_as_<run>/")
    ap.add_argument("--reward", type=float, default=REWARD, help="R, the reward for the target's road")
    ap.add_argument("--scale", type=float, default=SCALE_M, help="L, the unit of the penalty's x, in metres")
    ap.add_argument("--view", type=float, default=VIEW_S, help="V, seconds in front that a target stays in view")
    ap.add_argument("--rewards", type=float, nargs="*", default=list(REWARDS), help="the rewards of the sweep")
    ap.add_argument("--boot", type=int, default=BOOT, help="bootstrap resamples of people")
    ap.add_argument("--limit", type=int, default=0, help="only the first N trips: a quick check, not a result")
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args()

    if args.check:
        check(Decisions(World()))
        return
    run_dir = C.OUT / args.run
    if not (run_dir / "trips.jsonl").exists():
        raise SystemExit(f"runs/{args.run}/trips.jsonl not found: run the Agent World first (bash run_experiments.sh agent-world).")
    out = run_dir / "analysis"
    keep = None
    if args.people_from:
        keep = {p.stem for p in (C.OUT / args.people_from / "agents").glob("A*.json")}
        if not keep:
            raise SystemExit(f"no people found in runs/{args.people_from}/agents/")
        out = out / f"same_people_as_{args.people_from}"
    out.mkdir(parents=True, exist_ok=True)

    world = World()
    D = Decisions(world)
    print("loading the Agent World trips", flush=True)
    with open(run_dir / "trips.jsonl", encoding="utf-8") as f:
        raw = [t for t in map(json.loads, f) if t["segments"] and (keep is None or t["agent"] in keep)]
    if args.limit:
        raw = raw[:args.limit]
    agents = [t for t in as_decisions(D, raw) if t["seq"]]
    del raw
    leaders = Leaders(agents)
    n_dec = sum(len(t["seq"]) for t in agents)
    print(f"{len(agents):,} trips with at least one junction, {n_dec:,} decisions", flush=True)

    base = trail_scan(agents, leaders)
    rewards = sorted(set(args.rewards) | {args.reward, 0.0})
    scans, stats = {}, {}
    for r in rewards:
        t0 = time.time()
        walks = [follow(D, leaders, t, reward=r, view_s=args.view, scale_m=args.scale) for t in agents]
        scans[r], stats[r] = trail_scan(walks, leaders), describe(walks, agents)
        print(f"reward {r:g} (up to {tolerance_m(r, args.scale):.0f} m off course): T_3 {t_k(scans[r], 3):.3f}, "
              f"followed at {100 * stats[r]['followed_share']:.1f}% of decisions, {time.time() - t0:.0f} s", flush=True)

    # checks on the code: a follower with no reward must follow nobody and walk the quickest path
    if stats[0.0]["followed_share"] != 0:
        raise SystemExit("check failed: followers with reward 0 followed someone")
    main_scan = scans[args.reward]

    tk_rows = []
    for k in range(1, KMAX + 1):
        row = {"k": k, "agents": t_k(base, k), "follower": t_k(main_scan, k),
               "agents_given_k": t_k(base, k, True), "follower_given_k": t_k(main_scan, k, True)}
        row["agents_lo"], row["agents_hi"] = interval(base, k, args.boot)
        row["follower_lo"], row["follower_hi"] = interval(main_scan, k, args.boot)
        tk_rows.append(row)
    with open(out / "follower_tk.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(tk_rows[0]))
        w.writeheader()
        w.writerows({k: (v if k == "k" else round(v, 4)) for k, v in r.items()} for r in tk_rows)

    sweep = [{"reward": r, "tolerance_m": round(tolerance_m(r, args.scale)), "t3": t_k(scans[r], 3), "t5": t_k(scans[r], 5),
              "t10": t_k(scans[r], 10), **stats[r]} for r in rewards]
    with open(out / "follower_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sweep[0]))
        w.writeheader()
        w.writerows({k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()} for s in sweep)

    def pct(x):
        return f"{100 * x:.1f}%"

    def ci(row, key):
        return f"{pct(row[key])} ({pct(row[key + '_lo'])} to {pct(row[key + '_hi'])})"

    s = stats[args.reward]
    L = [f"# The deliberate follower: {args.run}", "",
         f"{len(agents):,} Agent World trips with at least one junction, {n_dec:,} decisions. One follower per trip: same "
         f"start, time, pace and destination. Followers see the Agent World people, who walk as they did; followers do "
         f"not see each other. Reward R = {args.reward:g} for the target's road while the target is at most "
         f"{args.view:g} s in front on the same road; penalty 0.5 x^2 for a road that leaves the follower x beyond the "
         f"closest it has been to its destination, x in units of {args.scale:g} m. So a follower goes at most "
         f"{tolerance_m(args.reward, args.scale):.0f} m off course for its target.", "",
         "## Share of walkers trailing the same stranger through k junctions", "",
         f"The walker is at most {FOLLOW_M} m behind along the road each time. In brackets: 95% bootstrap interval, "
         f"resampling people ({args.boot} resamples).", "",
         "| k | Agent World (coincidence) | Deliberate follower | Agent World, trips with at least k | Follower, trips with at least k |",
         "|---|---|---|---|---|"]
    for r in tk_rows:
        if r["k"] in (1, 2, 3, 4, 5, 6, 8, 10):
            L.append(f"| {r['k']} | {ci(r, 'agents')} | {ci(r, 'follower')} | {pct(r['agents_given_k'])} | {pct(r['follower_given_k'])} |")
    L += ["", "## How the followers walked", "",
          f"- Decisions made by following a target: {pct(s['followed_share'])}.",
          f"- Followers who followed someone at least once: {pct(s['trips_that_followed'])}.",
          f"- Followers whose route is exactly their trip's route: {pct(s['same_route'])}.",
          f"- Extra walking from the first junction to the destination, per follower: {s['extra_metres']:.0f} m "
          f"(stairs counted at their flat equivalent for the follower's last stretch).",
          f"- Followers who arrived (the rest reached the limit on junctions): {pct(s['arrived'])}.", "",
          "## By reward", "",
          "| R | Off course, at most | T_3 | T_5 | T_10 | Decisions by following | Same route as the trip | Extra metres | Arrived |",
          "|---|---|---|---|---|---|---|---|---|"]
    for x in sweep:
        L.append(f"| {x['reward']:g} | {x['tolerance_m']} m | {pct(x['t3'])} | {pct(x['t5'])} | {pct(x['t10'])} | "
                 f"{pct(x['followed_share'])} | {pct(x['same_route'])} | {x['extra_metres']:.0f} | {pct(x['arrived'])} |")
    L += ["", "## Checks", "",
          f"- With R = 0 no follower followed anyone (checked by the script), and {pct(stats[0.0]['same_route'])} of them "
          f"walked exactly their trip's route. The rest are trips that did not take the quickest path (strolls, and "
          f"any trip walked with other speeds than today's).",
          "- Nothing is drawn by chance: running the script again gives the same numbers.", "",
          "Tables: follower_tk.csv, follower_sweep.csv. Figure: graphs/follower-trailing.pdf."]
    if args.limit:
        L.insert(2, f"**Quick check on the first {args.limit:,} trips only. Not a result.**")
        L.insert(3, "")
    (out / "follower.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    if not args.no_figure:
        figure(tk_rows, sweep, args.run)
    print(f"wrote {out / 'follower.md'}")


if __name__ == "__main__":
    main()
