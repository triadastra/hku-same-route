"""Real intersections, and the choices each one offers.

OpenStreetMap draws sidewalks, crossings and short paths as separate ways, so on a typical trip the walking
network has a junction every 13 m. People do not decide at every one of them. Here:

- short dead-end stubs (building entrances, kerb stubs) are not roads;
- junctions joined by a short path are merged into one intersection (the four corners of a crossroads,
  the two sides of a crossing);
- each intersection gets its real roads ("arms"): a Y junction has 3, a crossroads 4. A street and its
  sidewalks leaving the same way are one arm, even when they reach different junctions next.

A decision is the arm someone leaves an intersection by, given the arm they came in on. Any trip can be
turned into its list of decisions:

    D = Decisions(World())
    D.trip_decisions(trip)  ->  [(intersection, arm_in, arm_out, t), ...]

Intersections with fewer than 3 arms are not decisions (a bend, two sidewalks merging); walking passes
through them. The thresholds are below and in method.md, section 2.
"""
import heapq
import math
from collections import Counter, defaultdict
from functools import lru_cache

from world import xy

MERGE_M = 20        # junctions joined by a path this short or shorter belong to the same intersection...
SPAN_M = 40         # ...as long as the intersection stays within this size (metres between its farthest junctions)
STUB_M = 15         # a dead-end branch shorter than this is not a road
SAME_ARM_DEG = 60   # branches toward the same next intersection within this angle are one arm
PARALLEL_DEG = 35   # branches leaving in about the same direction...
PARALLEL_M = 20     # ...that are still this close HEADING_M along (a street and its sidewalks) are one arm
HEADING_M = 40      # an arm's direction is measured where it is this far from the intersection's centre
LABEL_FRONT_DEG = 40  # for tables only: within this angle of straight ahead is "front"


def angle_diff(a, b):
    """Smallest absolute difference between two directions, in degrees."""
    return abs((math.degrees(a - b) + 180) % 360 - 180)


