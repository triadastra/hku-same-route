"""Write the results of a live-world run that was stopped before midnight, from its checkpoint.

live.py only writes trips.jsonl, agents/ and run_summary.json when the whole day is finished. This script
writes the same files from out/<run>/checkpoint.pkl for the part of the day that was simulated, so that
following.py can analyse it. Only finished trips are written: a walk still in progress at the stop is left
out, and nobody is walked home by the simulator. The checkpoint is not changed, so the run can still be
resumed with live.py afterwards (which then overwrites these files with the full day).

    python export_partial_live.py --run live_census
"""
import argparse
import json
import pickle
import sys
from collections import Counter

import __main__
import config as C
import live as L

for _n in dir(L):          # the checkpoint was pickled with live.py as the main module
    if not _n.startswith("__"):
        setattr(__main__, _n, getattr(L, _n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="live_census")
    args = ap.parse_args()
    out_dir = C.OUT / args.run
    ckpt = out_dir / "checkpoint.pkl"
    if not ckpt.exists():
        sys.exit(f"no checkpoint in {out_dir}: the run either finished or never started")
    st = pickle.loads(ckpt.read_bytes())
    people, heap = list(st["people"].values()), st["heap"]
    clock = L.hhmm(heap[0][0]) if heap else "the end"

    (out_dir / "agents").mkdir(parents=True, exist_ok=True)
    recs = []
    for p in people:
        r = {"agent": p.a, "calls": p.calls, "cost_usd": round(p.cost, 5),
             "stop": p.stop or ("ended" if p.summary else "cut"), "summary": p.summary, "end": L.hhmm(p.t),
             "log": p.log, "trips": p.trips}
        recs.append(r)
        (out_dir / "agents" / f"{p.id}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    with open(out_dir / "trips.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            for t in r["trips"]:
                f.write(json.dumps(t) + "\n")
    n, trips = len(recs), sum(len(r["trips"]) for r in recs)
    summary = {"arm": "live", "planner": "claude", "partial": True, "clock_reached": clock,
               "note": "stopped before midnight; only trips finished by clock_reached are included",
               "agents": n, "agents_started": sum(1 for p in people if p.started),
               "walks_in_progress_left_out": sum(1 for p in people if p.trip),
               "calls": st["calls"], "trips": trips,
               "auto_trips": sum(t["auto"] for r in recs for t in r["trips"]), "usd": round(st["usd"], 4),
               "usd_per_agent": round(st["usd"] / n, 5) if n else 0, "tokens": st["tok"],
               "how_days_ended": dict(Counter(r["stop"] for r in recs))}
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
