"""What an agent can do during its day: the map tools, the clock, and the record of every trip.

The same tools serve the Claude planner and the free rule-based planner, so both produce the same
records: every search, every route check and every walk, with each segment and turn timed.

The tools describe what they do and nothing more. Variety in behaviour has to come from the people
(make_agents.py), not from hints in the instructions.
"""
import json
import random
import zlib

import config as C
from world import hhmm, parse_hhmm

CATEGORIES = ["any", "hku", "hall", "mtr", "bus", "food", "shop", "park", "library", "sight", "money", "health",
              "toilet", "vending", "worship", "school", "service", "building"]
LANDMARK_CATS = ("mtr", "hku", "hall", "library", "sight")
DAY_END = 24 * 3600 - 60
NIGHT_FROM = 20 * 3600  # residents' days can end from here on


def _tool(name, description, props, required):
    return {"name": name, "description": description, "strict": True,
            "input_schema": {"type": "object", "properties": props, "required": required, "additionalProperties": False}}


PACE_TEXT = "how fast you walk: normal is your usual speed, slow about a quarter slower, fast about a third faster"

TOOLS = [
    _tool("where_am_i", "Where you are now: the neighbourhood and the closest places around you, with direction "
          "and walking time.", {}, []),
    _tool("search_places", "Search the map for places by words (name, what it is, what you can do there). "
          "Returns up to 8 places with their code, what they are, direction and walking time from you.",
          {"query": {"type": "string"}, "category": {"type": "string", "enum": CATEGORIES}}, ["query", "category"]),
    _tool("nearby", "List places within a walking time of where you are, closest first.",
          {"category": {"type": "string", "enum": CATEGORIES},
           "max_minutes": {"type": "integer", "description": "1 to 30"}}, ["category", "max_minutes"]),
    _tool("route_info", "Check the walk to a place without going: minutes, metres, stairs, lifts, arrival time "
          "and turn-by-turn directions.",
          {"to": {"type": "string", "description": "place code"}}, ["to"]),
    _tool("go_to", "Walk to a place now by the quickest path. The clock moves to your arrival time.",
          {"to": {"type": "string", "description": "place code"},
           "pace": {"type": "string", "enum": ["slow", "normal", "fast"], "description": PACE_TEXT},
           "reason": {"type": "string", "description": "a few words"}}, ["to", "pace", "reason"]),
    _tool("stroll", "Walk without a set route for about the given number of minutes, heading roughly toward a "
          "place. You end at whichever place you reach when the time is up.",
          {"toward": {"type": "string", "description": "place code"},
           "minutes": {"type": "integer", "description": "10 to 180"},
           "pace": {"type": "string", "enum": ["slow", "normal", "fast"], "description": PACE_TEXT},
           "reason": {"type": "string", "description": "a few words"}}, ["toward", "minutes", "pace", "reason"]),
    _tool("stay", "Stay where you are doing something until a time today.",
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
- You act only through the tools. Each tool result tells you the time and where you are.
- Walking takes real time. go_to and stroll move you; stay passes time where you are.
- You know your own neighbourhood roughly, as described to you. For anything else, look it up with the \
tools, as you would with a phone map. Use only place codes that a tool or the list below gave you.
- People who commute arrive at, and leave from, their MTR exit or bus stop. Hall residents sleep in their hall.
- Keep any text very short; use one tool per turn.

Landmarks (code | name). Shops, food, toilets, ATMs, homes and everything else are found with the tools:
{chr(10).join(lines)}
"""


def mental_map(a, world):
    """What this person already knows about where things are, from where their day starts."""
    home = world.places[a["home"]]
    here = home["xy"]
    times = world.times_from(home["node"])

    def line(code, label=None):
        p = world.places[code]
        mins = max(1, round(times[p["node"]] / 60))
        return f"- {label or p['name']} ({code}): about {mins} min walk {world.compass(here, p['xy'])}"

    known, listed = [], {a["home"]}

    def add(code, label=None):
        if code and code not in listed:
            listed.add(code)
            known.append(line(code, label))

    for c in dict.fromkeys(x["place"] for x in a["commitments"]):
        add(c)
    mtr = min((p for p in world.places.values() if p["category"] == "mtr"), key=lambda p: times[p["node"]])
    add(mtr["code"], f"nearest MTR exit, {mtr['name']}")
    add(world.code_by_name("Main Building"), "HKU main campus (Main Building)")
    add(world.code_by_name("Central Podium"), "HKU Centennial Campus (Central Podium)")
    for area in ("Kennedy Town", "Sai Ying Pun"):
        if world.area_of(here) != area:
            c = min((p for p in world.places.values() if p["category"] == "mtr" and area in p["name"]),
                    key=lambda p: times[p["node"]], default=None)
            if c:
                add(c["code"], f"{area} (its MTR exit)")
    return f"You start at {home['name']} ({a['home']}), in {world.area_of(here)}. Places you already know:\n" + "\n".join(known)


def persona_card(a, world):
    def place(c):
        return f"{c} {world.places[c]['name']}" if c in world.places else c
    who = f"{a['name']}, {a['age']}, {a['role']}"
    if a.get("faculty"):
        who += f", Faculty of {a['faculty']}" + (f", year {a['year']}" if a.get("year") else "")
    if a.get("occupation"):
        who += f" ({a['occupation']})"
    todo = "\n".join(f"- {c['start']}{'-' + c['end'] if c.get('end') else ''}: {c['what']} at {place(c['place'])}"
                     for c in a["commitments"])
    t = a.get("today", {})
    extra = [f"Personality: {a['personality']}. Habits: {'; '.join(a['habits'])}."]
    if a.get("interests"):
        extra.append(f"Interests: {', '.join(a['interests'])}. {a.get('plans_style', '')}".strip())
    if t:
        extra.append(f"Today: {t['feeling']}." + "".join(f" {x}." for x in t.get("notes", [])))
    return f"""You are {who}.
{chr(10).join(extra)}
Weather: {C.WEATHER}
Home: {place(a['home'])} ({a['home_kind']}).
Fixed things today:
{todo}

{mental_map(a, world)}

It is {a['start']}. Your day starts now."""


class AgentDay:
    def __init__(self, agent, world, policy="quickest", beta=0.05, rng=None):
        self.a, self.w = agent, world
        self.t = parse_hhmm(agent["start"])
        self.at = agent["home"]
        self.node = world.places[self.at]["node"]
        self.trips, self.log = [], []
        self.calls, self.done, self.summary = 0, False, ""
        self.policy, self.beta, self.rng = policy, beta, rng
        # Fixed per person, so reruns give the same day: how fast they walk, and the seconds of
        # dawdling before each departure (nobody leaves on the exact minute).
        self.jitter = random.Random(zlib.crc32(agent["id"].encode()))
        self.pace = agent.get("pace") or round(self.jitter.uniform(0.85, 1.2), 2)

    @property
    def night(self):
        return self.t >= 19 * 3600 or self.t < 6.5 * 3600

    @property
    def commuter(self):
        return self.a["home_kind"].startswith("commutes")

    def where(self):
        return {"now": hhmm(self.t), "at": f"{self.at} {self.w.places[self.at]['name']}"}

    def run(self, name, args):
        """Execute one tool call. Returns (result dict, is_error)."""
        t_start = hhmm(self.t)
        try:
            out = getattr(self, "_" + name)(**args)
            err = False
        except (KeyError, ValueError, TypeError) as e:
            out, err = {"error": str(e).strip("'\"")}, True
        out.update(self.where())
        self.log.append({"t": t_start, "t_after": hhmm(self.t), "tool": name, "input": args, "error": err})
        return out, err

    def _code(self, code):
        code = str(code).strip().upper()
        if code not in self.w.places:
            raise ValueError(f"unknown place code {code!r}; use search_places to find a code")
        return code

    def _where_am_i(self):
        return self.w.surroundings(self.node)

    def _search_places(self, query, category):
        return {"results": self.w.search(query, self.node, None if category == "any" else category)}

    def _nearby(self, category, max_minutes):
        return {"results": self.w.nearby(self.node, None if category == "any" else category, max(1, min(30, int(max_minutes))))}

    def _route_info(self, to):
        to = self._code(to)
        dst = self.w.places[to]["node"]
        return {"to": f"{to} {self.w.places[to]['name']}", **self.w.route_summary(self.node, dst, self.t, self.night),
                "directions": self.w.directions(self.node, dst, self.t, self.night, self.pace)}

    def _walk(self, to, reason, policy, beta, kind, auto=False, until=None, pace="normal"):
        """pace: the person's choice for this walk, relative to their own comfortable speed (config.PACES)."""
        speed = self.pace * C.PACES.get(pace, 1.0)
        dst = self.w.places[to]["node"]
        start = self.t + self.jitter.randint(0, 75)
        walk = self.w.walk(self.node, dst, start, self.night, policy, beta, self.jitter if policy != "quickest" else self.rng, speed)
        if until is not None and walk["arrive"] > until + 120:
            # Time is up mid-walk: stop at the junction reached by then and finish at the closest place
            keep = [s for s in walk["segments"] if s["t"] < until] or walk["segments"][:1]
            stop_node = keep[-1]["to"]
            times = self.w.times_from(stop_node)
            to = min(self.w.places, key=lambda c: (times[self.w.places[c]["node"]], c))
            dst = self.w.places[to]["node"]
            t_stop = keep[-1]["t"] + self.w.edges[keep[-1]["edge"]]["secs"] / speed
            tail = self.w.walk(stop_node, dst, t_stop, self.night, pace=speed) if stop_node != dst else \
                {"segments": [], "turns": [], "arrive": round(t_stop), "metres": 0}
            last_turn = [x for x in walk["turns"] if x["t"] <= keep[-1]["t"]]
            if tail["segments"] and len(self.w.adj[stop_node]) >= 3:  # the turn where the stroll bends toward the stop
                last_turn.append({"node": stop_node, "turn": self.w.turn(stop_node, keep[-1]["edge"], None, tail["segments"][0]["edge"]),
                                  "t": round(t_stop)})
            walk = {"segments": keep + tail["segments"], "turns": last_turn + tail["turns"], "arrive": tail["arrive"],
                    "metres": round(sum(self.w.edges[s["edge"]]["len"] for s in keep)) + tail["metres"]}
        trip = {"agent": self.a["id"], "trip": len(self.trips) + 1, "from": self.at, "to": to, "pace": round(speed, 3),
                "pace_choice": pace,
                "depart": round(start), "arrive": walk["arrive"], "metres": walk["metres"], "reason": reason,
                "kind": kind, "auto": auto, "segments": walk["segments"], "turns": walk["turns"]}
        self.trips.append(trip)
        self.t, self.at, self.node = walk["arrive"], to, dst
        return trip

    def _go_to(self, to, reason="", auto=False, pace="normal"):
        to = self._code(to)
        if to == self.at:
            raise ValueError("you are already there")
        if pace not in C.PACES:
            raise ValueError("pace must be slow, normal or fast")
        trip = self._walk(to, reason, self.policy, self.beta, "go", auto, pace=pace)
        return {"arrived": f"{to} {self.w.places[to]['name']}", "walked_min": round((trip["arrive"] - trip["depart"]) / 60),
                "metres": trip["metres"], "turns": "".join(x["turn"] for x in trip["turns"])}

    def _stroll(self, toward, minutes, reason="", pace="normal"):
        """Meander toward a place, then on to other nearby places, until the time is up."""
        toward = self._code(toward)
        if pace not in C.PACES:
            raise ValueError("pace must be slow, normal or fast")
        minutes = max(10, min(180, int(minutes)))
        end = min(self.t + minutes * 60, DAY_END)
        legs, target = [], toward
        while self.t < end and len(legs) < 8:
            if target == self.at:
                times = self.w.times_from(self.node)
                options = [c for c, p in self.w.places.items()
                           if c != self.at and 4 * 60 <= times[p["node"]] <= 15 * 60]
                if not options:
                    break
                target = self.jitter.choice(options)
            trip = self._walk(target, reason, "noisy", 0.02, "stroll", until=end, pace=pace)
            legs.append(self.w.places[trip["to"]]["name"])
            if trip["to"] != target:
                break  # cut short because the time was up
        if not legs:
            raise ValueError("nowhere to stroll to from here")
        return {"walked": " -> ".join(legs), "minutes": minutes, "ended_at": f"{self.at} {self.w.places[self.at]['name']}"}

    def _stay(self, until, activity=""):
        end = min(parse_hhmm(until), DAY_END)
        if end <= self.t:
            raise ValueError(f"'until' must be later than now ({hhmm(self.t)})")
        self.t = end
        return {"did": activity}

    def _end_day(self, summary=""):
        if self.commuter:
            if self.at != self.a["home"]:
                raise ValueError(f"you commute: leave through {self.a['home']} first")
        elif self.t < NIGHT_FROM:
            raise ValueError(f"it is only {hhmm(self.t)}; the day goes on until night. Use stay if you are staying in")
        self.done, self.summary = True, summary
        return {"ended": True}

    def finish(self):
        """After the last call: send the person home if they are not there, so every day closes."""
        if self.at != self.a["home"] and self.t < DAY_END:
            self._walk(self.a["home"], "heading home (added by the simulator)", self.policy, self.beta, "go", auto=True)
        self.done = True

    def record(self, cost=0.0, stop=""):
        return {"agent": self.a, "calls": self.calls, "cost_usd": round(cost, 5), "stop": stop or ("ended" if self.summary else "cut"),
                "summary": self.summary, "end": hhmm(self.t), "log": self.log, "trips": self.trips}


def tool_result_text(out):
    return json.dumps(out, ensure_ascii=False)
