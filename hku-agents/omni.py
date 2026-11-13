"""The omni arm: agents who can see the people walking near them, and can follow one.

The crowd is a finished run (for example day1). An omni agent lives its own day among those recorded
people, with its own recorded self removed. It gets the same eight tools plus two:

  look_around   the people walking within sight right now
  follow        walk behind one of them for a few minutes

The crowd does not react to the agent, and omni agents do not see each other.

    python run_day.py --run omni --planner claude --agents out/day1/people.jsonl --omni-crowd day1 --limit 2000
"""
import bisect
import json
import math
from collections import defaultdict

import config as C
from agent_tools import TOOLS, AgentDay, _tool, system_prompt

SIGHT_M = 50        # how far an agent can see other walkers
MAX_SEEN = 8
CATCH_UP_S = 20     # you can join someone if you reach a junction no later than this after they do
GAP_S = 5           # how far behind them you then walk

OMNI_TOOLS = TOOLS + [
    _tool("look_around", "See the people walking near you right now: a label for each, roughly how old they look, "
          "how far away they are, and which way they are heading.", {}, []),
    _tool("follow", "Walk behind one of the people you saw with look_around, for up to the given number of minutes. "
          "You end at the place nearest to where you stop.",
          {"person": {"type": "string", "description": "label from look_around"},
           "minutes": {"type": "integer", "description": "1 to 60"},
           "reason": {"type": "string", "description": "a few words"}}, ["person", "minutes", "reason"]),
]


def omni_system_prompt(world):
    return system_prompt(world).replace(
        "- Keep any text very short; use one tool per turn.",
        "- Other people are out walking too. look_around shows who is near you; follow walks behind one of them.\n"
        "- Keep any text very short; use one tool per turn.")


