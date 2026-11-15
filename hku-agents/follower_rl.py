"""A follower trained by Q-learning to follow one of the Agent World's people.

The Agent World run is replayed unchanged: its people walk exactly as they did. A follower is put a few seconds
behind one of them (its target) at the first junction of one of that person's trips. The follower is going
somewhere else: its destination and walking pace are those of a trip of a different, randomly chosen person.
So following pulls it one way and its own destination the other, and it has to learn when to keep following
and when to let go. Followers see only their target; nobody sees them.

The decision problem (one episode = one follower)
  Decision   at each junction, while the target is in view and has taken a road other than the follower's
             quickest road: FOLLOW (take the target's road) or LEAVE (take the quickest road to its own
             destination). If the target took the quickest road, the follower takes it too (and is rewarded: it
             is behind its target). Once it leaves, or the target is out of view, the chase is over and it walks
             the quickest path to its destination.
  In view    the target came to this junction by the follower's road at most V seconds before it. The map has
             no buildings, so a true line of sight cannot be computed.
  Reward     for closeness: each time it takes its target's road while the target is in view it earns
             R * (1 - gap / V), where gap is how many seconds behind the target it is: R right behind them,
             nothing at the edge of view. There is no separate reward for catching the target: being close is
             the whole reward, at every junction. (The script still counts who came within CATCH_S seconds of
             their target, as a statistic.) It starts START_GAP_S behind.
  Penalty    the follower remembers d_min, the shortest walking distance to its destination over every
             junction it has passed. A road that leaves it at distance d costs 0.5 * x^2, with
             x = max(0, d - d_min) / L. A little farther costs almost nothing; walking away costs more and more,
             and it keeps costing on the way back until the follower is as close as it had been.
  Roads      any road out of the junction, the one it came by included: a follower that lets go may turn back.
  Speed      while it follows, it also chooses how fast to go to the next junction, from five speeds given as
             multiples of its own comfortable walking speed (SPEEDS): walk 1.0, fast walk 1.30, jog 1.54, run
             2.61, sprint 4.33. For an adult who walks at 1.34 m/s these are 1.34, 1.74, 2.07 (the speed at
             which people change from walking to running), 3.5 (critical speed, the fastest speed a recreational
             runner can hold) and 5.8 m/s (an untrained adult's 100 m). It never overtakes its target (it
             reaches the next junction at least 1 s after them), so a faster speed only helps it keep up.
             After the chase it walks at its own pace.
  Stamina    a bar that only going faster than critical speed drains, as in the critical-speed model: the
             bar is D' = 130 m of running above critical speed, so a sprint lasts about a minute. Walking,
             fast walking, jogging and running at critical speed do not drain it. With the bar empty a
             sprint is only a run. The bar does not refill during a walk.
  Effort     draining the bar is penalised: SPRINT_COST times the share of the bar used on that stretch.
  End        when it takes the road its destination is on, or after MAX_STEPS junctions ("did not arrive").

What is learned
  A table Q[state, action], by one-step Q-learning: Q <- Q + alpha * (r + gamma * max Q[next state] - Q).
  The state is what the follower can know at the junction, in bins: how far beyond its closest point its
  quickest road leaves it, how far the target's road would, how many seconds behind the target it is, whether
  that gap is closing or widening, how full its stamina bar is, and how far it still is from its destination. So what it learns is a rule about distances and gaps, not a route on
  this map, and it can be tested on people it never trained on.
  Training and testing use different people: the people are split in two at random, followers are trained
  behind the trips of one half and tested behind the trips of the other. Exploration is epsilon-greedy, with
  epsilon falling from 1 to EPS_END. All episodes of an epoch are stepped together as tensors, on CUDA when
  there is a GPU and on the CPU otherwise; the results do not depend on the device.

What is reported (on the test people)
  T_k, the share of followers who trail the same stranger through k junctions in a row, at most FOLLOW_M
  behind along the road each time (the study's following rule, as in follower.py), and the average score
  (rewards minus penalties) per follower, for five kinds of walker in exactly the same episodes:
    Agent World     the test people's own trips: following by coincidence
    never           a follower that always leaves: someone who just happens to start behind the target
    rule, walking   follows while the target's road scores better at this junction alone (closeness reward
                    minus 0.5 x^2), at its own walking pace
    rule, with speed  the same rule for the road, and a rule for the speed: the slowest speed that brings it to
                    the next junction right behind its target, sprinting only until it has first come close.
                    It is told when its target reaches the next junction, which the learner cannot see
    Q-learning      the trained follower, choosing its road and its speed
    always          follows for as long as the target is in view, running: the most following there can be
  Q-learning should score at least as well as the rule and the two fixed walkers; the script says if it does.

    python follower_rl.py --run census_run
    python follower_rl.py --run census_run --device cuda --epochs 200
    python follower_rl.py --check            # test the code on trips made here; needs no run and no GPU

Writes out/<run>/analysis/follower_rl.md, follower_rl_tk.csv, follower_rl_curve.csv, follower_rl_policy.csv and
follower_rl_q.npy, and graphs/follower-rl.pdf.
"""
import argparse
import csv
import json
import math
import random
import time

import numpy as np
import torch

import config as C
from decisions import Decisions
from follower import Leaders, interval, t_k, trail_scan
from following import FOLLOW_M, KMAX, as_decisions
from world import World

