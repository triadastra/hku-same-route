"""Groups of people, and what each group does on each road.

Every person belongs to exactly one group (role x where they live), so group counts add up to
everyone. A "road" is one path segment between two junctions; its direction matters for turns.
"""
from collections import Counter, defaultdict

GROUPS = ["ug_hall", "ug_commute", "pg_hall", "pg_commute", "staff", "resident"]
LABELS = {"ug_hall": "Undergrads in halls", "ug_commute": "Commuting undergrads", "pg_hall": "Postgrads in halls",
          "pg_commute": "Commuting postgrads", "staff": "Staff", "resident": "Local residents"}
TURNS = "LRSB"


def group_of(agent):
    role = agent["role"]
    if role in ("staff", "resident"):
        return role
    hall = agent.get("home_kind", "").startswith("lives in")
    return ("ug" if role == "undergrad" else "pg") + ("_hall" if hall else "_commute")


def decisions(trip, degree):
    """(directed segment code, turn) for every junction decision in a trip: the turn made at the end
    of a segment is credited to that segment. code = edge * 2 + (0 if walked u->v else 1)."""
    segs, turns = trip["segments"], trip["turns"]
    out, j = [], 0
    for k in range(1, len(segs)):
        if degree[segs[k]["from"]] >= 3 and j < len(turns):
            prev = segs[k - 1]
            out.append((prev["edge"] * 2 + prev["dir"], turns[j]["turn"]))
            j += 1
    return out


def add_dirs(trips, edges):
    for tr in trips:
        for s in tr["segments"]:
            s["dir"] = 0 if s["from"] == edges[s["edge"]]["u"] else 1


def road_tables(trips, group_by_agent, degree):
    """usage[(group, hour)][edge] = walkers entering; turns[(code, group)] = Counter of L/R/S/B."""
    usage = defaultdict(Counter)
    turns = defaultdict(Counter)
    for tr in trips:
        g = group_by_agent[tr["agent"]]
        for s in tr["segments"]:
            usage[(g, int(s["t"] // 3600) % 24)][s["edge"]] += 1
        for code, t in decisions(tr, degree):
            turns[(code, g)][t] += 1
    return usage, turns
