# Plan: the parts of the method we have not done yet

Compared: the Methodology and Evaluation sections of the paper draft against the code in `hku-agents/`
and the finished run in `hku-agents/out/day1/`.

## Update

Steps 1 to 4 are now implemented and run; results are in `hku-agents/out/day1/analysis/compare.md` and
`graphs/`. Step 5 was redesigned as the live world (`hku-agents/live.py`): no navigation app, one shared clock,
every turn chosen by the agent. It is tested free but the paid run has not been made; see `method.md`,
section 7. Step 6 (census) and step 7 (paper text) are not started.
`method.md` exists as a skeleton with the open design choices marked `DECIDE:`. The table below describes
the state before this work.

## Where we stand

| Paper says | Status | Evidence |
|---|---|---|
| Agent World, 10,000 agents, Haiku 5.5, eight map tools (3.2.1) | Done | `run_day.py`, `agent_tools.py`, `out/day1/` (57,530 trips, US$20.49) |
| Shared-turn metrics $P_k$, $\bar S_k$, $U_e$, $p_v(\tau)$ (2.1) | Done for the agent arm | `analyze.py`, `shared_turns.csv`, `segment_usage.csv`, `turns_by_junction.csv` |
| Fig. 1 amenity maps | Done | `graphs/amenity-*.pdf` |
| **Random walking arm**: random building to random building (3.2.2) | **Not done as described** | The "Random" column in Table 1 is a different thing: the agents' own trips re-walked with softmax-noisy turns (`analyze.py: rewalk`, beta = 0.01) |
| **Markov chain of 3 turns** (abstract) | **Not done** | Nothing in the code |
| **Omni agent** that sees and can follow others (3.2.1, third arm) | **Not done** | No tool reveals other agents; agents run independently, each on its own clock |
| **Diebold-Mariano test per junction**, paired left-to-left etc. (3.3) | **Not done** | No significance test anywhere |
| **Road utilisation, agents vs baseline** (3.3) | **Not done** | `segment_usage.csv` has the agent arm only |
| **2021 census preprocessing** (3.1) | **Not done** | The population mixes in `make_agents.py` are guesses (its README says so) |
| `shared-turns-three-arms.pdf` (Results figure) | **Missing** | Not in `graphs/`; needs all three arms first |
| `method.md` in the repository (AI declaration) | **Missing** | The declaration says it is in the repo; it is not |

Two smaller mismatches to fix while we are there:

- Table 1 calls the agent column "Quickest", but 5,010 of the 57,530 trips (8.7%) are `stroll` trips,
  which walk with noisy turns. Either rename the column "Agent World" or report `go` and `stroll` apart.
- `turns_by_junction.csv` keeps only the 200 busiest junctions. The per-junction test needs all of them.

## Work to do, in order

Steps 1 to 4 cost nothing (no API calls). Step 5 costs money. Step 6 is a decision about wording.

### 1. Random-walk arm (`random_walk.py`, new)

What the paper describes: every place on the map can be an origin or a destination, each with equal
chance, walked by the quickest path.

- Draw 57,530 trips (the same number as the agent run). Origin and destination: uniform over the 1,538
  places, origin ≠ destination. Walk with `World.walk(policy="quickest")`.
- Departure time and pace: copy them from the agent trips, one for one. Then both arms have the same
  number of people on the map at each hour, so a difference in $P_k$ is about route choice and not about
  crowding. (This is the exposure problem the current baseline has; see "Limits" in `hku-agents/README.md`.)
- Trip owners: give each random trip the agent id of the agent trip it copies its time from, so
  "stranger" means the same thing in both arms.
- Write `out/day1/random_walk/trips.jsonl` in the existing trip format, so `analyze.py` reads it unchanged.
- Fixed seed. Repeat with 5 seeds to get a spread for every number we report.

Keep the current softmax re-walk as a fourth, clearly named column ("same trips, noisy turns"), or drop
it from the paper. It answers a different question (same origins and destinations, different turns).

### 2. Markov chain of 3 turns (`markov.py`, new)

- State: a directed segment (edge plus direction of travel). Transition: the share of walkers on that
  directed segment who take each exit at its end. Estimate it from the random-walk trips.
- Coincidence probability: two independent walkers who enter the same directed segment $a$ make the same
  next $k$ turns with probability
  $q_k(a) = \sum_{b} p_{ab}^2 \, q_{k-1}(b)$, with $q_0 = 1$. Report $q_3$, weighted by how busy each
  segment is.
- Compare with the agent arm: among pairs that already share one turn within $W$, the observed share that
  go on to share the next 3. `shared_runs` in `analyze.py` already tracks the streak; add this one
  conditional count.
- This gives the abstract its sentence: "agents keep sharing 3 more turns X% of the time; the Markov
  chain of random walking predicts Y%."

### 3. Significance tests (`stats_tests.py`, new)

For each junction: the agent arm's turn counts (L, R, S, B) against the random-walk arm's.

**Problem with the test named in the paper.** Diebold-Mariano compares the errors of *two forecasts*
against one *observed* series. With only "agents" and "random walk" there is no third series, so DM
cannot be run "over each junction" as section 3.3 is worded. Recommended replacement, which keeps DM
where it is valid:

