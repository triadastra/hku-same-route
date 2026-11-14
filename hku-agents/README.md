# HKU same-route agents

Synthetic people live one weekday around HKU, Kennedy Town and Sai Ying Pun on the real OpenStreetMap
walking network. Each person is played by Claude Haiku 5.5 and lives the day through map tools, like
someone with a phone map. Every walk records each segment and each turn (left, right, straight,
back). The analysis then measures how often a stranger makes the same k turns as you, in a row, by
coincidence, and how different groups use each road.

## Repeat the experiment

You need Python 3.10 or newer (tested on 3.13). Everything runs from this folder, or from the
repository root as `python hku-agents/pipeline.py ...`.

```bash
pip install -r requirements.txt
```

```bash
python pipeline.py check
```

`check` is free and needs no key and no network. It confirms that your checkout has the map and
places the published run used, that `make_agents.py` draws the same 10,000 people on your machine,
that the walking code rebuilds all 10,533 walks published in `../web.json` segment by segment and
to the second, and that the Claude loop works against a fake server. It ends with a 300-person
rule-based run through the whole chain.

Then copy `.env.example` to `.env` and put your own Anthropic API key after `ANTHROPIC_API_KEY=`.
Every script reads it, and `.gitignore` keeps it out of git. Never share or upload that file.

```bash
python preflight.py --one
```

That checks the key with a free token count, then runs one real person for a whole day (under one
US cent) and prints every tool call. Now the experiment itself, in our default setup:

```bash
python pipeline.py default
```

It draws the 10,000 people (seed 7), lets each live their day with Claude Haiku 5.5, analyses the
trips, writes the website data and prints your numbers next to the published ones. The published
run cost US$20.49 and took two hours; `default` stops starting new people at US$45. If it stops
(budget, network, Ctrl+C), run the same command again: finished people are kept and not paid for
twice. A wrong or missing key stops the run on the first call.

### What repeats exactly, and what does not

| Part | Repeats exactly? |
|---|---|
| The map and places (`data/graph.json`, `data/places.csv`) | Yes: both are in the repository. Do not rerun `build_map.py` for a repeat, because OpenStreetMap has changed since. |
| The 10,000 people | Yes: `make_agents.py --n 10000 --seed 7`, also saved as `data/agents_10k.jsonl`. |
| Every walk, given where a person decides to go | Yes: quickest paths have no randomness, and each person's dawdling and strolls come from a random stream fixed by their id. |
| What each person decides to do | No. Claude plans each day afresh, so a repeat gives different days and the tables move a little. `compare.py` shows by how much. |
| The analysis of a finished run | Yes: the sample of 5,000 trips and the random-turn baseline are drawn with the run's seed. |

Because the plans are the only part that does not repeat, every run saves them in a small file,
`out/<run>/plans.jsonl.gz`: each tool call of each person. The `replay` mode walks those plans again
for free and rebuilds the run's trips exactly.

Each run folder also gets a `manifest.json`: the settings, the model, the seed, checksums of the map,
places and people, and for every session the command, the code version (git commit), and the Python
and SDK versions. A run folder holds one setup only: resuming it with other settings, or after the
data changed, stops with an explanation rather than mixing two experiments.

## Modes

`python pipeline.py` with no arguments lists them. A mode is a set of defaults; any flag overrides
it, for example `python pipeline.py default --n 2000 --run small`. Output goes to `out/<mode>/`
unless you pass `--run`.

| Mode | People | Planner | Cost | What it is for |
|---|---|---|---|---|
| `check` | 300 | rule-based | free | Verify the checkout, then test the whole chain |
| `smoke` | 300 | rule-based | free | The whole chain in seconds |
| `pilot` | 200 | Claude | about US$0.40 | A cheap look at real behaviour before the big run |
| `default` | 10,000 | Claude | about US$20 | **Our default setup**, as published |
| `mock` | 10,000 | rule-based | free | A full-size comparison with no LLM: people who only follow their timetable |
| `replay` | as the replayed run | plans of a finished run | free | Rebuild a run from its plans, or walk the same plans by other routes |

The free full-size modes (`mock`, `replay`) take about three minutes on a laptop.

Three planners decide what people do (`--planner`): `claude` plays each person with the model,
`mock` is a rule-based timetable-follower, and `replay` repeats the tool calls of a finished run.

