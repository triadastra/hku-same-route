# method.md: design of the same-route experiment

**Status: skeleton.** Each section says what the code does today, then lists the design choices that are
yours to make. A line starting with `DECIDE:` is waiting for you; the value after `default:` is what the
code uses now. Replace the line with your choice and a one-line reason, and delete this notice when the
document is yours.

## Decisions made by the authors

Made on 2026-11-14, after reviewing the defaults that Claude Code had filled in. The sections below follow them.

1. Study area: Kennedy Town to Sai Ying Pun, from the Pok Fu Lam Road halls to the waterfront (kept).
2. Walkable paths: every path a pedestrian may use, including roads, because sidewalks are often not drawn
   separately (kept).
3. Walking speed: values from published studies, cited; each person chooses their own pace, within a range
   that makes sense, for every walk.
4. Destinations: all 1,538 places in the 17 categories (kept).
5. Junctions: every junction drawn on the map is a junction, and nothing is merged.
6. Population: 10,000 people in the proportions of the 2021 census and HKU's figures, not 70% HKU students.
7. Following: the follower is at most 30 m behind, measured along the road, not in a straight line.
8. No traffic lights in the simulation: nobody waits at a crossing, so no catch-up allowance is needed.

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
- Decision points (`decisions.py`), by the authors' decision 5: every junction drawn on the map is a junction,
  and every path out of it is its own choice. Nothing is merged. That gives 2,371 junctions (1,710 where 3
  paths meet, 652 with 4, 9 with 5). A trip passes a median of 15 junctions, about 13 m apart, because
  sidewalks and crossings are drawn as separate paths. Merging nearby junctions into intersections is kept
  in the code (`Decisions(world, merge=True)`) but not used; `graphs/intersections.pdf` shows what it would do.
- A decision is (junction, path in, path out, time), the record the project plan's thermal sensors would
  produce. For tables a decision is also labelled front (within 40° of straight on), left, right or back.
- Walking speed (authors' decision 3; values in `config.py`, sources in `hku-agents/data/walking_speeds.csv`):
  - each person's comfortable speed on the flat comes from their age: the mean of men's and women's speeds for
    their decade (Bohannon & Andrews 2011: 1.35 m/s in the 20s, 1.41 in the 40s, 1.29 in the 60s, 0.96 at
    80+), plus a spread of 0.15 m/s between people (Bohannon 1997). Teenagers walk like adults (McKay et al.
    2017). The 10,000 people have a median of 1.34 m/s, the middle half 1.22 to 1.45 m/s;
  - for every walk the person chooses slow, normal or fast: about a quarter slower or a third faster than
    their own speed (Lythgo, Wilson & Galea 2011; Oberg et al. 1993 give the same ratios);
  - stairs: 0.67 m/s along the stair, the mean of up (0.57) and down (0.77) from Fruin (1971), because the
    map does not say which way a stair goes up; Hong Kong stairs measured 0.61 to 0.66 m/s (Lam et al. 1995);
  - map walking times use 1.34 m/s, the mean free walking speed (Weidmann 1993), scaled by each person's speed.
  - All values were taken from abstracts or from later papers quoting them: check the originals before citing.
  - day1 was run before this, with 1.35 m/s for everyone, stairs 2.2 times slower and a random 0.85 to 1.2
    multiplier; the next run uses these values.
- DECIDE: the international speeds by age, or the same curve scaled to Hong Kong measurements? Hong Kong
  walkways measured about 1.3 m/s (Lam & Cheung 2000) and older Hong Kong men 1.05 m/s at 65 to 70 (Mr OS
  study), slower than the international 1.29 m/s for their decade. default: international.
- DECIDE: children aged 6 to 9 walk at 1.2 m/s, an assumption within the 0.82 to 1.34 m/s found for ages 1 to
  10 (Dusing & Thorpe 2007, no values per age). default: as stated.
- DECIDE: lifts take 40 s (waiting and riding); no published value was found. default: 40 s.

## 3. The population (paper section 3.1)

- Authors' decision 6: 10,000 people in the proportions of who is in the area on a weekday, from the 2021
  census and HKU's figures (sources in `hku-agents/data/population_figures.csv`):
  - residents of the nine census areas from Kennedy Town to Sai Ying Pun: 143,781 (2021);
  - HKU people by faculty and job, from HKU's 2025/26 figures: students by faculty and level (undergraduate,
    taught postgraduate, research postgraduate), and staff by type (professors, research staff, teaching
    staff, administrative staff, technical staff). The 1,206 taught postgraduates studying in Beijing and
    Shanghai are taken out of each faculty in proportion.
  - Medicine (6,525 students) is based at the Sassoon Road campus, off the map, so its students and staff are
    left out. Dentistry is at the Prince Philip Dental Hospital in Sai Ying Pun, on the map, and is kept.
  - On the map that is 46,110 HKU people (37,647 students and 8,462 staff) against 143,781 residents: one HKU
    person for every 3.1 residents. As shares: 75.7% residents, 19.8% HKU students (8.4% undergraduate, 9.5%
    taught postgraduate, 1.9% research) and 4.5% HKU staff; in 10,000 people, about 7,570 residents, 1,980
    HKU students and 450 HKU staff. HKU people by faculty: Engineering 23.6%, Business and Economics 22.1%,
    Science 10.8%, Social Sciences 10.7%, Arts 9.3%, Education 7.2%, Architecture 5.5%, Law 4.3%, Dentistry
    2.3%, central offices 3.7%.
  - Each HKU person works or studies in their faculty's building; staff have office hours, professors and
    teaching staff also teach classes, research staff work in labs until 17:30 to 19:30.