- *Is the agent arm different from random walking at this junction?* Chi-square test of homogeneity on
  the 2 × 4 table (G-test where counts are small; skip junctions with under 30 passes in either arm).
  Benjamini-Hochberg correction across junctions. Report the share of junctions significant at 5%.
- *How different?* With 12,000 passes at the busiest junction, everything will be significant. So also
  report the effect size: total variation distance between the two turn distributions, and the paired
  differences left-to-left, right-to-right, straight-to-straight (mean, and a paired Wilcoxon test
  across junctions).
- *DM, used properly:* take the agent arm as the observed series and compare two predictors of it, the
  equal-chance model (1/N per exit, from the Introduction) and the random-walk model. Loss = squared
  error of the predicted turn share, one value per junction and direction; DM tests whether the
  random-walk model predicts the agents better than 1/N. This matches the three hypotheses in the
  Introduction (equal chance, weighted chance, no correlation).

Section 3.3 then needs two sentences changed to say this. Do the tests per incoming direction as well
(as in `road_decisions.csv`), because "left" at a junction means a different street depending on where
you came from.

### 4. Road utilisation comparison (extend `analyze.py`, `make_figures.py`)

- $U_e$ for both arms, side by side: `road_usage_compare.csv` (segment, name, agents, random walk, ratio).
- Spearman rank correlation of $U_e$ between arms; share of all walking carried by the busiest 5% of
  segments in each arm (how concentrated each arm is).
- Link to amenities: regress log(agent $U_e$ / random $U_e$) on the number of places within 60 m of the
  segment, by function (the eight functions already in `export_amenity_map.py`). This is the test of
  "weighted chance based on nearby amenities".
- Figures: a map of the ratio (over-used and under-used roads), and `shared-turns-three-arms.pdf`
  ($P_k$ against $k$, one line per arm, band = spread over seeds).

### 5. Omni arm: agents who can see and follow others (costs API money)

The hard part: today every agent lives its whole day alone, in parallel. Seeing others needs other
people's positions at the agent's current time.

Recommended design (two-pass, keeps the parallel and resumable runner):

- The day1 run is the crowd. An omni agent walks through that recorded crowd, with its own day1 self
  removed.
- Position index: from `trips.jsonl`, who is on which segment at what time (`analyze.py: index_trips`
  already builds this), plus who is staying at which place.
- Two new tools in `agent_tools.py`:
  - `look_around()`: up to 8 people within about 50 m, each with an anonymous label, a short description
    (group, e.g. "a student"), which way they are heading, how far.
  - `follow(person, minutes)`: walk that person's recorded segments for up to N minutes; the trip is
    recorded with `kind: "follow"`.
- The system prompt must stay neutral: it says the tools exist, not that the agent should use them.
  Otherwise we script the following we want to measure.
- Output `out/omni/`, same format; `analyze.py` gives $P_k$ and $\bar S_k$, plus how many trips are
  `follow` trips and how long they last.

Limit to state: omni agents see the crowd but the crowd does not react to them, and omni agents do not
see each other. A fully shared clock (all agents stepping together) would fix that but removes the
parallel runner and takes much longer.

Size: 2,000 agents drawn from the same 10,000 (about US$5, about 30 minutes), run the mock planner and
`preflight.py --one` first. Full 10,000 is about US$25 with the extra tool text.

### 6. Census preprocessing (3.1)

Section 3.1 says the population comes from the 2021 census. It does not yet. Options:

- **(recommended) Reweight, no new run.** Get the 2021 Population Census tables for Central and Western
  District (age, economic activity, place of work) and HKU's published head counts (undergraduates,
  postgraduates, staff, hall places). Compute a weight per group so the 10,000 agents match those
  totals, and report weighted $P_k$ next to the unweighted one. Add `data/census_2021.csv` with sources.
- Rebuild `make_agents.py` from the census and run again: another US$20 and all tables change.
- Change the sentence in 3.1 to say the mixes are our own assumptions.

### 7. Paper and repository clean-up (after the numbers exist)

- Table 1: three arms (Agent World, random walk, omni), plus the Markov $q_3$ line.
- New table: junction tests (junctions tested, share significant, median effect size, DM statistic).
- Fill the abstract's "[...]", write Results text, add Discussion and Conclusion (the declaration refers
  to Section 5, which does not exist yet).
- Add `method.md` to the repository, or remove the claim from the declaration. It must be the authors'
  own document.
- Add the new sheets to `results.xlsx` and the new arms to the README table.

## Decisions needed before coding

1. **Significance test:** accept the chi-square + effect size + DM-on-two-predictors design in step 3
   (and edit section 3.3), or keep the paper's wording and find a way to force DM per junction?
2. **Omni arm:** two-pass with 2,000 agents (about US$5), two-pass with 10,000 (about US$25), or cut the
   third arm from the paper?
3. **Census:** reweight, re-run, or reword?
4. **Old "random turns" baseline:** keep as a fourth column or drop?

Steps 1 to 4 do not depend on these answers except decision 1, and can start right away.