class Crowd:
    """Where every recorded person is walking at any moment of the day."""

    def __init__(self, world, run):
        self.w = world
        run_dir = C.OUT / run
        self.trips = [t for t in (json.loads(l) for l in open(run_dir / "trips.jsonl", encoding="utf-8")) if t["segments"]]
        self.age = {}
        people = run_dir / "people.jsonl"
        if people.exists():
            self.age = {a["id"]: a.get("age") for a in (json.loads(l) for l in open(people, encoding="utf-8"))}
        self.minute = defaultdict(list)
        self.by_agent = defaultdict(list)
        for g, tr in enumerate(self.trips):
            tr["_ts"] = [s["t"] for s in tr["segments"]]
            self.by_agent[tr["agent"]].append(g)
            for m in range(tr["depart"] // 60, tr["arrive"] // 60 + 1):
                self.minute[m].append(g)

    @staticmethod
    def label(agent_id):
        return "P" + agent_id[1:]

    def position(self, g, t):
        """(x, y, heading in radians, segment index) of trip g at time t, or None if not walking then."""
        tr = self.trips[g]
        if not tr["segments"][0]["t"] <= t < tr["arrive"]:
            return None
        j = bisect.bisect_right(tr["_ts"], t) - 1
        s = tr["segments"][j]
        t1 = tr["_ts"][j + 1] if j + 1 < len(tr["_ts"]) else tr["arrive"]
        f = (t - s["t"]) / max(1, t1 - s["t"])
        a, b = self.w.xy[s["from"]], self.w.xy[s["to"]]
        return a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), math.atan2(b[1] - a[1], b[0] - a[0]), j

    def near(self, pt, t, me):
        out = []
        for g in self.minute.get(int(t) // 60, ()):
            if self.trips[g]["agent"] == me:
                continue
            p = self.position(g, t)
            if p and math.hypot(p[0] - pt[0], p[1] - pt[1]) <= SIGHT_M:
                out.append((math.hypot(p[0] - pt[0], p[1] - pt[1]), g, p))
        return sorted(out)[:MAX_SEEN]

    def walking_trip(self, agent_id, t):
        for g in self.by_agent.get(agent_id, ()):
            tr = self.trips[g]
            if tr["segments"][0]["t"] <= t < tr["arrive"]:
                return tr
        return None


class OmniDay(AgentDay):
    def __init__(self, agent, world, crowd):
        super().__init__(agent, world)
        self.crowd = crowd

    def _look_around(self):
        here = self.w.xy[self.node]
        people = []
        for dist, g, (x, y, heading, _) in self.crowd.near(here, self.t, self.a["id"]):
            tr = self.crowd.trips[g]
            age = self.crowd.age.get(tr["agent"])
            ahead = (x + 100 * math.cos(heading), y + 100 * math.sin(heading))
            people.append({"person": self.crowd.label(tr["agent"]),
                           "looks": f"in their {age // 10 * 10}s" if age else "an adult",
                           "metres_away": round(dist),
                           "is_to_your": self.w.compass(here, (x, y)) if dist > 3 else "right beside you",
                           "heading": self.w.compass((x, y), ahead)})
        return {"people_walking_nearby": people}

    def _follow(self, person, minutes, reason=""):
        target_id = "A" + str(person).strip().upper().lstrip("PA")
        minutes = max(1, min(60, int(minutes)))
        start = self.t + self.jitter.randint(0, 10)
        tr = self.crowd.walking_trip(target_id, start) if target_id != self.a["id"] else None
        if tr is None:
            raise ValueError(f"{person} is not walking near you now; use look_around to see who is")
        xs = tr["segments"]
        c = bisect.bisect_right(tr["_ts"], start) - 1
        mine = self.w.times_from(self.node, self.night)
        join = next((j for j in range(c + 1, len(xs))
                     if start + mine[xs[j]["from"]] / self.pace <= xs[j]["t"] + CATCH_UP_S), None)
        if join is None:
            raise ValueError(f"{person} is too far ahead to catch up with")
        node = xs[join]["from"]
        approach = self.w.walk(self.node, node, start, self.night, pace=self.pace) if node != self.node else \
            {"segments": [], "arrive": round(start)}
        gap = max(GAP_S, approach["arrive"] - xs[join]["t"])
        until = start + minutes * 60
        copied = [{"edge": s["edge"], "from": s["from"], "to": s["to"], "t": round(s["t"] + gap)}
                  for s in xs[join:] if s["t"] + gap < until] or [dict(xs[join], t=round(xs[join]["t"] + gap))]
        whole = len(copied) == len(xs) - join
        stop_node = copied[-1]["to"]
        if whole:
            to, t_stop = tr["to"], tr["arrive"] + gap
            tail = []
        else:
            nxt = xs[join + len(copied)]["t"] + gap   # when they, and you behind them, reach the next junction
            times = self.w.times_from(stop_node)
            to = min(self.w.places, key=lambda p: (times[self.w.places[p]["node"]], p))
            dst = self.w.places[to]["node"]
            tail_walk = self.w.walk(stop_node, dst, nxt, self.night, pace=self.pace) if dst != stop_node else \
                {"segments": [], "arrive": round(nxt)}
            tail, t_stop = tail_walk["segments"], tail_walk["arrive"]
        segs = approach["segments"] + copied + tail
        turns = [{"node": s["from"], "turn": self.w.turn(s["from"], segs[k - 1]["edge"], None, s["edge"]), "t": s["t"]}
                 for k, s in enumerate(segs) if k and len(self.w.adj[s["from"]]) >= 3]
        trip = {"agent": self.a["id"], "trip": len(self.trips) + 1, "from": self.at, "to": to, "pace": self.pace,
                "depart": round(start), "arrive": round(t_stop),
                "metres": round(sum(self.w.edges[s["edge"]]["len"] for s in segs)), "reason": reason,
                "kind": "follow", "auto": False, "followed": target_id, "followed_segments": len(copied),
                "segments": segs, "turns": turns}
        self.trips.append(trip)
        self.t, self.at, self.node = trip["arrive"], to, self.w.places[to]["node"]
        return {"followed": person, "walked_min": round((trip["arrive"] - trip["depart"]) / 60), "metres": trip["metres"],
                "they": f"went into {self.w.places[to]['name']}" if whole else "kept walking",
                "ended_at": f"{to} {self.w.places[to]['name']}"}