REWARD = 1.0            # R
SCALE_M = 100.0         # L, metres: the unit of x in the penalty 0.5 * x^2
VIEW_S = 30.0           # V, seconds
START_GAP_S = 20.0      # the follower reaches the first junction this long after its target
CATCH_S = 5.0           # it has come close to its target when it reaches a junction at most this long after them
CATCH_REWARD = 0.0      # no reward for the catch itself (authors' decision): closeness is the reward
GAMMA = 1.0             # no discount: the follower maximises its total score over the walk
ALPHA = 0.2             # learning rate at the start; it falls to ALPHA / 10
EPS_END = 0.02
EPOCHS = 150
SEEDS = 3
MAX_STEPS = 400
TEST_SHARE = 0.5
X_EDGES = (1e-9, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0)   # bins of x (in units of L): 0, then up to each edge, then more
GAP_EDGES = (10.0, 20.0)                          # seconds behind the target
HERE_EDGES = (200.0, 500.0, 1000.0)               # metres still to the follower's destination
BAR_EDGES = (1 / 3, 2 / 3)                        # share of the stamina bar left
TREND_EDGES = (-2.0, 2.0)                         # seconds the gap changed since the last junction: closing, steady, widening
# Speeds while following, as multiples of the follower's own comfortable walking speed (sources in
# data/walking_speeds.csv). For an adult walking at 1.34 m/s: 1.34, 1.74, 2.07, 3.5 and 5.8 m/s.
SPEEDS = (1.0, 1.30, 1.54, 2.61, 4.33)
SPEED_NAMES = ("walk", "fast walk", "jog", "run", "sprint")
RUN = 3                                           # the level of critical speed: the fastest that does not drain the bar
D_PRIME_M = 130.0                                 # the stamina bar: metres of running above critical speed
SPRINT_COST = 1.0                                 # penalty for using the whole bar (the same size as one reward)
N_MODE = 3                                        # 0 no target, 1 target on the quickest road, 2 a real choice
NX, NG, NH = len(X_EDGES) + 1, len(GAP_EDGES) + 1, len(HERE_EDGES) + 1
NB, NT = len(BAR_EDGES) + 1, len(TREND_EDGES) + 1
N_STATES = N_MODE * NX * NX * NG * NH * NB * NT * 2    # the last 2: has it caught its target yet
N_ACT = 1 + len(SPEEDS)                           # 0 leave (and walk); 1.. follow at each speed
POLICIES = ("never", "rule", "rule_run", "q", "always")
NAMES = {"agents": "Agent World (coincidence)", "never": "Never follows", "rule": "Rule, walking",
         "rule_run": "Rule, with speed", "q": "Q-learning", "always": "Always follows, running"}


