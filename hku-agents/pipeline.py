"""The whole experiment in one command: people -> day -> analysis -> website data.

    python pipeline.py                 # list the modes
    python pipeline.py check           # free: is this checkout able to repeat the experiment?
    python pipeline.py smoke           # free: 300 rule-based people through the whole chain
    python pipeline.py default         # OUR DEFAULT SETUP: 10,000 people played by Claude (about US$20)
    python pipeline.py replay --from default --routes step-free    # free: same plans, other routes

Every mode is a set of defaults; any flag overrides it (python pipeline.py default --n 2000 --run mine).
Results go to out/<run>/, with a manifest.json recording exactly what was run. A stopped run can be
restarted with the same command: finished people are kept and not paid for again.
"""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time

import config as C
from agent_tools import ROUTE_MODES

# The published run (out/day1) used these people and samples: 10,000 people drawn with seed 7.
SEED = 7
PUBLISHED = "day1"
BASE = {"n": 300, "seed": SEED, "planner": "mock", "routes": "quickest", "budget": C.BUDGET_USD,
        "concurrency": C.CONCURRENCY, "web_agents": 2000}
MODES = {
    "default": ({"n": 10000, "planner": "claude", "budget": 45.0, "concurrency": 24},
                "our default setup: 10,000 people played by Claude, quickest paths (about US$20, 2 hours)"),
    "pilot": ({"n": 200, "planner": "claude", "budget": 2.0, "concurrency": 8},
              "200 people played by Claude: a cheap look at real behaviour (about US$0.40)"),
    "smoke": ({}, "300 rule-based people: tests the whole chain in seconds (free, no key)"),
    "mock": ({"n": 10000}, "10,000 rule-based people: a no-LLM comparison at full size (free, no key)"),
    "replay": ({"n": 10000, "planner": "replay"},
               "walk the plans of a finished run again, usually with another --routes (free, no key)"),
    "check": (None, "verify the data, the walking code and the Claude loop, then run smoke (free, no key)"),
}


