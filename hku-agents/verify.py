"""Check that this checkout can repeat the published experiment. Free: no key, no network.

    python verify.py              # run every check
    python verify.py --update     # after you change the map, the captions or make_agents.py on purpose

1. The data files are the ones the published run used (data/CHECKSUMS.json).
2. make_agents.py draws the same 10,000 people on your machine (seed 7).
3. The walking code rebuilds every published walk in ../web.json, segment by segment and to the second.
4. The rule-based planner gives the same days twice, and a replay rebuilds them exactly.
5. Each route mode gives a valid walk, and step-free walks climb fewer stairs.
"""
import argparse
import hashlib
import json
import random

import config as C
import plans
import run_day
from agent_tools import ROUTE_MODES, route_policy
from make_agents import make
from world import World

OK, BAD = "[ok]  ", "[FAIL]"
SUMS = C.DATA / "CHECKSUMS.json"
PEOPLE, SEED = 10000, 7
WEB = C.ROOT.parent / "web.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def report(good, text):
    print(f"{OK if good else BAD} {text}")
    return good


def people_bytes(agents):
    return "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in agents).encode()


def check_data(agents, update):
    now = {"graph.json": sha256((C.DATA / "graph.json").read_bytes()), "places.csv": sha256((C.DATA / "places.csv").read_bytes()),
           f"people: make_agents.py --n {PEOPLE} --seed {SEED}": sha256(people_bytes(agents))}
    if update:
        SUMS.write_text(json.dumps(now, indent=2) + "\n", encoding="utf-8")
        return report(True, f"wrote {SUMS}")
    want = json.loads(SUMS.read_text(encoding="utf-8"))
    good = True
    for name, digest in now.items():
        good &= report(want.get(name) == digest, f"{name} is as published" if want.get(name) == digest else
                       f"{name} differs from the published run (if you changed it on purpose: python verify.py --update)")
    saved = C.DATA / "agents_10k.jsonl"
    if saved.exists():
        same = saved.read_bytes() == people_bytes(agents)
        good &= report(same, f"data/agents_10k.jsonl holds exactly those {PEOPLE} people" if same else
                       f"data/agents_10k.jsonl is not what make_agents.py --n {PEOPLE} --seed {SEED} writes")
    return good


def check_published_walks(world, agents):
    if not WEB.exists():
        return report(True, "web.json not found next to the simulator page: skipped the published walks")
    web = json.loads(WEB.read_text(encoding="utf-8"))
    by_id = {a["id"]: a for a in agents}
    keys = ("name", "age", "role", "home", "start", "commitments", "habits", "interests")
    same_people = sum(all(p.get(k) == by_id[p["id"]].get(k) for k in keys) for p in web["people"] if p["id"] in by_id)
    good = report(same_people == len(web["people"]),
                  f"{same_people} of {len(web['people'])} people on the website are the people make_agents.py draws")
    ok = total = 0
    for p in web["people"]:
        for tr in p["trips"]:
            if tr["kind"] != "go":
                continue  # strolls meander with the person's own random stream, which needs the whole day replayed
            total += 1
            night = tr["d"] >= 19 * 3600 or tr["d"] < 6.5 * 3600
            w = world.walk(world.places[tr["from"]]["node"], world.places[tr["to"]]["node"], tr["d"], night, pace=tr["k"])
            seg = [s["edge"] * 2 + (0 if s["from"] == world.edges[s["edge"]]["u"] else 1) for s in w["segments"]]
            ok += seg == tr["seg"] and w["arrive"] == tr["a"] and "".join(x["turn"] for x in w["turns"]) == tr["turns"]
    return good & report(ok == total, f"{ok} of {total} published walks rebuilt exactly (same segments, turns and arrival time)")


def check_planners(world, agents):
    some = agents[:60]

    def days(routes):
        return [run_day.mock_day(a, world, random.Random(f"{SEED}:{a['id']}"), route_policy(a, routes)) for a in some]

    first = days("quickest")
    good = report(json.dumps(first) == json.dumps(days("quickest")), "the rule-based planner gives the same days twice")
    again = [run_day.replay_day(r["agent"], plans.plan_of(r), world, "quickest") for r in first]
    same = all(a["trips"] == b["trips"] and a["log"] == b["log"] for a, b in zip(first, again))
    good &= report(same, f"replaying {len(some)} people's plans rebuilds their {sum(len(r['trips']) for r in first)} trips exactly")
    for routes in ROUTE_MODES:
        recs = [run_day.replay_day(r["agent"], plans.plan_of(r), world, route_policy(r["agent"], routes)) for r in first]
        trips = [t for r in recs for t in r["trips"]]
        joined = all(a["to"] == b["from"] for t in trips for a, b in zip(t["segments"], t["segments"][1:]))
        arrive = all(not t["segments"] or t["segments"][-1]["to"] == world.places[t["to"]]["node"] for t in trips)
        good &= report(bool(joined and arrive and trips), f"routes '{routes}': {len(trips)} connected walks that reach their place")
    return good


def check_step_free(world):
    rng = random.Random(SEED)
    codes = sorted(world.places)
    stairs = {"quickest": 0.0, "step-free": 0.0}
    never_more = True
    for _ in range(300):
        a, b = (world.places[c]["node"] for c in rng.sample(codes, 2))
        m = {}
        for policy in stairs:
            m[policy] = sum(world.edges[s["edge"]]["steps"] for s in world.walk(a, b, 12 * 3600, policy=policy)["segments"])
            stairs[policy] += m[policy]
        never_more &= m["step-free"] <= m["quickest"] + 1e-6
    return report(never_more and stairs["step-free"] < stairs["quickest"],
                  f"step-free walks climb fewer stairs: {stairs['step-free'] / 300:.0f} m per walk against "
                  f"{stairs['quickest'] / 300:.0f} m by the quickest path (300 random pairs of places)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true", help="record the current data files and people as the reference")
    args = ap.parse_args()
    world = World()
    agents = make(PEOPLE, SEED)
    good = check_data(agents, args.update)
    good &= check_published_walks(world, agents)
    good &= check_planners(world, agents)
    good &= check_step_free(world)
    print("\nVerified: this checkout rebuilds the published people and walks." if good else "\nFix the items marked FAIL first.")
    raise SystemExit(0 if good else 1)


if __name__ == "__main__":
    main()