class Env:
    """The map and the Agent World trips as tensors, and the walk of many followers at once."""

    def __init__(self, D, trips, device, reward=REWARD, scale_m=SCALE_M, view_s=VIEW_S, gamma=GAMMA, start_gap=START_GAP_S):
        self.D, self.trips, self.dev, self.start_gap = D, trips, device, start_gap
        self.R, self.L, self.V, self.gamma = reward, scale_m, view_s, gamma
        w = D.w
        # decision states: a junction and the road arrived by
        self.sid, self.state = {}, []
        for c in range(len(D.arms)):
            if D.is_decision[c]:
                for ai in range(len(D.arms[c])):
                    self.sid[(c, ai)] = len(self.state)
                    self.state.append((c, ai))
        S = len(self.state)
        A = max(len(D.arms[c]) for c, _ in self.state)       # every road out, the road arrived by included
        valid = np.zeros((S, A), bool)
        nxt = np.zeros((S, A), np.int64)
        leg_s, leg_m, first_s = (np.zeros((S, A), np.float32) for _ in range(3))
        next_node, first_node = np.zeros((S, A), np.int64), np.zeros((S, A), np.int64)
        node = np.zeros(S, np.int64)
        for s, (c, ai) in enumerate(self.state):
            node[s] = D.arms[c][ai]["main"]["node"]
            for j, ao in enumerate(range(len(D.arms[c]))):
                st = D.step(c, ao)
                if st is None or (st[0], st[1]) not in self.sid:
                    continue
                c2, a2, secs, m = st
                cross = D.through_secs(c, ai, ao)
                br = D.arms[c][ao]["main"]
                e = w.edges[br["edge"]]
                valid[s, j], nxt[s, j] = True, self.sid[(c2, a2)]
                leg_s[s, j], leg_m[s, j] = cross + secs, m + cross * C.WALK_SPEED
                next_node[s, j] = D.arms[c2][a2]["main"]["node"]
                first_s[s, j], first_node[s, j] = e["secs"], e["v"] if e["u"] == br["node"] else e["u"]
        # walking time from every node to every destination used by a trip (daytime costs)
        dest_nodes = sorted({w.places[t["to"]]["node"] for t in trips})
        self.dest_of_node = {n: i for i, n in enumerate(dest_nodes)}
        rem = np.array([w.times_from(n) for n in dest_nodes], np.float32)
        # the trips as flat arrays
        off, l_sid, l_slot, l_t, l_ok = [0], [], [], [], []
        for t in trips:
            seq = t["seq"]
            for m, (c, ai, ao, tt) in enumerate(seq):
                s = self.sid[(c, ai)]
                slot = ao if valid[s, ao] else -1
                l_sid.append(s); l_slot.append(slot); l_t.append(tt)
                # can the chase go on to the trip's next recorded junction?
                l_ok.append(slot >= 0 and m + 1 < len(seq) and nxt[s, slot] == self.sid[(seq[m + 1][0], seq[m + 1][1])])
            off.append(len(l_sid))
        T = lambda a, dt=None: torch.as_tensor(np.asarray(a), dtype=dt, device=device)
        self.valid, self.nxt, self.leg_s, self.leg_m = T(valid), T(nxt), T(leg_s), T(leg_m)
        self.first_s, self.next_node, self.first_node, self.node = T(first_s), T(next_node), T(first_node), T(node)
        self.rem = T(rem)
        self.off, self.l_sid, self.l_slot = T(off, torch.int64), T(l_sid, torch.int64), T(l_slot, torch.int64)
        self.l_t, self.l_ok = T(l_t, torch.float64), T(l_ok, torch.bool)
        self.trip_dest = T([self.dest_of_node[w.places[t["to"]]["node"]] for t in trips], torch.int64)
        self.trip_pace = T([t["pace"] for t in trips], torch.float64)
        self.xe, self.ge, self.he = T(X_EDGES, torch.float32), T(GAP_EDGES, torch.float32), T(HERE_EDGES, torch.float32)
        self.be, self.te = T(BAR_EDGES, torch.float32), T(TREND_EDGES, torch.float32)
        self.speeds = T(SPEEDS, torch.float64)

    def episodes(self, leaders, rng):
        """For each leader trip, a donor trip of another person: the follower's destination and pace."""
        people = [self.trips[g]["agent"] for g in leaders]
        donors = []
        for a in people:
            while True:
                d = rng.randrange(len(self.trips))
                if self.trips[d]["agent"] != a:
                    donors.append(d)
                    break
        return torch.as_tensor(leaders, device=self.dev), torch.as_tensor(donors, device=self.dev)

    def run(self, lead, donor, policy, Q=None, eps=0.0, alpha=0.0, gen=None, record=False):
        """Walk one follower behind each leader trip. policy: never | rule | rule_run | always | q. With alpha > 0 the table
        Q is updated as they walk (Q-learning). Returns the score of each follower, and with record=True the
        walks. Episodes are independent of each other, so stepping them together changes nothing."""
        dev, B = self.dev, lead.numel()
        ar = torch.arange(B, device=dev)
        m = self.off[lead].clone()                            # index of the target's current decision
        m_end = self.off[lead + 1]
        s = self.l_sid[m].clone()
        t = self.l_t[m] + self.start_gap
        dest, pace = self.trip_dest[donor], self.trip_pace[donor]
        chasing = torch.ones(B, dtype=torch.bool, device=dev)
        alive = torch.ones(B, dtype=torch.bool, device=dev)
        arrived = torch.zeros(B, dtype=torch.bool, device=dev)
        d_min = torch.full((B,), math.inf, device=dev)
        score = torch.zeros(B, dtype=torch.float64, device=dev)
        metres = torch.zeros(B, dtype=torch.float64, device=dev)
        followed = torch.zeros(B, dtype=torch.int64, device=dev)
        bar = torch.ones(B, dtype=torch.float64, device=dev)       # share of the stamina bar left
        caught = torch.zeros(B, dtype=torch.bool, device=dev)
        prev_gap = torch.full((B,), float(self.start_gap), device=dev)
        used = torch.zeros(len(SPEEDS), dtype=torch.float64, device=dev)   # stretches followed at each speed
        prev_f = torch.zeros(B, dtype=torch.int64, device=dev)
        prev_a = torch.zeros(B, dtype=torch.int64, device=dev)
        prev_r = torch.zeros(B, device=dev)
        has_prev = torch.zeros(B, dtype=torch.bool, device=dev)
        log = []
        visits = torch.zeros((N_STATES, 2), device=dev) if record else None   # real choices: left, followed

        def learn(idx, target):
            """Q[f, a] <- Q[f, a] + alpha * mean over the followers that were there of (target - Q[f, a])."""
            if alpha <= 0 or idx.numel() == 0:
                return
            flat = prev_f[idx] * N_ACT + prev_a[idx]
            err = target - Q.view(-1)[flat]
            tot = torch.zeros(N_STATES * N_ACT, device=dev).index_add_(0, flat, err)
            cnt = torch.zeros(N_STATES * N_ACT, device=dev).index_add_(0, flat, torch.ones_like(err))
            Q.view(-1).add_(alpha * tot / cnt.clamp(min=1))

        for step in range(MAX_STEPS + 1):
            if not alive.any():
                break
            here = self.rem[dest, self.node[s]] * C.WALK_SPEED
            d_min = torch.minimum(d_min, here)
            at_dest = alive & (here <= 1e-3)
            via = torch.where(self.valid[s], self.first_s[s] + self.rem[dest[:, None], self.first_node[s]],
                              torch.full_like(self.first_s[s], math.inf))
            q_slot = via.argmin(1)
            ends = via < self.leg_s[s] - 1e-3                 # the destination is on this road
            after = torch.where(ends, torch.zeros_like(via), self.rem[dest[:, None], self.next_node[s]] * C.WALK_SPEED)
            x = (after - d_min[:, None]).clamp(min=0) / self.L
            gap = (t - self.l_t[m.clamp(max=self.l_t.numel() - 1)]).float()
            in_view = chasing & (m < m_end) & (gap <= self.V) & (gap >= 0)
            l_slot = torch.where(in_view, self.l_slot[m.clamp(max=self.l_slot.numel() - 1)], torch.full_like(q_slot, -1))
            in_view = in_view & (l_slot >= 0)
            l_safe = l_slot.clamp(min=0)
            xq, xl = x[ar, q_slot], x[ar, l_safe]
            mode = torch.where(~in_view, 0, torch.where(l_slot == q_slot, 1, 2))
            f = (((mode * NX + torch.bucketize(xq, self.xe)) * NX + torch.where(in_view, torch.bucketize(xl, self.xe), 0)) * NG
                 + torch.where(in_view, torch.bucketize(gap, self.ge), 0)) * NH + torch.bucketize(here, self.he)
            f = (f * NB + torch.bucketize(bar.float(), self.be)) * NT + torch.where(in_view, torch.bucketize(gap - prev_gap, self.te), 0)
            prev_gap = torch.where(in_view, gap, prev_gap)
            catch = alive & in_view & (gap <= CATCH_S) & ~caught          # it has just caught its target
            caught = caught | catch
            f = f * 2 + caught.long()
            bonus = torch.where(catch, CATCH_REWARD, 0.0)
            score += bonus.double()
            near = (self.R * (1 - gap / self.V)).clamp(min=0)             # the reward for closeness, if it follows

            # learn from the step just taken, now that the state it led to is known
            if alpha > 0:
                stay = Q[f, 1:].max(1).values
                value = torch.where(mode == 0, Q[f, 0], torch.where(mode == 1, stay, torch.maximum(Q[f, 0], stay)))
                value = torch.where(at_dest, torch.zeros_like(value), value)
                idx = (alive & has_prev).nonzero().squeeze(1)
                learn(idx, prev_r[idx] + bonus[idx] + self.gamma * value[idx])
            arrived |= at_dest
            alive = alive & ~at_dest
            if step == MAX_STEPS or not alive.any():
                break

            # choose the road (follow or leave) and, when following, the speed
            level = torch.zeros(B, dtype=torch.int64, device=dev)
            if policy == "never":
                want = torch.zeros(B, dtype=torch.bool, device=dev)
            elif policy == "always":
                want, level = torch.ones(B, dtype=torch.bool, device=dev), level + RUN
            elif policy in ("rule", "rule_run"):
                want = near - 0.5 * xl * xl >= -0.5 * xq * xq
                if policy == "rule_run":
                    # the slowest speed that brings it to the next junction right behind its target; faster than a
                    # run (a sprint) only until it has first come close, and only while there is stamina left
                    can = self.l_ok[m.clamp(max=self.l_ok.numel() - 1)] & (m + 1 < m_end)
                    room = (self.l_t[(m + 1).clamp(max=self.l_t.numel() - 1)] + 1.0 - t).clamp(min=1e-6)
                    need = self.leg_s[s, l_safe].double() / pace / room          # multiples of its walking speed
                    level = torch.bucketize(need, self.speeds).clamp(max=len(SPEEDS) - 1)
                    level = torch.where((level > RUN) & (caught | (bar <= 0)), RUN, level)
                    level = torch.where(can, level, 0)
            else:
                best_speed = Q[f, 1:].argmax(1)
                want, level = Q[f, 1:].max(1).values >= Q[f, 0], best_speed
                if eps > 0:
                    explore = torch.rand(B, device=dev, generator=gen) < eps
                    pick = torch.randint(0, N_ACT, (B,), device=dev, generator=gen)      # any action, with equal chance
                    any_speed = torch.randint(0, len(SPEEDS), (B,), device=dev, generator=gen)
                    want = torch.where(explore, pick > 0, want)
                    level = torch.where(explore, torch.where(pick > 0, pick - 1, any_speed), level)
            follow = (mode == 1) | ((mode == 2) & want)
            level = torch.where(follow, level, 0)
            act = torch.where(follow, level + 1, 0)
            j = torch.where(follow, l_safe, q_slot)
            end_now = alive & ends[ar, j]

            # the time to the next junction at that speed; never overtake the target; drain the bar above critical speed
            mult = self.speeds[level]
            mult = torch.where((level > RUN) & (bar <= 0), self.speeds[RUN], mult)       # no stamina left: a run
            own = self.leg_s[s, j].double() / pace                                       # seconds at its own walking pace
            t2 = t + own / mult
            go_on = follow & self.l_ok[m.clamp(max=self.l_ok.numel() - 1)] & (m + 1 < m_end)
            t2 = torch.where(go_on, torch.maximum(t2, self.l_t[(m + 1).clamp(max=self.l_t.numel() - 1)] + 1.0), t2)
            dur = (t2 - t).clamp(min=1e-6)
            above = (own / dur - self.speeds[RUN] - 1e-9).clamp(min=0)                   # multiples of walking speed above critical speed
            drain = torch.minimum(above * C.WALK_SPEED * dur / D_PRIME_M, bar)
            drain = torch.where(follow, drain, torch.zeros_like(drain))
            r = torch.where(follow, near, torch.zeros_like(near)) - 0.5 * x[ar, j] ** 2 - SPRINT_COST * drain.float()
            if record:
                choice = alive & (mode == 2)
                visits.view(-1).index_add_(0, (f * 2 + follow.long())[choice], torch.ones(int(choice.sum()), device=dev))
                used.index_add_(0, level[alive & follow], torch.ones(int((alive & follow).sum()), dtype=torch.float64, device=dev))
                log.append((alive.clone(), s.clone(), j.clone(), t.clone(), metres.clone()))
            score += torch.where(alive, r.double(), 0.0)
            followed += (alive & follow).long()
            bar = torch.where(alive, bar - drain, bar)

            # move on
            if alpha > 0:
                idx = end_now.nonzero().squeeze(1)
                prev_f, prev_a, prev_r = torch.where(alive, f, prev_f), torch.where(alive, act, prev_a), torch.where(alive, r, prev_r)
                learn(idx, prev_r[idx])
                has_prev = alive & ~end_now
            arrived |= end_now
            moving = alive & ~end_now
            metres = torch.where(moving, metres + self.leg_m[s, j].double(), metres)
            s = torch.where(moving, self.nxt[s, j], s)
            t = torch.where(moving, t2, t)
            m = torch.where(moving & go_on, m + 1, m)
            chasing = chasing & go_on
            alive = moving
        out = {"score": score, "arrived": arrived, "followed": followed, "bar_left": bar, "caught": caught}
        if record:
            out["visits"], out["speeds"] = visits, used
            out["walks"] = self._walks(lead, donor, log)
        return out

    def _walks(self, lead, donor, log):
        """The recorded steps as walks in the form the following measure uses."""
        B = lead.numel()
        seqs, tts, dds = [[] for _ in range(B)], [[] for _ in range(B)], [[] for _ in range(B)]
        for alive, s, j, t, metres in log:
            idx = alive.nonzero().squeeze(1).tolist()
            sv, jv, tv, mv = s[alive].tolist(), j[alive].tolist(), t[alive].tolist(), metres[alive].tolist()
            for i, si, ji, ti, mi in zip(idx, sv, jv, tv, mv):
                c, ai = self.state[si]
                seqs[i].append((c, ai, ji, ti))
                tts[i].append(ti)
                dds[i].append(mi)
        walks = []
        for i, (g, d) in enumerate(zip(lead.tolist(), donor.tolist())):
            if not seqs[i]:
                continue
            v = self.trips[d]["pace"] * C.WALK_SPEED          # it walked up to the first junction at its own pace
            walks.append({"agent": "F" + self.trips[g]["agent"], "seq": seqs[i], "depart": seqs[i][0][3],
                          "tt": [tts[i][0] - 120.0] + tts[i], "dd": [-120.0 * v] + dds[i]})
        return walks


