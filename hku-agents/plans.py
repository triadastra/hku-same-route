"""The plans of a finished run: every tool call each person made, without the trips.

A plans file is small (a few MB for 10,000 people) where the full output is hundreds of MB, and it is
all the replay planner needs to walk the same days again for free, with the same or another route mode.
run_day.py writes out/<run>/plans.jsonl.gz when a run finishes. For an older run:

    python plans.py --run day1          # -> out/day1/plans.jsonl.gz
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import config as C

NAME = "plans.jsonl.gz"


def fingerprint(agent):
    """A short hash of a person, so plans are never replayed on different people."""
    return hashlib.sha1(json.dumps(agent, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def plan_of(rec):
    return {"id": rec["agent"]["id"], "who": fingerprint(rec["agent"]), "calls": rec["calls"], "stop": rec["stop"],
            "cost_usd": rec["cost_usd"], "log": [[l["tool"], l["input"]] for l in rec["log"]]}


def write_plans(run_dir, recs, summary):
    """First line: what the run was. Then one line per person, in id order."""
    head = {"plans_of": run_dir.name, **{k: summary.get(k) for k in ("planner", "model", "routes", "agents", "usd")}}
    path = run_dir / NAME
    with gzip.GzipFile(path, "wb", mtime=0) as f:  # mtime=0: the same run always gives the same bytes
        f.write((json.dumps(head, ensure_ascii=False) + "\n").encode())
        for rec in recs:
            f.write((json.dumps(plan_of(rec), ensure_ascii=False) + "\n").encode())
    return path


def find(source):
    """A run name, a run folder or a plans file -> (plans file or None, agents folder or None)."""
    p = Path(source)
    if p.is_file():
        return p, None
    run_dir = p if p.is_dir() else C.OUT / source
    if (run_dir / NAME).exists():
        return run_dir / NAME, None
    if (run_dir / "agents").is_dir():
        return None, run_dir / "agents"
    raise SystemExit(f"no plans to replay for '{source}': expected {run_dir / NAME} or {run_dir / 'agents'}.\n"
                     f"Finish that run first, or name another with --replay-from.")


def load_plans(source):
    """-> (header, {person id: plan})."""
    file, agents_dir = find(source)
    if file:
        with gzip.open(file, "rt", encoding="utf-8") as f:
            head = json.loads(f.readline())
            return head, {p["id"]: p for p in map(json.loads, f)}
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(agents_dir.glob("A*.json"))]
    summary = agents_dir.parent / "run_summary.json"
    head = json.loads(summary.read_text(encoding="utf-8")) if summary.exists() else {}
    if head.get("planner") == "claude":
        head.setdefault("model", C.MODEL)
    return {"plans_of": agents_dir.parent.name, **head}, {r["agent"]["id"]: plan_of(r) for r in recs}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    run_dir = C.OUT / args.run
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((run_dir / "agents").glob("A*.json"))]
    if not recs:
        raise SystemExit(f"no finished people in {run_dir / 'agents'}")
    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    if summary.get("planner") == "claude":
        summary.setdefault("model", C.MODEL)
    summary.setdefault("routes", "quickest")
    path = write_plans(run_dir, recs, summary)
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB): the plans of {len(recs)} people")


if __name__ == "__main__":
    main()