- Residents are split by the census: working in Central & Western 26,413; working outside it 33,383; no
  fixed place of work 7,809; domestic helpers 9,665; working at home 1,607; students 18,414; retired 25,818;
  home-makers 5,952; unpaid carers 2,486; not working 12,234. Ages follow the census age bands within each
  kind's age range.
- Implemented in `make_agents.py`; it prints the generated mix against these targets. With 10,000 people
  every kind is within 0.5 points of its target, and the residents' ages within 2 points in every band
  except under 15 (6.5% against 10.1%, because children under 6 are not simulated on their own).
- Not yet run with the model (about US$20).
- DECIDE: the assumptions the figures do not settle (marked ASSUMPTION in `make_agents.py`). defaults:
  - half of the residents working in Central & Western work inside the study area, half in Central or
    Sheung Wan;
  - 70% of resident students are school pupils (6 to 17) at a school in the area; the rest go to college
    elsewhere;
  - 75% of commuters use the MTR, 25% a bus;
  - the age range of each kind of resident (for example retired 65 to 95, domestic helpers 25 to 55);
  - children under 6 are not simulated on their own; the census "others" are simulated as adults 18 to 80;
  - every HKU student and staff member comes to campus that day, and 17.2% of students live in a hall
    (7,800 places over 45,303 students, university-wide);
  - Medicine is left out because it is based off the map;
  - HKU publishes no staff numbers by faculty: professors and teaching staff are spread over faculties like
    all students, research and technical staff like research postgraduates, and half of the administrative
    staff work in central offices (Main Building, Knowles Building), half in the faculties;
  - HKU people who live in the area are counted twice (as residents and as HKU); not removed.
- DECIDE: the fixed plans given to each kind of resident (work hours, school 08:00 to 15:30, a morning
  market trip for retired people, home-makers and helpers, a school pick-up for half the helpers, a clinic
  visit for carers). default: as in `make_agents.py`.
- DECIDE: include A13 Tung Wah (12,320 people), which reaches Aberdeen Street? default: no.
- DECIDE: how to count people who come into the area to work, shop or visit. default: left out (no data
  below district level).

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

### 6a. The deliberate follower (implemented in `hku-agents/follower.py`)

Added on 2026-11-14 at the authors' request: a walker that follows on purpose, by a fixed rule with no
personality, to show what the measure reads when following is intended. It is not a Markov chain: it has
a destination, a target and a memory of its closest point.