def train(env, lead, seed, epochs=EPOCHS, alpha=ALPHA, eps_end=EPS_END, valid=None, log=None):
    """Q-learning behind the given leader trips. Every epoch draws new destinations for the followers."""
    dev = env.dev
    Q = torch.zeros((N_STATES, N_ACT), device=dev)
    gen = torch.Generator(device=dev).manual_seed(seed)
    rng = random.Random(seed)
    for ep in range(epochs):
        frac = ep / max(1, epochs - 1)
        eps = max(eps_end, 1.0 - frac / 0.7 * (1.0 - eps_end))     # falls to eps_end at 70% of the epochs
        a = alpha * (0.1 ** frac)
        L, Dn = env.episodes(lead, rng)
        out = env.run(L, Dn, "q", Q=Q, eps=eps, alpha=a, gen=gen)
        if log is not None and (ep % 5 == 0 or ep == epochs - 1):
            row = {"seed": seed, "epoch": ep, "epsilon": round(eps, 3), "alpha": round(a, 4),
                   "train_score": round(out["score"].mean().item(), 4)}
            if valid is not None:
                row["test_score_greedy"] = round(env.run(*valid, "q", Q=Q)["score"].mean().item(), 4)
            log.append(row)
    return Q


def evaluate(env, leaders_index, L, Dn, policy, Q=None):
    out = env.run(L, Dn, policy, Q=Q, record=True)
    rows = trail_scan(out["walks"], leaders_index)
    return {"rows": rows, "score": out["score"].mean().item(), "arrived": out["arrived"].float().mean().item(),
            "followed": out["followed"].double().mean().item(), "visits": out["visits"].cpu().numpy(),
            "speeds": (out["speeds"] / out["speeds"].sum().clamp(min=1)).tolist(),
            "caught": out["caught"].float().mean().item(),
            "bar_used": 1 - out["bar_left"].mean().item(), "sprinted": (out["bar_left"] < 1 - 1e-9).double().mean().item(),
            "junctions": sum(len(w["seq"]) for w in out["walks"]) / max(1, len(out["walks"]))}


