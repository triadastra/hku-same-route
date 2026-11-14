"""Put a run next to the published 10,000-person run (out/day1), or next to any other run.

    python compare.py --run default               # your repeat vs the published run
    python compare.py --run replay-default-step-free --ref default

Writes out/<run>/analysis/compare.md. A repeat with the Claude planner will not match to the decimal:
the people, the map and the walking are the same, but the model plans each day afresh.
"""
import argparse
import csv

import config as C


def table(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(x):
    return f"{100 * float(x):.1f}%"


def points(a, b):
    return f"{100 * (float(a) - float(b)):+.1f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--ref", default="day1", help="the run to compare with (default: the published day1)")
    args = ap.parse_args()
    mine, ref = C.OUT / args.run / "analysis", C.OUT / args.ref / "analysis"
    for p in (mine, ref):
        if not (p / "shared_turns.csv").exists():
            raise SystemExit(f"no analysis in {p}; run analyze.py --run {p.parent.name} first")

    lines = [f"# {args.run} compared with {args.ref}", "",
             "Chance that some stranger makes your same k turns in a row (quickest-path column of each run).", "",
             f"| Same turns in a row (k) | {args.ref} | {args.run} | Difference (points) |", "|---|---|---|---|"]
    col = "p_someone_shares_k_quickest"
    theirs = {r["k_turns_in_a_row"]: r[col] for r in table(ref / "shared_turns.csv")}
    for r in table(mine / "shared_turns.csv"):
        k = r["k_turns_in_a_row"]
        if k in theirs:
            lines.append(f"| {k} | {pct(theirs[k])} | {pct(r[col])} | {points(r[col], theirs[k])} |")

    lines += ["", f"| Group | People: {args.ref} | {args.run} | Trips each: {args.ref} | {args.run} | "
              f"Stranger shares 5+ turns: {args.ref} | {args.run} |", "|---|---|---|---|---|---|---|"]
    theirs = {r["group"]: r for r in table(ref / "groups.csv")}
    for r in table(mine / "groups.csv"):
        t = theirs.get(r["group"])
        if t:
            lines.append(f"| {r['label']} | {t['people']} | {r['people']} | {t['trips_per_person']} | {r['trips_per_person']} | "
                         f"{pct(t['p_shares_5'])} | {pct(r['p_shares_5'])} |")
    (mine / "compare.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
