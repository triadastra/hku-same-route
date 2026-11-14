"""The map as the agents experience it: find places, check routes, and walk.

Walking always follows the quickest path (or a noisy variant used for the random-turn baseline) and
records every segment entered, with its direction and time, plus the turn made at every junction.
"""
import csv
import heapq
import json
import math
import random
import re
from functools import lru_cache

import config as C

LAT0, LON0 = 22.2830, 114.1371


def _english(s):
    """Keep the English part of bilingual names: '大學街 University Street' -> 'University Street'."""
    if not s:
        return s
    parts = []
    for part in s.split(" / "):
        latin = "".join(ch for ch in part if ord(ch) < 0x2E80).strip(" -/")
        parts.append(latin if sum(ch.isalpha() for ch in latin) >= 3 else part)
    return " / ".join(parts)


def xy(lat, lon):
    return ((lon - LON0) * math.cos(math.radians(LAT0)) * 111320.0, (lat - LAT0) * 110540.0)


def hhmm(t):
    t = int(round(t))
    return f"{t // 3600 % 24:02d}:{t // 60 % 60:02d}"


def parse_hhmm(s):
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(s))
    if not m:
        raise ValueError(f"time must look like 14:30, got {s!r}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60


class World:
    def __init__(self):
        g = json.loads((C.DATA / "graph.json").read_text(encoding="utf-8"))
        self.nodes = g["nodes"]
        self.edges = g["edges"]
        for e in self.edges:   # walking time from the speeds in config.py (graph.json was built with older values)
            e["secs"] = round((e["len"] - e["steps"]) / C.WALK_SPEED + e["steps"] / C.STAIRS_SPEED
                              + (C.LIFT_SECONDS / 2 if e["lift"] else 0), 1)
        self.adj = [[] for _ in self.nodes]
        for i, e in enumerate(self.edges):
            self.adj[e["u"]].append((e["v"], i))
            self.adj[e["v"]].append((e["u"], i))
        node_of = {p["code"]: p["node"] for p in g["places"]}
        with (C.DATA / "places.csv").open(encoding="utf-8-sig") as f:
            self.places = {r["code"]: {**r, "node": node_of[r["code"]]} for r in csv.DictReader(f)}
        self.xy = [xy(n["lat"], n["lon"]) for n in self.nodes]
        for p in self.places.values():
            p["xy"] = xy(float(p["lat"]), float(p["lon"]))
        self.areas = self._areas()

    # ---------- orientation ----------
    def _areas(self):
        """Neighbourhood centres, from the places that define them."""
        def centre(pred):
            pts = [p["xy"] for p in self.places.values() if pred(p)]
            return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)) if pts else None
        areas = {
            "Kennedy Town": centre(lambda p: p["category"] == "mtr" and "Kennedy Town" in p["name"]),
            "Sai Ying Pun": centre(lambda p: p["category"] == "mtr" and "Sai Ying Pun" in p["name"]),
            "Shek Tong Tsui, around HKU station": centre(lambda p: p["category"] == "mtr" and "HKU" in p["name"]),
            "HKU main campus": centre(lambda p: p["name"] in ("Main Building", "Knowles Building", "Haking Wong Building")),
            "HKU Centennial Campus": centre(lambda p: p["name"] in ("Central Podium", "Cheng Yu Tung Tower", "The Jockey Club Tower")),
            "the student halls on the hillside": centre(lambda p: p["category"] == "hall"),
        }
        return {k: v for k, v in areas.items() if v}

    def area_of(self, pt):
        name, c = min(self.areas.items(), key=lambda kv: math.hypot(kv[1][0] - pt[0], kv[1][1] - pt[1]))
        return name

    @staticmethod
    def compass(a, b):
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        return ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"][round(ang / 45) % 8]

    def directions(self, src, dst, t0, night=False, pace=1.0):
        """Turn-by-turn steps for the quickest walk, like a phone map."""
        w = self.walk(src, dst, t0, night, pace=pace)
        turn_at = {x["node"]: x["turn"] for x in w["turns"]}
        verbs = {"L": "Turn left onto", "R": "Turn right onto", "S": "Continue onto", "B": "Turn back onto"}
        groups = []
        for s in w["segments"]:
            e = self.edges[s["edge"]]
            label = "the lift" if e["lift"] else "steps" if e["steps"] > 0.5 * e["len"] else (_english(e["name"]) or "a footpath")
            if groups and groups[-1][0] == label:
                groups[-1][1] += e["len"]
            else:
                groups.append([label, e["len"], turn_at.get(s["from"])])
        out = []
        for i, (label, metres, turn) in enumerate(groups):
            verb = "Start along" if i == 0 else verbs.get(turn, "Take")
            out.append(f"{verb} {label}" + ("" if label == "the lift" else f" for {round(metres / 10) * 10 or 10} m"))
        if len(out) > 12:
            out = out[:11] + [f"... then {len(out) - 11} more steps"]
        return out

    # ---------- routing ----------
    def seg_cost(self, i, night):
        e = self.edges[i]
        return e["secs"] + (C.UNLIT_PENALTY if night and e["lit"] is False else 0)

    @lru_cache(maxsize=4096)
    def times_from(self, src, night=False):
        """Quickest walking time in seconds from src to every junction."""
        dist = [math.inf] * len(self.nodes)
        dist[src] = 0.0
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for v, i in self.adj[u]:
                nd = d + self.seg_cost(i, night)
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        return tuple(dist)

    def path(self, src, dst, night=False, policy="quickest", beta=0.05, rng=None):
        """List of (from_node, to_node, edge) steps. 'noisy' picks each turn with softmax over extra time."""
        to_dst = self.times_from(dst, night)  # undirected costs, so time-to-dst == time-from-dst
        steps, u, prev = [], src, None
        limit = 4 * max(1, len(self._quickest(src, dst, night))) + 20
        while u != dst:
            opts = [(v, i) for v, i in self.adj[u] if v != prev] or self.adj[u]
            if policy == "quickest" or len(steps) >= limit:
                v, i = min(opts, key=lambda o: self.seg_cost(o[1], night) + to_dst[o[0]])
            else:
                extra = [self.seg_cost(i, night) + to_dst[v] - to_dst[u] for v, i in opts]
                w = [math.exp(-beta * max(0.0, x)) for x in extra]
                v, i = (rng or random).choices(opts, weights=w)[0]
            steps.append((u, v, i))
            prev, u = u, v
        return steps

    @lru_cache(maxsize=65536)
    def _quickest(self, src, dst, night):
        to_dst = self.times_from(dst, night)
        out, u = [], src
        while u != dst:
            v, i = min(self.adj[u], key=lambda o: self.seg_cost(o[1], night) + to_dst[o[0]])
            out.append(i)
            u = v
        return tuple(out)

    # ---------- geometry ----------
    def _bearing_out(self, u, i):
        """Direction (radians) of leaving junction u along edge i."""
        e = self.edges[i]
        g = e["geom"] if e["u"] == u else e["geom"][::-1]
        a, b = xy(*g[0]), xy(*g[1])
        return math.atan2(b[1] - a[1], b[0] - a[0])

    def turn(self, n, e_in, prev, e_out):
        """Turn made at junction n: 'L', 'R', 'S' (straight) or 'B' (back)."""
        h_in = self._bearing_out(n, e_in) + math.pi  # reverse of leaving n back along the incoming edge
        h_out = self._bearing_out(n, e_out)
        d = math.degrees((h_out - h_in + math.pi) % (2 * math.pi) - math.pi)
        if abs(d) < 35:
            return "S"
        if abs(d) > 145:
            return "B"
        return "L" if d > 0 else "R"

    # ---------- walking ----------
    def walk(self, src, dst, t0, night=False, policy="quickest", beta=0.05, rng=None, pace=1.0):
        """pace scales walking speed: 1.2 walks 20% faster than average, 0.85 slower."""
        steps = self.path(src, dst, night, policy, beta, rng)
        t, segs, turns = t0, [], []
        for k, (a, b, i) in enumerate(steps):
            if k and len(self.adj[a]) >= 3:
                turns.append({"node": a, "turn": self.turn(a, steps[k - 1][2], steps[k - 1][0], i), "t": round(t)})
            segs.append({"edge": i, "from": a, "to": b, "t": round(t)})
            t += self.edges[i]["secs"] / pace
        metres = sum(self.edges[i]["len"] for _, _, i in steps)
        return {"segments": segs, "turns": turns, "arrive": round(t), "metres": round(metres)}

    def route_summary(self, src, dst, t0, night=False):
        w = self.walk(src, dst, t0, night)
        names, last = [], None
        for s in w["segments"]:
            n = _english(self.edges[s["edge"]]["name"])
            if n and n != last:
                names.append(n)
                last = n
        stairs = sum(self.edges[s["edge"]]["steps"] for s in w["segments"])
        lifts = sum(self.edges[s["edge"]]["lift"] for s in w["segments"]) // 2
        return {"minutes": max(1, round((w["arrive"] - t0) / 60)), "metres": w["metres"], "stairs_m": round(stairs),
                "lifts": lifts, "turns": len(w["turns"]), "via": names[:6], "arrive": hhmm(w["arrive"])}

    # ---------- places ----------
    def minutes_between(self, src, dst, night=False):
        return self.times_from(src, night)[dst] / 60

    def search(self, query, at_node, category=None, limit=8):
        """Best text matches first; among equally good matches, the closest first."""
        words = [w for w in re.findall(r"[a-z0-9]+", (query or "").lower()) if len(w) > 1]
        times = self.times_from(at_node)
        here = self.xy[at_node]
        hits = []
        for p in self.places.values():
            if category and p["category"] != category:
                continue
            text = f"{p['code']} {p['name']} {p['caption']} {p['aliases']} {p['category']}".lower()
            score = sum(3 if w in p["name"].lower() or w == p["code"].lower() else 1 for w in words if w in text)
            if words and not score:
                continue
            hits.append((-score, times[p["node"]], p))
        hits.sort(key=lambda h: (h[0], h[1], h[2]["code"]))
        return [self.describe(p, times[p["node"]], here) for _, _, p in hits[:limit]]

    def nearby(self, at_node, category=None, max_minutes=10, limit=10):
        times = self.times_from(at_node)
        here = self.xy[at_node]
        out = [(times[p["node"]], p) for p in self.places.values()
               if (not category or p["category"] == category) and times[p["node"]] <= max_minutes * 60]
        out.sort(key=lambda x: (x[0], x[1]["code"]))
        return [self.describe(p, t, here) for t, p in out[:limit]]

    def describe(self, p, secs, here=None):
        d = {"code": p["code"], "name": p["name"], "category": p["category"], "about": p["caption"],
             "walk_min": round(secs / 60, 1)}
        if here is not None and secs > 30:
            d["direction"] = self.compass(here, p["xy"])
        return d

    def surroundings(self, node, limit=8):
        """What a person standing here would notice: the area and the closest places in each direction."""
        times = self.times_from(node)
        here = self.xy[node]
        near = sorted(((times[p["node"]], p) for p in self.places.values()), key=lambda tp: (tp[0], tp[1]["code"]))
        seen_dirs, picks = {}, []
        for t, p in near:
            if t > 15 * 60 or len(picks) >= limit:
                break
            dirn = self.compass(here, p["xy"]) if t > 30 else "here"
            if seen_dirs.get(dirn, 0) >= 2:
                continue  # spread the picks around instead of listing one block's shops
            seen_dirs[dirn] = seen_dirs.get(dirn, 0) + 1
            picks.append(self.describe(p, t, here))
        return {"area": self.area_of(here), "around_you": picks}

    def code_by_name(self, *fragments):
        for f in fragments:
            for p in self.places.values():
                if f.lower() in p["name"].lower():
                    return p["code"]
        return None