def paired(rows_a, rows_b, k):
    """Matched pairs by person: for every test person, the share of their trips on which walker B trails the same
    stranger through k junctions, minus the same share for walker A. Returns the mean difference over people, its
    95% t-interval (mean +- t* s / sqrt(n)) and the number of people. A person is one observation, so several
    trips by one person do not count as independent, and both walkers are compared behind the same trips."""
    from scipy import stats

    def by_person(rows):
        n, hit = {}, {}
        for r in rows:
            a = r["agent"].lstrip("F")                  # a follower is filed under the person it walked behind
            n[a] = n.get(a, 0) + 1
            hit[a] = hit.get(a, 0) + (r["max"] >= k)
        return {a: hit[a] / n[a] for a in n}
    A, B = by_person(rows_a), by_person(rows_b)
    d = np.array([B[a] - A[a] for a in sorted(A) if a in B])
    mean, se = float(d.mean()), float(d.std(ddof=1) / math.sqrt(len(d)))
    half = float(stats.t.ppf(0.975, len(d) - 1)) * se
    return {"diff": mean, "lo": mean - half, "hi": mean + half, "people": len(d), "t": mean / se if se else float("inf")}


def policy_table(Q, visits):
    """What was learned, where the test followers had a real choice: by how far the target's road would take the
    follower beyond its closest point, the share of those choices in which the table says FOLLOW."""
    q = Q.cpu().numpy().reshape(N_MODE, NX, NX, NG, NH, NB, NT, 2, N_ACT)[2]
    v = visits.reshape(N_MODE, NX, NX, NG, NH, NB, NT, 2, 2)[2].sum(-1)
    says = (q[..., 1:].max(-1) >= q[..., 0])
    edges = [0.0] + [e for e in X_EDGES[1:]]
    rows = []
    for b in range(NX):
        n = v[:, b].sum()
        lo = "0" if b == 0 else f"{edges[b - 1] * SCALE_M:.0f}"
        label = "0 m (not beyond its closest point)" if b == 0 else (f"{lo} to {edges[b] * SCALE_M:.0f} m" if b < NX - 1 else f"over {lo} m")
        rows.append({"target_road_beyond_closest": label, "choices": int(n),
                     "follow_share": float((v[:, b] * says[:, b]).sum() / n) if n else float("nan")})
    return rows


