"""Where the Agent World's people chose to go: is there a bias, and what do they prefer?

A trip's destination is fixed if it is the person's home or the place of one of the commitments on their persona
card (work, class, school), and free otherwise: a place the agent picked for itself with the map tools.

For the free trips, by category of place:
  share of trips        how often people went to a place of this category
  share of places       how many of the map's places are of this category: what picking a place at random gives
  ratio                 the first over the second: above 1, agents go there more often than chance; below 1, less
and the same shares for each kind of resident and for HKU people (students and staff together); how concentrated the free trips are on a few
places; the places visited most; and how far people walk for a free trip.

    python destinations.py --run census_run

Writes out/<run>/analysis/destinations.md and destinations.csv, and graphs/destination-choice.pdf (the ratios)
and graphs/destination-by-kind.pdf (the shares for each kind of person).
"""
import argparse
import csv
import json
from collections import Counter, defaultdict

import numpy as np

import config as C
from world import World, _english

# the kinds of resident on the persona cards (from the census), and HKU students and staff as one group
GROUPS = [("works outside Central & Western", "Works outside C&W"), ("works in Central & Western", "Works in C&W"),
          ("works with no fixed place", "No fixed workplace"), ("works at home", "Works at home"),
          ("domestic helper", "Domestic helper"), ("school pupil", "School pupil"),
          ("student at a college elsewhere", "College student"), ("retired", "Retired"), ("home-maker", "Home-maker"),
          ("unpaid carer", "Unpaid carer"), ("not working", "Not working"), ("hku", "HKU")]
SHOWN = 9                                      # categories with their own row in the figure; the rest are "other"


def group_of(person):
    return person.get("role_detail") if person["role"] == "resident" else "hku"


