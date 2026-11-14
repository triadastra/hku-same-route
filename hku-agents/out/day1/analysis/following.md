# Following at real intersections: day1

57,223 trips, 475,883 decisions at 573 decision points. A stranger is following you for k decisions if the same person, at most 30 m behind you each time (about 22 s), arrives at and leaves k of your intersections in a row by your roads. Chain walkers and random trips: 3 repeats, mean (± standard deviation).

## Chance that a stranger follows you through k intersections

| k | Agent World | Same people, no LLM | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|---|
| 1 | 77.9% | 83.4% | 83.7% ± 0.0 | 69.2% ± 0.2 | 74.6% ± 0.1 | 76.5% ± 0.0 | 78.6% ± 0.1 |
| 2 | 60.4% | 67.8% | 68.1% ± 0.1 | 42.4% ± 0.0 | 54.3% ± 0.1 | 58.5% ± 0.2 | 62.2% ± 0.1 |
| 3 | 43.7% | 47.4% | 50.7% ± 0.3 | 18.0% ± 0.2 | 33.5% ± 0.1 | 38.8% ± 0.1 | 42.7% ± 0.1 |
| 4 | 31.8% | 32.7% | 36.3% ± 0.2 | 5.7% ± 0.1 | 18.7% ± 0.0 | 23.7% ± 0.1 | 27.0% ± 0.0 |
| 5 | 21.7% | 21.7% | 26.4% ± 0.2 | 1.6% ± 0.1 | 9.1% ± 0.1 | 13.4% ± 0.1 | 15.8% ± 0.2 |
| 6 | 14.7% | 13.9% | 19.0% ± 0.1 | 0.4% ± 0.0 | 4.3% ± 0.1 | 7.5% ± 0.1 | 9.1% ± 0.1 |

Among trips that make at least k decisions:

| k | Agent World | Same people, no LLM | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|---|
| 3 | 55.7% | 63.8% | 53.0% | 22.9% | 42.7% | 49.5% | 54.5% |
| 5 | 34.2% | 40.0% | 29.6% | 2.5% | 14.3% | 21.2% | 24.9% |

## Two people arriving together: same next k decisions

Pairs who arrive at an intersection by the same road, one at most 30 m behind the other. The formula is the Markov chain's prediction for the same pairs (the counted chain uses the table of the hour they arrive in); for the chain walkers it checks the code.

| k | Agent World | Counted chain, formula | Momentum, formula | Equal chance, formula | Equal: walkers / formula | Momentum: walkers / formula | Counted: walkers / formula | Imitation: walkers |
|---|---|---|---|---|---|---|---|---|
| 1 | 74.4% | 68.6% | 58.5% | 38.5% | 39.4% / 39.4% | 62.3% / 62.3% | 67.2% / 67.4% | 69.1% |
| 2 | 59.0% | 50.2% | 36.0% | 15.6% | 15.8% / 15.8% | 39.4% / 39.4% | 48.6% / 48.9% | 50.8% |
| 3 | 49.3% | 37.5% | 22.7% | 6.4% | 6.5% / 6.5% | 24.9% / 24.9% | 36.1% / 36.4% | 38.3% |
| 4 | 42.6% | 28.3% | 14.5% | 2.6% | 2.6% / 2.6% | 15.7% / 15.6% | 27.2% / 27.6% | 29.1% |
| 5 | 38.0% | 21.4% | 8.8% | 1.1% | 1.1% / 1.1% | 9.9% / 9.8% | 20.3% / 20.8% | 22.0% |

Agent pairs counted at k = 1: 1,913,009.

## Same next road, by how many roads the intersection has

| Roads | Agent pairs | Agent World | Equal chance | Momentum | Counted | Imitation | Random place to place |
|---|---|---|---|---|---|---|---|
| 3 | 865,199 | 81.7% | 50.0% | 72.5% | 75.9% | 77.5% | 90.8% |
| 4 | 616,079 | 77.2% | 33.2% | 55.7% | 69.9% | 71.4% | 76.3% |
| 5 | 251,673 | 62.5% | 25.3% | 43.8% | 48.6% | 51.3% | 70.7% |
| 6+ | 180,058 | 46.7% | 19.9% | 40.5% | 41.4% | 44.0% | 61.1% |

## Is the choice at each intersection equal chance? (chi-square)

Goodness of fit of the Agent World's counts of each road out, at each intersection and road in with at least 30 passes (turning back left out), to equal chance and to momentum. p-values corrected over all of them (Benjamini-Hochberg). Calibration: the same test on the equal-chance walkers' counts, which do follow equal chance, so after the correction it should reject almost none.

| Counts tested against | Intersection and road-in pairs | Rejected at 5% | Median effect size w | Calibration: rejected |
|---|---|---|---|---|
| Equal chance | 1,168 | 83.9% | 0.69 | 0.0% |
| Momentum (kappa 2) | 1,168 | 87.4% | 0.79 |  |

w = sqrt(chi-square / passes): about 0.1 is a small difference, 0.3 medium, 0.5 large. Passes by the same person on different trips are not independent, so p-values are too small; the effect size does not have that problem.

## Sweeps

| What | Value | P_3 | P_5 | q_3 formula on agent pairs |
|---|---|---|---|---|
| momentum, kappa | 0.5 | 19.6% | 2.0% | 7.7% |
| momentum, kappa | 1 | 24.1% | 3.5% | 11.3% |
| momentum, kappa | 2 | 33.4% | 9.0% | 22.7% |
| momentum, kappa | 4 | 45.4% | 19.1% | 43.4% |
| imitation, rho | 0 | 39.1% | 13.5% |  |
| imitation, rho | 0.1 | 39.9% | 14.0% |  |
| imitation, rho | 0.3 | 42.8% | 15.7% |  |
| imitation, rho | 0.5 | 46.0% | 18.2% |  |
| following distance, Agent World | 15 | 30.4% | 11.6% |  |
| following distance, Markov: counted | 15 | 24.8% | 6.4% |  |
| following distance, Agent World | 30 | 43.7% | 21.7% |  |
| following distance, Markov: counted | 30 | 38.8% | 13.4% |  |
| following distance, Agent World | 60 | 53.0% | 31.6% |  |
| following distance, Markov: counted | 60 | 49.5% | 22.3% |  |

## Who follows whom in the Agent World

Of 24,983 trips with a stranger following for 3+ intersections, the stranger started within 150 m of where you started on 86.8%, was going to within 150 m of your destination on 67.1%, both on 57.5%, and was in your group on 48.0%.

Tables: following_pk.csv, following_qk.csv, following_by_roads.csv, following_by_hour.csv, following_sweeps.csv, following_chi2.csv, decision_table.csv (shares of each road out per intersection and road in, with equal-chance and momentum probabilities, and the share that stop there).