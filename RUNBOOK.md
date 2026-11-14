# Runbook: the final experiments

For whoever runs the final experiments next, person or Claude. It says what is ready, what to run, what it
costs, what to check after each step, and what to report. Read it all before running a step that costs money.

## Where things stand (14 November 2026)

- The design is in `method.md`. Start with "Decisions made by the authors" at the top: those were made by the
  authors and are not to be changed without them. Lines marked `DECIDE:` are still open; the code uses the
  default written there.
- The code is ready and has been tested with the free rule-based planner and with a fake API server. Nothing has
  been run with the model since the population and walking speeds were rebuilt.
- The earlier 10,000-person run, `day1` (old population, 74% HKU students, old speeds), and its analysis are in
  `hku-agents/out/day1/`. Keep it: it is the "old mix" comparison.
- One script runs everything: `hku-agents/run_experiments.sh`. Each step is documented at the top of the script.

## What each experiment is

| # | Experiment | Run name | Cost |
|---|---|---|---|
| 2 | Agent World: 10,000 people in the proportions of the 2021 census and HKU's figures, each played by Claude Haiku, planning one weekday with map tools, walking by the quickest path at a pace they choose | `census_run` | about US$20, capped at US$30 |
| 3 | Live world: the first 1,000 of the same people on one shared clock, choosing every junction themselves with no navigation app, seeing people within 50 m | `live_census` | estimated US$20 to 60, capped at US$60 |
| 4, 5 | Random place to place, and the same people with a rule-based planner (no LLM) | inside the analysis, and `census_control` | free |
| 6 to 9 | Markov chains: equal chance, momentum, counted shares, counted plus imitation | inside the analysis | free |

Experiment 1 is `day1`, already done.

## Before you start

1. **The API key.** It must be in the environment variable `ANTHROPIC_API_KEY`. The authors added it in the cloud
   environment's settings; a session only sees new variables after it starts or resumes. Check without showing
   it:

   ```bash
   python -c 'import os; print(bool(os.environ.get("ANTHROPIC_API_KEY")))'
   ```

   If this prints `False`, ask the user to add it (cloud environment menu, Edit, environment variables) and
   restart the session, or to put `ANTHROPIC_API_KEY=<key>` in `hku-agents/.env`. Never print, log, commit or
   paste the key, and never ask for it in the chat.
2. **Packages:** `pip install anthropic numpy scipy matplotlib` (the `check` step does this).
3. **Money:** the caps above stop spending. Ask the user before raising a cap or running anything else that
   costs money. Suggest they set a monthly limit in the Anthropic Console.
4. **Disk:** each run writes about 150 MB of trips and 10,000 small files.

## The steps

Run them from `hku-agents/`, in this order.

| Step | Command | Time | Check afterwards |
|---|---|---|---|
| 1. People | `bash run_experiments.sh people` | 1 min | The printed mix: about 7,570 residents, 1,980 HKU students and 450 HKU staff in 10,000; "1 HKU person for every 3.1 residents"; faculties and ages close to their targets |
| 2. Check | `bash run_experiments.sh check` | 1 min | Offline checks pass, "API key: found", and one real person's day is printed with its cost (under US$0.01) |
| 3. Agent World | `bash run_experiments.sh agent-world` | about 2 h | The summary: 10,000 agents, about 50,000 trips, about US$20, almost all days `ended` |
| 4. Control | `bash run_experiments.sh control` | 1 min | 10,000 days ended, US$0 |
| 5. Live world | `bash run_experiments.sh live` | a few hours | Watch the first progress lines: spend so far against the clock time. The summary: 1,000 agents, the share of `auto_trips` (people the simulator walked home because they got lost), the cost |
| 6. Analysis | `bash run_experiments.sh analyse` | 1 to 2 h | `out/census_run/analysis/following.md`: equal-chance and momentum walkers must match their formula ("walkers / formula" columns); the chi-square calibration must reject about 0% |
| 7. Pack | `bash run_experiments.sh pack` | 5 min | No file over 95 MB |

`bash run_experiments.sh all` runs all seven in order, but running them one by one lets you check each.

Optional, before step 5: a 20-person live pilot to measure the cost per person.

```bash
LIVE_RUN=live_pilot LIVE_PEOPLE=20 LIVE_BUDGET=3 bash run_experiments.sh live
```

## If something goes wrong

- **A paid step stopped** (budget, network, Ctrl+C, a closed session): run the same command again. Finished
  people are kept and not paid for twice; the live world resumes from its checkpoint.
- **"rate limit" errors (429):** run again with fewer at once, e.g. `CONCURRENCY=8 bash run_experiments.sh agent-world`.
- **AuthenticationError (401):** the key is wrong or missing. Ask the user; do not try other keys.
- **The live world costs far more than estimated:** press Ctrl+C (it saves), report the spend and the clock time
  reached to the user, and ask before continuing.
- **Out of disk:** delete test runs you made in `hku-agents/out/` (never `day1`, `census_run` or `live_census`).

## After the runs

1. Commit the compressed output and the analysis: for each of `census_run` and `live_census`, the `.gz` files,
   `agents.tar.gz`, `run_summary.json` and `analysis/` (`.gitignore` keeps exactly these), plus `graphs/`.
   Push to the session's working branch and open a pull request, following the session's own git rules.
2. Report to the user, in plain numbers:
   - each run's summary: people, trips, cost, how days ended, and for the live world the share of trips the
     simulator had to finish;
   - from `following.md`: the chance of being followed through 3, 5 and 10 junctions for the Agent World and
     each Markov chain; pairs arriving together against each chain's formula; same next path by number of
     paths; by hour; the chi-square result; who follows whom;
   - live world against the Agent World on the same 1,000 people
     (`out/census_run/analysis/same_people_as_live_census/following.md` and `out/live_census/analysis/following.md`);
   - what changed from `day1` (old mix) to `census_run` (census mix).
3. Remind the user to delete `ANTHROPIC_API_KEY` from the environment's settings.

## Things to keep in mind when reporting

- Every map junction counts (nothing is merged), so junctions are about 13 m apart: "3 junctions" is often about
  40 m. Say so next to every k.
- No traffic lights are simulated; 10,000 people are fewer than the real crowd, so chances are lower bounds.
- The walking-speed sources were read from abstracts or later papers: they need checking against the originals
  before the paper cites them (`hku-agents/data/walking_speeds.csv`).
- Medicine is left out (based at Sassoon Road, off the map). HKU publishes no staff numbers by faculty, so staff
  are spread over faculties by an assumption (see `method.md`, section 3).
