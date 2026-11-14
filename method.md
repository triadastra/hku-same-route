# method.md: design of the same-route experiment

**Status: skeleton.** Each section says what the code does today, then lists the design choices that are
yours to make. A line starting with `DECIDE:` is waiting for you; the value after `default:` is what the
code uses now. Replace the line with your choice and a one-line reason, and delete this notice when the
document is yours.

## 1. Question and hypotheses

- Question (project plan, 2.2): how the number of intersections, the possible directions and popular routes
  change the chance that two people appear to follow each other, at different times of day; and (plan,
  section 5) how that chance changes when route preference or imitation is added.
- What is measured: the chance that a stranger, close behind you, makes your decisions at k real
  intersections in a row, under a ladder of assumptions: equal chance (1/n), momentum, counted shares
  (popular routes, as sensors would record them), imitation, and people with their own plans (Agent World).
- We do not claim that anyone sharing turns is following on purpose (plan, section 5).
- DECIDE: the main hypothesis in one sentence, and which number would count as support for it.
  default: none written.
- DECIDE: how many intersections count as "appearing to follow". default: 3, with 5 also reported.

## 2. The map and its decision points (preprocessing)

- Area: Kennedy Town to Sai Ying Pun, Pok Fu Lam Road to the waterfront, 22.276–22.292 N, 114.124–114.147 E
  (`BBOX` in `config.py`).
- Walking network (`build_map.py`): every OpenStreetMap way a pedestrian can use (footways, paths, steps,
  pedestrian streets, corridors, cycleways, tracks and public roads), minus ways tagged foot=no,
  foot=private or access=no, plus lifts. Largest connected part only; runs of two-way nodes contracted.
  Result: 3,543 nodes, 4,835 segments, 155.8 km of path, 383 segments with stairs, 48 lifts. Lighting is
  tagged on only 87 segments (2%), so it is not used in the analysis.
- Walking time: 1.35 m/s, stairs 2.2 times slower, 40 s per lift (`config.py`).
- Places: 1,538 named buildings and amenities in 17 categories, each snapped to the nearest network node
  within 150 m; unnamed amenities are named after the nearest landmark (`build_map.py`, `captions.py`).
- Decision points (`decisions.py`). The raw network has 2,372 junctions, one every 13 m on a typical trip,
  because sidewalks and crossings are separate ways. Three steps turn it into real intersections:
  1. a dead-end branch shorter than 15 m is not a road (188 stubs);
  2. junctions joined by a path of at most 20 m are one intersection, shortest links first, while the
     intersection stays within 40 m from end to end;
  3. paths out of an intersection toward the same next intersection within 60°, or leaving within 35° of
     each other and still within 20 m of each other 40 m from the centre (a street and its sidewalks),
     are one road ("arm").
  An intersection with 3 or more roads is a decision point: 573 of them (405 with 3 roads, 107 with 4, 51
  with 5, 10 with 6). 133 intersections with 2 roads are passed through. Figure: `graphs/intersections.pdf`.
- A decision is (intersection, road in, road out, time), the record the project plan's thermal sensors
  would produce. The 57,223 day1 trips give 475,883 decisions: median 6 per trip, 61 m apart (quartiles
  42–91 m). For tables a decision is also labelled front (within 40° of straight on), left, right or back;
  93.5% of "back" decisions are crossing to the other side of the same street and walking back.
- DECIDE: the thresholds 15 m, 20 m, 40 m, 35°, 60°. default: as above, chosen by looking at the result
  (`graphs/intersections.pdf`, panel b). Check a few intersections you know on the ground.
- DECIDE: are the walking constants sourced, or assumptions? default: assumptions, uncited.

## 3. The population (paper section 3.1)

- Today: 10,000 people drawn from mixes written by hand in `make_agents.py`: 74% HKU students, 10% staff,
  16% residents. It does not represent the area.
