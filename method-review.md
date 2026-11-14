# Review of the Methodology draft

Checked against the code and `method.md` on 14 November 2026. Each section has two parts: the errors in each
paragraph as written, then what the section still needs to describe.

"Code" below means what `hku-agents/` does today. Where the draft and the code disagree, either the draft or
the code has to change; I have assumed the code and the authors' decisions in `method.md` are the truth.

## The four biggest problems

1. **The number of conditions.** The draft says three and describes four. The code has eight (nine with the
   first run): two LLM conditions, two non-LLM trip baselines, and four Markov chains.
2. **Two baselines are mixed up.** "Random walking" (a random choice at each junction) and "Random Init and
   End" (a random start and end joined by the quickest path) are different experiments, but several
   paragraphs treat them as one.
3. **The evaluation described is not the evaluation in the code.** The draft tests left/right/front/back
   pairs. The code tests each path out of each junction, and its main measure is following through k
   junctions in a row, which the draft never defines.
4. **Whole topics are missing:** the population, walking speeds, the model and its settings, the Markov
   chains, and the limitations.

## 1. Preprocessing

### Errors by paragraph

| Paragraph | Error | Fix |
|---|---|---|
| "First, we will need to reconstruct…" | "OpenStreetMap package" names no tool or data. "Footways or car roads" is narrower than what is used. Future tense for work already done. | Say the data is OpenStreetMap, and list the way types: footways, paths, steps, pedestrian streets, corridors, cycleways, tracks and public roads, plus lifts. |
| "Sometimes calculating every node isn't needed…" | "Merge all roads into a single line with only two decisions" reads as if junctions were merged. Only chains of nodes with two roads are joined into one segment. Junctions are never merged (authors' decision 5). "Conjunction" should be "junction". | "A node where only two segments meet offers no choice, so we join such chains into one segment. Every node where three or more paths meet is kept as its own junction; nearby junctions are not merged." |
| "The result is 3543 roads with 4835 segments…" | 3,543 is the number of nodes, not roads. "Below are the features" is followed only by a figure. | "3,543 nodes joined by 4,835 segments, 155.8 km of path." |
| Figure "Constructing the Map" | Label is `fig:placeholder`, the same as the second figure, so references will point to the wrong one. The figure is never cited in the text. | Give it its own label and refer to it. |

### Still to describe

- The study area and its bounding box (22.276–22.292 N, 114.124–114.147 E), and the date the map was downloaded.
- What is excluded: ways tagged `foot=no`, `foot=private` or `access=no`; only the largest connected part is kept.
- Stairs and lifts: 383 segments with stairs, 48 lifts.
- Why 713 nodes with two roads remain after joining: a place or a lift sits there.
- The places: 1,538 named places in 17 categories, each attached to the nearest node within 150 m.
- The table of junction types belongs here, not in the next section.
- A consequence the reader needs: junctions are about 13 m apart, because sidewalks and crossings are drawn
  separately. A trip passes a median of 15.

## 2. What Counts as Following

### Errors by paragraph

| Paragraph | Error | Fix |
|---|---|---|
| "To define a clear range…" | "We might refer to" is not a definition. Distance alone does not define following: there is no time, direction or duration. | State the code's definition: the same stranger is at most 30 m behind you along the road when you reach a junction, arrives and leaves by your roads, and does so at k junctions in a row. |
| "If someone makes a turn…" | Correct, and matches the code. "Pythagorean distance" is unusual. | "Straight-line distance". |
| "Our basic formation of agent choice…" | "Positional encoders" is a machine-learning term that means something else. "35 degrees away from the vertical line" does not match the code: front is within 40° of straight on, measured from the direction of arrival. "Back" is not defined. | Give the 40° rule from the direction of arrival. Say the labels are used only to name choices in tables. |
| "Since navigation apps would still prefer…" | "Predetermined chance … based on location-to-location walk" does not say where the chance comes from. "25%" is not the code's equal chance, which is 1/(n−1) because walkers do not turn back. "Including lights" contradicts authors' decision 8: no traffic lights are simulated. The last sentence ("penalize … the third choice") cannot be followed. | Say the chances are the shares counted at each junction, for each road in, in the Agent World run. Remove the mention of lights, or state that lights are not simulated. |
| "Through our construction, the number of four conjunction allowed roads is merely:" | Not a sentence a reader can parse. | "Table X counts the nodes by the number of roads that meet there." |
| Table | The draft has 1,711 three-way junctions; `method.md` has 1,710 (2,371 junctions in all). One of them is wrong. Caption says "Conjunctions". Label is a placeholder. | Check the count in the code's output and use one number everywhere. |
| "As we can see, there are even more three way junctions…" | "THis". "Disadvantage some of the conjunction reasons" has no clear meaning. The graph is described as node to node, but in the code the chance depends on the road you arrived by, not only the junction. | Say why four directions fail (73% of junctions have three roads) and that the state is the junction plus the road in. |
| Figure "An example of conjunctions…" | Same placeholder label as the first figure. | Own label; cite it. |
| "In this graph, each connection would have its own weights…" | Fine. | – |
| "The reason for we to keep both…" | The current analysis does not compare the two methods: the four-direction tests in `arms.py` are marked superseded in `method.md`, with "drop" as the default. Typos: "naviagte", "theirselves", "chosing". | Either drop this paragraph, or decide to keep the old tests and say so in `method.md`. |

### Still to describe

- The value of k that counts as "appearing to follow": 3, with 5 also reported. Note that 3 junctions is
  often only about 40 m.
- The three measures: the share of trips with such a stranger (P_k), the average number of such strangers
  per trip (S_k), and the share of pairs arriving together that make the same next k choices (q_k).
- That "stranger" excludes the person themselves, and how people who share a start and destination are
  treated (the code reports them separately, within 150 m).
- That 15 m and 60 m were also tried.
- That no traffic lights are simulated, so nobody is split up or bunched at a crossing.

## 3. Agent World Modeling

This is a `\subsubsection` under "What Counts as Following". It should be under its own subsection for the
experimental conditions.

### Errors by paragraph

| Paragraph | Error | Fix |
|---|---|---|
| "For each agent, we will give them unlimited tool calls and turns…" | Not unlimited: the code allows at most 40 tool calls per agent. | State the limit of 40. |
| "To test this, we would ablate the experiment into three parts…" | These are conditions, not an ablation. "Three" is wrong (see the top of this review). "Walk to any destination simply" describes random start and end, not random walking. "MCP" is wrong: the tools are passed to the model through the API's tool use, with no MCP server. "Could follow other agents" overstates it: the prompt never mentions following. | List the conditions in one table. Say "tools" throughout. Say omni agents can see others and nothing tells them to follow. |
| "Since people do not just have a path planned…" | Says agents decide each step, but `go_to` walks the whole quickest path, so in this condition agents choose destinations, not junctions. "Unless we deploy some clock-like mechanism" is wrong: every agent already has a clock that each walk and stay moves forward. | Say the agent decides one trip at a time; the choice at each junction is read off the path afterwards. Only `stroll` leaves the quickest path. |
| Tool list | Matches the code. | – |
| "The first four functions only observe…" | Correct. | – |

### Still to describe

- The model and settings: Claude Haiku 5.5, low effort, one simulated weekday per agent.
- How many agents (10,000), and that each is run separately with no shared state.
- How `stroll` picks its turns (noisy turns toward the named place).
- How separate clocks become one timeline: trips are replayed together afterwards to find who was near whom.
- Which run the paper reports: `day1` (old mix, 74% HKU students, done) or `census_run` (census mix, not
  yet run).
- How days end, and what happens to an agent that reaches the call limit.

## 4. Random Walking

### Errors by paragraph

| Paragraph | Error | Fix |
|---|---|---|
| "Random walking, as the name suggests…" | "Any random choice" is not exact: in the code every road except the one you came by has the same chance, and walkers turn back only at a dead end. "Agency" is the wrong word. | "At each junction the walker takes each road other than the one it arrived by with equal chance, 1/(n−1)." |
| "For this quality, this yields the baseline…" | "For this quality" has no meaning here. | "This gives the baseline share of each choice at each junction." |

### Still to describe

- Where and when each walker starts: one walker per Agent World trip, starting at that trip's first junction
  at the same time and pace, and making the same number of choices.
- The number of repeats (3).
- The other three chains, which the draft never mentions: momentum (prefers straight on), counted shares
  (taken from the Agent World run), and counted shares plus a 30% chance of copying the person in front.
- The formula for two independent walkers making the same next k choices, and that the simulated walkers
  match it.

## 5. Random Init and End

### Errors by paragraph

| Paragraph | Error | Fix |
|---|---|---|
| "We could randomly choose any point on the map…" | "Could" for something that is done. Not any point: the start and end are drawn from the 1,538 places. "Map API" should be the same quickest-path routing as `go_to`. "Representative baseline" does not say of what. | "Each start and end is drawn with equal chance from the 1,538 places and joined by the quickest path." |
| "In comparison to these three methods," | Unfinished sentence. | Finish or delete. |

The heading is a `\subsection` while the conditions before it are `\subsubsection`s.

### Still to describe

- Each random trip copies the departure time, pace and owner of one real trip, so the streets are as busy at
  each hour as in the Agent World.
- 5 repeats with different seeds.
- The known limit: random trips are longer (1,119 m against 666 m in `day1`), so they have more chances to overlap.
- What this baseline isolates: the effect of the road network and routing alone, without people's choice of
  where to go.
- The rule-based planner control (the same people, no LLM), if you report it.

## 6. Omni Agents

### Errors by paragraph

| Paragraph | Error | Fix |
|---|---|---|
| "These are agents who live in the present time…" | Agent World agents do not have a "completely preplanned route" either; the real difference is a shared clock, sight of others, and choosing every junction with no navigation. The long sentence beginning "This is because…" cannot be parsed. Typos: "preplaneed", "signficiant", "wheter", "chosing". | "If following rises when agents can see each other, the extra is deliberate; what remains in the Agent World is coincidence." |
| "For this benefit, we even allow the agents to speed up…" | Pace is not special to this condition: Agent World agents also choose slow, normal or fast. "Skills" should be "tools". | Drop "even"; say pace is the same choice as before. |
| Tool list | Matches the code. | – |
| Prompt figure | Shows only the Agent World prompt, which mentions `go_to` and `stroll`. Omni agents do not have those tools. | Add the omni system prompt, or say how it differs. |

### Still to describe

- The people: the first 1,000 of the same 10,000, so the two conditions are compared on the same people.
- The shared clock: everyone whose next choice falls in the next 10 s is asked at once.
- What is seen: people within 50 m; people inside buildings are not seen.
- That nothing in the prompt mentions following.
- The limit of 500 model calls per person, and that the simulator walks a person to their destination if a
  trip passes 90 minutes. Report the share of trips finished this way.
- That this condition has not been run yet.

## 7. Evaluation Requirements

### Errors by paragraph

| Paragraph | Error | Fix |
|---|---|---|
| "For evaluating the results, we are going to deploy a Chi Squared test…" | A test does not "prove". The paragraph does not say what is compared with what. "Left-to-left, right-to-right" is not what the code does: it compares the count for each path out with the count expected under equal chance or momentum. | "For each junction and road in with at least 30 passes, a chi-square goodness-of-fit test compares the agents' counts for each road out with those expected under equal chance and under momentum." |
| "On the other hand, road utilization is another aspect…" | Ends on a question and names no measure. "Random walking could use the navigation APIs" contradicts section 4: the random walker does not navigate; the random start-and-end baseline does. | State the measure: how often each segment is used in each condition, and the ratio between conditions. |

### Still to describe

- The hypotheses, numbered, and which number would support each.
- The main comparison: P_k, S_k and q_k for the agents against each Markov chain.
- Correction for testing thousands of junctions (Benjamini–Hochberg) and the significance level (5%).
- The effect size (w = √(chi-square / passes)), because with this many passes almost any difference is significant.
- That turning back is left out of the test.
- The check on the test itself: run on the equal-chance walkers' own counts, it rejects 0%.
- The independence problem: one person passes the same junction on several trips, so p-values are too small.
- The breakdowns: by number of roads at the junction, by hour, and by who follows whom.
- How the omni condition is compared with the Agent World on the same 1,000 people.

## 8. Sections that do not exist yet

| Section | What it must say |
|---|---|
| Overview of conditions | One table of every condition: who picks the destination, who picks the route, whether they see others, how many people, whether it uses an LLM. |
| Population | 10,000 people in the proportions of the 2021 census and HKU's figures: 75.7% residents, 19.8% HKU students, 4.5% HKU staff. How residents are split by kind, how schedules are given, and the assumptions made (Medicine left out, 17.2% of students in halls, 75% of commuters by MTR). |
| Walking speed | Speed by age from published studies, the spread between people, the three paces, stairs at 0.67 m/s, lifts at 40 s. The sources still need checking against the originals. |
| Limitations | Synthetic people; one day and one run; fewer people than the real streets, so the chances are lower bounds; no traffic lights; no real pedestrian data to validate against; junctions only about 13 m apart; LLM choices may not match real preferences. |

## 9. Throughout

- Use "junction" everywhere; "conjunction" is a grammar term.
- Pick one tense. Past for what was done, present for definitions; avoid "would", "could" and "will".
- "MCP" and "map API" should be "tools" and "quickest-path routing".
- Every figure and table needs its own label and a sentence in the text that refers to it.
