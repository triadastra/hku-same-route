# HKU same-route agents

Synthetic people live one weekday around HKU, Kennedy Town and Sai Ying Pun on the real OpenStreetMap
walking network. Each person is played by Claude Haiku 5.5 and lives the day through map tools, like
someone with a phone map. Every walk records each segment and each turn (left, right, straight,
back). The analysis then measures how often a stranger makes the same k turns as you, in a row, by
coincidence, and how different groups use each road.

## Quick start

```bash
pip install anthropic
```

```bash
python preflight.py
```

`preflight.py` checks the files and the SDK, and drives the Claude loop through a fake server, so it
needs no key and costs nothing. Put your key in `.env` in this folder after `ANTHROPIC_API_KEY=`; every
script reads it automatically, and `.gitignore` keeps it out of git. Never share or upload that file.

```bash
python preflight.py --one
```

That checks the key with a free token count, then runs one real person for a whole day (under one US
cent) and prints every tool call. Then run the whole experiment in one command:

```bash
python pipeline.py --run day1 --n 10000 --planner claude --budget 45 --concurrency 24
```

It makes the people, lets each live their day, analyses the trips and writes the website data. If it
stops (budget, network, Ctrl+C), run the same command again: finished people are kept and not paid for
twice. A wrong or missing key stops the run on the first call. To try the chain for free first:
`python pipeline.py --run test --n 300 --planner mock`.

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

`python make_agents.py --n 10000 --seed 7` draws each person at random from the mixes in the file:

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

- `out/<run>/agents/<id>.json`: the person, every tool call with its time, every trip with segments,
  turns and kind (`go` or `stroll`), calls used and cost.
- `out/<run>/trips.jsonl` and `out/<run>/run_summary.json`.
- `out/<run>/analysis/summary.md`: the main table and a table by group; `shared_turns.csv` (k = 1 to 10,
  quickest path vs random turns), `by_hour.csv`, `turns_by_junction.csv` (the Plan's turn-probability
  table), `segment_usage.csv`.
- By group (`groups.py`: undergrads and postgrads each split into hall residents and commuters, staff,
  local residents): `groups.csv`, `share_matrix.csv` (which group the stranger who made your turns came
  from), `road_usage.csv` (walkers per road by group, peak hour) and `road_decisions.csv` (for each road
  and direction, how each group turned at its end).
- `out/<run>/web/web.json`: the website data. Copy it next to `same-route-simulator.html` and republish
  the page; its banner switches from "Test run" to the model's name by itself.

## Cost and time

Measured on 8 real people with the current setup: about **US$0.0026 per person** (13 calls on average),
so about **US$26 for 10,000**. The budget guard (`--budget`) stops starting new people once it is
reached, counting earlier attempts of the same run. A 10,000-person day takes a few hours at 24 people in
parallel. Set a monthly spend limit in the Anthropic Console too.

## Limits to state in the report

- People, habits, interests and timetables are synthetic. The mixes in `make_agents.py` are guesses;
  replace them with HKU's published numbers and cite them.
- Lighting is known for few segments in OpenStreetMap, and indoor routes through buildings are mostly
  missing. Opening hours are known for only some places, and the simulation does not enforce them.
- Captions for HKU buildings were written by hand from general knowledge and need checking.
- In the random-turn baseline, people wander longer, so they meet more strangers for short runs. Discuss
  this exposure effect rather than presenting the baseline as a clean control.
- People decide independently, so nobody reacts to anyone else. Stranger-following is not modelled.

## AI declaration

The report must name the model (Claude Haiku 5.5, `claude-haiku-5-5`, via the Anthropic API) and include
the exact prompts: the system prompt, tool descriptions and persona card are built in `agent_tools.py`
(`system_prompt`, `TOOLS`, `persona_card` and `mental_map`).

Map data © OpenStreetMap contributors, ODbL.
