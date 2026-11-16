# Same route, by coincidence

COMP1110 group project at HKU (Celsia, Jerry, Angie, Bryan, Michelle): *Modeling and understanding
coincidences: accidentally having the same route.*

10,000 synthetic people live one weekday on the real footpaths from Kennedy Town to Sai Ying Pun. Each
person is played by Claude Haiku 5.5 and plans their own day with map tools; every walk follows the
quickest path and records each turn. The analysis measures how often a stranger makes your same turns
in a row, within 90 seconds, purely by coincidence.

**Results website:** https://claude.ai/artifact/KwTUxCbLH9h1zDb2tTBqUp

## Start here

```bash
pip install -r requirements.txt
```

```bash
python -m sameroute ui
```

Open http://127.0.0.1:8765. On the left are the runs in `runs/`; pick one to replay its day on the map (press
play, drag the clock, click anyone to see who they are and every walk and tool call of their day), read its
analysis tables under **Results**, and browse the paper figures under **Figures**. **New free run** starts a
simulation with the rule-based planner (no API key, no cost) so you can watch one in progress: the live world
moves on its shared clock in front of you; the Agent World fills up as each person finishes their day. Paid runs
started from the command line show up in the same way, with their spend against the budget.

## One command for everything

Every part of the project is a command of `python -m sameroute` (run from the repository root). With no command it
lists them all; `python -m sameroute <command> --help` lists a command's options.

| To... | Run |
|---|---|
| See every command | `python -m sameroute` |
| Watch runs and read results in the browser | `python -m sameroute ui` |
| See how far each run got, in the terminal | `python -m sameroute status` |
| Check everything before spending money (free) | `python -m sameroute check` |
| Make people | `python -m sameroute people --n 10000 --seed 7 --out runs/<run>/people.jsonl` |
| Run the Agent World (experiment 2) | `python -m sameroute agent-world --run <run> --agents runs/<run>/people.jsonl --planner mock` (free) or `--planner claude` (paid) |
| Run the live world (experiment 3) | `python -m sameroute live --run <run> --agents runs/<run>/people.jsonl --limit 1000 --planner mock` (free) or `--planner claude` (paid) |
| The main analysis | `python -m sameroute analyse following --run <run>` |
| The Q-learning follower | `python -m sameroute analyse follower-rl --run <run>` |
| A paper figure | `python -m sameroute figure following --run <run>` (and `figure arms`, `figure junction-shares`, ...) |
| The final experiments, step by step | `bash run_experiments.sh <step>`, as `docs/RUNBOOK.md` explains |

Paid runs stop at their `--budget`, and can be stopped any time with Ctrl+C (or **Stop** in the UI); run the same
command again to continue, without paying twice for anyone who finished. Put your Anthropic API key in `.env` at
the repository root (`ANTHROPIC_API_KEY=...`; git ignores the file) or in the environment.

## What is where

