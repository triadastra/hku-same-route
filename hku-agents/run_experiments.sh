#!/usr/bin/env bash
# =====================================================================================================================
# run_experiments.sh: run the final experiments of the HKU same-route study, one step at a time.
#
# Read RUNBOOK.md (in the repository root) before running any step that costs money.
#
#   bash run_experiments.sh people        free      make the 10,000 people in census and HKU proportions
#   bash run_experiments.sh check         < US$0.01 offline tests, then the API key and one real person
#   bash run_experiments.sh agent-world   ~US$20    experiment 2: Agent World, 10,000 people (stops at US$30)
#   bash run_experiments.sh control       free      experiment 5: the same people with the rule-based planner, no LLM
#   bash run_experiments.sh live          ~US$20-60 experiment 3: live world, 1,000 of the same people (stops at US$60)
#   bash run_experiments.sh analyse       free      following, Markov chains, tests and figures (1 to 2 hours of computing)
#   bash run_experiments.sh pack          free      compress the raw output so it fits on GitHub
#   bash run_experiments.sh all           all of the above, in this order
#
# The paid steps can be stopped at any time (budget, network, Ctrl+C) and run again with the same command: people
# who finished are kept and are not paid for twice.
#
# Settings can be changed with environment variables, for example a 20-person live-world pilot:
#   LIVE_RUN=live_pilot LIVE_PEOPLE=20 LIVE_BUDGET=3 bash run_experiments.sh live
# Only the run names census_run and live_census are kept by .gitignore; other names stay out of git.
#
# The API key is read from the environment variable ANTHROPIC_API_KEY (or from hku-agents/.env, which git ignores).
# Never print, log, commit or paste the key.
# =====================================================================================================================
set -euo pipefail
cd "$(dirname "$0")"                             # always run from hku-agents/

CENSUS_RUN="${CENSUS_RUN:-census_run}"           # experiment 2: Agent World, census population
CONTROL_RUN="${CONTROL_RUN:-census_control}"     # experiment 5: same people, rule-based planner (free, not kept in git)
LIVE_RUN="${LIVE_RUN:-live_census}"              # experiment 3: live world
N_PEOPLE="${N_PEOPLE:-10000}"                    # people in the Agent World run
SEED="${SEED:-7}"                                # seed of the people (the mix checked in method.md uses 7)
LIVE_PEOPLE="${LIVE_PEOPLE:-1000}"               # the first N of the same people go into the live world
AGENT_BUDGET="${AGENT_BUDGET:-30}"               # US$: the Agent World stops starting new people at this spend
LIVE_BUDGET="${LIVE_BUDGET:-60}"                 # US$: the live world stops (and saves) at this spend
CONCURRENCY="${CONCURRENCY:-24}"                 # people asked at once; lower it (e.g. 8) if the API rate-limits

PEOPLE="out/$CENSUS_RUN/people.jsonl"

say() { printf '\n==== %s\n' "$*"; }

need_key() {
  # True if the key is set in the environment or in .env (config.py loads .env). Prints only yes or no.
  if ! python -c 'import os, sys, config; sys.exit(0 if os.environ.get("ANTHROPIC_API_KEY") else 1)'; then
    echo "ANTHROPIC_API_KEY is not set in this session."
    echo "Add it in the cloud environment's settings (environment variables) and restart the session,"
    echo "or put the line ANTHROPIC_API_KEY=<key> in hku-agents/.env (git ignores that file)."
    exit 1
  fi
  echo "API key: found (not shown)."
}

need_people() {
  [ -f "$PEOPLE" ] || { echo "No people yet: run   bash run_experiments.sh people   first."; exit 1; }
}

summary() {
  # Print a run's summary: people, trips, cost, how the days ended.
  python - "$1" <<'PY'
import json, sys
s = json.load(open(f"out/{sys.argv[1]}/run_summary.json"))
keys = ("planner", "agents", "trips", "auto_trips", "calls", "usd", "usd_per_agent", "how_days_ended")
print(json.dumps({k: s[k] for k in keys if k in s}, indent=2))
PY
}

step_people() {
  say "People: $N_PEOPLE in census and HKU proportions (seed $SEED) -> $PEOPLE"
  mkdir -p "out/$CENSUS_RUN"
  if [ -f "$PEOPLE" ]; then
    echo "Keeping the existing $PEOPLE (delete it to make the people again)."
  else
    # Prints the mix against its targets: residents, HKU students and staff by faculty, ages, walking speeds.
    python make_agents.py --n "$N_PEOPLE" --seed "$SEED" --out "$PEOPLE"
  fi
}

