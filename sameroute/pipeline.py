"""The whole experiment in one command: agents -> day -> analysis -> website data.

    python -m sameroute pipeline --run test --n 300 --planner mock                  # free dry run
    python -m sameroute pipeline --run day1 --n 5000 --planner claude --budget 40   # the real thing

A stopped run can be restarted with the same command: finished agents are kept and not paid for again.
"""
import argparse
import subprocess
import sys

from sameroute import config as C


def step(*cmd):
    """Run one command of python -m sameroute in its own process; stop if it fails."""
    print("\n$ python -m sameroute " + " ".join(cmd), flush=True)
    if subprocess.call([sys.executable, "-m", "sameroute", *cmd], cwd=C.ROOT) != 0:
        raise SystemExit(f"stopped: '{' '.join(cmd[:2])}' failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--n", type=int, default=300, help="number of people")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--planner", choices=["mock", "claude"], default="mock")
    ap.add_argument("--budget", type=float, default=C.BUDGET_USD)
    ap.add_argument("--concurrency", type=int, default=C.CONCURRENCY)
    ap.add_argument("--web-agents", type=int, default=2500, help="people included in the website replay")
    args = ap.parse_args()

    if not (C.DATA / "graph.json").exists():
        step("build-map")
    if not (C.DATA / "places.csv").exists():
        step("captions")
    run = C.OUT / args.run
    run.mkdir(parents=True, exist_ok=True)
    agents = run / "people.jsonl"
    if not agents.exists():  # keep the same people when a run is resumed
        step("people", "--n", str(args.n), "--seed", str(args.seed), "--out", str(agents))
    if args.planner == "claude":
        step("check", "--agents", str(agents), "--key")
    step("agent-world", "--run", args.run, "--planner", args.planner, "--agents", str(agents),
         "--budget", str(args.budget), "--concurrency", str(args.concurrency), "--seed", str(args.seed))
    step("analyse", "summary", "--run", args.run, "--seed", str(args.seed))
    step("export", "web", "--run", args.run, "--max-agents", str(args.web_agents), "--seed", str(args.seed))
    print(f"\nDone. Results: {run / 'analysis' / 'summary.md'}  Website data: {run / 'web' / 'web.json'}")


if __name__ == "__main__":
    main()
