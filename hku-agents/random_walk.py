"""The random-walk arm: people with no plan, walking from a random place to a random place.

Every place on the map has the same chance of being an origin and a destination. Each walk takes the
quickest path, like a navigation app. To keep the map as busy as in the agent run, every random trip
copies the departure time, walking pace and owner of one real trip from that run; only where it starts
and ends is random.

    python random_walk.py --run day1 --seed 1

Writes out/<run>/random_walk/trips.jsonl in the same format as the agent run's trips.jsonl.
"""
import argparse
import json
import random

import config as C
from world import World


def random_trips(world, trips, seed):
    """One random trip per real trip: same agent, departure time and pace; origin and destination drawn
    uniformly from all places (at different junctions)."""
    rng = random.Random(seed)
    codes = sorted(world.places)
    out = []
    for tr in trips:
        while True:
            a, b = rng.choice(codes), rng.choice(codes)
            na, nb = world.places[a]["node"], world.places[b]["node"]
            if na != nb:
                break
        night = tr["depart"] >= 19 * 3600 or tr["depart"] < 6.5 * 3600  # the same rule as AgentDay.night
        w = world.walk(na, nb, tr["depart"], night, pace=tr.get("pace", 1.0))
        out.append({"agent": tr["agent"], "trip": tr["trip"], "from": a, "to": b, "pace": tr.get("pace", 1.0),
                    "depart": tr["depart"], "arrive": w["arrive"], "metres": w["metres"], "reason": "random walk",
                    "kind": "random", "auto": False, "segments": w["segments"], "turns": w["turns"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="day1")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    world = World()
    run_dir = C.OUT / args.run
    trips = [json.loads(l) for l in open(run_dir / "trips.jsonl", encoding="utf-8")]
    trips = [t for t in trips if t["segments"]]
    out = random_trips(world, trips, args.seed)
    (run_dir / "random_walk").mkdir(exist_ok=True)
    with open(run_dir / "random_walk" / "trips.jsonl", "w", encoding="utf-8") as f:
        for t in out:
            f.write(json.dumps(t) + "\n")
    km = sum(t["metres"] for t in out) / 1000
    print(f"{len(out)} random trips, {km:.0f} km walked ({km * 1000 / len(out):.0f} m per trip), seed {args.seed}")


if __name__ == "__main__":
    main()
