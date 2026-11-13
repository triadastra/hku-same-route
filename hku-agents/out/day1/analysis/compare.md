# Comparison of the arms: day1

57223 trips in each arm (5000 used as 'you'); a turn is shared within 90 s. Random walk: 5 repeats, mean ± standard deviation.

## Chance that a stranger makes your same k turns in a row

| k | Agent World | Random walk | Same trips, noisy turns |
|---|---|---|---|
| 1 | 95.2% | 97.3% ± 0.3% | 98.6% |
| 2 | 90.6% | 95.2% ± 0.3% | 97.5% |
| 3 | 85.0% | 92.6% ± 0.4% | 96.0% |
| 4 | 79.2% | 89.7% ± 0.4% | 93.9% |
| 5 | 74.2% | 87.0% ± 0.4% | 89.8% |
| 6 | 68.6% | 84.2% ± 0.3% | 84.1% |
| 7 | 63.1% | 81.0% ± 0.2% | 75.2% |
| 8 | 57.8% | 77.9% ± 0.4% | 63.0% |
| 9 | 52.4% | 74.8% ± 0.5% | 48.5% |
| 10 | 48.2% | 71.8% ± 0.5% | 36.6% |

Average trip length: Agent World 666 m, Random walk 1119 m, Same trips, noisy turns 2611 m. Longer trips give more chances to share turns, so the arms differ in exposure as well as in route choice.

Within the Agent World arm: `go_to` trips (4524) share 5+ turns 76.5% of the time, `stroll` trips (476) 52.5%.

## Markov chain of turns

Two people start walking the same road together. Chance that they then make the same next k turns: what happened, and what a chain predicts in which every turn depends only on the current road.

| k more turns | Random walk, observed | Random walk, Markov chain | Agents, observed | Agents, Markov chain (fitted on agents) | Agents, Markov chain (fitted on random walk) |
|---|---|---|---|---|---|
| 1 | 72.0% | 82.5% | 67.5% | 65.5% | 79.0% |
| 2 | 59.1% | 69.7% | 49.3% | 43.8% | 59.0% |
| 3 | 50.0% | 58.6% | 39.6% | 31.7% | 47.1% |
| 4 | 44.3% | 50.8% | 33.2% | 23.7% | 39.6% |
| 5 | 38.1% | 43.6% | 26.2% | 16.6% | 32.4% |

Pairs that met: random walk 165,678, agents 526,687.

## Do agents turn differently from random walkers?

G-test of the left/right/straight/back counts, agents against random walk, where both arms have at least 30 passes. p-values corrected over all units (Benjamini-Hochberg). 'Noise check' is one random-walk repeat against another: what the same test gives when there is no real difference.

| Unit | Tested | Significant at 5% | Median difference (TVD) | Pass-weighted TVD | Noise check: significant | Noise check: median TVD |
|---|---|---|---|---|---|---|
| Junction | 1819 | 83.6% | 0.182 | 0.170 | 0.0% | 0.017 |
| Road and direction | 3774 | 80.3% | 0.194 | 0.165 | 0.0% | 0.008 |

TVD (total variation distance) is the share of turns that would have to change for the two arms to agree: 0 = identical, 1 = completely different.

Paired differences, agents minus random walk, per road and direction:

| Turn | Mean difference | Mean absolute difference | Wilcoxon p |
|---|---|---|---|
| Left | +4.4% | 14.2% | 1.48e-56 |
| Right | +4.5% | 14.1% | 3.92e-56 |
| Straight | -9.3% | 17.6% | 2.17e-117 |
| Back | +0.3% | 0.4% | 2.09e-31 |

## Diebold-Mariano: which model predicts the agents' turns better?

Brier score over 1,283,334 agent turns (lower is better): equal chance per exit 0.6777, random-walk shares 0.4021.
DM statistic over 18 hours of the day (Newey-West, lag 2): 6.70, p = 3.72e-06. Positive means random walking predicts the agents better than equal chance.
Across 4849 roads and directions: random walking is the better predictor on 63.0% of them (paired t = 28.55, p = 6.72e-166).

## Road use

Spearman rank correlation of walkers per segment, agents against random walk: 0.586 (4720 segments used by either arm).
Share of all metres walked on the busiest 5% of segments: agents 59.2%, random walk 57.0%.
Segments never walked: agents 150, random walk 874 of 4835.

Regression of log(agent share / random-walk share) on places within 60 m of the segment (4309 segments, R² = 0.111, robust standard errors):

| Places nearby | Coefficient | Std. error | p |
|---|---|---|---|
| (intercept) | +0.202 | 0.071 | 0.00447 |
| Food and drink | -0.031 | 0.011 | 0.00725 |
| Shops | +0.074 | 0.013 | 3.23e-08 |
| University | +0.586 | 0.030 | 9.92e-84 |
| Named buildings | -0.041 | 0.008 | 1.42e-06 |
| Transport stops | +0.057 | 0.020 | 0.00437 |
| Parks and sights | +0.109 | 0.020 | 8.57e-08 |
| Schools | +0.165 | 0.042 | 0.000104 |
| Everyday services | -0.171 | 0.022 | 3.9e-15 |

A coefficient of +0.10 means each extra place of that kind nearby goes with about 10% more agent walking on the segment than random walking would put there.

Tables: arms_shared_turns.csv, arms_markov.csv, junction_tests.csv, junction_tests_directed.csv, road_usage_compare.csv, road_amenity_regression.csv.