"""The live world: everyone lives the same day on one shared clock, and chooses every turn themselves.

There is no navigation app here: no go_to, no stroll and no route_info. At each real intersection (decisions.py)
a person sees the roads leading off it (name, direction, length, stairs, what they pass) and the people around
them, and picks one road; walking goes on by itself to the next intersection. Where to go, and which way, is
their own choice.

The simulator keeps one clock for everybody. It takes everyone whose next decision falls within the next
WINDOW seconds, asks them all at once, applies their choices, and moves on. A person sees the others where
they really are at that moment, and the others see them.

    python live.py --run live_test --planner mock --limit 500               # free, rule-based, for testing
    python live.py --run live --planner claude --limit 2000 --budget 80     # the real thing; see method.md

The people are the first --limit people of --agents (default: the day1 people), so the arms can be
compared on the same people. Writes out/<run>/trips.jsonl (the same format as the other arms),
out/<run>/agents/<id>.json and out/<run>/run_summary.json. A stopped run (budget, network, Ctrl+C)
resumes from out/<run>/checkpoint.pkl when the same command is run again.
"""
import argparse
import asyncio
import heapq
import json
import math
import pickle
import random
import time
import zlib
from collections import Counter, defaultdict
from functools import lru_cache

import config as C
from agent_tools import CATEGORIES, DAY_END, LANDMARK_CATS, NIGHT_FROM, _tool, persona_card
from decisions import Decisions
from world import World, _english, hhmm, parse_hhmm

WINDOW = 10            # seconds of the shared clock handled in one round of decisions
SIGHT_M = 50           # how far a person can see others
MAX_SEEN = 8
CELL = 100             # metres, grid for finding who is near whom
MAX_CALLS = 500        # model calls per person per day
MAX_CALLS_PER_STEP = 6 # calls without moving the clock before the simulator steps in
LOST_AFTER = 90 * 60   # a trip longer than this is finished by the simulator, by the quickest path
KEEP_TURNS, PRUNE_AT = 8, 24   # conversation memory: when it reaches PRUNE_AT exchanges, keep the last KEEP_TURNS
OUTDOOR = ("park", "sight", "bus", "mtr")  # people staying at these places can be seen from the street
TURN_WORD = {"L": "left", "R": "right", "S": "straight on", "F": "straight on", "B": "back the way you came"}


def compass(angle):
    return ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"][round(math.degrees(angle) / 45) % 8]

TOOLS = [
    _tool("look", "Look around where you are: the roads leading off, the people near you and the places here.", {}, []),
    _tool("search_places", "Search a phone map for places by words (name, what it is, what you can do there). "
          "Gives up to 8 places with their code, what they are, and their direction and straight-line distance from "
          "you. It does not show the way there.",
          {"query": {"type": "string"}, "category": {"type": "string", "enum": CATEGORIES}}, ["query", "category"]),
    _tool("nearby", "List places within a straight-line distance of you, closest first.",
          {"category": {"type": "string", "enum": CATEGORIES},
           "max_metres": {"type": "integer", "description": "50 to 2000"}}, ["category", "max_metres"]),
    _tool("walk", "Walk along one of the roads leading off from where you are, to the next intersection. You arrive "
          "by yourself when you reach the place you are heading for.",
          {"road": {"type": "integer", "description": "the road's number"},
           "toward": {"type": "string", "description": "code of the place you are heading for, or an empty string to keep the one you have"},
           "pace": {"type": "string", "enum": ["slow", "normal", "fast"],
                    "description": "how fast you walk: normal is your usual speed, slow about a quarter slower, fast about a third faster"}},
          ["road", "toward", "pace"]),
    _tool("enter", "Go into a place at the junction where you are, and end your walk there.",
          {"place": {"type": "string", "description": "place code"}}, ["place"]),
    _tool("stay", "Stay at the place where you are, doing something, until a time today.",
          {"until": {"type": "string", "description": "HH:MM, 24-hour, later than now"},
           "activity": {"type": "string", "description": "a few words"}}, ["until", "activity"]),
    _tool("end_day", "Finish your day once you are home for the night (or, if you commute, once you have left "
          "through your MTR exit or bus stop).",
          {"summary": {"type": "string", "description": "one sentence about your day"}}, ["summary"]),
]


