"""The whole experiment in one command: agents -> day -> analysis -> website data.

    python pipeline.py --run test --n 300 --planner mock                     # free dry run
    python pipeline.py --run day1 --n 5000 --planner claude --budget 40      # the real thing

A stopped run can be restarted with the same command: finished agents are kept and not paid for again.
"""
import argparse
import subprocess
import sys

import config as C


def step(*cmd):
    print("\n$ python " + " ".join(cmd), flush=True)
    if subprocess.call([sys.executable, *cmd], cwd=C.ROOT) != 0:
        raise SystemExit(f"stopped: '{cmd[0]}' failed")


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
        step("build_map.py")
    if not (C.DATA / "places.csv").exists():
        step("captions.py")
    run = C.OUT / args.run
    run.mkdir(parents=True, exist_ok=True)
    agents = run / "people.jsonl"
    if not agents.exists():  # keep the same people when a run is resumed
        step("make_agents.py", "--n", str(args.n), "--seed", str(args.seed), "--out", str(agents))
    if args.planner == "claude":
        step("preflight.py", "--agents", str(agents), "--key")
    step("run_day.py", "--run", args.run, "--planner", args.planner, "--agents", str(agents),
         "--budget", str(args.budget), "--concurrency", str(args.concurrency), "--seed", str(args.seed))
    step("analyze.py", "--run", args.run, "--seed", str(args.seed))
    step("export_web.py", "--run", args.run, "--max-agents", str(args.web_agents), "--seed", str(args.seed))
    print(f"\nDone. Results: {run / 'analysis' / 'summary.md'}  Website data: {run / 'web' / 'web.json'}")


if __name__ == "__main__":
    main()
