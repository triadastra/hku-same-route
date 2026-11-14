# Same route, by coincidence

COMP1110 group project at HKU (Celsia, Jerry, Angie, Bryan, Michelle): *Modeling and understanding
coincidences: accidentally having the same route.*

10,000 synthetic people live one weekday on the real footpaths from Kennedy Town to Sai Ying Pun. Each
person is played by Claude Haiku 5.5 and plans their own day with map tools; every walk follows the
quickest path and records each turn. The analysis measures how often a stranger makes your same turns
in a row, within 90 seconds, purely by coincidence.

**Results website:** https://claude.ai/artifact/KwTUxCbLH9h1zDb2tTBqUp

| Path | What it is |
|---|---|
| `RUNBOOK.md` | How to run the final experiments: what is ready, the commands, costs, checks and what to report. Start here. |
| `hku-agents/run_experiments.sh` | One documented script for every step of the final experiments (`bash run_experiments.sh people`, `check`, `agent-world`, `control`, `live`, `analyse`, `pack`). |
| `hku-agents/` | The simulator: map building, people, agent tools, the day runner and the analysis. Its README explains how to run everything. |
| `hku-agents/out/day1/analysis/` | Result tables from the 10,000-person run (one weekday, US$20.49, 57,530 trips). |
| `hku-agents/out/day1/trips.jsonl.gz` | Every trip of the run (57,530), with each road segment, time and turn. |
| `hku-agents/out/day1/people.jsonl.gz` | The 10,000 people: group, home, schedule and traits. |
| `hku-agents/out/day1/agents.tar.gz` | One file per person: their whole day, including every tool call the agent made. |
| `hku-agents/out/day1/analysis/following.md` | The main analysis: how often a stranger close behind you makes your decisions at real intersections, in the Agent World and under four Markov chains, with chi-square tests and the table of each intersection's choices. Rebuilt by `python following.py --run day1` inside `hku-agents/`. |
| `hku-agents/out/day1/analysis/compare.md` | The agent run against random walking: shared turns, the Markov chain of turns, junction tests and road use. Rebuilt by `python arms.py --run day1` inside `hku-agents/`. |
| `graphs/` | Paper figures: the amenity maps, the real intersections, following under each model (`following-*.pdf`), and the road-use map. |
| `method.md` | Design document for the experiment. A skeleton: the lines marked `DECIDE:` are still to be filled in. |
| `plan.md` | What of the method is done and what is not. |
| `results.xlsx` | All the results in one workbook: a summary sheet with the key findings, then every table from the analysis. |
| `same-route-simulator.html` | The results website. It reads `web.json` from the same folder. |
| `amenity-heat-map.html` | Heat map of what each block is for: the 1,538 places on the map, counted per one-hectare block in eight functions. Rebuilt by `python hku-agents/export_amenity_map.py`. |
| `web.json` | Website data exported from the run (2,000 of the 10,000 people, for the map replay). |

The raw output of the run is compressed because the plain files are over GitHub's size limit. To
re-run the analysis on it, unpack it in place:

```bash
cd hku-agents/out/day1
gunzip -k trips.jsonl.gz people.jsonl.gz
tar -xzf agents.tar.gz
cd ../.. && python analyze.py --run day1
```

Running `python pipeline.py` inside `hku-agents/` runs a new simulation from scratch. That calls the API
(about US$20 for 10,000 people) and gives a different day, since the agents are not deterministic. Put your
own Anthropic API key in `hku-agents/.env` (never commit it). Downloaded OpenStreetMap caches are not in the
repository and are fetched again when needed.

Map data © OpenStreetMap contributors, ODbL.