def system_prompt(world):
    lines = [f"{p['code']} | {p['name']}" for p in world.places.values() if p["category"] in LANDMARK_CATS]
    return f"""You are one ordinary person living a single weekday around the University of Hong Kong, \
Kennedy Town and Sai Ying Pun. Act as this person would, from the start time until your day ends.

How the world works:
- Everyone around you is living the same day, at the same time.
- You act only through the tools. Each tool result tells you the time and where you are.
- There is no navigation app. You find your own way: at every intersection you choose which road to take. \
search_places and nearby give a place's direction and straight-line distance, not the way there.
- Walking takes real time: walk takes you to the next intersection. stay passes time at a place.
- You know your own neighbourhood roughly, as described to you. Use only place codes that a tool or the list \
below gave you.
- People who commute arrive at, and leave from, their MTR exit or bus stop. Hall residents sleep in their hall.
- Keep any text very short; use one tool per turn.

Landmarks (code | name). Shops, food, toilets, ATMs, homes and everything else are found with the tools:
{chr(10).join(lines)}
"""


class Person:
    """One person's state. Plain data, so a run can be saved and resumed."""

    def __init__(self, a, world):
        self.a, self.id = a, a["id"]
        self.t = parse_hhmm(a["start"])
        self.place = a["home"]
        self.node = world.places[self.place]["node"]
        self.e_in = None          # the segment just walked (None at a place)
        self.arm_in = None        # at an intersection: the road they came in by
        self.dest = None          # place code they are heading for
        self.trip = None          # the trip in progress
        self.track = []           # (t_start, from, to, edge, t_end) for the walk in progress
        self.trips, self.log = [], []
        self.calls, self.cost = 0, 0.0
        self.started = self.done = self.gone = False
        self.summary, self.stop, self.note = "", "", ""
        self.messages, self.pending, self.pending_extra = [], None, []
        jitter = random.Random(zlib.crc32(a["id"].encode()))
        self.pace = a.get("pace") or round(jitter.uniform(0.85, 1.2), 2)
        self.rng_state = jitter.getstate()
        self.visits = Counter()   # mock planner only
        self.done_commitments = set()

    @property
    def commuter(self):
        return self.a["home_kind"].startswith("commutes")