- Official figures, with sources, are in `hku-agents/data/population_figures.csv`:
  - residents of the nine census areas from Kennedy Town to Sai Ying Pun (2021 census): 143,781.
    Ages: under 15 10.1%, 15-24 7.4%, 25-44 31.6%, 45-64 29.9%, 65+ 20.9%. Activity: working 54.9%,
    students 12.8% (including school children), retired 18.0%, home-makers 4.1%, unpaid carers 1.7%,
    others 8.5%. Of the working residents, 33.5% work in Central & Western, 14.3% at home (12.3% of
    working residents are domestic helpers), 9.9% have no fixed place, and the rest work elsewhere;
  - HKU (2025/26): 45,303 students (20,103 undergraduate, 20,366 taught postgraduate, 4,834 research),
    10,076 staff, 7,800 hall places.
- In those proportions (residents plus HKU students and staff, before removing HKU people who already live
  in the area): residents about 73%, HKU students about 22%, staff about 5%.
- Gaps: the census counts residents at night (30 June 2021, during COVID), so it includes HKU people who
  live locally and leaves out everyone who comes in by day; workers coming in can only be counted for the
  whole district, which includes Central; no station or pedestrian counts were found.
- Not in the current generator at all: school children (10.1% of residents) and domestic helpers
  (6.7% of residents), two groups that walk a lot locally.
- DECIDE: how to use the figures. default: nothing done. Options:
  - same size, new mix: 10,000 people in the proportions above, about US$20; same crowd density as day1,
    so the effect of the mix can be seen on its own;
  - bigger: for example 50,000 people, about US$100, closer to the real number of people in the area;
  - reweight day1 to these proportions: free, but only 1,618 residents carry the residents' weight.
- DECIDE: include A13 Tung Wah (12,320 people), which reaches Aberdeen Street? default: no.
- DECIDE: how to estimate people who come into the area to work, shop or visit. default: left out.

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

## 6. The Markov chains (implemented in `hku-agents/following.py`)

- State: a decision point and the road you arrived by. Choice: the road out. No other memory: this is the
  plan's chain of decisions, made exact.
- Four tables of choice probabilities:
  - equal: every road out has the same chance, 1/n, where n is the number of roads other than the one
    you came by (turning back only at a dead end);
  - momentum: weight exp(kappa cos(change of direction)), kappa = 2, so straight on is e^2 = 7.4 times
    likelier than a right-angle turn;
  - counted: the shares counted at each intersection and road in, per hour of day, in the Agent World run.
    This is what the plan's thermal sensors would record, with no way to follow anyone. An hour with fewer
    than 30 passes uses the whole day's shares;
  - imitation: counted, but with chance rho = 0.3 a walker takes the road the person just in front of
    them took (at most 30 m ahead): the stranger-following effect of Wang et al.
- Chain walkers: one per Agent World trip, starting at that trip's first decision, at the same time and
  pace, making the same number of decisions. All walkers share one clock. 3 repeats.