Four route modes decide how a `go_to` walk gets there (`--routes`); strolls meander in every mode:

| Routes | How people walk |
|---|---|
| `quickest` | Everyone takes the quickest path. The published setup. |
| `step-free` | Everyone takes the quickest path when each metre of stairs feels 6 seconds longer (`STAIRS_AVOID` in `config.py`), so walks detour to slopes and lifts. |
| `noisy` | Everyone picks each turn at random, weighted toward the quicker ways. |
| `personal` | Each person walks by their own habits: step-free if they avoid stairs or their knees ache, quickest if they always take the quickest way or are running late, noisy if they walk slowly or explore, otherwise quickest. |

Routes combine with any planner. The useful combination is a replay, which changes the routes and
nothing else:

```bash
python pipeline.py replay --from default --routes step-free
```

That writes `out/replay-default-step-free/` and compares it with `default`. The people make the
same decisions as before; only the paths differ. Arrival times shift a little, so a few calls no
longer fit (staying until a time that has passed, for example) and fail as they would have then.

`--from` defaults to `day1`, the published run. Its full output is not in the repository, so
`replay` works on `day1` only once its plans file is there (see the note at the end of Outputs).

## The world

`python build_map.py` downloads the map (cached in `data/osm_*.json`) and writes `data/graph.json`:
about 3,500 junctions, 4,800 path segments, 156 km of walkable path, 383 stair segments, 48 lift links,
and **1,538 places**: every named building and every amenity in the area. That covers HKU buildings,
halls, MTR exits, bus stops, food, shops, parks, sights and the waterfront, ATMs and banks, pharmacies
and clinics, public toilets, vending machines and drinking water, schools, places of worship, public
services, and residential and office buildings. Unnamed amenities get a name from the nearest landmark,
such as "Public toilet near Hill Road Garden".

`python captions.py` writes `data/places.csv`, one row per place with a caption (what it is and what you
can do there) and search aliases. **Check and correct the captions by hand**; rerunning keeps your edits.

## The people

`python make_agents.py --n 10000 --seed 7` (what `default` runs) draws each person at random from the mixes in the file:

- role: undergrad, postgrad, staff or local resident, with faculty, year and age
- home: a hall, the MTR exit or bus stop they commute through, or (for residents) a real residential
  building. Residents are retired, work outside the area (leave by MTR, back in the evening), work a
  shift at a nearby shop or restaurant, or are at home today
- fixed commitments: classes in HKU's :30 to :20 slots, office hours, a shift or an errand
- personality, two habits, how spontaneous they are, two or three interests, how they feel today,
  and facts such as an assignment due tomorrow or money being tight
- walking pace (0.85 to 1.2 times average)

Behaviour is never scripted. The instructions do not suggest what to do with free time; any variety,
such as one person wandering the Kennedy Town waterfront while another games in their hall, comes from
these drawn traits. Each person starts with a rough mental map: their neighbourhood and the direction
and walking time to their commitments, the nearest MTR exit, the main and Centennial campuses, Kennedy
Town and Sai Ying Pun. Everything else they look up with the tools.

## What a person can do

| Tool | What it does |
|---|---|
| `where_am_i` | The neighbourhood and the closest places around, with direction and walking time |
| `search_places` | Find places by words in their name, caption or aliases, in any category |
| `nearby` | Places within N minutes' walk, closest first |
| `route_info` | Minutes, metres, stairs, lifts, arrival time and turn-by-turn directions |
| `go_to` | Walk there now by the quickest path; the clock moves to the arrival time |
| `stroll` | Walk without a set route, roughly toward a place, for N minutes |
| `stay` | Spend time where you are until a given time |
| `end_day` | Finish the day: at night once home, or once a commuter has left through their exit |

A person gets at most 40 calls (`MAX_CALLS_PER_AGENT` in `config.py`). If they run out, or the budget
runs out, the simulator walks them home so every day closes; those trips are marked `"auto": true`.

## Outputs

- `out/<run>/manifest.json`: what was run, with which data, code and versions.
- `out/<run>/people.jsonl`: the people of this run.
- `out/<run>/agents/<id>.json`: the person, every tool call with its time, every trip with segments,
  turns and kind (`go` or `stroll`), calls used and cost.
