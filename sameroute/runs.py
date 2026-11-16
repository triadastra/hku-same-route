"""What is in runs/: each run's kind, how far it got, and its trips, people and analysis.

    python -m sameroute status          # one line per run

A run folder can hold any of: people.jsonl(.gz), agents/ or agents.tar.gz (one record per person),
trips.jsonl(.gz), run_summary.json, analysis/, checkpoint.pkl (a stopped live run) and progress.json (written
while a run is going; see sameroute/sim/progress.py). This module only reads them.
"""
import gzip
import json
import os
import tarfile
import time

from sameroute import config as C
from sameroute.world.groups import LABELS, group_of

STALE_S = 120     # a "running" run whose progress has not changed for this long, and whose process is gone, stopped


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_names():
    if not C.OUT.exists():
        return []
    marks = ("trips.jsonl", "trips.jsonl.gz", "agents", "agents.tar.gz", "progress.json", "checkpoint.pkl",
             "run_summary.json")
    return sorted(d.name for d in C.OUT.iterdir() if d.is_dir() and any((d / m).exists() for m in marks))


def info(name):
    """Everything the UI and `status` show about one run."""
    d = C.OUT / name
    summary = read_json(d / "run_summary.json")
    progress = read_json(d / "progress.json")
    live = bool((progress or {}).get("kind") == "live" or (summary or {}).get("arm") == "live"
                or (d / "checkpoint.pkl").exists() or (d / "live_positions.json").exists())
    status = "no output"
    if progress:
        status = progress.get("status", "running")
        if status == "running" and not pid_alive(progress.get("pid")) and time.time() - progress.get("updated", 0) > 5:
            status = "stopped"
    elif summary:
        status = "partial" if summary.get("partial") else "finished"
    elif (d / "checkpoint.pkl").exists():
        status = "stopped"
    if status == "finished" and summary and summary.get("partial"):
        status = "partial"
    analysis = sorted(str(p.relative_to(d / "analysis")) for p in (d / "analysis").rglob("*")
                      if p.is_file() and p.suffix in (".md", ".csv", ".tex")) if (d / "analysis").exists() else []
    people = (progress or {}).get("people") or (summary or {}).get("agents")
    agent_files = None
    if (d / "agents").is_dir():
        agent_files = sum(1 for _ in (d / "agents").glob("A*.json"))
    return {
        "name": name, "kind": "live" if live else "agent-world", "status": status,
        "planner": (progress or {}).get("planner") or (summary or {}).get("planner"),
        "people": people, "agent_files": agent_files, "summary": summary, "progress": progress,
        "has_trips": (d / "trips.jsonl").exists() or (d / "trips.jsonl.gz").exists(),
        "has_people": (d / "people.jsonl").exists() or (d / "people.jsonl.gz").exists(),
        "has_agents": (d / "agents").is_dir() or (d / "agents.tar.gz").exists(),
        "has_positions": (d / "live_positions.json").exists(),
        "analysis": analysis,
        "updated": max((p.stat().st_mtime for p in d.iterdir()), default=0),
    }


# ---------------- reading a run ----------------
def _lines(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def trips(name):
    """Every trip of a run: from trips.jsonl, else trips.jsonl.gz, else the people finished so far (agents/)."""
    d = C.OUT / name
    for p in (d / "trips.jsonl", d / "trips.jsonl.gz"):
        if p.exists():
            yield from _lines(p)
            return
    if (d / "agents").is_dir():
        for p in sorted((d / "agents").glob("A*.json")):
            rec = read_json(p)
            if rec:
                yield from rec.get("trips", [])


def trips_source(name):
    """The file trips() reads, and its modification time (for caching)."""
    d = C.OUT / name
    for p in (d / "trips.jsonl", d / "trips.jsonl.gz"):
        if p.exists():
            return p, p.stat().st_mtime
    if (d / "agents").is_dir():
        return d / "agents", max((p.stat().st_mtime for p in (d / "agents").glob("A*.json")), default=0)
    return None, 0


def people(name, ids=None):
    """{id: person} for a run: its own people file, else the file the run was started from, else any other run's
    people file that has these people (a live run takes its people from an Agent World run)."""
    d = C.OUT / name
    cands = [d / "people.jsonl", d / "people.jsonl.gz"]
    pf = (read_json(d / "progress.json") or {}).get("people_file")
    if pf:
        cands.append(C.ROOT / pf if not os.path.isabs(pf) else type(d)(pf))
    for other in run_names():
        if other != name:
            cands += [C.OUT / other / "people.jsonl", C.OUT / other / "people.jsonl.gz"]
    cands += [C.DATA / "agents.jsonl", C.DATA / "agents_10k.jsonl"]
    want = set(ids) if ids else None
    for p in cands:
        if not p.exists():
            continue
        found = {a["id"]: a for a in _lines(p) if want is None or a["id"] in want}
        if found and (want is None or len(found) >= 0.9 * len(want)):
            return found
    return {}


def person(name, pid):
    """One person's full record (persona, every tool call, every trip): agents/<id>.json or agents.tar.gz."""
    d = C.OUT / name
    p = d / "agents" / f"{pid}.json"
    if p.exists():
        return read_json(p)
    tar = d / "agents.tar.gz"
    if tar.exists():
        with tarfile.open(tar, "r:gz") as t:
            for m in t:
                if m.name.endswith(f"/{pid}.json") or m.name == f"{pid}.json":
                    return json.loads(t.extractfile(m).read().decode("utf-8"))
    return None


def group_label(agent):
    try:
        return LABELS[group_of(agent)]
    except (KeyError, TypeError):
        return "Unknown"


# ---------------- python -m sameroute status ----------------
def main():
    names = run_names()
    if not names:
        print(f"No runs yet in {C.OUT}. Try a free one:  python -m sameroute agent-world --run try --planner mock --limit 300")
        return
    print(f"{'run':<16} {'kind':<12} {'status':<10} {'planner':<7} {'people':>7} {'trips':>7} {'US$':>8}  notes")
    for n in names:
        r = info(n)
        s, p = r["summary"] or {}, r["progress"] or {}
        notes = []
        if r["status"] == "running":
            if r["kind"] == "live" and p.get("clock") is not None:
                clock = int(p["clock"])
                notes.append(f"clock {clock // 3600 % 24:02d}:{clock // 60 % 60:02d}")
            notes.append(f"{p.get('done', 0)}/{p.get('people')} people done")
        if s.get("clock_reached"):
            notes.append(f"stopped at {s['clock_reached']}")
        if p.get("message") and r["status"] != "finished":
            notes.append(p["message"])
        if r["analysis"]:
            notes.append(f"{len(r['analysis'])} analysis files")
        usd = s.get("usd", p.get("usd"))
        print(f"{n:<16} {r['kind']:<12} {r['status']:<10} {str(r['planner'] or ''):<7} {str(r['people'] or ''):>7} "
              f"{str(s.get('trips', '')):>7} {'' if usd is None else f'{usd:.2f}':>8}  {'; '.join(notes)}")
    print("\nSee them in the browser:  python -m sameroute ui")


if __name__ == "__main__":
    main()
