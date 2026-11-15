"""Who follows whom in the Agent World: are people followed by their own kind more than by anyone?

Nobody in the Agent World can see anybody, so nobody follows on purpose: "following" here is a stranger who
happens to stay at most 30 m behind you through k junctions in a row (the study's rule, following.py). For
every trip that is followed, take the stranger who followed it longest, and count the pairs by the kind of
person in front and the kind of person behind (the census kinds of resident, and HKU students and staff as one).

If people were followed by anyone alike, the kind of person behind would not depend on the kind in front: the
expected count of a pair is (row total x column total) / all pairs, as in a chi-square test of independence.
Each cell of the heat map is observed / expected: 1 means as often as chance, 2 twice as often.

    python who_follows.py --run census_run

Writes out/<run>/analysis/who_follows.md and who_follows.csv, and graphs/who-follows-whom.pdf.
"""
import argparse
import csv
import json

import numpy as np
from scipy import stats

import config as C
from decisions import Decisions
from destinations import GROUPS, group_of
from following import as_decisions, follow_scan
from world import World


def figure(lift, counts, labels, k, run):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib.colors import TwoSlopeNorm
    from make_figures import save

    shown = np.log2(np.clip(lift, 2 ** -3, 2 ** 3))
    text = np.array([[f"{v:.1f}" if n >= 5 else "" for v, n in zip(lr, nr)] for lr, nr in zip(lift, counts)])
    with sns.axes_style("white"), sns.plotting_context("paper", font_scale=0.9):
        fig, ax = plt.subplots(figsize=(7.2, 5.2))
        sns.heatmap(shown, ax=ax, annot=text, fmt="", cmap=sns.diverging_palette(28, 250, s=75, l=55, as_cmap=True),
                    norm=TwoSlopeNorm(0, -3, 3), linewidths=1.5, linecolor="white", annot_kws={"fontsize": 7},
                    xticklabels=labels, yticklabels=labels,
                    cbar_kws={"shrink": 0.75, "pad": 0.015, "ticks": [-3, -2, -1, 0, 1, 2, 3]})
        cb = ax.collections[0].colorbar
        cb.ax.set_yticklabels(["8× less", "4× less", "2× less", "as chance", "2× more", "4× more", "8× more"])
        cb.set_label("Pairs observed against pairs expected if anyone followed anyone")
        for i in range(len(labels)):                          # outline the same-kind cells
            ax.add_patch(plt.Rectangle((i, i), 1, 1, fill=False, ec="#1f2423", lw=1.1))
        ax.set_xlabel(f"Kind of person behind (the stranger following through {k} or more junctions)")
        ax.set_ylabel("Kind of person in front")
        ax.tick_params(axis="both", length=0)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=38, ha="right", rotation_mode="anchor")
        fig.tight_layout()
    save(fig, "who-follows-whom" if run == "census_run" else f"who-follows-whom-{run}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="census_run")
    ap.add_argument("--k", type=int, default=3, help="junctions in a row that count as being followed")
    args = ap.parse_args()
    run_dir = C.OUT / args.run
    out = run_dir / "analysis"
    D = Decisions(World())
    with open(run_dir / "people.jsonl", encoding="utf-8") as f:
        people = {p["id"]: p for p in map(json.loads, f)}
    print("loading the trips and finding who follows whom", flush=True)
    with open(run_dir / "trips.jsonl", encoding="utf-8") as f:
        trips = as_decisions(D, [t for t in map(json.loads, f) if t["segments"] and t["agent"] in people])
    rows = follow_scan(trips)

    keys = [g for g, _ in GROUPS]
    labels = [label for _, label in GROUPS]
    at = {g: i for i, g in enumerate(keys)}
    counts = np.zeros((len(keys), len(keys)))
    for t, r in zip(trips, rows):
        if r["max"] >= args.k:
            counts[at[group_of(people[t["agent"]])], at[group_of(people[trips[r["top"]]["agent"]])]] += 1
    total = counts.sum()
    expected = counts.sum(1, keepdims=True) * counts.sum(0, keepdims=True) / total
    lift = np.divide(counts, expected, out=np.ones_like(counts), where=expected > 0)
    chi2, p, dof, _ = stats.chi2_contingency(counts)
    same, same_exp = np.trace(counts) / total, np.trace(expected) / total
    v = float(np.sqrt(chi2 / (total * (len(keys) - 1))))       # Cramer's V

    with open(out / "who_follows.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["in_front", "behind", "pairs", "expected", "observed_over_expected"])
        for i, a in enumerate(labels):
            for j, b in enumerate(labels):
                w.writerow([a, b, int(counts[i, j]), round(float(expected[i, j]), 1), round(float(lift[i, j]), 3)])

    pct = lambda x: f"{100 * x:.1f}%"
    M = [f"# Who follows whom in the Agent World: {args.run}", "",
         f"{len(trips):,} trips; {int(total):,} are followed by a stranger through {args.k} or more junctions (at most 30 m behind "
         f"along the road each time). For each, the stranger who followed longest is counted. Nobody in the Agent World can see "
         f"anybody, so this is who ends up behind whom, not who chooses to follow whom.", "",
         f"- The person behind is of the same kind as the person in front in {pct(same)} of pairs. If the kind behind did not "
         f"depend on the kind in front, it would be {pct(same_exp)}: {same / same_exp:.1f} times as often as chance.",
         f"- Chi-square test of independence: chi-square = {chi2:,.0f}, {dof} degrees of freedom, p {'< 0.001' if p < 0.001 else f'= {p:.3f}'}; "
         f"Cramér's V = {v:.2f} (0 no association, 1 complete). Trips by one person are not independent, so the p-value is too "
         f"small; the ratios below are the result.", "",
         "## Same kind in front and behind", "",
         "| Kind of person | Pairs with this kind in front | Followed by the same kind | Expected by chance | Observed / expected |",
         "|---|---|---|---|---|"]
    for i, label in enumerate(labels):
        n = counts[i].sum()
        if n:
            M.append(f"| {label} | {int(n):,} | {pct(counts[i, i] / n)} | {pct(expected[i, i] / n)} | {lift[i, i]:.1f} |")
    M += ["", "## Every pair: observed / expected", "",
          "Rows: the kind of person in front. Columns: the kind of person behind.", "",
          "| | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for i, label in enumerate(labels):
        M.append(f"| {label} | " + " | ".join(f"{lift[i, j]:.1f}" for j in range(len(labels))) + " |")
    M += ["", "Table: who_follows.csv. Figure: graphs/who-follows-whom.pdf."]
    (out / "who_follows.md").write_text("\n".join(M) + "\n", encoding="utf-8")
    figure(lift, counts, labels, args.k, args.run)
    print(f"wrote {out / 'who_follows.md'}")


if __name__ == "__main__":
    main()