class Live:
    def __init__(self, world, people):
        self.w = world
        self.D = Decisions(world)
        self.people = {p.id: p for p in people}
        self.places_at = defaultdict(list)
        for code, p in world.places.items():
            self.places_at[p["node"]].append(code)
        self.cells = defaultdict(set)
        self.cells_of = {}
        for p in people:
            self.reindex(p)

    # ---------------- map views ----------------
    def night(self, t):
        return t >= 19 * 3600 or t < 6.5 * 3600

    def at_junction(self, node):
        c = self.D.cluster_of.get(node)
        return c if c is not None and self.D.is_decision[c] else None

    @lru_cache(maxsize=None)
    def road_walk(self, node, k):
        """Where road k (counting from 0) from node leads: the steps to the next intersection, and where they end
        (see Decisions.advance)."""
        start, edge = self.D.roads_from(node)[k]
        c = self.at_junction(node)
        cross = self.D.crossing_path(c, node, start) if c is not None and start != node else []
        steps, where = self.D.advance(start, edge)
        return tuple(cross + steps), where

    def roads(self, p):
        out, node = [], p.node
        c = self.at_junction(node)
        for k, (start, edge) in enumerate(self.D.roads_from(node)):
            steps, where = self.road_walk(node, k)
            E = self.w.edges[edge]
            if c is not None:
                A = self.D.arms[c][k]
                label = "a lift" if E["lift"] else "steps" if E["steps"] > 0.5 * E["len"] else (_english(A["name"]) or "a footpath")
                heading = compass(A["heading"])
                turn = TURN_WORD[self.D.label(c, p.arm_in, k)] if p.arm_in is not None else None
            else:
                label = "a lift" if E["lift"] else "steps" if E["steps"] > 0.5 * E["len"] else (_english(E["name"]) or "a footpath")
                heading = compass(self.w._bearing_out(node, edge))
                turn = TURN_WORD[self.w.turn(node, p.e_in, None, edge)] if p.e_in is not None else None
            d = {"road": k + 1, "is": label}
            if turn:
                d["turn"] = turn
            d["heading"] = heading
            edges = [e for _, _, e in steps]
            d["metres"] = round(sum(self.w.edges[e]["len"] for e in edges))
            stairs = sum(self.w.edges[e]["steps"] for e in edges)
            if stairs >= 5:
                d["stairs_m"] = round(stairs)
            if any(self.w.edges[e]["lift"] for e in edges):
                d["lift"] = True
            if self.night(p.t) and any(self.w.edges[e]["lit"] is False for e in edges):
                d["unlit"] = True
            passes = list(dict.fromkeys(self.w.places[x]["name"] for _, b, _ in steps for x in self.places_at.get(b, ())))[:3]
            if passes:
                d["passes"] = passes
            if where[0] == "junction" and where[1] == c and where[2] == k:
                d["ends"] = "dead end, you would come back here"
            elif where[0] == "junction":
                d["leads_to"] = f"an intersection with {len(self.D.arms[where[1]])} roads"
            out.append(d)
        return out

    def straight(self, code, node):
        p = self.w.places[code]
        here = self.w.xy[node]
        m = math.hypot(p["xy"][0] - here[0], p["xy"][1] - here[1])
        return {"code": code, "name": p["name"], "category": p["category"], "about": p["caption"],
                "metres_straight_line": round(m), **({"direction": self.w.compass(here, p["xy"])} if m > 20 else {})}

    def search(self, query, node, category):
        hits = self.w.search(query, node, None if category == "any" else category, limit=40)
        here = self.w.xy[node]
        # the phone map orders equal matches by distance as the crow flies, not by walking time
        hits.sort(key=lambda h: math.dist(here, self.w.places[h["code"]]["xy"]))
        order = {h["code"]: i for i, h in enumerate(hits)}
        best = sorted(hits, key=lambda h: order[h["code"]])[:8]
        return [self.straight(h["code"], node) for h in best]

    def nearby(self, node, category, max_m):
        here = self.w.xy[node]
        out = [(math.dist(here, p["xy"]), c) for c, p in self.w.places.items()
               if (category == "any" or p["category"] == category) and math.dist(here, p["xy"]) <= max_m]
        return [self.straight(c, node) for _, c in sorted(out)[:10]]

    # ---------------- who is where ----------------
    def position(self, p, t):
        """(x, y, step) where p is at time t; step is (from, to, edge) while walking, else None."""
        if p.track and p.track[0][0] <= t < p.track[-1][4]:
            for t0, a, b, e, t1 in p.track:
                if t0 <= t < t1:
                    f = (t - t0) / max(1e-6, t1 - t0)
                    A, B = self.w.xy[a], self.w.xy[b]
                    return A[0] + f * (B[0] - A[0]), A[1] + f * (B[1] - A[1]), (a, b, e)
        node = p.track[0][1] if p.track and t < p.track[0][0] else p.node
        x, y = self.w.xy[node]
        return x, y, None

    def visible(self, p, t):
        if not p.started or p.gone or t < parse_hhmm(p.a["start"]):
            return False
        if p.place and not (p.track and t < p.track[-1][4]):
            return self.w.places[p.place]["category"] in OUTDOOR   # indoors otherwise
        return True

    def reindex(self, p):
        for c in self.cells_of.get(p.id, ()):
            self.cells[c].discard(p.id)
        nodes = {p.node} | {s[1] for s in p.track} | {s[2] for s in p.track}
        cells = {(int(self.w.xy[n][0] // CELL), int(self.w.xy[n][1] // CELL)) for n in nodes}
        for c in cells:
            self.cells[c].add(p.id)
        self.cells_of[p.id] = cells

    def people_near(self, me, t):
        here = self.w.xy[me.node]
        cx, cy = int(here[0] // CELL), int(here[1] // CELL)
        cand = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand |= self.cells.get((cx + dx, cy + dy), set())
        seen = []
        for pid in cand:
            o = self.people[pid]
            if o is me or not self.visible(o, t):
                continue
            x, y, step = self.position(o, t)
            d = math.hypot(x - here[0], y - here[1])
            if d <= SIGHT_M:
                seen.append((d, pid, o, step, (x, y)))
        out = []
        c = self.at_junction(me.node)
        for d, pid, o, step, xy in sorted(seen)[:MAX_SEEN]:
            road, away = None, False
            if step:
                a, b, e = step
                if c is not None:
                    k = self.D.arm_edges[c].get(e)
                    if k is not None:
                        road = k + 1
                        away = math.dist(self.w.xy[b], self.D.centre[c]) > math.dist(self.w.xy[a], self.D.centre[c])
                else:
                    for k, (_, i) in enumerate(self.D.roads_from(me.node), 1):
                        if i == e:
                            road, away = k, a == me.node
                if road:
                    doing = f"walking away from you along road {road}" if away else f"coming toward you along road {road}"
                else:
                    doing = f"walking {self.w.compass(self.w.xy[a], self.w.xy[b])}"
            else:
                doing = f"standing at {self.w.places[o.place]['name']}" if o.place else "standing at a junction"
            age = o.a.get("age")
            out.append({"person": "P" + pid[1:], "looks": f"in their {age // 10 * 10}s" if age else "an adult",
                        "metres_away": round(d), "doing": doing})
        return out

    def view(self, p):
        here = self.w.xy[p.node]
        v = {"now": hhmm(p.t)}
        if p.note:
            v["note"], p.note = p.note, ""
        if p.place:
            v["at"] = f"{p.place} {self.w.places[p.place]['name']}"
        else:
            c = self.at_junction(p.node)
            if c is not None:
                names = sorted({_english(A["name"]) for A in self.D.arms[c]} - {""})
                kind = "an intersection"
            else:
                names = sorted({_english(self.w.edges[i]["name"]) for _, i in self.w.adj[p.node]} - {""})
                kind = "a path"
            v["at"] = kind + (f" of {', '.join(names)}" if names else "") + f", {self.w.area_of(here)}"
        if p.dest and p.dest != p.place:
            s = self.straight(p.dest, p.node)
            v["heading_for"] = f"{p.dest} {s['name']}: {s['metres_straight_line']} m {s.get('direction', 'here')} in a straight line"
        here_places = [c for c in self.places_at.get(p.node, ()) if c != p.place]
        if here_places:
            v["places_here"] = [f"{c} {self.w.places[c]['name']}" for c in here_places[:6]]
        v["roads"] = self.roads(p)
        v["people_near_you"] = self.people_near(p, p.t)
        return v

    # ---------------- actions ----------------
    def code(self, c):
        c = str(c).strip().upper()
        if c not in self.w.places:
            raise ValueError(f"unknown place code {c!r}; use search_places to find a code")
        return c

    def act(self, p, name, args):
        """Run one tool. Returns (result, moves_clock, is_error)."""
        t_before = hhmm(p.t)
        try:
            out, moves = getattr(self, "_" + name)(p, **args)
            err = False
        except (KeyError, ValueError, TypeError) as e:
            out, moves, err = {"error": str(e).strip("'\"")}, False, True
        p.log.append({"t": t_before, "tool": name, "input": args, "error": err})
        return out, moves, err

    def _look(self, p):
        return self.view(p), False

    def _search_places(self, p, query, category):
        return {"results": self.search(query, p.node, category), "now": hhmm(p.t)}, False

    def _nearby(self, p, category, max_metres):
        return {"results": self.nearby(p.node, category, max(50, min(2000, int(max_metres)))), "now": hhmm(p.t)}, False

    def _walk(self, p, road, toward="", pace="normal"):
        if pace not in C.PACES:
            raise ValueError("pace must be slow, normal or fast")
        speed = p.pace * C.PACES[pace]
        options = self.D.roads_from(p.node)
        k = int(road)
        if not 1 <= k <= len(options):
            raise ValueError(f"there is no road {k} here; the roads are numbered 1 to {len(options)}")
        if toward:
            p.dest = self.code(toward)
        start, edge = options[k - 1]
        dest_node = self.w.places[p.dest]["node"] if p.dest else None
        c = self.at_junction(p.node)
        steps, where = [], None
        if c is not None and start != p.node:
            for st in self.D.crossing_path(c, p.node, start):
                steps.append(st)
                if st[1] == dest_node:
                    where = ("place", dest_node)
                    break
        if where is None:
            more, where = self.D.advance(start, edge, dest_node)
            steps += more
        t = p.t
        if p.trip is None:
            p.trip = {"agent": p.id, "trip": len(p.trips) + 1, "from": p.place, "to": None, "pace": p.pace,
                      "depart": round(t), "arrive": None, "metres": 0, "reason": "", "kind": "live", "auto": False,
                      "segments": [], "turns": []}
            p.visits = Counter()
        p.track = []
        for a, b, e in steps:
            secs = self.w.edges[e]["secs"] / speed
            p.trip["segments"].append({"edge": e, "from": a, "to": b, "t": round(t)})
            p.track.append((t, a, b, e, t + secs))
            t += secs
        p.place, p.node, p.e_in, p.t = None, steps[-1][1], steps[-1][2], t
        p.arm_in = where[2] if where[0] == "junction" else None
        p.visits[p.node] += 1
        self.reindex(p)
        return {}, True

    def _enter(self, p, place):
        place = self.code(place)
        if p.place:
            raise ValueError("you are already at a place; use walk to leave")
        if self.w.places[place]["node"] != p.node:
            raise ValueError(f"{place} is not at this junction; places here: {self.places_at.get(p.node, [])}")
        self.arrive(p, place)
        return self.view(p), False

    def _stay(self, p, until, activity=""):
        if not p.place:
            raise ValueError("you can only stay at a place; enter one first")
        end = min(parse_hhmm(until), DAY_END)
        if end <= p.t:
            raise ValueError(f"'until' must be later than now ({hhmm(p.t)})")
        p.t, p.track = end, []
        self.reindex(p)
        return {}, True

    def _end_day(self, p, summary=""):
        if p.commuter:
            if p.place != p.a["home"]:
                raise ValueError(f"you commute: leave through {p.a['home']} first")
        else:
            if p.place != p.a["home"]:
                raise ValueError(f"go home first ({p.a['home']})")
            if p.t < NIGHT_FROM:
                raise ValueError(f"it is only {hhmm(p.t)}; the day goes on until night. Use stay if you are staying in")
        p.done, p.gone, p.summary = True, True, summary
        return {"ended": True}, False

    def arrive(self, p, place):
        tr = p.trip
        if tr:
            segs = tr["segments"]
            tr["to"], tr["arrive"] = place, round(p.t)
            tr["metres"] = round(sum(self.w.edges[s["edge"]]["len"] for s in segs))
            tr["turns"] = [{"node": segs[k]["from"], "turn": self.w.turn(segs[k]["from"], segs[k - 1]["edge"], None, segs[k]["edge"]),
                            "t": segs[k]["t"]} for k in range(1, len(segs)) if len(self.w.adj[segs[k]["from"]]) >= 3]
            p.trips.append(tr)
        p.trip, p.place, p.e_in, p.arm_in = None, place, None, None
        if p.dest == place:
            p.dest = None
        p.node = self.w.places[place]["node"]
        p.track = []
        self.reindex(p)

    def auto_walk(self, p, place, why):
        """The simulator takes the person to a place by the quickest path (they were lost, or the day ran out)."""
        dst = self.w.places[place]["node"]
        if p.trip is None:
            p.trip = {"agent": p.id, "trip": len(p.trips) + 1, "from": p.place, "to": None, "pace": p.pace,
                      "depart": round(p.t), "arrive": None, "metres": 0, "reason": why, "kind": "live", "auto": True,
                      "segments": [], "turns": []}
        p.trip["auto"] = True
        if p.node != dst:
            w = self.w.walk(p.node, dst, p.t, self.night(p.t), pace=p.pace)
            p.trip["segments"] += w["segments"]
            p.track = [(s["t"], s["from"], s["to"], s["edge"], s["t"] + self.w.edges[s["edge"]]["secs"] / p.pace)
                       for s in w["segments"]]
            p.t = w["arrive"]
        p.node = dst
        self.arrive(p, place)
        p.note = why

    def wake(self, p):
        """Bring a person up to their decision time. Returns what they see, or None if the simulator moved them."""
        p.started = True
        if p.trip and p.dest and p.node == self.w.places[p.dest]["node"]:
            name = self.w.places[p.dest]["name"]
            self.arrive(p, p.dest)
            p.note = f"you have arrived at {name}"
        elif p.trip and p.t - p.trip["depart"] > LOST_AFTER:
            target = p.dest or p.a["home"]
            self.auto_walk(p, target, f"you could not find the way, so you asked someone and they walked you to "
                                      f"{self.w.places[target]['name']}")
            return None if p.t > DAY_END else self.view(p)
        return self.view(p)

    def finish(self, p, stop):
        if not p.done:
            if p.place != p.a["home"] and p.t < DAY_END + 3600:
                self.auto_walk(p, p.a["home"], "heading home (added by the simulator)")
            p.done, p.gone, p.stop = True, True, p.stop or stop

    def record(self, p):
        return {"agent": p.a, "calls": p.calls, "cost_usd": round(p.cost, 5), "stop": p.stop or ("ended" if p.summary else "cut"),
                "summary": p.summary, "end": hhmm(p.t), "log": p.log, "trips": p.trips}


# ---------------- planners ----------------
def mock_step(live, p):
    """A rule-based walker with no map app: at each junction it takes the road whose far end is closest, as the
    crow flies, to where it is going. Only for testing the simulator; it says nothing about real people."""
    rng = random.Random()
    rng.setstate(p.rng_state)
    w = live.w

    def head(code):
        """Take one road toward a place: the one ending closest to it, avoiding going back and repeat visits."""
        target = w.places[code]["xy"]
        options, n_roads = [], len(live.D.roads_from(p.node))
        for k in range(n_roads):
            steps, where = live.road_walk(p.node, k)
            if n_roads > 1 and ((p.arm_in is not None and k == p.arm_in) or
                                (p.arm_in is None and p.e_in is not None and steps and steps[0][2] == p.e_in)):
                continue   # not back the way it came
            end = steps[-1][1] if steps else p.node
            options.append((math.dist(w.xy[end], target) + 150 * p.visits[end] + rng.uniform(0, 20), k + 1))
        k = min(options)[1] if options else 1
        if p.place is None and rng.random() < 0.2:   # sometimes go the way someone ahead is going (tests the view)
            away = [int(x["doing"].rsplit(" ", 1)[1]) for x in live.people_near(p, p.t) if "walking away" in x["doing"]]
            if away:
                k = rng.choice(away)
        live.act(p, "walk", {"road": k, "toward": code})

    try:
        if live.wake(p) is None:
            return
        for _ in range(4):
            p.calls += 1
            if p.place is None:   # at a junction, on the way somewhere
                head(p.dest or p.a["home"])
                return
            todo = sorted((parse_hhmm(c["start"]), j, c) for j, c in enumerate(p.a["commitments"])
                          if j not in p.done_commitments)
            if todo:
                start, j, c = todo[0]
                if p.place == c["place"]:
                    p.done_commitments.add(j)
                    end = parse_hhmm(c["end"]) if c.get("end") else max(p.t, start) + 3600
                    if end > p.t + 60:
                        live.act(p, "stay", {"until": hhmm(end), "activity": c["what"]})
                        return
                    continue
                metres = math.dist(w.places[p.place]["xy"], w.places[c["place"]]["xy"])
                leave = start - metres * 1.6 / (C.WALK_SPEED * p.pace) - 5 * 60
                if leave > p.t + 120:
                    live.act(p, "stay", {"until": hhmm(leave), "activity": "getting ready"})
                else:
                    head(c["place"])
                return
            if p.place != p.a["home"]:
                head(p.a["home"])
            elif not p.commuter and p.t < 22.5 * 3600:
                live.act(p, "stay", {"until": "22:30", "activity": "evening at home"})
            else:
                live.act(p, "end_day", {"summary": "followed the timetable"})
            return
    finally:
        p.rng_state = rng.getstate()


def add_user(p, blocks):
    if p.messages and p.messages[-1]["role"] == "user":
        c = p.messages[-1]["content"]
        if isinstance(c, str):
            c = [{"type": "text", "text": c}]
        p.messages[-1]["content"] = c + blocks
    else:
        p.messages.append({"role": "user", "content": blocks})


def prune(p):
    """Keep the persona and the most recent exchanges. Cut in blocks, so the cached prefix stays stable."""
    if len(p.messages) <= 1 + 2 * PRUNE_AT:
        return
    j = len(p.messages) - 2 * KEEP_TURNS
    while j < len(p.messages) and p.messages[j]["role"] != "assistant":
        j += 1
    p.messages = [p.messages[0]] + p.messages[j:]


async def claude_step(live, p, client, system, spend):
    view = live.wake(p)
    if view is None:
        return
    text = json.dumps(view, ensure_ascii=False)
    if not p.messages:
        p.messages = [{"role": "user", "content": persona_card(p.a, live.w) + "\n\nWhat you see now: " + text}]
    elif p.pending:
        add_user(p, p.pending_extra + [{"type": "tool_result", "tool_use_id": p.pending, "content": text}])
    else:
        add_user(p, [{"type": "text", "text": "What you see now: " + text}])
    p.pending, p.pending_extra = None, []
    nudges = 0
    for _ in range(MAX_CALLS_PER_STEP):
        if p.calls >= MAX_CALLS:
            p.stop = "call limit"; p.done = True; return
        if spend.exhausted:
            raise BudgetReached
        prune(p)
        resp = await client.messages.create(
            model=C.MODEL, max_tokens=C.MAX_TOKENS, tools=TOOLS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=p.messages, output_config={"effort": C.EFFORT}, cache_control={"type": "ephemeral"})
        p.calls += 1
        p.cost += spend.add(resp.usage)
        p.messages.append({"role": "assistant", "content": [b.model_dump(mode="json", exclude_none=True) for b in resp.content]})
        if resp.stop_reason == "refusal":
            p.stop = "refusal"; p.done = True; return
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            nudges += 1
            if nudges > 2:
                p.stop = "no tool call"; p.done = True; return
            add_user(p, [{"type": "text", "text": f"Continue your day with the tools. It is {hhmm(p.t)}."}])
            continue
        results, moved = [], None
        for b in uses:
            if moved or p.done:
                out, mv, err = {"error": "one action at a time" if moved else "the day has ended"}, False, True
            else:
                out, mv, err = live.act(p, b.name, dict(b.input))
            if mv:
                moved = b.id
                continue
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, ensure_ascii=False), "is_error": err})
        if moved:
            p.pending, p.pending_extra = moved, results
            return
        add_user(p, results)
        if p.done:
            return
    # Too many calls without acting: the person waits a little where they are, or keeps walking
    p.note = "you stood still for a moment"
    if p.place:
        live._stay(p, hhmm(min(DAY_END, p.t + 15 * 60)))
    else:
        ks = [k for k in range(len(live.D.roads_from(p.node))) if k != p.arm_in] or [0]
        live._walk(p, ks[0] + 1)


class BudgetReached(Exception):
    pass


# ---------------- the shared clock ----------------
def save(out_dir, live, heap, spend, done):
    state = {"people": live.people, "heap": heap, "usd": spend.usd, "tok": spend.tok, "calls": spend.calls, "done": done}
    tmp = out_dir / "checkpoint.tmp"
    tmp.write_bytes(pickle.dumps(state))
    tmp.replace(out_dir / "checkpoint.pkl")


async def run(args, world, people, out_dir):
    from run_day import Spend
    spend = Spend(args.budget)
    ckpt = out_dir / "checkpoint.pkl"
    if ckpt.exists():
        st = pickle.loads(ckpt.read_bytes())
        live = Live(world, list(st["people"].values()))
        heap, spend.usd, spend.tok, spend.calls = st["heap"], st["usd"], st["tok"], st["calls"]
        print(f"resuming at {hhmm(heap[0][0]) if heap else 'the end'}, US${spend.usd:.3f} spent so far")
    else:
        live = Live(world, people)
        heap = [(p.t, p.id) for p in people]
        heapq.heapify(heap)
    client = system = None
    if args.planner == "claude":
        import anthropic
        client = anthropic.AsyncAnthropic(max_retries=8)
        system = system_prompt(world)
        sem = asyncio.Semaphore(args.concurrency)

    async def step(p):
        if args.planner == "mock":
            mock_step(live, p)
            return
        async with sem:
            await claude_step(live, p, client, system, spend)

    t_real, last_save, rounds, stop = time.time(), time.time(), 0, ""
    try:
        while heap and heap[0][0] < DAY_END:
            t0 = heap[0][0]
            batch = []
            while heap and heap[0][0] <= t0 + WINDOW:
                batch.append(live.people[heapq.heappop(heap)[1]])
            results = await asyncio.gather(*(step(p) for p in batch), return_exceptions=True)
            for p, r in zip(batch, results):
                if isinstance(r, BudgetReached):
                    stop = "budget"
                elif isinstance(r, Exception):
                    if args.planner == "claude":
                        import anthropic
                        if isinstance(r, (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
                                          anthropic.NotFoundError, anthropic.BadRequestError, TypeError)):
                            stop = stop or f"{type(r).__name__}: {r}"
                        elif isinstance(r, (anthropic.APIStatusError, anthropic.APIConnectionError)):
                            print(f"  {p.id}: {type(r).__name__}, will ask again next round")
                        else:
                            raise r
                    else:
                        raise r
                if not p.done:
                    heapq.heappush(heap, (max(p.t, t0), p.id))
            rounds += 1
            if stop:
                save(out_dir, live, heap, spend, False)
                print(f"stopped at {hhmm(t0)}: {stop}. Saved; run the same command again to continue"
                      + (" with a higher --budget" if stop == "budget" else ""))
                return None, spend, time.time() - t_real
            if rounds % 500 == 0:
                walking = sum(1 for p in live.people.values() if p.started and not p.gone and not p.place)
                print(f"  {hhmm(t0)}  {walking} people walking, {spend.calls} calls, US${spend.usd:.3f}", flush=True)
            if args.planner == "claude" and time.time() - last_save > 120:
                save(out_dir, live, heap, spend, False)
                last_save = time.time()
    except KeyboardInterrupt:
        save(out_dir, live, heap, spend, False)
        print("interrupted; saved. Run the same command again to continue")
        return None, spend, time.time() - t_real
    for p in live.people.values():
        live.finish(p, "midnight")
    return live, spend, time.time() - t_real


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="live_test")
    ap.add_argument("--planner", choices=["mock", "claude"], default="mock")
    ap.add_argument("--agents", default=str(C.OUT / "day1" / "people.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="only the first N people")
    ap.add_argument("--budget", type=float, default=C.BUDGET_USD)
    ap.add_argument("--concurrency", type=int, default=C.CONCURRENCY)
    args = ap.parse_args()

    world = World()
    agents = [json.loads(l) for l in open(args.agents, encoding="utf-8")]
    if args.limit:
        agents = agents[: args.limit]
    out_dir = C.OUT / args.run
    (out_dir / "agents").mkdir(parents=True, exist_ok=True)
    live, spend, secs = asyncio.run(run(args, world, [Person(a, world) for a in agents], out_dir))
    if live is None:
        return
    recs = [live.record(p) for p in live.people.values()]
    for r in recs:
        (out_dir / "agents" / f"{r['agent']['id']}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    with open(out_dir / "trips.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            for t in r["trips"]:
                f.write(json.dumps(t) + "\n")
    n, trips = len(recs), sum(len(r["trips"]) for r in recs)
    summary = {"arm": "live", "planner": args.planner, "agents": n, "calls": sum(r["calls"] for r in recs), "trips": trips,
               "auto_trips": sum(t["auto"] for r in recs for t in r["trips"]), "usd": round(spend.usd, 4),
               "usd_per_agent": round(spend.usd / n, 5) if n else 0, "tokens": spend.tok, "seconds": round(secs, 1),
               "how_days_ended": dict(Counter(r["stop"] for r in recs))}
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "checkpoint.pkl").unlink(missing_ok=True)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