- Formula: two independent walkers arriving at state s make the same next k decisions with chance
  q_k(s) = sum over roads a of p(a | s)^2 q_(k-1)(next(s, a)), q_0 = 1 (the plan's "X^3", made exact).
  The simulated walkers match it (equal and momentum exactly, counted within half a point because a walk
  can cross into the next hour), which checks the code.
- DECIDE: kappa (default 2; 0.5 to 4 in `following_sweeps.csv`), rho (default 0.3; 0 to 0.5), and the
  minimum passes for an hour's own table (default 30).

## 7. Arm C: the live world (implemented in `hku-agents/live.py`, not run)

- No navigation app: no `go_to`, `stroll` or `route_info`. At every real intersection (section 2) the
  person sees its roads (name, compass heading, metres to the next intersection, stairs, lifts, unlit at
  night, places passed, dead ends, how many roads the next intersection has) and the people within 50 m,
  and picks one road with `walk`. Walking then goes on by itself to the next intersection.
- `search_places` and `nearby` give a place's direction and straight-line distance, not the way there.
  Once a person names where they are heading, every view shows its direction and straight-line distance.
- One shared clock: everyone whose next decision falls in the next 10 s is asked at once, then the clock
  moves on. Each person sees the others where they really are at that moment ("walking away from you along
  road 2", "coming toward you", "standing at X"). People inside buildings are not seen.
- Nothing in the prompt mentions following. Whether anyone follows anyone is up to the agents.
- The people are the first N of the day1 people, so the arms are compared on the same people.
- The simulator steps in only when a trip passes 90 minutes (it walks the person to where they were going,
  marked `auto`), and at midnight.
- Tested with a free rule-based walker (1,000 people; every walk continuous) and a fake API server (2,610
  valid requests, before the move to real intersections). The rule-based walker, which steers only by
  straight-line distance, gets lost on the hillside: the simulator had to finish 42% of its trips.
- Estimated cost, assuming about 55 to 85 calls per person (about 6 to 12 decisions per trip plus look-ups)
  and about US$0.0002 per call (day1 measured US$0.000175): about US$10 to 30 per 1,000 people. Not measured.
- DECIDE: run a 20-person pilot first (`--limit 20 --budget 2`) to measure the cost and how often agents
  get lost. default: not run.
- DECIDE: how many people; what a person sees at an intersection; sight distance (50 m); clock step (10 s);
  when the simulator takes over (90 min).
- DECIDE: whether the persona card's mental map, which gives walking minutes to known places, is
  acceptable without a navigation app. default: kept.

## 8. Measures (implemented in `hku-agents/following.py`; paper section 2.1)

- Following through k intersections: the same stranger, at most 30 m (about 22 s) behind you when you
  reach each intersection, arrives and leaves by your roads at k of your intersections in a row. P_k: share
  of trips with such a stranger (also among trips with at least k decisions). S_k: average number of such
  strangers per trip.
- Pairs arriving together: two people arrive at an intersection by the same road, one at most 30 m behind
  the other; q_k is the share that make the same next k decisions. Compared with each chain's formula.
- Same next road, by the number of roads at the intersection (3, 4, 5, 6+).
- By hour of departure.
- Who follows whom: shared start and destination (within 150 m), same group.
- The plan's table (`decision_table.csv`): for each intersection and road in, the share of each road out,
  labelled front, left, right or back, and the share that stop there, next to the equal-chance and momentum
  probabilities.
- DECIDE: the following distance. default: 30 m (15 m and 60 m in `following_sweeps.csv`).
- DECIDE: the "same place" radius for who follows whom. default: 150 m.

## 9. Tests

- Chi-square goodness of fit at each intersection and road in with at least 30 passes: do the Agent
  World's counts of each road out fit equal chance, or momentum? Turning back is left out, since equal
  chance never turns back. Benjamini-Hochberg correction; effect size w = sqrt(chi-square / passes).
  Calibrated on the equal-chance walkers' own counts (0% rejected after correction).
- Models against the Agent World: the formula is exact, and the chain walkers have 3 repeats, so the
  differences are shown with their spread rather than p-values (more simulation always gives smaller p).
- Known limit: one person passes the same intersection on several trips, so passes are not independent
  and p-values are too small. The effect sizes do not have this problem.
- The older tests in `arms.py` (chi-square, G-test and Diebold-Mariano on raw map junctions with four
  fixed options) are superseded by this. DECIDE: keep them in the paper or drop them. default: drop.
- DECIDE: significance level. default: 5% after correction.

## 10. What we report

- Figures: `graphs/intersections.pdf` (preprocessing), `graphs/following-models.pdf`,
  `graphs/following-pairs.pdf`, `graphs/following-roads.pdf`, `graphs/following-hours.pdf`, and the two
  amenity maps. `graphs/road-use-ratio.pdf` (road use, from `arms.py`) is still valid.
- Superseded (raw junctions, 90 s window): `graphs/shared-turns-three-arms.pdf`, `graphs/markov-turns.pdf`.
- Tables: `hku-agents/out/day1/analysis/following.md` and its CSV files.
- DECIDE: which of these go in the paper, given the page limit.

## 11. Limits to state

- Synthetic people; one simulated day; one run of the agents. The mix (74% students) is not yet based on
  the census.
- In the Agent World people choose where to go, but walk the quickest path; the live world, where they
  choose every road, has not been run.
- 10,000 people are fewer than the real number of pedestrians. With the same behaviour, more people can only
  add strangers, so the chances reported are lower than they would be on real streets.
- Lighting is tagged on 2% of segments and indoor routes are mostly missing; opening hours are not enforced.
- The preprocessing thresholds (section 2) are our choices.
- DECIDE: anything else you want stated.
