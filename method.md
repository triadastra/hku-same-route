# method.md: design of the same-route experiment

**Status: skeleton.** Each section says what the code does today, then lists the design choices that are
yours to make. A line starting with `DECIDE:` is waiting for you; the value after `default:` is what the
code uses now. Replace the line with your choice and a one-line reason, and delete this notice when the
document is yours.

## 1. Question and hypotheses

- Question: when a stranger makes your same turns several times in a row, how often is that coincidence?
- Three explanations to separate (from the Introduction): equal chance per exit (1/N), a chance weighted
  by the road network and nearby places, or people's own plans.
- DECIDE: the main hypothesis in one sentence, and which number would count as support for it.
  default: none written.
- DECIDE: the number of turns that counts as "being followed". default: the paper says 3 or more; the
  group tables in the code use 5 (`SHARE_K` in `analyze.py`).

## 2. The map

- Area: Kennedy Town to Sai Ying Pun, Pok Fu Lam Road to the waterfront (`BBOX` in `config.py`).
- Source: OpenStreetMap walking network. 3,500 junctions, 4,835 segments, 1,538 places (`build_map.py`).
- Walking time: 1.35 m/s, stairs 2.2 times slower, 40 s per lift, 60 s felt penalty for an unlit segment
  at night (`config.py`).
- A turn is left, right, straight or back by the change of bearing: under 35° is straight, over 145° is
  back (`World.turn`). A junction counts as a decision only if it has 3 or more ways.
- DECIDE: are these walking constants sourced, or assumptions? default: assumptions, uncited.

## 3. The population (paper section 3.1)

- Today: 10,000 people drawn from mixes written by hand in `make_agents.py`. Six groups: undergraduates
  and postgraduates (in halls, commuting), staff, local residents.
- The paper says the population represents the 2021 census. That is not true yet.
- DECIDE: reweight the existing 10,000 to census and HKU totals (no new run), rebuild and re-run (about
  US$20), or change the sentence in the paper. default: nothing done.
- DECIDE: the sources for the totals (census table numbers, HKU head counts) and the year.

## 4. Arm A: Agent World (done)

- One Claude Haiku 5.5 agent per person, effort low, at most 40 tool calls, one simulated weekday.
- Eight tools (`agent_tools.py`): four that look at the map, four that move the clock.
- `go_to` walks the quickest path. `stroll` walks with noisy turns toward a place.
- Agents cannot see each other, so nobody follows anybody on purpose.
- Result: `out/day1/`, 57,530 trips, US$20.49.
- DECIDE: is one weekday, one run enough, or do you want a second run for a spread? default: one run.

## 5. Arm B: random walking (implemented in `random_walk.py`)

- Origin and destination: each drawn with equal chance from all 1,538 places.
- Path: the quickest path, the same routing as `go_to`.
- Each random trip copies the departure time, pace and owner of one real trip, so the map is as busy at
  each hour as in Arm A.
- 5 repeats with different seeds.
- Known limit: random trips are longer (1,119 m against 666 m on average), so random walkers have more
  chances to share turns.