def figure(tk, curve, run, suffix=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from make_figures import save
    from make_following_figures import BLUE, GREEN, GRID, MUTED, ORANGE, PURPLE

    look = {"agents": (BLUE, "o"), "never": (MUTED, "D"), "rule": (GREEN, "^"), "rule_run": (GREEN, "P"), "q": (PURPLE, "v"),
            "always": (ORANGE, "s")}
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.7))
    k = [r["k"] for r in tk]
    for key, (col, mk) in look.items():
        a.plot(k, [100 * r[key] for r in tk], color=col, lw=1.6, marker=mk, ms=4, mec="white", mew=0.7, label=NAMES[key])
    a.set_xlabel("Junctions in a row, $k$")
    a.set_ylabel("Walkers trailing the same stranger (%)")
    a.set_xticks(k)
    a.set_ylim(0, 100)
    a.legend(frameon=False, fontsize=6, loc="upper right")
    for seed in sorted({r["seed"] for r in curve}):
        rs = [r for r in curve if r["seed"] == seed]
        b.plot([r["epoch"] for r in rs], [r["test_score_greedy"] for r in rs], color=PURPLE, lw=1.2, alpha=0.7)
    b.set_xlabel("Training epoch")
    b.set_ylabel("Score per follower on the test people")
    for ax in (a, b):
        ax.grid(axis="y", color=GRID, lw=0.5)
    fig.tight_layout()
    save(fig, ("follower-rl" if run == "census_run" else f"follower-rl-{run}") + suffix.replace("_", "-"))


def split_people(trips, seed, test_share=TEST_SHARE):
    people = sorted({t["agent"] for t in trips})
    random.Random(seed).shuffle(people)
    test = set(people[:int(len(people) * test_share)])
    tr = [g for g, t in enumerate(trips) if t["agent"] not in test]
    te = [g for g, t in enumerate(trips) if t["agent"] in test]
    return tr, te