- `out/<run>/trips.jsonl` and `out/<run>/run_summary.json`.
- `out/<run>/plans.jsonl.gz`: every person's tool calls, without the trips. Enough to replay the run.
- `out/<run>/analysis/summary.md`: the main table and a table by group; `shared_turns.csv` (k = 1 to 10,
  quickest path vs random turns), `by_hour.csv`, `turns_by_junction.csv` (the Plan's turn-probability
  table), `segment_usage.csv`.
- By group (`groups.py`: undergrads and postgrads each split into hall residents and commuters, staff,
  local residents): `groups.csv`, `share_matrix.csv` (which group the stranger who made your turns came
  from), `road_usage.csv` (walkers per road by group, peak hour) and `road_decisions.csv` (for each road
  and direction, how each group turned at its end).
- `out/<run>/analysis/compare.md`: your tables next to the published run's (or, for a replay, next to
  the replayed run's). `python compare.py --run A --ref B` compares any two runs.
- `out/<run>/web/web.json`: the website data. Copy it next to `same-route-simulator.html` and republish
  the page; its banner switches from "Test run" to the model's name by itself.

The published run is `out/day1/`. Its analysis tables, `run_summary.json` and its raw output
(compressed) are in the repository. After unpacking `out/day1/agents.tar.gz`, its plans can be added with
`python plans.py --run day1` and commit `out/day1/plans.jsonl.gz` (a few MB; `.gitignore` already lets
it through). After that, anyone can rebuild the published trips for free with `python pipeline.py replay`.

## The other arms

The agent run is one arm of the experiment. The others are compared with it by `arms.py`:

```bash
python arms.py --run day1
```

```bash
python make_compare_figures.py --run day1
```

- **Random walk** (`random_walk.py`): one trip per real trip, from a random place to a random place by the
  quickest path, with the real trip's departure time and pace. Five repeats. Costs nothing.
- **Same trips, noisy turns**: the older baseline from `analyze.py`, kept for reference.
- **Live world** (`live.py`): no navigation app. Everyone lives the day on one shared clock; at every junction
  each person sees the roads leading off and the people around them, and picks a road. The people are the
  first N of the day1 people. Try it free with the rule-based walker first:

```bash
python live.py --run live_test --planner mock --limit 1000
```

Then the real run, which costs money (see `method.md`, section 7, for the estimate). A stopped run resumes
from its checkpoint when the same command is run again:

```bash
python live.py --run live --planner claude --limit 1000 --budget 60 --concurrency 24
```

```bash
python arms.py --run day1 --live live
```

`arms.py` writes `out/<run>/analysis/compare.md` and its tables: shared turns per arm, the Markov chain of
turns against what happened, the per-junction tests with the Diebold-Mariano test, and road use per arm
with its regression on nearby places. It needs `numpy` and `scipy`; the figures need `matplotlib`.

## Cost and time

The published run of 10,000 people cost **US$20.49**: about US$0.002 per person, 117,318 calls (12 per
person on average), in two hours at 24 people in parallel. The budget guard (`--budget`) stops starting
new people once it is reached, counting earlier attempts of the same run. Prices are set in `config.py`;
check the pricing page before a big run, and set a monthly spend limit in the Anthropic Console too.

## Limits to state in the report

- People, habits, interests and timetables are synthetic. The mixes in `make_agents.py` are guesses;
  replace them with HKU's published numbers and cite them.
- Lighting is known for few segments in OpenStreetMap, and indoor routes through buildings are mostly
  missing. Opening hours are known for only some places, and the simulation does not enforce them.
- Captions for HKU buildings were written by hand from general knowledge and need checking.
- In the random-turn baseline, people wander longer, so they meet more strangers for short runs. Discuss
  this exposure effect rather than presenting the baseline as a clean control.
- People decide independently, so nobody reacts to anyone else. Stranger-following is not modelled.
- A repeat with the Claude planner gives different days, because the model does not plan the same way
  twice. Report results from more than one run, or the spread between runs, if you can afford it.
- In the `step-free`, `noisy` and `personal` route modes the tool descriptions still say that `go_to`
  takes the quickest path, so that the instructions are the same in every mode.

## AI declaration

The report must name the model (Claude Haiku 5.5, `claude-haiku-5-5`, via the Anthropic API) and include
the exact prompts: the system prompt, tool descriptions and persona card are built in `agent_tools.py`
(`system_prompt`, `TOOLS`, `persona_card` and `mental_map`).

Map data © OpenStreetMap contributors, ODbL.