| Path | What it is |
|---|---|
| `docs/RUNBOOK.md` | How to run the final experiments: the commands, costs, checks and what to report. Read before spending money. |
| `docs/method.md` | The design of the experiment, with the authors' decisions. `docs/plan.md` and `docs/method-review.md` track it against the paper. |
| `docs/simulator.md` | How the simulator works: the world, the people, their tools, the outputs, each analysis. |
| `run_experiments.sh` | The final experiments, one step at a time (`people`, `check`, `agent-world`, `control`, `live`, `analyse`, `pack`). |
| `sameroute/config.py` | Every setting the simulation uses (walking speeds, the model, prices, budgets) and where files live. |
| `sameroute/world/` | The map: building it from OpenStreetMap (`build_map.py`), place captions, routing and walking (`world.py`), intersections (`decisions.py`), groups of people. |
| `sameroute/people.py` | The synthetic population, in the proportions of the 2021 census and HKU's figures. |
| `sameroute/sim/` | The simulations: the Agent World (`agent_world.py`, with the agent's tools and prompts in `agent_tools.py`), the live world (`live_world.py`), random walking, the preflight checks, and the progress reports the UI reads. |
| `sameroute/analysis/` | Following at real intersections and the Markov chains (`following.py`), the Q-learning follower (`follower_rl.py`), the arms compared (`arms.py`), chain tests (`model_tests.py`), shared turns. |
| `sameroute/figures/` | The paper figures, written to `graphs/`. |
| `sameroute/export/` | The website data, the amenity heat map, and the results of a live run stopped before midnight. |
| `sameroute/ui/` | The browser UI (standard library only). |
| `data/` | The map (`graph.json`, `places.csv`), the population sources (`population_figures.csv`) and the walking-speed sources (`walking_speeds.csv`). |
| `runs/` | One folder per run (below). Test runs you make stay out of git. |
| `graphs/` | Paper figures (PDF and PNG). |
| `results/` | Paper tables. `results.xlsx` has all the results in one workbook. |
| `website/` | The results website (`same-route-simulator.html`, which reads `web.json` next to it) and the amenity heat map. |
| `tests/` | `python -m unittest discover tests`: checks that the simulation still gives exactly the results it gave before (30 seconds, free). |

## The runs in this repository

| Run | What it is | People | Walks | Cost |
|---|---|---|---|---|
| `runs/day1/` | Experiment 1: Agent World, the earlier population (74% HKU students) | 10,000 | 57,530 | US$20.49 |
| `runs/census_run/` | Experiment 2: Agent World, the census population | 10,000 | 42,377 | US$17.06 |
| `runs/live_census/` | Experiment 3: live world, the first 1,000 census people, stopped at 16:22 on its clock | 1,000 | 3,169 | US$36.30 |

Each holds `run_summary.json`, `analysis/` (the result tables; `analysis/following.md` is the main one), and the raw
output compressed, because the plain files are over GitHub's size limit: `trips.jsonl.gz` (every walk, with each
road segment, time and turn), `people.jsonl.gz` (the people) and `agents.tar.gz` (one file per person: their whole
day, including every tool call the agent made). The UI reads the compressed files directly. To re-run an analysis,
unpack them in place first:

```bash
cd runs/census_run && gunzip -k trips.jsonl.gz people.jsonl.gz && tar -xzf agents.tar.gz && cd ../..
```

```bash
python -m sameroute analyse following --run census_run
```

## Before the reorganisation

The code used to live in `hku-agents/` as one script per step, run from inside that folder, with outputs in
`hku-agents/out/`. The same code is now the `sameroute` package, the same steps are commands of
`python -m sameroute`, and outputs are in `runs/`. The simulations, protocols and methods are unchanged: every
step was run before and after on the same inputs and gave byte-identical outputs, and `tests/` keeps checking it.

| Before (in `hku-agents/`) | Now (in the repository root) |
|---|---|
| `python make_agents.py ...` | `python -m sameroute people ...` |
| `python preflight.py ...` | `python -m sameroute check ...` |
| `python run_day.py ...` | `python -m sameroute agent-world ...` |
| `python live.py ...` | `python -m sameroute live ...` |
| `python random_walk.py ...` | `python -m sameroute random-walk ...` |
| `python analyze.py ...` | `python -m sameroute analyse summary ...` |
| `python following.py ...` | `python -m sameroute analyse following ...` |
| `python arms.py ...` | `python -m sameroute analyse arms ...` |
| `python follower_rl.py ...`, `follower.py ...` | `python -m sameroute analyse follower-rl ...`, `analyse follower ...` |
| `python extra_analysis.py ...` | `python -m sameroute analyse model-tests ...` |
| `python make_shared_turns_table.py ...`, `live_shared_turns.py ...` | `python -m sameroute analyse shared-turns-table ...`, `analyse live-shared-turns ...` |
| `python make_following_figures.py`, `make_compare_figures.py`, `make_junction_figure.py`, `make_junction_graph.py` | `python -m sameroute figure following`, `figure arms`, `figure junction-shares`, `figure junction-probabilities` |
| `python live_figures.py`, `live_single_figures.py`, `make_network_figure.py`, `make_figures.py`, `make_map_figure.py` | `python -m sameroute figure live-vs-agent-world`, `figure live-single`, `figure intersections`, `figure amenity`, `figure map` |
| `python export_web.py`, `export_amenity_map.py`, `export_partial_live.py` | `python -m sameroute export web`, `export amenity-map`, `export partial-live` |
| `python build_map.py`, `captions.py`, `pipeline.py` | `python -m sameroute build-map`, `captions`, `pipeline` |

A live-world checkpoint saved by the old `live.py` still loads (`python -m sameroute export partial-live`).
`pip install -e .` also installs a `sameroute` command, so `sameroute ui` works from anywhere.

Map data © OpenStreetMap contributors, ODbL.
