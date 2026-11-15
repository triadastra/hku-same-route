"""Where the Agent World's people chose to go: is there a bias, and what do they prefer?

A trip's destination is fixed if it is the person's home or the place of one of the commitments on their persona
card (work, class, school), and free otherwise: a place the agent picked for itself with the map tools.

For the free trips, by category of place:
  share of trips        how often people went to a place of this category
  share of places       how many of the map's places are of this category: what picking a place at random gives
  ratio                 the first over the second: above 1, agents go there more often than chance; below 1, less
and the same shares for residents, HKU students and HKU staff; how concentrated the free trips are on a few
places; the places visited most; and how far people walk for a free trip.

    python destinations.py --run census_run

Writes out/<run>/analysis/destinations.md and destinations.csv, and graphs/destination-choice.pdf.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict

import numpy as np

import config as C
from world import World, _english

GROUPS = [("resident", "Residents"), ("student", "HKU students"), ("staff", "HKU staff")]


def group_of(person):
    role = person["role"]
    return role if role in ("resident", "staff") else "student"       # undergraduates and postgraduates together


def figure(rows, by_group, run):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    from make_figures import save

    rows = sorted(rows, key=lambda r: r["ratio"])
    cats = [r["category"] for r in rows]
    more, less = "#4c72b0", "#dd8452"
    with sns.axes_style("whitegrid"), sns.plotting_context("paper", font_scale=0.9):
        fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.6), sharey=True, gridspec_kw={"width_ratios": [1.15, 1]})
        y = np.arange(len(rows))
        x = np.log2([max(r["ratio"], 2 ** -4.6) for r in rows])
        a.barh(y, x, color=[more if v >= 0 else less for v in x], height=0.62)
        a.axvline(0, color="#1f2423", lw=0.8)
        for yi, r, v in zip(y, rows, x):
            a.text(v + (0.08 if v >= 0 else -0.08), yi, f"{r['ratio']:.1f}×" if r["ratio"] >= 0.095 else f"{r['ratio']:.2f}×",
                   va="center", ha="left" if v >= 0 else "right", fontsize=6.5, color="#1f2423")
        ticks = [-4, -2, 0, 2, 4]
        a.set_xticks(ticks, ["16× less", "4× less", "as often", "4× more", "16× more"])
        a.set_xlim(-5.4, 5.4)
        a.set_yticks(y, cats)
        a.grid(axis="y", visible=False)
        a.set_title("Free trips against picking a place at random", loc="left", fontsize=8.5)
        colours = dict(zip([g for g, _ in GROUPS], ["#4c72b0", "#c44e52", "#55a868"]))
        marks = dict(zip([g for g, _ in GROUPS], ["o", "s", "^"]))
        for g, name in GROUPS:
            b.plot([100 * by_group[g].get(c, 0) for c in cats], y, marks[g], color=colours[g], ms=5, mec="white", mew=0.7, label=name)
        b.set_xlabel("Share of the group's free trips (%)")
        b.grid(axis="y", color="#eef0ef", lw=0.6)
        b.set_title("By kind of person", loc="left", fontsize=8.5)
        b.legend(frameon=False, fontsize=7.5, loc="lower right")
        sns.despine(fig=fig, left=True)
        fig.tight_layout()
    save(fig, "destination-choice" if run == "census_run" else f"destination-choice-{run}")


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
    M += ["", "## By kind of person", "", "Share of each group's free trips.", "",
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
    M += ["", "Table: destinations.csv. Figure: graphs/destination-choice.pdf."]
    (out / "destinations.md").write_text("\n".join(M) + "\n", encoding="utf-8")
    if not args.no_figure:
        figure(rows, by_group, args.run)
    print(f"wrote {out / 'destinations.md'}")


if __name__ == "__main__":
    main()