def figure(rows, by_group, n_group, run):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    from make_figures import save

    name = "destination-choice" if run == "census_run" else f"destination-choice-{run}"
    by_ratio = sorted(rows, key=lambda r: r["ratio"])
    more, less = "#4c72b0", "#dd8452"
    with sns.axes_style("whitegrid"), sns.plotting_context("paper", font_scale=0.9):
        fig, a = plt.subplots(figsize=(4.2, 3.6))
        y = np.arange(len(by_ratio))
        x = np.log2([max(r["ratio"], 2 ** -4.6) for r in by_ratio])
        a.barh(y, x, color=[more if v >= 0 else less for v in x], height=0.62)
        a.axvline(0, color="#1f2423", lw=0.8)
        for yi, r, v in zip(y, by_ratio, x):
            a.text(v + (0.08 if v >= 0 else -0.08), yi, f"{r['ratio']:.1f}×", va="center", ha="left" if v >= 0 else "right",
                   fontsize=6.5, color="#1f2423")
        a.set_xticks([-4, -2, 0, 2, 4], ["16× less", "4× less", "as often", "4× more", "16× more"])
        a.set_xlim(-5.4, 5.6)
        a.set_yticks(y, [r["category"] for r in by_ratio])
        a.grid(axis="y", visible=False)
        a.set_xlabel("Free trips against picking a place at random")
        sns.despine(fig=fig, left=True)
        fig.tight_layout()
        save(fig, name)

        # the share of each kind of person's free trips that go to each category
        cats = [r["category"] for r in rows[:SHOWN]]            # rows are sorted by number of free trips
        groups = [(g, label) for g, label in GROUPS if n_group.get(g)]
        table = np.array([[100 * by_group[g].get(c, 0) for g, _ in groups] for c in cats])
        table = np.vstack([table, 100 - table.sum(axis=0)])
        fig, ax = plt.subplots(figsize=(7.2, 3.5))
        sns.heatmap(table, ax=ax, annot=True, fmt=".0f", cmap=sns.light_palette("#4c72b0", as_cmap=True), vmin=0, vmax=60,
                    linewidths=1.5, linecolor="white", annot_kws={"fontsize": 7},
                    cbar_kws={"label": "Share of the group's free trips (%)", "shrink": 0.8, "pad": 0.015},
                    xticklabels=[f"{label}\n({n_group[g]:,})" for g, label in groups], yticklabels=cats + ["other"])
        ax.tick_params(axis="both", length=0)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=38, ha="right", rotation_mode="anchor", fontsize=7)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
        ax.axvline(len(groups) - 1, color="#1f2423", lw=0.8)    # residents to the left, HKU to the right
        fig.tight_layout()
        save(fig, name.replace("destination-choice", "destination-by-kind"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="census_run")
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args()
    run_dir = C.OUT / args.run
    out = run_dir / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    world = World()
    with open(run_dir / "people.jsonl", encoding="utf-8") as f:
        people = {p["id"]: p for p in map(json.loads, f)}
    fixed_places = {a: {p["home"]} | {c["place"] for c in p.get("commitments", [])} for a, p in people.items()}

    trips, free = 0, []
    with open(run_dir / "trips.jsonl", encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            if t["to"] not in world.places or t["agent"] not in people or t["from"] == t["to"]:
                continue
            trips += 1
            if t["to"] not in fixed_places[t["agent"]]:
                free.append((t["agent"], t["to"], t.get("metres", 0), t.get("kind", "")))

    n_places = Counter(p["category"] for p in world.places.values())
    n_trips = Counter(world.places[to]["category"] for _, to, _, _ in free)
    rows = []
    for cat in sorted(n_places, key=lambda c: -n_trips[c]):
        st, sp = n_trips[cat] / len(free), n_places[cat] / len(world.places)
        rows.append({"category": cat, "places": n_places[cat], "free_trips": n_trips[cat], "share_of_trips": st,
                     "share_of_places": sp, "ratio": st / sp})
    by_group, n_group = {}, {}
    for g, _ in GROUPS:
        mine = [to for a, to, _, _ in free if group_of(people[a]) == g]
        n_group[g] = len(mine)
        c = Counter(world.places[to]["category"] for to in mine)
        by_group[g] = {cat: c[cat] / len(mine) for cat in c} if mine else {}
    with open(out / "destinations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "places", "free_trips", "share_of_trips", "share_of_places", "ratio"] + [f"share_{g}" for g, _ in GROUPS])
        for r in rows:
            w.writerow([r["category"], r["places"], r["free_trips"], round(r["share_of_trips"], 4), round(r["share_of_places"], 4),
                        round(r["ratio"], 3)] + [round(by_group[g].get(r["category"], 0), 4) for g, _ in GROUPS])

    visits = Counter(to for _, to, _, _ in free)
    ranked = [n for _, n in visits.most_common()]
    top1 = sum(ranked[: max(1, len(world.places) // 100)]) / len(free)
    top10 = sum(ranked[: len(world.places) // 10]) / len(free)
    never = 1 - len(visits) / len(world.places)
    walk = np.array([m for _, _, m, k in free if k == "go" and m])
    strolls = sum(k == "stroll" for _, _, _, k in free) / len(free)

    pct = lambda x: f"{100 * x:.1f}%"
    M = [f"# Where the agents chose to go: {args.run}", "",
         f"{trips:,} trips. {trips - len(free):,} ({pct(1 - len(free) / trips)}) go to the person's home or to a place fixed on their "
         f"persona card (work, class, school). The other {len(free):,} ({pct(len(free) / trips)}) are free trips, to a place the "
         f"agent picked for itself; everything below is about those. The map has {len(world.places):,} places.", "",
         "## By category of place", "",
         "The ratio compares how often agents went to a category with how many of the map's places are of that category, "
         "which is what picking a place at random would give.", "",
         "| Category | Places | Free trips | Share of trips | Share of places | Ratio |", "|---|---|---|---|---|---|"]
    for r in rows:
        M.append(f"| {r['category']} | {r['places']:,} | {r['free_trips']:,} | {pct(r['share_of_trips'])} | {pct(r['share_of_places'])} | {r['ratio']:.2f} |")
    M += ["", "## By kind of person", "",
          "Share of each group's free trips. The kinds of resident are those of the census; HKU is students and staff together.", "",
          "| Category | " + " | ".join(f"{name} ({n_group[g]:,} trips)" for g, name in GROUPS) + " |", "|---|" + "---|" * len(GROUPS)]
    for r in rows:
        M.append(f"| {r['category']} | " + " | ".join(pct(by_group[g].get(r["category"], 0)) for g, _ in GROUPS) + " |")
    M += ["", "## How concentrated the choices are", "",
          f"- The {max(1, len(world.places) // 100)} most visited places (1% of the map) take {pct(top1)} of the free trips; the top 10% take {pct(top10)}.",
          f"- {pct(never)} of the places were never chosen by anyone.",
          f"- Free trips walked by the quickest path: median {np.median(walk):.0f} m, middle half {np.percentile(walk, 25):.0f} to "
          f"{np.percentile(walk, 75):.0f} m. {pct(strolls)} of the free trips are strolls with no fixed route.", "",
          "## The places chosen most", "", "| Place | Category | Free trips |", "|---|---|---|"]
    for code, n in visits.most_common(15):
        p = world.places[code]
        M.append(f"| {_english(p['name']) or p['name']} ({code}) | {p['category']} | {n:,} |")
    M += ["", "Table: destinations.csv. Figures: graphs/destination-choice.pdf, graphs/destination-by-kind.pdf."]
    (out / "destinations.md").write_text("\n".join(M) + "\n", encoding="utf-8")
    if not args.no_figure:
        figure(rows, by_group, n_group, args.run)
    print(f"wrote {out / 'destinations.md'}")


if __name__ == "__main__":
    main()