- DECIDE: equal chance per place, or weighted (for example by category or building size)? default: equal.
- DECIDE: keep the copied departure times, or draw times at random too? default: copied.
- DECIDE: keep the older baseline (the agents' own trips re-walked with noisy turns, 2,611 m per trip) as
  a fourth column, or drop it? default: kept and labelled.

## 6. The Markov chain of turns (implemented in `arms.py`)

- State: a road segment and the direction walked. Next state: the next segment, with the shares seen in
  the trips. No memory of where the walker came from or is going.
- Number reported: two people start walking the same road together; the chance that they make the same
  next k turns. Compared with what the trips really show, for agents and for random walkers.
- A pair counts as "met" when they enter the same segment the same way within 90 s and were not on the
  same route just before.
- DECIDE: is k = 3 the headline, as in the abstract? default: k = 1 to 5 in the table, 3 in the text.
- DECIDE: fit the chain on the random-walk trips, the agent trips, or report both? default: both.

## 7. Arm C: the live world (implemented in `hku-agents/live.py`, not run)

- No navigation app: no `go_to`, `stroll` or `route_info`. At every junction the person sees the roads
  leading off (name, compass heading, length, stairs, lifts, unlit at night, places passed, dead ends) and
  picks one with `walk`. `search_places` and `nearby` give only direction and straight-line distance.
- One shared clock. Everyone whose next decision falls in the next 10 s is asked at once, then the clock
  moves on. Each person sees the others where they really are at that moment (within 50 m: a label, age
  decade, distance, and "walking away from you along road 2", "coming toward you", or "standing at X").
  People inside buildings are not seen; people at parks, sights, bus stops and MTR exits are.
- Nothing in the prompt mentions following. Whether anyone follows anyone is up to the agents.
- The people are the first N of the day1 people (same personas, homes and timetables), so the arms are
  compared on the same people.
- The simulator steps in only when a trip passes 90 minutes (it walks the person to where they were going,
  marked `auto`), and at midnight.
- Memory: the persona card stays; the conversation keeps the last 8 to 24 exchanges.
- Tested with a free rule-based walker (1,000 people) and with a fake API server (2,610 valid requests).
- Estimated cost, assuming about 185 calls per person and about US$0.0002 per call (day1 measured
  US$0.000175): 1,000 people about US$30 to 60, 2,000 about US$60 to 120, 10,000 about US$300 to 600.
  Time at 24 calls in parallel: about 4 hours per 1,000 people.
- DECIDE: how many people. With N people, everyone meets fewer strangers than with 10,000, so the live
  world is only compared with the other arms on the same N people. default: none run.
- DECIDE: what a person sees at a junction (list above), sight distance (default 50 m), clock step
  (default 10 s), when the simulator takes over a lost walker (default 90 min).
- DECIDE: whether the persona card's mental map, which gives walking minutes to known places, is
  acceptable without a navigation app. default: kept.

## 8. Measures (paper section 2.1)

- $P_k$, $\bar S_k$: `analyze.py` and `arms.py`. Window W = 90 s. 5,000 trips sampled as "you".
- $U_e$ and $p_v(\tau)$: per segment and per junction, per arm.
- DECIDE: W. default: 90 s. A sensitivity check at 30 s and 180 s is not done.

## 9. Tests (paper section 3.3; implemented in `arms.py`)

- Per junction, and per road and direction: Pearson chi-square test of the left/right/straight/back counts,
  agents against random walk, at least 30 passes in each arm, Benjamini-Hochberg correction. The G-test is
  reported next to it, and the result restricted to units where every expected count is 5 or more. One
  pooled chi-square over all turns. Effect sizes: Cramér's V and total variation distance. A noise check compares two random-walk repeats with each other.
- Paired by direction (left with left, and so on): mean difference and Wilcoxon test across roads.
- Diebold-Mariano: the agents' turns are the observed series; the two forecasts are equal chance per exit
  and the random-walk shares; loss is the Brier score; one value per hour of the day.
- Road use: Spearman correlation, share of walking on the busiest 5% of segments, and a regression of the
  agent-to-random ratio on places within 60 m, by the eight functions of Fig. 1.
- Known limit: one person passes the same junction several times a day, so passes are not independent and
  the p-values are too small. The effect sizes do not have this problem.
- DECIDE: accept this design and change the two sentences in section 3.3 that say Diebold-Mariano is run
  over each junction? default: design as above.
- DECIDE: significance level. default: 5% after correction.

## 10. What we report

- Table: $P_k$ and $\bar S_k$ for each arm. Table: junction tests. Table or figure: Markov chain.
- Figures: `graphs/shared-turns-three-arms.pdf`, `graphs/markov-turns.pdf`, `graphs/road-use-ratio.pdf`.
- DECIDE: which of these go in the paper, given the page limit.

## 11. Limits to state

- Synthetic people; one simulated day; one run of the agents.
- Lighting and indoor routes are mostly missing from the map; opening hours are not enforced.
- Arms differ in trip length (section 5).
- DECIDE: anything else you want stated.
