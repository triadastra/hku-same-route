"""Extra tables and figures asked for by the authors after the final runs. Reads a finished run; costs nothing.

  out/<run>/analysis/model_tests.md      the three Markov chains (momentum, counted, counted + imitation) against
                                         the Agent World, with the chi-square test and the G-test
  out/<run>/analysis/model_tests.csv     the same tests per junction and path in
  out/<run>/analysis/net_flow.csv        per path and part of the day: people each way, net, momentum-weighted net
  graphs/movement-bars.pdf               composite bar charts: when, how far and how fast each kind of person walks
  graphs/road-choice-bars.pdf            composite bar charts: which path people and each chain take at a junction
  graphs/net-flow.pdf                    map of net flow (one way minus the other), plain and momentum-weighted

Run:  python hku-agents/extra_analysis.py --run census_run --control census_control
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats

import config as C
import following as F
from decisions import Decisions
from world import World, xy

BLUE, ORANGE, GREEN, YELLOW, PURPLE = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"
INK, MUTED, GRID, PALE = "#1f2423", "#6b7370", "#e3e6e4", "#c9cecb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.labelcolor": INK})
GRAPHS = C.ROOT.parent / "graphs"
MIN_PASSES = 30
CHAINS = [("momentum", f"Markov: momentum (kappa {F.KAPPA:g})"), ("counted", "Markov: counted"),
          ("imitate", f"Markov: counted + imitation (rho {F.RHO:g})")]
PERIODS = [("morning", "Morning, 06:00 to 12:00", 6, 12), ("evening", "Evening, 16:00 to 22:00", 16, 22)]


def save(fig, name):
    GRAPHS.mkdir(exist_ok=True)
    fig.savefig(GRAPHS / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(GRAPHS / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def pct(x):
    return "n/a" if x != x else f"{100 * x:.1f}%"


# ---------------- 1. tests ----------------
def state_counts(trips_lists):
    """(junction, path in) -> Counter of path out, over one or more sets of trips."""
    cnt = defaultdict(Counter)
    for trips in trips_lists:
        for t in trips:
            for c, ai, ao, _ in t["seq"]:
                cnt[(c, ai)][ao] += 1
    return cnt


def two_sample(D, a_counts, b_counts):
    """Per (junction, path in) with at least MIN_PASSES in both: are the paths out chosen in the same proportions
    in a and in b? Pearson chi-square and G-test (likelihood ratio) on the 2 x paths table; turning back left out."""
    rows = []
    for (c, ai), ca in sorted(a_counts.items()):
        cb = b_counts.get((c, ai))
        if not cb:
            continue
        opts = [o for o in D.options(c, ai) if o != ai and ca.get(o, 0) + cb.get(o, 0) > 0]
        a = [ca.get(o, 0) for o in opts]
        b = [cb.get(o, 0) for o in opts]
        if len(opts) < 2 or sum(a) < MIN_PASSES or sum(b) < MIN_PASSES:
            continue
        table = np.array([a, b])
        chi2, p_chi, dof, exp = stats.chi2_contingency(table, correction=False)
        g, p_g, _, _ = stats.chi2_contingency(table, correction=False, lambda_="log-likelihood")
        n = table.sum()
        tvd = 0.5 * sum(abs(x / sum(a) - y / sum(b)) for x, y in zip(a, b))
        rows.append({"c": c, "ai": ai, "roads": len(D.arms[c]), "n_a": sum(a), "n_b": sum(b), "dof": dof,
                     "chi2": chi2, "p_chi": p_chi, "g": g, "p_g": p_g, "v": math.sqrt(chi2 / n), "tvd": tvd,
                     "exp5": bool((exp >= 5).all())})
    if rows:
        for key in ("p_chi", "p_g"):
            adj = stats.false_discovery_control([r[key] for r in rows], method="bh")
            for r, x in zip(rows, adj):
                r[key + "_bh"] = x
    return rows


def summarise(rows):
    if not rows:
        return None
    n = len(rows)
    med = lambda k: sorted(r[k] for r in rows)[n // 2]
    big = [r for r in rows if r["exp5"]]
    w = sum(r["n_a"] for r in rows)
    return {"n": n, "chi": sum(r["p_chi_bh"] < 0.05 for r in rows) / n, "g": sum(r["p_g_bh"] < 0.05 for r in rows) / n,
            "chi_exp5": sum(r["p_chi_bh"] < 0.05 for r in big) / len(big) if big else float("nan"), "n_exp5": len(big),
            "v": med("v"), "tvd": med("tvd"), "tvd_w": sum(r["tvd"] * r["n_a"] for r in rows) / w}


def pooled(D, a_counts, b_counts):
    """All junctions pooled by the label of the choice (front, left, right): one 2 x 3 table."""
    def by_label(cnt):
        out = Counter()
        for (c, ai), cc in cnt.items():
            for ao, n in cc.items():
                if ao != ai:
                    out[D.label(c, ai, ao)] += n
        return out
    a, b = by_label(a_counts), by_label(b_counts)
    labels = [l for l in "FLRB" if a[l] + b[l] > 0]
    table = np.array([[a[l] for l in labels], [b[l] for l in labels]])
    chi2, p, dof, _ = stats.chi2_contingency(table, correction=False)
    g, pg, _, _ = stats.chi2_contingency(table, correction=False, lambda_="log-likelihood")
    return {"chi2": chi2, "p": p, "g": g, "pg": pg, "dof": dof, "v": math.sqrt(chi2 / table.sum()),
            "a": {l: a[l] / sum(a.values()) for l in labels}, "b": {l: b[l] / sum(b.values()) for l in labels}}


def pair_test(qa, qb, k):
    """Pairs arriving together: same next k decisions, yes or no, in a against b. 2 x 2 chi-square and G-test."""
    table = np.array([[qa[1][k], qa[0][k] - qa[1][k]], [qb[1][k], qb[0][k] - qb[1][k]]])
    chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
    g, pg, _, _ = stats.chi2_contingency(table, correction=False, lambda_="log-likelihood")
    return {"a": qa[1][k] / qa[0][k], "b": qb[1][k] / qb[0][k], "chi2": chi2, "p": p, "g": g, "pg": pg,
            "phi": math.sqrt(chi2 / table.sum()), "pairs_a": qa[0][k], "pairs_b": qb[0][k]}


def fmt_p(p):
    return "< 1e-300" if p == 0 else f"{p:.3g}"


def tests(D, agents, walkers, out, run):
    a_counts = state_counts([agents])
    w_counts = {n: state_counts(walkers[n]) for n, _ in CHAINS}
    rows = {n: two_sample(D, a_counts, w_counts[n]) for n, _ in CHAINS}
    noise = two_sample(D, state_counts(walkers["counted"][:1]), state_counts(walkers["counted"][1:2]))
    half = [[t for t in agents if int(t["agent"][1:]) % 2 == r] for r in (0, 1)]
    split = two_sample(D, state_counts([half[0]]), state_counts([half[1]]))

    with open(out / "model_tests.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "junction", "path_in", "paths", "passes_agents", "passes_model", "dof", "chi2", "p_chi2",
                    "p_chi2_bh", "g", "p_g", "p_g_bh", "cramers_v", "tvd", "all_expected_5_or_more"])
        for n, _ in CHAINS:
            for r in rows[n]:
                w.writerow([n, r["c"], r["ai"], r["roads"], r["n_a"], r["n_b"], r["dof"], round(r["chi2"], 2),
                            f"{r['p_chi']:.3g}", f"{r['p_chi_bh']:.3g}", round(r["g"], 2), f"{r['p_g']:.3g}",
                            f"{r['p_g_bh']:.3g}", round(r["v"], 3), round(r["tvd"], 3), int(r["exp5"])])

    F.D_GLOBAL = D
    q = {n: F.q_scan(walkers[n][0]) for n, _ in CHAINS}
    q["agents"] = F.q_scan(agents)

    L = [f"# The three Markov chains against the Agent World: {run}", "",
         f"{len(agents):,} Agent World trips. Each chain has one walker per trip, {len(walkers['momentum'])} repeats, "
         "pooled. Equal chance is left out here; it is in following.md.", "",
         "## 1. Do the chain's walkers choose paths in the same proportions as the Agent World's people?", "",
         f"One test per junction and path in with at least {MIN_PASSES} passes in both: a 2 × (paths out) table of "
         "counts, Agent World against the chain's walkers, turning back left out. Pearson chi-square and the G-test "
         "(likelihood ratio). p-values corrected over all tests (Benjamini-Hochberg). 'Noise check' is one repeat "
         "of the counted chain against another: what the tests give when there is no real difference. 'Half the "
         "people against the other half' is the Agent World's people with odd numbers against those with even "
         "numbers.", "",
         "| Chain | Tested | Chi-square: significant at 5% | Same, only tests with all expected counts 5+ | "
         "G-test: significant at 5% | Median Cramér's V | Median TVD | Pass-weighted TVD |",
         "|---|---|---|---|---|---|---|---|"]
    for n, lab in CHAINS + [("noise", "Noise check"), ("split", "Agent World: half the people against the other half")]:
        s = summarise({"noise": noise, "split": split}.get(n) if n in ("noise", "split") else rows[n])
        if s:
            L.append(f"| {lab} | {s['n']:,} | {pct(s['chi'])} | {pct(s['chi_exp5'])} of {s['n_exp5']:,} | {pct(s['g'])} | "
                     f"{s['v']:.3f} | {s['tvd']:.3f} | {s['tvd_w']:.3f} |")
    L += ["",
          "Cramér's V runs from 0 (same proportions) to 1. TVD (total variation distance) is the share of choices "
          "that would have to change for the two to agree.", "",
          "How to read it: the counted chain takes its probabilities from the Agent World's own counts (per hour), "
          "so its walkers reproduce the shares at each junction by construction, and imitation copies people who "
          "were themselves drawn from those shares. A low rejection rate for these two is expected, not a finding. "
          "What separates them from the Agent World is not the share at one junction but whether two people "
          "choose alike several junctions in a row (section 3).", "",
          "## 2. All junctions pooled", "",
          "One table per chain, Agent World against the chain: choices labelled front (within 40° of straight on), left, "
          "right or (rarely, at sharp bends) back.", "",
          "| Chain | Chi-square | G | Degrees of freedom | p | Cramér's V | Front: Agent World / chain | Left | Right |",
          "|---|---|---|---|---|---|---|---|---|"]
    for n, lab in CHAINS:
        s = pooled(D, a_counts, w_counts[n])
        sh = lambda l: f"{pct(s['a'].get(l, 0))} / {pct(s['b'].get(l, 0))}"
        L.append(f"| {lab} | {s['chi2']:,.0f} | {s['g']:,.0f} | {s['dof']} | {fmt_p(max(s['p'], s['pg']))} | {s['v']:.3f} | "
                 f"{sh('F')} | {sh('L')} | {sh('R')} |")
    L += ["", "## 3. Two people arriving together: do they make the same next k decisions as often as the chain says?", "",
          "Pairs who arrive at a junction by the same path, one at most 30 m behind the other. A 2 × 2 table per "
          "chain and k: same next k decisions or not, Agent World pairs against the chain's pairs (first repeat).", "",
          "| Chain | k | Agent World | Chain | Difference | Chi-square | G | p | Effect size phi |",
          "|---|---|---|---|---|---|---|---|---|"]
    for n, lab in CHAINS:
        for k in (1, 3, 5):
            s = pair_test(q["agents"], q[n], k)
            L.append(f"| {lab} | {k} | {pct(s['a'])} | {pct(s['b'])} | {100 * (s['a'] - s['b']):+.1f} points | "
                     f"{s['chi2']:,.0f} | {s['g']:,.0f} | {fmt_p(max(s['p'], s['pg']))} | {s['phi']:.3f} |")
    L += ["", f"Agent World pairs at k = 1: {q['agents'][0][1]:,}.", "",
          "Limits: one person passes the same junction on several trips and belongs to many pairs, so the counts "
          "are not independent and every p-value is too small. With this many pairs almost any difference is "
          "significant; read the difference in points and the effect size (about 0.1 small, 0.3 medium, 0.5 "
          "large).", "",
          "Table per junction and path in: model_tests.csv."]
    (out / "model_tests.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return a_counts


# ---------------- 2. bar charts ----------------
GROUPS = ["Resident, working", "Resident, at school or college", "Resident, retired or at home",
          "Domestic helper", "HKU student", "HKU staff"]
GROUP_COLOURS = [BLUE, GREEN, YELLOW, PURPLE, ORANGE, MUTED]


def group_of(person):
    k = person["kind"]
    if not k.startswith("resident"):
        return "HKU student" if person.get("role") in ("undergrad", "postgrad") or "grad" in k else "HKU staff"
    d = k.split(": ", 1)[1]
    if d == "domestic helper":
        return "Domestic helper"
    if d == "student":
        return "Resident, at school or college"
    if d.startswith("works") and d != "works at home":
        return "Resident, working"
    return "Resident, retired or at home"


def stacked(ax, labels, parts, colours, names, horizontal=True, percent=True, legend_cols=4):
    """parts[i][j]: value of part j in bar i. Thin white gaps between parts; the legend names the parts."""
    base = np.zeros(len(labels))
    y = np.arange(len(labels))
    for j, (name, col) in enumerate(zip(names, colours)):
        v = np.array([p[j] for p in parts], dtype=float)
        if horizontal:
            ax.barh(y, v, left=base, color=col, edgecolor="white", linewidth=0.8, height=0.72, label=name)
            for yi, (b, x) in enumerate(zip(base, v)):
                if percent and x >= 7:
                    ax.text(b + x / 2, yi, f"{x:.0f}%", ha="center", va="center", fontsize=6.5, color="white")
        else:
            ax.bar(y, v, bottom=base, color=col, edgecolor="white", linewidth=0.6, width=0.8, label=name)
        base += v
    if horizontal:
        ax.set_yticks(y, labels)
        if not ax.yaxis_inverted():
            ax.invert_yaxis()
        ax.tick_params(axis="y", length=0, labelcolor=INK)
        if percent:
            ax.set_xlim(0, 100)
            ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    ax.legend(frameon=False, fontsize=6.5, ncol=legend_cols, loc="lower left", bbox_to_anchor=(0, 1.0),
              handlelength=1, columnspacing=1, borderaxespad=0.2)


def movement_bars(raw, people, run_label):
    g_of = {pid: group_of(p) for pid, p in people.items()}
    n_people = Counter(g_of.values())
    by_hour = {g: [0] * 24 for g in GROUPS}
    pace = {g: Counter() for g in GROUPS}       # metres by pace choice
    length = {g: Counter() for g in GROUPS}
    kind = {g: Counter() for g in GROUPS}
    bands = [(250, "under 250 m"), (500, "250 to 500 m"), (1000, "500 m to 1 km"), (1e9, "over 1 km")]
    for t in raw:
        g = g_of.get(t["agent"])
        if g is None:
            continue
        by_hour[g][int(t["depart"] // 3600) % 24] += 1
        pace[g][t.get("pace_choice") or "normal"] += t["metres"]
        length[g][next(b for lim, b in bands if t["metres"] < lim)] += 1
        kind[g]["auto" if t.get("auto") else (t.get("kind") or "go_to")] += 1

    fig, axs = plt.subplots(2, 2, figsize=(9.6, 6.0), gridspec_kw={"hspace": 0.62, "wspace": 0.95})
    ax = axs[0][0]
    hours = list(range(5, 24))
    stacked(ax, [f"{h:02d}" for h in hours], [[by_hour[g][h] for g in GROUPS] for h in hours], GROUP_COLOURS, GROUPS,
            horizontal=False, percent=False, legend_cols=2)
    ax.set_xticks(range(1, len(hours), 3), [f"{h:02d}:00" for h in hours[1::3]], fontsize=6.5)
    ax.set_ylabel("Trips starting in the hour")
    ax.grid(axis="y", color=GRID, linewidth=0.5); ax.set_axisbelow(True)

    ax = axs[0][1]
    pcs, pc_names, pc_cols = ["slow", "normal", "fast"], ["Slow", "Normal", "Fast"], [PALE, BLUE, ORANGE]
    stacked(ax, GROUPS, [[pace[g][p] / max(1, n_people[g]) / 1000 for p in pcs] for g in GROUPS], pc_cols, pc_names,
            percent=False)
    for i, g in enumerate(GROUPS):
        tot = sum(pace[g].values()) / max(1, n_people[g]) / 1000
        ax.text(tot + 0.03, i, f"{tot:.1f} km", va="center", fontsize=6.5, color=INK)
    ax.set_xlabel("Kilometres walked per person, by pace chosen")
    ax.set_xlim(0, max(sum(pace[g].values()) / max(1, n_people[g]) / 1000 for g in GROUPS) * 1.2)
    ax.grid(axis="x", color=GRID, linewidth=0.5); ax.set_axisbelow(True)

    ax = axs[1][0]
    names = [b for _, b in bands]
    stacked(ax, GROUPS, [[100 * length[g][b] / max(1, sum(length[g].values())) for b in names] for g in GROUPS],
            ["#a9c9ef", "#6fa5e3", BLUE, "#174f94"], names, legend_cols=2)
    ax.set_xlabel("Share of trips, by length")

    ax = axs[1][1]
    ks = [k for k in ("go", "go_to", "stroll", "walk", "auto") if any(kind[g][k] for g in GROUPS)]
    kn = {"go": "Quickest path to a place", "go_to": "Quickest path to a place", "stroll": "Stroll", "walk": "Chose each junction",
          "auto": "Walked home by the simulator"}
    stacked(ax, GROUPS, [[100 * kind[g][k] / max(1, sum(kind[g].values())) for k in ks] for g in GROUPS],
            [{"go": BLUE, "go_to": BLUE, "stroll": GREEN, "walk": YELLOW, "auto": PALE}[k] for k in ks], [kn[k] for k in ks],
            legend_cols=2)
    ax.set_xlabel("Share of trips, by how the person walked")
    fig.suptitle(f"How people move in the {run_label}: {len(g_of):,} people, {len(raw):,} trips", fontsize=9, x=0.02,
                 ha="left", y=0.99)
    save(fig, "movement-bars")


def road_choice_bars(D, a_counts, sets, labels):
    """sets: name -> list of trip lists. Two rows of 100% bars per junction size: the direction of the path taken,
    and how popular the path taken is among Agent World people arriving the same way."""
    rank = {}
    for (c, ai), cc in a_counts.items():
        order = sorted((o for o in D.options(c, ai) if o != ai), key=lambda o: -cc.get(o, 0))
        for r, o in enumerate(order):
            rank[(c, ai, o)] = min(r, 2)
    names = [n for n in labels if n in sets]
    fig, axs = plt.subplots(2, 2, figsize=(8.6, 4.9), sharey=True, gridspec_kw={"hspace": 0.75, "wspace": 0.08})
    for col, roads in enumerate((3, 4)):
        direction, popular = [], []
        for n in names:
            d, p = Counter(), Counter()
            for trips in sets[n]:
                for t in trips:
                    for c, ai, ao, _ in t["seq"]:
                        if len(D.arms[c]) != roads:
                            continue
                        d[D.label(c, ai, ao)] += 1
                        if ao != ai and (c, ai, ao) in rank:
                            p[rank[(c, ai, ao)]] += 1
            direction.append([100 * d[l] / max(1, sum(d.values())) for l in "FLRB"])
            popular.append([100 * p[r] / max(1, sum(p.values())) for r in range(roads - 1)])
        ys = [labels[n] for n in names]
        stacked(axs[0][col], ys, direction, [BLUE, GREEN, ORANGE, PALE], ["Straight on", "Left", "Right", "Back"])
        axs[0][col].set_xlabel(f"Direction of the path taken, where {roads} paths meet")
        stacked(axs[1][col], ys, popular, [BLUE, "#8fb8ea", PALE][:roads - 1],
                ["The most-used path", "The second", "The least-used"][:roads - 1])
        axs[1][col].set_xlabel(f"Popularity of the path taken, where {roads} paths meet")
    fig.suptitle("Which path is taken at a junction: people and Markov chains", fontsize=9, x=0.02, ha="left", y=1.02)
    save(fig, "road-choice-bars")


# ---------------- 3. net flow ----------------
def net_flow(world, raw, out, kappa):
    """Per path and part of the day: people walking it u -> v ("forward") minus v -> u ("back"). The momentum-
    weighted version counts each walk of a path by how straight the person's last junction decision was:
    weight = exp(kappa cos(turn)) divided by the mean of that over the paths they could have taken, so 1 means
    as likely as chance under the momentum chain, more than 1 a straight-on choice, less than 1 a turn. The
    weight carries along the path until the next junction; the first path of a trip has weight 1."""
    E = len(world.edges)
    flow = {p: np.zeros((E, 2)) for p, *_ in PERIODS}
    wflow = {p: np.zeros((E, 2)) for p, *_ in PERIODS}
    cache = {}

    def weight(n, e_in, e_out):
        key = (n, e_in, e_out)
        if key not in cache:
            h_in = world._bearing_out(n, e_in) + math.pi
            opts = [i for _, i in world.adj[n] if i != e_in]
            ws = {i: math.exp(kappa * math.cos(world._bearing_out(n, i) - h_in)) for i in opts}
            cache[key] = ws[e_out] * len(ws) / sum(ws.values()) if e_out in ws else 1.0
        return cache[key]

    for t in raw:
        w, prev = 1.0, None
        for s in t["segments"]:
            e, n = s["edge"], s["from"]
            if prev is not None and len(world.adj[n]) >= 3:
                w = weight(n, prev, e)
            prev = e
            h = s["t"] / 3600
            d = 0 if world.edges[e]["u"] == n else 1
            for p, _, lo, hi in PERIODS:
                if lo <= h < hi:
                    flow[p][e, d] += 1
                    wflow[p][e, d] += w
    with open(out / "net_flow.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["segment", "name", "period", "forward", "back", "net", "net_momentum_weighted",
                     "net_direction_degrees_from_east"])
        for e, ed in enumerate(world.edges):
            for p, *_ in PERIODS:
                fw, bk = flow[p][e]
                if fw + bk == 0:
                    continue
                a, b = xy(*ed["geom"][0]), xy(*ed["geom"][-1])
                ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) + (180 if fw < bk else 0)
                wr.writerow([e, ed.get("name") or "", p, int(fw), int(bk), int(fw - bk),
                             round(wflow[p][e, 0] - wflow[p][e, 1], 1), round(ang % 360)])
    return flow, wflow


def net_flow_figure(world, flow, wflow, run_label):
    wheel = LinearSegmentedColormap.from_list("wheel", [BLUE, GREEN, ORANGE, PURPLE, BLUE])   # east, north, west, south
    fig, axs = plt.subplots(2, 2, figsize=(9.6, 6.4), gridspec_kw={"hspace": 0.1, "wspace": 0.02, "right": 0.88})
    top = max(np.abs(f[:, 0] - f[:, 1]).max() for f in flow.values())
    for r, (data, what) in enumerate(((flow, "People one way minus the other"),
                                      (wflow, "Momentum-weighted"))):
        for c, (p, title, _, _) in enumerate(PERIODS):
            ax = axs[r][c]
            ax.add_collection(LineCollection([[xy(*q) for q in e["geom"]] for e in world.edges], colors=GRID, linewidths=0.3))
            segs, cols, widths, size = [], [], [], []
            for e, ed in enumerate(world.edges):
                net = data[p][e, 0] - data[p][e, 1]
                if abs(net) < 5:
                    continue
                g = [xy(*q) for q in ed["geom"]]
                ang = math.atan2(g[-1][1] - g[0][1], g[-1][0] - g[0][0]) + (math.pi if net < 0 else 0)
                strength = min(1.0, abs(net) / top) ** 0.5
                rgba = list(wheel((ang % (2 * math.pi)) / (2 * math.pi)))
                rgba[3] = 0.35 + 0.65 * strength
                segs.append(g); cols.append(rgba); widths.append(0.3 + 2.4 * strength); size.append(abs(net))
            order = np.argsort(size)
            ax.add_collection(LineCollection([segs[i] for i in order], colors=[cols[i] for i in order],
                                             linewidths=[widths[i] for i in order], capstyle="round"))
            for name in ("Kennedy Town", "HKU", "Sai Ying Pun"):
                m = [q["xy"] for q in world.places.values() if q["category"] == "mtr" and name in q["name"]]
                if m:
                    x, y = np.mean([q[0] for q in m]), np.mean([q[1] for q in m])
                    ax.plot(x, y, "o", ms=3, mfc="white", mec="black", mew=0.8, zorder=6)
                    ax.annotate(name if name != "HKU" else "HKU station", (x, y), xytext=(0, 6), textcoords="offset points",
                                ha="center", fontsize=5.5, zorder=6,
                                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="0.4", lw=0.3))
            ax.autoscale(); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
            for s in ax.spines.values():
                s.set_visible(False)
            ax.set_title(f"{what}. {title}", fontsize=7, loc="left", pad=3)
    # the key: a compass wheel of the colours
    kx = fig.add_axes([0.905, 0.42, 0.085, 0.16], projection="polar")
    th = np.linspace(0, 2 * np.pi, 181)
    kx.pcolormesh(th, [0.55, 1], np.array([th[:-1] / (2 * np.pi)]), cmap=wheel, shading="flat")
    kx.set_yticks([]); kx.set_xticks(np.radians([0, 90, 180, 270]), ["E", "N", "W", "S"], fontsize=6.5)
    kx.tick_params(pad=-2); kx.spines["polar"].set_visible(False); kx.grid(False)
    kx.set_title("Net flow\nheads", fontsize=6.5, pad=6)
    fig.text(0.905, 0.36, f"Thicker, stronger\ncolour: more\npeople (up to\n{int(top):,} net)", fontsize=6, va="top", color=MUTED)
    fig.suptitle(f"Where people are heading in the {run_label}: net flow on each path", fontsize=9, x=0.125, ha="left", y=0.94)
    save(fig, "net-flow")


# ---------------- main ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="census_run")
    ap.add_argument("--control", default=None, help="a rule-based run of the same people, for the road-choice bars")
    ap.add_argument("--seeds", type=int, default=F.SEEDS)
    ap.add_argument("--label", default="Agent World")
    args = ap.parse_args()
    run_dir = C.OUT / args.run
    out = run_dir / "analysis"
    out.mkdir(exist_ok=True)
    world = World()
    D = Decisions(world)
    people = {a["id"]: a for a in (json.loads(l) for l in open(run_dir / "people.jsonl", encoding="utf-8"))} \
        if (run_dir / "people.jsonl").exists() else {}

    print("loading trips", flush=True)
    raw = [json.loads(l) for l in open(run_dir / "trips.jsonl", encoding="utf-8")]
    raw = [t for t in raw if t["segments"]]
    if not people:   # a live run keeps no people file of its own: take them from the run it was drawn from
        ids = {t["agent"] for t in raw}
        people = {a["id"]: a for a in (json.loads(l) for l in open(C.OUT / "census_run" / "people.jsonl", encoding="utf-8"))
                  if a["id"] in ids}
    agents = F.as_decisions(D, raw)

    print("walking the Markov chains", flush=True)
    counts, hourly = defaultdict(Counter), defaultdict(Counter)
    for t in agents:
        for c, ai, ao, tt in t["seq"]:
            counts[(c, ai)][ao] += 1
            hourly[(c, ai, int(tt // 3600) % 24)][ao] += 1
    models = {"equal": F.Model(D, "equal"), "momentum": F.Model(D, "momentum"),
              "counted": F.Model(D, "counted", counts=counts, hourly=hourly)}
    walkers = {n: [F.chain_walk(D, agents, models[n], 100 + s) for s in range(args.seeds)]
               for n in ("equal", "momentum", "counted")}
    walkers["imitate"] = [F.chain_walk(D, agents, models["counted"], 200 + s, rho=F.RHO) for s in range(args.seeds)]

    print("tests", flush=True)
    a_counts = tests(D, agents, walkers, out, args.run)

    print("bar charts", flush=True)
    movement_bars(raw, people, args.label)
    sets = {"agents": [agents], **walkers}
    if args.control and (C.OUT / args.control / "trips.jsonl").exists():
        sets["no_llm"] = [F.load_trips(C.OUT / args.control / "trips.jsonl", D)]
    road_choice_bars(D, a_counts, sets, {"agents": args.label, "no_llm": "Same people, no LLM",
                                         "imitate": "Markov: counted + imitation", "counted": "Markov: counted",
                                         "momentum": "Markov: momentum", "equal": "Markov: equal chance"})

    print("net flow", flush=True)
    flow, wflow = net_flow(world, raw, out, F.KAPPA)
    net_flow_figure(world, flow, wflow, args.label)
    print(f"wrote {out}/model_tests.md, model_tests.csv, net_flow.csv and graphs/movement-bars, road-choice-bars, net-flow")