class Decisions:
    def __init__(self, world, merge_m=MERGE_M, span_m=SPAN_M, stub_m=STUB_M):
        self.w = world
        adj = world.adj
        self.n_nodes = len(adj)

        # 1. Stubs: short dead ends off a junction are not roads.
        self.stub = set()
        for n in range(self.n_nodes):
            if len(adj[n]) >= 3:
                for _, i in adj[n]:
                    end, length = self._raw_end(n, i)
                    if len(adj[end]) == 1 and length < stub_m:
                        self.stub.add((n, i))
        self.eff = [[(v, i) for v, i in adj[n] if (n, i) not in self.stub] for n in range(self.n_nodes)]
        junctions = [n for n in range(self.n_nodes) if len(self.eff[n]) >= 3]
        is_junction = set(junctions)

        # 2. Merge junctions joined by short paths into intersections, shortest links first.
        candidates = []
        for n in junctions:
            for _, i in self.eff[n]:
                end, length, _, mids, _, _ = self.follow(n, i, is_junction)
                if end in is_junction and end != n and length <= merge_m:
                    candidates.append((length, n, end))
        parent = {n: n for n in junctions}
        members = {n: [n] for n in junctions}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for _, a, b in sorted(candidates):
            ra, rb = find(a), find(b)
            if ra == rb:
                continue
            pts = members[ra] + members[rb]
            if max(math.dist(world.xy[p], world.xy[q]) for p in pts for q in pts) > span_m:
                continue
            parent[rb] = ra
            members[ra] = pts
            del members[rb]

        roots = sorted(members)
        self.members = [sorted(members[r]) for r in roots]
        self.cluster_of = {}
        for c, ms in enumerate(self.members):
            for n in ms:
                self.cluster_of[n] = c
        self.centre = [(sum(world.xy[n][0] for n in ms) / len(ms), sum(world.xy[n][1] for n in ms) / len(ms))
                       for ms in self.members]

        # 3. Paths between two junctions of the same intersection are inside it.
        self.inside = [set(ms) for ms in self.members]
        branches = defaultdict(list)   # intersection -> [(node, edge, end, metres, secs, chain nodes, last edge)]
        for c, ms in enumerate(self.members):
            for n in ms:
                for _, i in self.eff[n]:
                    end, length, secs, mids, last, edges = self.follow(n, i, is_junction)
                    if self.cluster_of.get(end) == c and length <= 2 * span_m:
                        self.inside[c].update(mids)
                    else:
                        branches[c].append((n, i, end, length, secs, mids, last, edges))
        for c, nodes in enumerate(self.inside):
            for n in nodes:
                self.cluster_of.setdefault(n, c)

        # 4. Arms: branches toward the same next intersection, in about the same direction, are one arm.
        self.arms = [[] for _ in self.members]
        self.branch_arm = {}
        for c in range(len(self.members)):
            for n, i, end, length, secs, mids, last, edges in sorted(branches[c], key=lambda b: (b[3], b[0], b[1])):
                dest = self.cluster_of.get(end) if end in is_junction else None
                head, point = self._heading(c, n, edges)
                arm = None
                for k, A in enumerate(self.arms[c]):
                    d = angle_diff(A["heading"], head)
                    if (dest is not None and A["dest"] == dest and d < SAME_ARM_DEG) or \
                            (d < PARALLEL_DEG and math.dist(A["point"], point) < PARALLEL_M):
                        arm = k
                        break
                if arm is None:
                    arm = len(self.arms[c])
                    self.arms[c].append({"dest": dest, "heading": head, "point": point, "branches": []})
                self.arms[c][arm]["branches"].append({"node": n, "edge": i, "end": end, "metres": length, "secs": secs,
                                                      "nodes": mids, "last": last})
                self.branch_arm[(n, i)] = (c, arm)
        for c, arms in enumerate(self.arms):
            for A in arms:
                A["main"] = min(A["branches"], key=lambda b: (b["metres"], b["node"], b["edge"]))
                names = Counter(world.edges[b["edge"]]["name"] for b in A["branches"])
                A["name"] = names.most_common(1)[0][0]
        self.is_decision = [len(a) >= 3 for a in self.arms]

    # ---------------- walking along the network ----------------
    def _raw_end(self, n, i):
        """Follow edge i from n through plain two-way nodes; (end node, metres)."""
        adj, e, a, length = self.w.adj, i, n, 0.0
        for _ in range(2000):
            E = self.w.edges[e]
            b = E["v"] if E["u"] == a else E["u"]
            length += E["len"]
            if len(adj[b]) != 2 or b == n:
                return b, length
            nxt = [j for _, j in adj[b] if j != e]
            if not nxt:
                return b, length
            a, e = b, nxt[0]
        return a, length

    def follow(self, n, i, is_junction):
        """Follow edge i from n through nodes that are not junctions (two real ways, stubs ignored).
        Returns (end node, metres, seconds, nodes passed on the way, last edge, edges walked)."""
        e, a, length, secs, mids, edges = i, n, 0.0, 0.0, [], []
        for _ in range(5000):
            E = self.w.edges[e]
            b = E["v"] if E["u"] == a else E["u"]
            length += E["len"]
            secs += E["secs"]
            edges.append(e)
            if b in is_junction or len(self.eff[b]) != 2 or b == n:
                return b, length, secs, mids, e, edges
            mids.append(b)
            nxt = [j for _, j in self.eff[b] if j != e]
            if not nxt:
                return b, length, secs, mids, e, edges
            a, e = b, nxt[0]
        return a, length, secs, mids, e, edges

    def _heading(self, c, n, edges):
        """Direction of a branch, from the intersection's centre to the first point of the road's shape that
        is HEADING_M from the centre (or the branch's end), and that point."""
        centre = self.centre[c]
        node, last = n, self.w.xy[n]
        for e in edges:
            E = self.w.edges[e]
            pts = [xy(*p) for p in (E["geom"] if E["u"] == node else E["geom"][::-1])]
            for p in pts[1:]:
                if math.dist(p, centre) >= HEADING_M:
                    d0, d1 = math.dist(last, centre), math.dist(p, centre)
                    f = (HEADING_M - d0) / (d1 - d0) if d1 > d0 else 1.0
                    f = min(1.0, max(0.0, f))
                    last = (last[0] + f * (p[0] - last[0]), last[1] + f * (p[1] - last[1]))
                    return math.atan2(last[1] - centre[1], last[0] - centre[0]), last
                last = p
            node = E["v"] if E["u"] == node else E["u"]
        if math.dist(last, centre) < 1:
            centre = self.w.xy[n]
        return math.atan2(last[1] - centre[1], last[0] - centre[0]), last

    # ---------------- trips as decisions ----------------
    def trip_decisions(self, trip):
        """[(intersection, arm in, arm out, time of arrival)] for every decision intersection a trip passes
        through, entering by one arm and leaving by one (the same arm means turning back)."""
        segs = trip["segments"]
        if not segs:
            return []
        nodes = [segs[0]["from"]] + [s["to"] for s in segs]
        times = [s["t"] for s in segs] + [trip["arrive"]]
        lab = [self.cluster_of.get(n) for n in nodes]
        out, k = [], 0
        while k < len(nodes):
            c = lab[k]
            if c is None:
                k += 1
                continue
            a = k
            while k + 1 < len(nodes) and lab[k + 1] == c:
                k += 1
            b = k
            if self.is_decision[c] and a > 0 and b < len(segs):
                ai = self.branch_arm.get((nodes[a], segs[a - 1]["edge"]))
                ao = self.branch_arm.get((nodes[b], segs[b]["edge"]))
                if ai and ao and ai[0] == c and ao[0] == c:
                    out.append((c, ai[1], ao[1], times[a]))
            k += 1
        return out

    def trip_end(self, trip):
        """(intersection, arm in) if the trip ends inside a decision intersection it walked into; else None.
        Used to count stopping ("stay") in the intersection tables."""
        segs = trip["segments"]
        if not segs:
            return None
        last = segs[-1]["to"]
        c = self.cluster_of.get(last)
        if c is None or not self.is_decision[c]:
            return None
        k = len(segs) - 1
        while k >= 0 and self.cluster_of.get(segs[k]["from"]) == c:
            k -= 1
        if k < 0:
            return None
        ai = self.branch_arm.get((segs[k]["to"], segs[k]["edge"]))
        return (c, ai[1]) if ai and ai[0] == c else None

    # ---------------- moving from one decision to the next ----------------
    @lru_cache(maxsize=None)
    def crossing_secs(self, c, n_in, n_out):
        """Quickest time inside intersection c from junction n_in to junction n_out."""
        if n_in == n_out:
            return 0.0
        inside = self.inside[c]
        dist, pq = {n_in: 0.0}, [(0.0, n_in)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == n_out:
                return d
            if d > dist.get(u, math.inf):
                continue
            for v, i in self.eff[u]:
                if v in inside:
                    nd = d + self.w.edges[i]["secs"]
                    if nd < dist.get(v, math.inf):
                        dist[v] = nd
                        heapq.heappush(pq, (nd, v))
        return math.dist(self.w.xy[n_in], self.w.xy[n_out]) / 1.35

    @lru_cache(maxsize=None)
    def step(self, c, arm):
        """Leave intersection c by an arm and walk on, through intersections with no choice, to the next
        decision. Returns (next intersection, arm arrived by, seconds, metres), or None if there is none.
        A dead end is walked to the end and back."""
        secs = metres = 0.0
        cur_c, cur_arm = c, arm
        for _ in range(60):
            br = self.arms[cur_c][cur_arm]["main"]
            secs += br["secs"]
            metres += br["metres"]
            nxt = self.branch_arm.get((br["end"], br["last"]))
            if nxt is None:       # dead end: walk back the same way
                secs += br["secs"]
                metres += br["metres"]
                nxt = (cur_c, cur_arm)
            c2, a2 = nxt
            if self.is_decision[c2]:
                return c2, a2, secs, metres
            others = [k for k in range(len(self.arms[c2])) if k != a2]
            out = others[0] if others else a2
            secs += self.crossing_secs(c2, self.arms[c2][a2]["main"]["node"], self.arms[c2][out]["main"]["node"])
            cur_c, cur_arm = c2, out
        return None

    def through_secs(self, c, arm_in, arm_out):
        return self.crossing_secs(c, self.arms[c][arm_in]["main"]["node"], self.arms[c][arm_out]["main"]["node"])

    # ---------------- describing choices ----------------
    def turn_angle(self, c, arm_in, arm_out):
        """Signed change of direction in degrees: 0 straight on, positive to the left, +-180 back."""
        h_in = self.arms[c][arm_in]["heading"] + math.pi   # the direction of travel when arriving
        h_out = self.arms[c][arm_out]["heading"]
        return (math.degrees(h_out - h_in) + 180) % 360 - 180

    def label(self, c, arm_in, arm_out):
        """F(ront), L(eft), R(ight) or B(ack), as in the project plan's table. For display only."""
        if arm_in == arm_out:
            return "B"
        d = self.turn_angle(c, arm_in, arm_out)
        if abs(d) <= LABEL_FRONT_DEG:
            return "F"
        if abs(d) >= 160:
            return "B"
        return "L" if d > 0 else "R"

    def options(self, c, arm_in):
        """Arms a person arriving by arm_in can leave by: all others, or back if there is no other."""
        k = [a for a in range(len(self.arms[c])) if a != arm_in]
        return k or [arm_in]

    def summary(self):
        n_arms = Counter(len(a) for a in self.arms)
        dec = sum(self.is_decision)
        return {"intersections": len(self.arms), "decision_intersections": dec,
                "arms": {k: n_arms[k] for k in sorted(n_arms)}, "stub_branches": len(self.stub)}