step_check() {
  say "Packages"
  python -c "import anthropic, numpy, scipy, matplotlib" 2>/dev/null || pip install anthropic numpy scipy matplotlib
  say "Offline checks: files, SDK, the agent loop through a fake server (no key, no cost)"
  python preflight.py
  need_key
  say "Key check (free token count) and one real person's day (less than US\$0.01)"
  need_people
  python preflight.py --one --agents "$PEOPLE"
}

step_agent_world() {
  need_key; need_people
  say "Experiment 2: Agent World, $N_PEOPLE people, Claude Haiku, budget US\$$AGENT_BUDGET, $CONCURRENCY at once"
  # Each person plans their own weekday with the map tools and walks by the quickest path, at a pace they choose.
  # About 2 hours. Progress every 10 people. Re-running the same command continues where it stopped.
  python run_day.py --run "$CENSUS_RUN" --planner claude --agents "$PEOPLE" \
    --budget "$AGENT_BUDGET" --concurrency "$CONCURRENCY"
  summary "$CENSUS_RUN"
}

step_control() {
  need_people
  say "Experiment 5: the same people with the rule-based planner, no LLM (free, about 1 minute)"
  python run_day.py --run "$CONTROL_RUN" --planner mock --agents "$PEOPLE"
  summary "$CONTROL_RUN"
}

step_live() {
  need_key; need_people
  say "Experiment 3: live world, first $LIVE_PEOPLE of the same people, budget US\$$LIVE_BUDGET, $CONCURRENCY at once"
  # Everyone shares one clock and chooses every junction themselves (no navigation app), seeing people within 50 m.
  # Prints the clock time, people walking, calls and spend every 500 rounds; saves a checkpoint every 2 minutes.
  # Watch the spend in the first progress lines: if it is heading far past the estimate, press Ctrl+C (it saves)
  # and ask the user before going on.
  python live.py --run "$LIVE_RUN" --planner claude --agents "$PEOPLE" --limit "$LIVE_PEOPLE" \
    --budget "$LIVE_BUDGET" --concurrency "$CONCURRENCY"
  summary "$LIVE_RUN"
}

step_analyse() {
  [ -f "out/$CENSUS_RUN/trips.jsonl" ] || { echo "Run the agent-world step first."; exit 1; }
  local control_arg=()
  [ -f "out/$CONTROL_RUN/trips.jsonl" ] && control_arg=(--control "$CONTROL_RUN")
  say "Following, Markov chains and tests on experiment 2 (30 to 60 minutes)"
  python following.py --run "$CENSUS_RUN" "${control_arg[@]}"
  python make_following_figures.py --run "$CENSUS_RUN"
  python make_junction_figure.py --run "$CENSUS_RUN"
  if [ -f "out/$LIVE_RUN/trips.jsonl" ]; then
    say "The live world's own results, and experiment 2 on the same people, to compare like with like"
    python following.py --run "$LIVE_RUN"
    python following.py --run "$CENSUS_RUN" --people-from "$LIVE_RUN"
  fi
  say "Road use and nearby places (10 to 20 minutes)"
  python arms.py --run "$CENSUS_RUN"
  python make_compare_figures.py --run "$CENSUS_RUN"
  echo
  echo "Results: out/$CENSUS_RUN/analysis/following.md (main), out/$CENSUS_RUN/analysis/compare.md (road use),"
  echo "out/$LIVE_RUN/analysis/following.md and out/$CENSUS_RUN/analysis/same_people_as_$LIVE_RUN/following.md (live"
  echo "world against the Agent World on the same people). Figures in ../graphs/."
}

step_pack() {
  say "Compress the raw output for GitHub (files over 100 MB are refused)"
  for run in "$CENSUS_RUN" "$LIVE_RUN"; do
    d="out/$run"
    [ -f "$d/trips.jsonl" ] || continue
    gzip -kf "$d/trips.jsonl"
    [ -f "$d/people.jsonl" ] && gzip -kf "$d/people.jsonl"
    [ -d "$d/agents" ] && tar -czf "$d/agents.tar.gz" -C "$d" agents
    for f in "$d"/*.gz; do
      size=$(stat -c %s "$f")
      printf '%-45s %6d MB\n' "$f" $((size / 1000000))
      [ "$size" -lt 95000000 ] || echo "  WARNING: $f is too big for GitHub; split it before committing."
    done
  done
  echo "Commit the .gz files, run_summary.json and analysis/ of each run, and ../graphs/. Raw files stay out (.gitignore)."
}

case "${1:-}" in
  people)       step_people ;;
  check)        step_check ;;
  agent-world)  step_agent_world ;;
  control)      step_control ;;
  live)         step_live ;;
  analyse)      step_analyse ;;
  pack)         step_pack ;;
  all)          step_people; step_check; step_agent_world; step_control; step_live; step_analyse; step_pack ;;
  *)            sed -n '2,26p' "$0"; exit 1 ;;
esac
