# Comparison of the arms: census_run

42161 trips in each arm (5000 used as 'you'); a turn is shared within 90 s. Random walk: 5 repeats, mean ± standard deviation.

## Chance that a stranger makes your same k turns in a row

| k | Agent World | Random walk | Same trips, noisy turns |
|---|---|---|---|
| 1 | 93.1% | 96.3% ± 0.3% | 98.8% |
| 2 | 87.2% | 93.4% ± 0.4% | 97.5% |
| 3 | 80.5% | 90.2% ± 0.5% | 95.4% |
| 4 | 72.6% | 86.7% ± 0.6% | 90.5% |
| 5 | 64.7% | 83.3% ± 0.6% | 82.0% |
| 6 | 57.8% | 79.8% ± 0.7% | 67.6% |
| 7 | 51.1% | 76.2% ± 0.7% | 51.0% |
| 8 | 46.3% | 72.3% ± 0.6% | 36.3% |
| 9 | 41.2% | 68.5% ± 0.5% | 24.9% |
| 10 | 37.7% | 64.5% ± 0.6% | 17.6% |

Average trip length: Agent World 750 m, Random walk 1115 m, Same trips, noisy turns 2718 m. Longer trips give more chances to share turns, so the arms differ in exposure as well as in route choice.

Within the Agent World arm: `go_to` trips (4330) share 5+ turns 68.1% of the time, `stroll` trips (670) 42.8%.

## Markov chain of turns

Two people start walking the same road together. Chance that they then make the same next k turns: what happened, and what a chain predicts in which every turn depends only on the current road.

| k more turns | Random walk, observed | Random walk, Markov chain | Agents, observed | Agents, Markov chain (fitted on agents) | Agents, Markov chain (fitted on random walk) |
|---|---|---|---|---|---|
| 1 | 70.9% | 81.8% | 61.7% | 64.0% | 78.6% |
| 2 | 58.5% | 69.2% | 41.9% | 40.8% | 60.0% |
| 3 | 48.8% | 57.9% | 31.2% | 27.4% | 48.8% |
| 4 | 43.2% | 50.2% | 24.4% | 18.6% | 40.6% |
| 5 | 36.1% | 41.9% | 18.9% | 12.3% | 32.8% |

Pairs that met: random walk 104,972, agents 143,823.

## Do agents turn differently from random walkers?

Pearson chi-square test of the left/right/straight/back counts, agents against random walk, where both arms have at least 30 passes. p-values corrected over all units (Benjamini-Hochberg). The G-test (likelihood ratio) is the same comparison with a statistic that copes better with small counts. 'Noise check' is one random-walk repeat against another: what the chi-square test gives when there is no real difference.

| Unit | Tested | Chi-square: significant at 5% | Same, only units with all expected counts 5+ | G-test: significant at 5% | Median Cramér's V | Median TVD | Pass-weighted TVD | Noise check: significant | Noise check: median TVD |
|---|---|---|---|---|---|---|---|---|---|
| Junction | 1863 | 82.1% | 81.4% of 1485 | 82.7% | 0.224 | 0.170 | 0.175 | 0.0% | 0.020 |
| Road and direction | 4242 | 80.3% | 81.4% of 3156 | 81.3% | 0.254 | 0.183 | 0.171 | 0.0% | 0.009 |

All turns pooled (one 2 × 4 table, 1,131,770 agent turns and 1,374,762 random-walk turns): chi-square = 78,197, 3 degrees of freedom, p < 1e-300, Cramér's V = 0.177. Shares, agents against random walk: left 25.8% / 17.3%, right 26.0% / 17.4%, straight 47.7% / 65.2%, back 0.5% / 0.1%.

Cramér's V runs from 0 (no difference) to 1. TVD (total variation distance) is the share of turns that would have to change for the two arms to agree: 0 = identical, 1 = completely different.

Paired differences, agents minus random walk, per road and direction:

| Turn | Mean difference | Mean absolute difference | Wilcoxon p |
|---|---|---|---|
| Left | +4.3% | 12.8% | 9.57e-71 |
| Right | +4.2% | 12.7% | 2.12e-70 |
| Straight | -8.9% | 16.0% | 1.5e-152 |
| Back | +0.3% | 0.4% | 1.88e-39 |

## Diebold-Mariano: which model predicts the agents' turns better?

Brier score over 1,131,770 agent turns (lower is better): equal chance per exit 0.6871, random-walk shares 0.4553.
DM statistic over 18 hours of the day (Newey-West, lag 2): 6.44, p = 6.14e-06. Positive means random walking predicts the agents better than equal chance.
Across 6062 roads and directions: random walking is the better predictor on 66.3% of them (paired t = 39.71, p = 1.04e-306).

## Road use

Spearman rank correlation of walkers per segment, agents against random walk: 0.727 (4745 segments used by either arm).
Share of all metres walked on the busiest 5% of segments: agents 40.4%, random walk 56.3%.
Segments never walked: agents 111, random walk 883 of 4835.

Regression of log(agent share / random-walk share) on places within 60 m of the segment (4414 segments, R² = 0.036, robust standard errors):

| Places nearby | Coefficient | Std. error | p |
|---|---|---|---|
| (intercept) | +0.754 | 0.064 | 4.72e-32 |
| Food and drink | -0.043 | 0.010 | 2.4e-05 |
| Shops | +0.048 | 0.012 | 6.31e-05 |
| University | +0.271 | 0.026 | 6.82e-26 |
| Named buildings | +0.027 | 0.008 | 0.000306 |
| Transport stops | +0.008 | 0.018 | 0.646 |
| Parks and sights | +0.056 | 0.019 | 0.00303 |
| Schools | +0.154 | 0.038 | 4.96e-05 |
| Everyday services | -0.129 | 0.020 | 2.08e-10 |

A coefficient of +0.10 means each extra place of that kind nearby goes with about 10% more agent walking on the segment than random walking would put there.

Tables: arms_shared_turns.csv, arms_markov.csv, junction_tests.csv, junction_tests_directed.csv, road_usage_compare.csv, road_amenity_regression.csv.