def check(device):
    """Test the code on trips made here (random place to random place by the quickest path)."""
    world = World()
    D = Decisions(world)
    rng = random.Random(7)
    codes, raw = sorted(world.places), []
    while len(raw) < 4000:
        a, b = rng.choice(codes), rng.choice(codes)
        if world.places[a]["node"] == world.places[b]["node"]:
            continue
        depart = rng.randrange(8 * 3600, 18 * 3600)
        wk = world.walk(world.places[a]["node"], world.places[b]["node"], depart)
        raw.append({"agent": f"T{len(raw) % 800:05d}", "from": a, "to": b, "depart": depart, "pace": 1.0, "kind": "go",
                    "arrive": wk["arrive"], "segments": wk["segments"]})
    trips = [t for t in as_decisions(D, raw) if t["seq"]]
    env = Env(D, trips, device)
    tr, te = split_people(trips, 7)
    L, Dn = env.episodes(te, random.Random(1))
    # 1. a follower given its target's own destination and told to follow always walks its target's route
    same = env.run(L, L, "always", record=True)
    ok = sum([x[:3] for x in w["seq"]] == [x[:3] for x in trips[g]["seq"]] for w, g in zip(same["walks"], te))
    assert ok >= 0.99 * len(te), f"only {ok} of {len(te)} followers with their target's destination repeat its route"
    assert same["arrived"].all(), "a follower with its target's destination did not arrive"
    assert (same["score"] > 0).all(), "a follower on its target's own route was not rewarded"
    # 2. a follower that never follows walks the quickest path to its own destination: no penalty, and it arrives
    never = env.run(L, Dn, "never")
    assert never["arrived"].all() and float(never["score"].min()) >= -1e-6, "never-follow walkers were penalised or lost"
    # 3. the same seed gives the same table; learning beats the fixed walkers on people it did not train on
    Q = train(env, tr, seed=1, epochs=40)
    Q2 = train(env, tr, seed=1, epochs=40)
    assert torch.equal(Q, Q2), "two trainings with one seed differ"
    sc = {p: env.run(L, Dn, p, Q=Q)["score"].mean().item() for p in POLICIES}
    assert sc["q"] >= max(sc["never"], sc["always"]) - 1e-6, f"Q-learning scores below a fixed walker: {sc}"
    assert sc["q"] >= sc["rule"] - 0.05, f"Q-learning scores below the walking rule: {sc}"
    # (the rule with speed is told when its target reaches the next junction, which the learner cannot see, so it
    # may score a little higher: it is reported, not required)
    assert sc["q"] >= 0.9 * sc["rule_run"], f"Q-learning scores far below the rule with speed: {sc}"
    # 4. only going faster than critical speed drains the bar, and a sprint is paid for
    L2 = L[:500]
    for lv, name in enumerate(SPEED_NAMES):
        Qf = torch.full((N_STATES, N_ACT), -1.0, device=device)
        Qf[:, lv + 1] = 1.0                                   # a table that always follows at this speed
        o = env.run(L2, L2, "q", Q=Qf)
        drained = float((1 - o["bar_left"]).max())
        assert (drained > 1e-6) == (lv > RUN), f"{name}: the stamina bar {'was' if drained > 1e-6 else 'was not'} drained"
    print(f"checks passed on {len(trips):,} quickest-path trips ({device}). Score per follower on the test half: "
          + ", ".join(f"{NAMES[p]} {sc[p]:.3f}" for p in POLICIES))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="census_run", help="the Agent World run whose people are followed")
    ap.add_argument("--device", default="auto", help="auto (CUDA if there is a GPU), cuda or cpu")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--seeds", type=int, default=SEEDS, help="trainings with different random numbers")
    ap.add_argument("--reward", type=float, default=REWARD, help="R")
    ap.add_argument("--scale", type=float, default=SCALE_M, help="L, metres")
    ap.add_argument("--view", type=float, default=VIEW_S, help="V, seconds")
    ap.add_argument("--gamma", type=float, default=GAMMA)
    ap.add_argument("--start-gap", type=float, default=START_GAP_S, help="seconds behind its target at the start")
    ap.add_argument("--suffix", default="", help="added to the names of the files written, e.g. _start5")
    ap.add_argument("--reuse", action="store_true", help="use the table saved by an earlier run instead of training again")
    ap.add_argument("--boot", type=int, default=500, help="bootstrap resamples of people")
    ap.add_argument("--check", action="store_true", help="test the code on trips made here, then stop")
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args()
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else
                          "cpu" if args.device == "auto" else args.device)
    if args.check:
        check(device)
        return

    run_dir = C.OUT / args.run
    if not (run_dir / "trips.jsonl").exists():
        raise SystemExit(f"out/{args.run}/trips.jsonl not found (unpack trips.jsonl.gz, or run the Agent World first).")
    out_dir = run_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    world = World()
    D = Decisions(world)
    print(f"loading the Agent World trips of {args.run}; device: {device}", flush=True)
    with open(run_dir / "trips.jsonl", encoding="utf-8") as f:
        raw = [t for t in map(json.loads, f) if t["segments"]]
    trips = [t for t in as_decisions(D, raw) if t["seq"]]
    del raw
    env = Env(D, trips, device, reward=args.reward, scale_m=args.scale, view_s=args.view, gamma=args.gamma,
              start_gap=args.start_gap)
    tr, te = split_people(trips, seed=7)
    n_people = len({t["agent"] for t in trips})
    print(f"{len(trips):,} trips of {n_people:,} people; training behind {len(tr):,} trips, testing behind {len(te):,}", flush=True)
    L, Dn = env.episodes(te, random.Random(7))             # the test episodes are the same for every walker
    index = Leaders(trips)

    res = {p: evaluate(env, index, L, Dn, p) for p in ("never", "rule", "rule_run", "always")}
    base = trail_scan([trips[g] for g in te], index)
    curve, runs, tables = [], [], []
    saved = out_dir / f"follower_rl_q{args.suffix}.npy"
    if args.reuse:
        if not saved.exists():
            raise SystemExit(f"{saved} not found: run once without --reuse")
        tables.append(torch.as_tensor(np.load(saved), device=device))
        runs.append(evaluate(env, index, L, Dn, "q", Q=tables[0]))
        with open(out_dir / f"follower_rl_curve{args.suffix}.csv") as f:
            curve = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    for seed in range(1, (0 if args.reuse else args.seeds) + 1):
        t0 = time.time()
        Q = train(env, tr, seed, epochs=args.epochs, valid=(L, Dn), log=curve)
        runs.append(evaluate(env, index, L, Dn, "q", Q=Q))
        tables.append(Q)
        print(f"seed {seed}: score {runs[-1]['score']:.3f}, T_3 {t_k(runs[-1]['rows'], 3):.3f}, {time.time() - t0:.0f} s", flush=True)
    best = max(range(len(runs)), key=lambda i: runs[i]["score"])
    res["q"] = runs[best]
    if not args.reuse:
        np.save(saved, tables[best].cpu().numpy())

    # matched pairs by person: each walker against the never-follow walker, and against the people's own trips
    pairs = []
    for k in (3, 5, 10):
        for a, b in [("never", p) for p in ("rule", "rule_run", "q", "always")] + [("agents", "never"), ("agents", "q"), ("rule_run", "q")]:
            ra = base if a == "agents" else res[a]["rows"]
            pairs.append({"k": k, "walker": NAMES[b], "minus": NAMES[a], **paired(ra, res[b]["rows"], k)})
    with open(out_dir / f"follower_rl_paired{args.suffix}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0]))
        w.writeheader()
        w.writerows({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in pairs)

    tk = []
    for k in range(1, KMAX + 1):
        row = {"k": k, "agents": t_k(base, k)}
        row["agents_lo"], row["agents_hi"] = interval(base, k, args.boot)
        for p in POLICIES:
            row[p] = t_k(res[p]["rows"], k)
            row[p + "_lo"], row[p + "_hi"] = interval(res[p]["rows"], k, args.boot)
        tk.append(row)
    for name, rows in ((f"follower_rl_tk{args.suffix}.csv", [{k: (v if k == "k" else round(v, 4)) for k, v in r.items()} for r in tk]),
                       (f"follower_rl_curve{args.suffix}.csv", curve)):
        if args.reuse and "curve" in name:
            continue
        with open(out_dir / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    pol = policy_table(tables[best], res["q"]["visits"])
    with open(out_dir / f"follower_rl_policy{args.suffix}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pol[0]))
        w.writeheader()
        w.writerows({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in pol)

    pct = lambda x: f"{100 * x:.1f}%"
    ci = lambda r, key: f"{pct(r[key])} ({pct(r[key + '_lo'])} to {pct(r[key + '_hi'])})"
    scores = [r["score"] for r in runs]
    sd = float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0
    t3 = [t_k(r["rows"], 3) for r in runs]
    beats = res["q"]["score"] >= max(res[p]["score"] for p in ("never", "rule", "always")) - 1e-9
    vs_speed = res["q"]["score"] - res["rule_run"]["score"]
    M = [f"# The Q-learning follower: {args.run}", "",
         f"{len(trips):,} Agent World trips of {n_people:,} people. The people are split in two at random: followers are "
         f"trained behind the {len(tr):,} trips of one half and tested behind the {len(te):,} trips of the other. A follower "
         f"starts {args.start_gap:g} s behind its target at the first junction of the target's trip; its destination and pace "
         f"are those of a trip of a different, randomly chosen person. Reward for closeness, R (1 - gap / {args.view:g} s) with R = {args.reward:g}, each "
         f"time it takes its target's road while the target is in view (no separate reward for catching it); penalty 0.5 x^2 for a road that leaves it x beyond "
         f"the closest it has been to its destination, x in units of {args.scale:g} m. While it follows it chooses its "
         f"speed: " + ", ".join(f"{n} {m:g}" for n, m in zip(SPEED_NAMES, SPEEDS)) + " times its own walking speed. Only "
         f"going faster than a run drains its stamina bar ({D_PRIME_M:g} m above critical speed), and using the whole bar "
         f"costs {SPRINT_COST:g}. Q-learning: {args.epochs} epochs, "
         f"gamma {args.gamma:g}, {args.seeds} trainings; the tables below use the training with the best test score. "
         f"Device: {device}.", "",
         "## Score per follower on the test people (rewards minus penalties)", "",
         "| Walker | Score | Came within " + f"{CATCH_S:g} s" + " of its target | Junctions passed | Junctions where it followed | Arrived |", "|---|---|---|---|---|---|"]
    for p in POLICIES:
        r = res[p]
        extra = f" (trainings: {np.mean(scores):.3f} ± {sd:.3f})" if p == "q" and len(scores) > 1 else ""
        M.append(f"| {NAMES[p]} | {r['score']:.3f}{extra} | {pct(r['caught'])} | {r['junctions']:.1f} | {r['followed']:.1f} | {pct(r['arrived'])} |")
    M += ["", ("Q-learning scores at least as well as the walkers that never follow, always follow, or follow by the "
               "walking rule, as it should." if beats else
               "**Q-learning scores below a simple fixed walker: it has not learned enough. Train for longer.**"),
          f"Against the rule with speed it scores {vs_speed:+.3f}. That rule is told when its target will reach the next "
          f"junction and sets its speed to match; the learner only sees its gap and whether it is closing.", "",
          "## Share of walkers trailing the same stranger through k junctions", "",
          f"At most {FOLLOW_M} m behind along the road each time. In brackets: 95% bootstrap interval, resampling people.", "",
          "| k | " + " | ".join(NAMES[p] for p in ("agents",) + POLICIES) + " |", "|---|" + "---|" * (len(POLICIES) + 1)]
    for r in tk:
        if r["k"] in (1, 2, 3, 4, 5, 6, 8, 10):
            M.append(f"| {r['k']} | " + " | ".join(ci(r, p) for p in ("agents",) + POLICIES) + " |")
    M += ["", "## Differences, as matched pairs by person", "",
          "For every test person: the share of their trips on which one walker trails the same stranger through k "
          "junctions, minus the same share for another walker behind the same trips. The table gives the mean "
          "difference over people in percentage points, with its 95% t-interval (mean ± t* s / √n). A person is one "
          "observation, so several trips by one person are not counted as independent.", "",
          "| k | Walker | minus | Difference (points) | 95% interval | People |", "|---|---|---|---|---|---|"]
    for r in pairs:
        M.append(f"| {r['k']} | {r['walker']} | {r['minus']} | {100 * r['diff']:+.1f} | {100 * r['lo']:+.1f} to {100 * r['hi']:+.1f} | {r['people']:,} |")
    M += ["", f"Q-learning, T_3 over the {len(runs)} trainings: " + ", ".join(pct(x) for x in t3) + ".", "",
          "## What the follower learned", "",
          "Where a test follower had a real choice (its target took a road other than its quickest road), the share of "
          "those choices in which the learned table says follow:", "",
          "| The target's road would leave it beyond its closest point by | Choices | Follows |", "|---|---|---|"]
    for r in pol:
        M.append(f"| {r['target_road_beyond_closest']} | {r['choices']:,} | {pct(r['follow_share']) if r['choices'] else ''} |")
    M += ["", f"The one-junction rule follows up to {args.scale * math.sqrt(2 * args.reward):.0f} m when it is right behind its "
          f"target, less when it is farther back, and never beyond.", "",
          "## The speed the Q-learning follower chose", "",
          "Of the stretches on which it followed its target (the speed it asked for; it never overtakes, so it may "
          "have gone slower):", "",
          "| " + " | ".join(SPEED_NAMES) + " |", "|" + "---|" * len(SPEEDS),
          "| " + " | ".join(pct(x) for x in res["q"]["speeds"]) + " |", "",
          f"Followers who used any of their stamina bar: {pct(res['q']['sprinted'])}. Average share of the bar used: "
          f"{pct(res['q']['bar_used'])}.", "",
          "Tables: follower_rl_tk.csv, follower_rl_curve.csv (learning curve), follower_rl_policy.csv, follower_rl_q.npy "
          "(the learned table). Figure: graphs/follower-rl.pdf."]
    (out_dir / f"follower_rl{args.suffix}.md").write_text("\n".join(M) + "\n", encoding="utf-8")
    if not args.no_figure:
        figure(tk, curve, args.run, args.suffix)
    print(f"wrote {out_dir / 'follower_rl.md'}")


if __name__ == "__main__":
    main()
