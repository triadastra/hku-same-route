"""Pack a finished run into one JSON file for the demo website.

    python export_web.py --run day1 --max-agents 2500        # -> out/day1/web/web.json

The map, the results tables and a sample of people (all of their trips, turns and tool calls) go in.
Coordinates are metres east/north of HKU, rounded to 0.5 m.
"""
import argparse
import csv
import json
import math
import random
import time

import config as C
from build_map import english
from groups import GROUPS, LABELS, TURNS, add_dirs, group_of, road_tables
from world import World, xy


def simplify(pts, tol=1.0):
    """Douglas-Peucker on a list of (x, y)."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-9
    far, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * (pts[i][0] - x1) - dx * (pts[i][1] - y1)) / norm
        if d > far:
            far, idx = d, i
    if far <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[: idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def r(v):
    return round(v * 2) / 2


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="pilot")
    ap.add_argument("--max-agents", type=int, default=2500)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    world = World()
    run = C.OUT / args.run
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((run / "agents").glob("A*.json"))]
    summary = json.loads((run / "run_summary.json").read_text(encoding="utf-8"))
    sample = recs if len(recs) <= args.max_agents else random.Random(args.seed).sample(recs, args.max_agents)
    sample.sort(key=lambda x: x["agent"]["id"])

    road_use = [0] * len(world.edges)
    for rec in recs:
        for tr in rec["trips"]:
            for s in tr["segments"]:
                road_use[s["edge"]] += 1

    edges = []
    for e in world.edges:
        pts = simplify([xy(lat, lon) for lat, lon in e["geom"]])
        name = " / ".join(english(n) for n in e["name"].split(" / ")) if e["name"] else ""
        edges.append({"u": e["u"], "v": e["v"], "p": [r(c) for pt in pts for c in pt], "s": 1 if e["steps"] else 0,
                      "l": 1 if e["lift"] else 0, "n": name, "t": e["secs"], "m": round(e["len"])})

    # Roads by group: walkers per (group, hour, segment) and the turn each group made at the end of each segment
    group_by_agent = {rec["agent"]["id"]: group_of(rec["agent"]) for rec in recs}
    all_trips = [tr for rec in recs for tr in rec["trips"] if tr["segments"]]
    add_dirs(all_trips, world.edges)
    usage, turns = road_tables(all_trips, group_by_agent, [len(a) for a in world.adj])
    gi = {g: i for i, g in enumerate(GROUPS)}
    heat = [[[] for _ in range(24)] for _ in GROUPS]
    for (g, h), c in usage.items():
        heat[gi[g]][h] = [x for e, n in sorted(c.items()) for x in (e, n)]
    dec = []
    for (code, g), c in turns.items():
        dec += [code, gi[g]] + [c[d] for d in TURNS]
    group_people = [sum(1 for v in group_by_agent.values() if v == g) for g in GROUPS]
    degree = [len(a) for a in world.adj]
    places = []
    for p in world.places.values():
        x, y = xy(float(p["lat"]), float(p["lon"]))
        places.append({"code": p["code"], "name": p["name"], "cat": p["category"], "about": p["caption"], "x": r(x), "y": r(y)})

    def pname(code):
        return world.places[code]["name"] if code in world.places else str(code)

    def say(l):
        i = l["input"]
        tool = l["tool"]
        if tool == "search_places":
            return f"searched the map for \"{i.get('query', '')}\"" + (f" ({i['category']})" if i.get("category") not in (None, "any") else "")
        if tool == "nearby":
            return f"looked for {'places' if i.get('category') in (None, 'any') else i['category']} within {i.get('max_minutes')} min"
        if tool == "route_info":
            return f"checked the walk to {pname(i.get('to'))}"
        if tool == "go_to":
            return f"walked to {pname(i.get('to'))}" + (f" ({i['reason']})" if i.get("reason") else "")
        if tool == "stay":
            return f"{i.get('activity') or 'stayed'} until {i.get('until')}"
        if tool == "end_day":
            return "ended the day" + (f": {i['summary']}" if i.get("summary") else "")
        if tool == "where_am_i":
            return "checked where they are"
        if tool == "stroll":
            return f"strolled toward {pname(i.get('toward'))} for about {i.get('minutes')} min" + (f" ({i['reason']})" if i.get("reason") else "")
        return tool

    people = []
    for rec in sample:
        a = rec["agent"]
        trips = []
        for tr in rec["trips"]:
            # segment times are rebuilt in the browser from each segment's walking time
            seg = [s["edge"] * 2 + (0 if s["from"] == world.edges[s["edge"]]["u"] else 1) for s in tr["segments"]]
            trips.append({"from": tr["from"], "to": tr["to"], "d": tr["depart"], "a": tr["arrive"], "k": tr.get("pace", 1.0),
                          "why": tr["reason"], "kind": tr.get("kind", "go"),
                          "auto": tr["auto"], "seg": seg, "turns": "".join(x["turn"] for x in tr["turns"])})
        log = [[l["t"], l["tool"][0], say(l), 1 if l["error"] else 0] for l in rec["log"]]
        people.append({"id": a["id"], "g": gi[group_of(a)], "name": a["name"], "age": a["age"], "role": a["role"], "faculty": a.get("faculty"),
                       "year": a.get("year"), "personality": a["personality"], "habits": a["habits"], "home": a["home"],
                       "home_kind": a["home_kind"], "start": a["start"], "commitments": a["commitments"],
                       "occupation": a.get("occupation"), "interests": a.get("interests", []), "today": a.get("today", {}),
                       "plans_style": a.get("plans_style", ""),
                       "summary": rec["summary"], "stop": rec["stop"], "calls": rec["calls"], "trips": trips, "log": log})

    an = run / "analysis"
    data = {
        "meta": {"run": args.run, "planner": summary["planner"], "model": C.MODEL if summary["planner"] == "claude" else None,
                 "agents_total": summary["agents"], "trips_total": summary["trips"], "agents_shown": len(people),
                 "usd": summary["usd"], "exported": time.strftime("%Y-%m-%d"), "window_s": C.SHARED_WINDOW,
                 "map_note": "Map data (c) OpenStreetMap contributors, ODbL",
                 "graph": {"junctions": len(world.nodes), "segments": len(world.edges),
                           "km": round(sum(e["len"] for e in world.edges) / 1000, 1),
                           "steps": sum(1 for e in world.edges if e["steps"] > 0), "lifts": sum(1 for e in world.edges if e["lift"]),
                           "lit_known": sum(1 for e in world.edges if e["lit"] is not None), "places": len(world.places)}},
        "edges": edges, "degree": degree, "places": places, "usage": road_use, "people": people,
        "groups": [{"key": g, "label": LABELS[g], "people": n} for g, n in zip(GROUPS, group_people)],
        "heat": heat, "dec": dec,
        "results": {"shared": read_csv(an / "shared_turns.csv"), "by_hour": read_csv(an / "by_hour.csv"),
                    "turns": read_csv(an / "turns_by_junction.csv")[:30], "groups": read_csv(an / "groups.csv"),
                    "share_matrix": read_csv(an / "share_matrix.csv")},
    }
    out = run / "web"
    out.mkdir(exist_ok=True)
    path = out / "web.json"
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB): {len(edges)} segments, {len(places)} places, "
          f"{len(people)} of {len(recs)} people")


if __name__ == "__main__":
    main()