- The world is the Agent World run, replayed unchanged. Followers see the Agent World people, who walk
  exactly as they did. Followers do not see each other, so a follower only ever follows a real person
  living their day (authors' decision).
- One follower per Agent World trip: it starts at that trip's first junction, by the same road, at the
  same time and pace, and keeps that trip's destination.
- At each junction it takes the road with the highest score, reward minus penalty. Nothing is trained and
  nothing is drawn by chance, so one run is the whole result.
- Penalty (authors' rule): the follower remembers the closest it has ever been to its destination (the
  minimum walking distance over every junction it has passed). A road that would leave it x beyond that
  closest distance costs 0.5 x^2. A little farther costs almost nothing, so a road that must go round is
  accepted; going the other way to follow someone is punished more and more.
- Reward (authors' rule): R = 1 for taking the road its target took, and only while the target is in view
  and at most 30 s of walking in front. "In view" is taken as: the target came to this junction by the
  follower's own road at most 30 s before it. The map has no buildings to block a line of sight.
- The target is the person nearest in front, kept from junction to junction until lost. With nobody to
  follow, the follower takes the quickest road.
- The follower never overtakes its target (it reaches the next junction at least 1 s after them). It does
  not speed up to keep up.
- It stops when it takes the road its destination is on, or after 3 times its trip's junctions plus 10.
  The share that do not arrive is reported: a follower can keep circling near its closest point, taking
  one target after another, because the penalty is measured from the closest point and not from the time
  spent.
- Measure: T_k, the share of walkers who trail the same stranger through k junctions in a row, at most
  30 m behind along the road each time. This is the study's following rule seen from the person behind.
  It is computed for the Agent World people (coincidence) and for the followers (intent), against the same
  leaders, with 95% bootstrap intervals that resample people.
- Checks (`python follower.py --check`, no run needed): with R = 0 a follower repeats its quickest-path
  trip exactly and follows nobody; with a reward it follows; two runs agree.
- Tested on the day1 trips only to see that it runs (5 minutes for 56,379 trips); those numbers are not
  kept. Results come from `census_run`: `out/census_run/analysis/follower.md`.
- DECIDE: the unit of x. default: 100 m, so with R = 1 a follower goes at most 141 m (100 m times the
  square root of 2) beyond its closest point. R from 0 to 16 (0 to 566 m) is in `follower_sweep.csv`.
- DECIDE: the view time (default 30 s); whether a follower may speed up to keep its target (default: no);
  whether followers should also see each other (default: no).

### 6b. The Q-learning follower (implemented in `hku-agents/follower_rl.py`; run on `census_run`)

Added on 2026-11-14 and revised on 2026-11-15 at the authors' request. It replaces 6a for results: the
follower of 6a changes targets and keeps its own trip's destination, which the authors ruled out.
`follower.py` is kept for the measure it defines (T_k) and as a record.

- The world is the census Agent World run, replayed unchanged. The Agent World people walk exactly as
  they did, at the pace they chose (slow, normal or fast; they never run). Nobody sees followers.
- A follower starts behind one Agent World person (its target) at the first junction of one of that
  person's trips. One target for the whole chase (authors' rule): if it loses its target or lets go, the
  chase is over and it walks the quickest path to its own destination. It never takes another target.
- Its destination and comfortable walking speed are those of a trip of a different, randomly chosen
  person (authors' rule), so following and its own destination pull in different directions.
- Road: at each junction while the target is in view and took a road other than the follower's quickest
  road, it chooses to follow or to leave. A follower may turn back the way it came.
- Speed (authors' rule: the follower chooses its speed, from walking to sprinting, from published values):
  while it follows it chooses one of five speeds, as multiples of its own walking speed: walk 1.0, fast
  walk 1.30, jog 1.54, run 2.61, sprint 4.33. For an adult who walks at 1.34 m/s these are 1.34, 1.74,
  2.07 (the walk-to-run transition), 3.5 (critical speed of recreational runners) and 5.8 m/s (an
  untrained adult's 100 m). It never overtakes its target. Sources and their weaknesses are in
  `hku-agents/data/walking_speeds.csv`: the run value comes from runners, who are fitter than an average
  resident, and the sprint value from a running website, not a study.
- Stamina (authors' rule: sprinting is penalised, fast walking is not): a bar of 130 m of running above
  critical speed (D' of the critical-speed model), drained only by going faster than a run. With the bar
  empty a sprint is only a run. It does not refill during a walk. Using the whole bar costs 1.
- Reward (authors' rule: closeness to the target, not the catch): each time it takes its target's road
  while the target is in view it earns 1 - gap / 30 s, where gap is how far behind the target it is. There
  is no separate reward for catching the target.
- Penalty (authors' rule, as in 6a): 0.5 x^2 for a road that leaves it x beyond the closest it has been
  to its destination, x in units of 100 m.
- Learning: one-step tabular Q-learning, no discount (gamma = 1), epsilon-greedy from 1 to 0.02, learning
  rate 0.2 falling to 0.02, 150 epochs, 3 trainings with different random numbers. The state is what the
  follower can know at the junction, in bins: how far beyond its closest point its quickest road and its
  target's road would leave it, seconds behind the target, whether that gap is closing or widening, how
  full its stamina bar is, whether it has been within 5 s of its target, and distance left to its
  destination. Six actions: leave, or follow at one of the five speeds.
- People are split in two at random: training behind the trips of one half, testing behind the trips of
  the other. Every number reported is from the test half.
- All followers of an epoch are stepped together as PyTorch tensors, on CUDA when there is a GPU. It was
  written and tested on a CPU (about 15 minutes for the whole script); it has not been run on a GPU.
- Compared in the same test episodes: a follower that never follows; the one-junction rule walking; the
  same rule with a rule for its speed (the slowest speed that keeps it right behind its target, sprinting
  only until it has first come close; this rule is told when its target reaches the next junction, which
  the learner cannot see); a follower that always follows, running; and the Agent World people's own
  trips (coincidence).
- Results on `census_run`, start 20 s behind (`out/census_run/analysis/follower_rl.md`). Trailing the same
  stranger through 3 junctions: Agent World 50.1%, never follows 65.3%, rule walking 86.5%, rule with
  speed 94.8%, Q-learning 96.4%, always follows 97.4%. Through 10: 11.7%, 15.6%, 34.2%, 58.7%, 60.8%,
  72.0%. Score per follower: never 1.20, rule walking 5.49, rule with speed 11.64, Q-learning 11.56,
  always -139.5. 93.2% of Q-learning followers came within 5 s of their target; 70.5% used some of their
  stamina bar, 6.0% of it on average. It follows up to about 200 m off course and not beyond.
- The same with a start 5 s behind is in `follower_rl_start5.md`: through 3 junctions Q-learning 97.2%,
  through 10 62.4%.
- The "speed chosen" table in the results counts the speed asked for. Asking for a sprint costs nothing
  when the no-overtaking rule holds the follower back, so that table overstates sprinting; the stamina
  used is the real measure.
- Checks (`python follower_rl.py --check`, no run needed): a follower given its target's own destination
  repeats the target's route; one that never follows is never penalised and arrives; the same seed gives
  the same table; Q-learning scores at least as well as the never, always and walking-rule followers on
  people it did not train on; only speeds above a run drain the bar.
- DECIDE: the start gap (20 s or 5 s: the authors wrote "5 seconds" without saying for which number, so
  both were run); the unit of x (100 m); the view time (30 s); the sprint cost (1); whether the bar
  refills; whether the speeds should be scaled down for the general population.

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
- The plan's table (`decision_table.csv`): for each junction and path in, the share of people leaving by
  each of its paths, and the share that stop there, next to the equal-chance and momentum probabilities. The
  paths are named by street and direction; there are no left/right/front/back labels, so a Y junction is
  simply 3 paths and a crossroads 4. `graphs/junction-shares.pdf` draws this as a connected diagram for two
  busy junctions near HKU station (`make_junction_figure.py`).
- Following distance (authors' decision 7): 30 m, measured along the road: the distance the stranger still has to
  walk to reach the junction you are at. 15 m and 60 m are in `following_sweeps.csv`.
- No traffic lights are simulated (authors' decision 8), so two people walking together are never split by a
  red light. On real streets lights would separate some of them; state this as a limit.
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

- Figures: `graphs/junction-shares.pdf` (how people split at a junction), `graphs/following-models.pdf`,
  `graphs/following-pairs.pdf`, `graphs/following-roads.pdf`, `graphs/following-hours.pdf`, and the two
  amenity maps. `graphs/road-use-ratio.pdf` (road use, from `arms.py`) is still valid.
- `graphs/intersections.pdf` shows what merging junctions would do; not used, by the authors' decision 5.
- Superseded (90 s window, four fixed directions): `graphs/shared-turns-three-arms.pdf`, `graphs/markov-turns.pdf`.
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
- No traffic lights: on real streets a red light can separate two people who would otherwise walk together.
- The preprocessing thresholds (section 2) are our choices.
- DECIDE: anything else you want stated.
