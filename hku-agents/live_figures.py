"""The live world against the Agent World on the same people and the same hours: one figure and LaTeX tables.

Reads out/live_census/analysis/ and out/census_run/analysis/same_people_same_hours_as_live_census/ (following.py
run on the Agent World trips of the same people that finished by the time the live world reached). Writes
../graphs/live-vs-agent-world.pdf/.png and out/live_census/analysis/paper_tables.tex and paper_tables.md.

    python live_figures.py
"""
import csv
import gzip
import itertools
import json
import statistics as S

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C

LIVE = C.OUT / "live_census"
AW = C.OUT / "census_run"
A_LIVE = LIVE / "analysis"
A_AW = AW / "analysis" / "same_people_same_hours_as_live_census"
GRAPHS = C.ROOT.parent / "graphs"
BLUE, ORANGE, AQUA, VIOLET, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#8a908d"
INK, MUTED, GRID = "#1f2423", "#6b7370", "#e3e6e4"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.labelcolor": INK})


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def pct(x):
    return 100 * float(x)


def trips_of(run):
    p = C.OUT / run / "trips.jsonl.gz"
    return [json.loads(l) for l in gzip.open(p, "rt", encoding="utf-8")]


def main():
    summary = json.loads((LIVE / "run_summary.json").read_text())
    clock = summary.get("clock_reached", "24:00")
    cut = int(clock[:2]) * 3600 + int(clock[3:]) * 60
    last_full_hour = int(clock[:2]) - 1

    pk_l, pk_a = rows(A_LIVE / "following_pk.csv"), rows(A_AW / "following_pk.csv")
    qk_l, qk_a = rows(A_LIVE / "following_qk.csv"), rows(A_AW / "following_qk.csv")
    hr_l = {r["hour"]: r for r in rows(A_LIVE / "following_by_hour.csv")}
    hr_a = {r["hour"]: r for r in rows(A_AW / "following_by_hour.csv")}
    rd_l = {r["roads"]: r for r in rows(A_LIVE / "following_by_roads.csv")}
    rd_a = {r["roads"]: r for r in rows(A_AW / "following_by_roads.csv")}

    # ---------------- figure ----------------
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.1), gridspec_kw={"wspace": 0.3})
    series = [("Live world", ORANGE, "-", "o"), ("Agent World", BLUE, "-", "s"), ("Momentum chain", AQUA, "--", "^"),
              ("Result based chain", VIOLET, "--", "D"), ("Random walking", GREY, ":", "v")]

    ax = axes[0]
    ks = [int(r["k"]) for r in pk_l]
    data = [[pct(r["p_agents"]) for r in pk_l], [pct(r["p_agents"]) for r in pk_a],
            [pct(r["p_momentum"]) for r in pk_l], [pct(r["p_counted"]) for r in pk_l], [pct(r["p_equal"]) for r in pk_l]]
    for (name, col, ls, mk), y in zip(series, data):
        ax.plot(ks, y, ls, color=col, marker=mk, markersize=3.5, linewidth=1.6, label=name)
    ax.set_xlabel("Junctions in a row, k")
    ax.set_ylabel("Trips with a stranger following (%)")
    ax.set_title("A stranger follows you through k junctions", fontsize=8.5, loc="left")
    ax.set_xticks(ks)

    ax = axes[1]
    ks = [int(r["k"]) for r in qk_l]
    data = [[pct(r["agents_observed"]) for r in qk_l], [pct(r["agents_observed"]) for r in qk_a],
            [pct(r["momentum_observed"]) for r in qk_l],
            [pct(r["counted_observed"]) for r in qk_l], [pct(r["equal_observed"]) for r in qk_l]]
    for (name, col, ls, mk), y in zip(series, data):
        ax.plot(ks, y, ls, color=col, marker=mk, markersize=3.5, linewidth=1.6, label=name)
    ax.set_xlabel("Next decisions, k")
    ax.set_ylabel("Pairs making the same choices (%)")
    ax.set_title("Two people arriving together stay together", fontsize=8.5, loc="left")
    ax.set_xticks(ks)

    ax = axes[2]
    hours = [f"{h:02d}:00" for h in range(6, last_full_hour + 1) if f"{h:02d}:00" in hr_l and f"{h:02d}:00" in hr_a]
    x = [int(h[:2]) for h in hours]
    ax.plot(x, [pct(hr_l[h]["p3_agents"]) for h in hours], "-", color=ORANGE, marker="o", markersize=3.5, linewidth=1.6)
    ax.plot(x, [pct(hr_a[h]["p3_agents"]) for h in hours], "-", color=BLUE, marker="s", markersize=3.5, linewidth=1.6)
    ax.set_xlabel("Hour the trip starts")
    ax.set_ylabel("Trips followed for 3 junctions (%)")
    ax.set_title("Through the day (3 junctions)", fontsize=8.5, loc="left")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{h:02d}" for h in x])

    for ax in axes:
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.09), fontsize=7.5)
    fig.text(0.5, -0.14, f"The same 1,000 people in both worlds, 06:00 to {clock}. Chains are run on the live world's trips.",
             ha="center", fontsize=6.5, color=MUTED)
    GRAPHS.mkdir(exist_ok=True)
    fig.savefig(GRAPHS / "live-vs-agent-world.pdf", bbox_inches="tight")
    fig.savefig(GRAPHS / "live-vs-agent-world.png", dpi=220, bbox_inches="tight")

    # ---------------- tables ----------------
    ids = {json.loads(l)["id"] for l in itertools.islice(open(AW / "people.jsonl", encoding="utf-8"), summary["agents"])}
    t_l = trips_of("live_census")
    t_a = [t for t in trips_of("census_run") if t["agent"] in ids and t.get("arrive") is not None and t["arrive"] <= cut]

    def trip_stats(T):
        m = [t["metres"] for t in T]
        return len(T), S.median(m), sum(m) / 1000

    def chi(path):
        r = rows(path)
        n = len(r)
        return n, 100 * sum(float(x["p_equal_bh"]) < 0.05 for x in r) / n, 100 * sum(float(x["p_momentum_bh"]) < 0.05 for x in r) / n

    def at(table, k, col):
        return next(pct(r[col]) for r in table if int(r["k"]) == k)

    (nl, ml, kl), (na, ma, ka) = trip_stats(t_l), trip_stats(t_a)
    (cl, el, mol), (ca, ea, moa) = chi(A_LIVE / "following_chi2.csv"), chi(A_AW / "following_chi2.csv")
    summary_rows = [("Finished trips", f"{na:,}", f"{nl:,}"),
                    ("Median trip length (m)", f"{ma:.0f}", f"{ml:.0f}"),
                    ("Total distance walked (km)", f"{ka:,.0f}", f"{kl:,.0f}")]
    for k in (3, 5, 10):
        summary_rows.append((f"Stranger follows for {k} junctions (%)", f"{at(pk_a, k, 'p_agents'):.1f}", f"{at(pk_l, k, 'p_agents'):.1f}"))
    for k in (1, 3, 5):
        summary_rows.append((f"Pairs: same next {k} decision{'s' if k > 1 else ''} (%)",
                             f"{at(qk_a, k, 'agents_observed'):.1f}", f"{at(qk_l, k, 'agents_observed'):.1f}"))
    for n in ("3", "4"):
        summary_rows.append((f"Pairs: same next road, {n}-road junctions (%)", f"{pct(rd_a[n]['agents']):.1f}", f"{pct(rd_l[n]['agents']):.1f}"))
    summary_rows += [("Junctions tested (road in, 30+ passes)", f"{ca:,}", f"{cl:,}"),
                     ("Random walking rejected (%)", f"{ea:.1f}", f"{el:.1f}"),
                     ("Momentum chain rejected (%)", f"{moa:.1f}", f"{mol:.1f}")]

    pairs_k1 = int(qk_l[0]["pairs_agents"])
    tex = [r"% Requires: \usepackage{booktabs}, \usepackage{siunitx}", "",
           r"\begin{table}[t]", r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{4pt}",
           r"\caption{The live world against the Agent World on the same 1{,}000 people, for trips finished by "
           + clock + r" (the live world was stopped at " + clock + r" on its clock, so the evening is not covered). "
           r"Tests are chi-square goodness of fit at each junction and road in, at the 5\% level after "
           r"Benjamini--Hochberg correction.}",
           r"\label{tab:live-summary}", r"\begin{tabular}{@{}lrr@{}}", r"\toprule",
           r" & \shortstack{Agent\\World} & \shortstack{Live\\World} \\", r"\midrule"]
    tex += [f"{a.replace('%', chr(92) + '%')} & {b.replace(',', '{,}')} & {c.replace(',', '{,}')} \\\\" for a, b, c in summary_rows]
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}", "",
            r"\begin{table}[t]", r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{4pt}",
            r"\caption{Live world (run \texttt{live\_census}, 06:00 to " + clock + r"): pairs arriving at a junction by the "
            r"same road, one at most \SI{30}{\metre} behind the other: share (\%) that make the same next $k$ decisions ("
            + f"{pairs_k1:,}".replace(",", "{,}") + r" live-world pairs at $k = 1$). The Agent World column is the same "
            r"1{,}000 people over the same hours. Chain values are from the first of three repeats.}",
            r"\label{tab:live-pairs}", r"\begin{tabular}{@{}rrrrrr@{}}", r"\toprule",
            r"$k$ & \shortstack{Live\\World} & \shortstack{Agent\\World} & \shortstack{Random\\Walking} & "
            r"\shortstack{Momentum\\Chain} & \shortstack{Result Based\\Chain} \\", r"\midrule"]
    for rl, ra in zip(qk_l, qk_a):
        if int(rl["k"]) > 5:
            continue
        tex.append(f"{rl['k']} & {pct(rl['agents_observed']):.1f} & {pct(ra['agents_observed']):.1f} & "
                   f"{pct(rl['equal_observed']):4.1f} & {pct(rl['momentum_observed']):.1f} & {pct(rl['counted_observed']):.1f} \\\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}", "",
            r"\begin{table}[t]", r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{4pt}",
            r"\caption{Live world (run \texttt{live\_census}, 06:00 to " + clock + r"): share (\%) of trips on which the same "
            r"stranger, at most \SI{30}{\metre} behind, follows through $k$ junctions in a row. The Agent World column is "
            r"the same 1{,}000 people over the same hours; the chains are run on the live world's trips (mean of three repeats).}",
            r"\label{tab:live-following}", r"\begin{tabular}{@{}rrrrrr@{}}", r"\toprule",
            r"$k$ & \shortstack{Live\\World} & \shortstack{Agent\\World} & \shortstack{Random\\Walking} & "
            r"\shortstack{Momentum\\Chain} & \shortstack{Result Based\\Chain} \\", r"\midrule"]
    for k in (1, 2, 3, 5, 10):
        tex.append(f"{k} & {at(pk_l, k, 'p_agents'):.1f} & {at(pk_a, k, 'p_agents'):.1f} & {at(pk_l, k, 'p_equal'):4.1f} & "
                   f"{at(pk_l, k, 'p_momentum'):.1f} & {at(pk_l, k, 'p_counted'):.1f} \\\\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    (A_LIVE / "paper_tables.tex").write_text("\n".join(tex), encoding="utf-8")

    md = [f"# Live world against Agent World, same 1,000 people, trips finished by {clock}", "",
          "| | Agent World | Live world |", "|---|---|---|"]
    md += [f"| {a} | {b} | {c} |" for a, b, c in summary_rows]
    (A_LIVE / "paper_tables.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(tex))


if __name__ == "__main__":
    main()