def step(*cmd):
    print("\n$ python " + " ".join(cmd), flush=True)
    if subprocess.call([sys.executable, *cmd], cwd=C.ROOT) != 0:
        raise SystemExit(f"stopped: '{cmd[0]}' failed")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_version():
    try:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=C.ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "."], cwd=C.ROOT, text=True,
                                        stderr=subprocess.DEVNULL).strip()
        return rev + (" (with uncommitted changes)" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown (not a git checkout)"


def settings_of(s):
    """Everything that decides what a run means. A run folder holds exactly one of these."""
    llm = s["planner"] == "claude"
    return {"people": s["n"], "seed": s["seed"], "planner": s["planner"], "routes": s["routes"],
            "replay_from": s["replay_from"] if s["planner"] == "replay" else None,
            "model": C.MODEL if llm else None, "effort": C.EFFORT if llm else None,
            "max_calls_per_agent": C.MAX_CALLS_PER_AGENT if llm else None, "max_tokens": C.MAX_TOKENS if llm else None,
            "weather": C.WEATHER, "shared_window_s": C.SHARED_WINDOW,
            "walking": {"speed_m_s": C.WALK_SPEED, "steps_factor": C.STEPS_FACTOR, "lift_seconds": C.LIFT_SECONDS,
                        "unlit_penalty_s": C.UNLIT_PENALTY, "stairs_avoid_s_per_m": C.STAIRS_AVOID}}


def write_manifest(run, mode, s, people):
    """Record what this run is. A resumed run must have the same settings, or its people would not be comparable."""
    path = run / "manifest.json"
    settings = settings_of(s)
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if old and old["settings"] != settings:
        diff = [f"  {k}: this folder has {old['settings'].get(k)!r}, you asked for {v!r}"
                for k, v in settings.items() if old["settings"].get(k) != v]
        raise SystemExit(f"stopped: {run} already holds a run with other settings:\n" + "\n".join(diff)
                         + "\nPick another name with --run, or delete that folder to start again.")
    try:
        import anthropic
        sdk = anthropic.__version__
    except ImportError:
        sdk = None
    files = {"data/graph.json": sha256(C.DATA / "graph.json"), "data/places.csv": sha256(C.DATA / "places.csv"),
             "people.jsonl": sha256(people)}
    if old and old["files"] != files:
        changed = [k for k, v in files.items() if old["files"].get(k) != v]
        raise SystemExit(f"stopped: {', '.join(changed)} changed since {run} was started, so its finished people lived "
                         f"in a different world. Pick another name with --run, or delete that folder.")
    session = {"started": time.strftime("%Y-%m-%d %H:%M:%S %z"), "command": "python pipeline.py " + " ".join(sys.argv[1:]),
               "budget_usd": s["budget"], "concurrency": s["concurrency"], "code": git_version(),
               "python": platform.python_version(), "platform": platform.platform(), "anthropic_sdk": sdk}
    manifest = {"run": run.name, "mode": mode, "settings": settings, "files": files,
                "sessions": (old["sessions"] if old else []) + [session]}
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def run_pipeline(mode, s):
    if not (C.DATA / "graph.json").exists():
        step("build_map.py")
    if not (C.DATA / "places.csv").exists():
        step("captions.py")
    run = C.OUT / s["run"]
    run.mkdir(parents=True, exist_ok=True)
    people = run / "people.jsonl"
    if not people.exists():  # keep the same people when a run is resumed
        source = C.OUT / s["replay_from"] / "people.jsonl"
        if s["planner"] == "replay" and source.exists():
            shutil.copyfile(source, people)  # a replay walks the very people of the run it replays
        else:
            step("make_agents.py", "--n", str(s["n"]), "--seed", str(s["seed"]), "--out", str(people))
    write_manifest(run, mode, s, people)
    print(f"\n{mode} mode -> {run}: {s['n']} people (seed {s['seed']}), planner {s['planner']}, routes {s['routes']}"
          + (f", budget US${s['budget']:.2f}, {s['concurrency']} in parallel" if s["planner"] == "claude" else "")
          + (f", plans from '{s['replay_from']}'" if s["planner"] == "replay" else ""), flush=True)
    if s["planner"] == "claude":
        step("preflight.py", "--agents", str(people), "--key")
    day = ["run_day.py", "--run", s["run"], "--planner", s["planner"], "--routes", s["routes"], "--agents", str(people),
           "--budget", str(s["budget"]), "--concurrency", str(s["concurrency"]), "--seed", str(s["seed"])]
    if s["planner"] == "replay":
        day += ["--replay-from", s["replay_from"]]
    step(*day)
    step("analyze.py", "--run", s["run"], "--seed", str(s["seed"]))
    step("export_web.py", "--run", s["run"], "--max-agents", str(s["web_agents"]), "--seed", str(s["seed"]))
    # Compare like with like: a replay with the run it replays, a full-size run with the published one.
    ref = s["replay_from"] if s["planner"] == "replay" else PUBLISHED
    if ref != s["run"] and (s["planner"] == "replay" or s["n"] == MODES["default"][0]["n"]) \
            and (C.OUT / ref / "analysis" / "shared_turns.csv").exists():
        step("compare.py", "--run", s["run"], "--ref", ref)
    print(f"\nDone. Results: {run / 'analysis' / 'summary.md'}  Website data: {run / 'web' / 'web.json'}")


def check():
    step("verify.py")
    step("preflight.py")
    shutil.rmtree(C.OUT / "check", ignore_errors=True)  # always a fresh run, so the check tests today's code
    run_pipeline("smoke", {**BASE, "run": "check", "replay_from": ""})
    print("\nAll checks passed: this checkout can repeat the experiment. Next: python pipeline.py default")


def main():
    ap = argparse.ArgumentParser(description="Run the whole experiment in one command.",
                                 epilog="Modes:\n" + "\n".join(f"  {m:<8} {text}" for m, (_, text) in MODES.items())
                                 + "\n\nRoutes:\n" + "\n".join(f"  {m:<10} {text}" for m, text in ROUTE_MODES.items()),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", choices=list(MODES), help="a named setup; see below")
    ap.add_argument("--run", help="name of the output folder out/<run>/ (default: the mode's name)")
    ap.add_argument("--n", type=int, help="number of people")
    ap.add_argument("--seed", type=int, help=f"draws the people and the samples (default {SEED}, as published)")
    ap.add_argument("--planner", choices=["mock", "claude", "replay"])
    ap.add_argument("--routes", choices=list(ROUTE_MODES), help="how walks are routed (default quickest)")
    ap.add_argument("--from", dest="replay_from", default="day1", help="replay: the finished run to take plans from (default day1)")
    ap.add_argument("--budget", type=float, help="US$ at which the Claude planner stops starting new people")
    ap.add_argument("--concurrency", type=int, help="people run in parallel by the Claude planner")
    ap.add_argument("--web-agents", type=int, help="people included in the website replay")
    args = ap.parse_args()

    if args.mode is None and args.run is None:
        ap.print_help()
        return
    if args.mode == "check":
        return check()
    mode = args.mode or "custom"
    s = {**BASE, **(MODES[mode][0] if args.mode else {})}
    s.update({k: v for k, v in vars(args).items() if v is not None and k != "mode"})
    if s["planner"] == "replay":
        s.setdefault("run", f"replay-{s['replay_from']}-{s['routes']}")
        if s["run"] == s["replay_from"]:
            raise SystemExit("stopped: a replay needs its own folder; pick another name with --run")
        source = C.OUT / s["replay_from"] / "manifest.json"
        if source.exists():  # the same people as the replayed run, whatever --n and --seed say
            old = json.loads(source.read_text(encoding="utf-8"))["settings"]
            s["n"], s["seed"] = old["people"], old["seed"]
    s.setdefault("run", mode)
    run_pipeline(mode, s)


if __name__ == "__main__":
    main()
