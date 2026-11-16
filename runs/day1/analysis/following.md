# Following at junctions: day1

57,223 trips, 1,283,334 decisions at 2,372 junctions. A stranger is following you for k decisions if the same person, at most 30 m behind you along the road each time, arrives at and leaves k of your junctions in a row by your paths. Chain walkers and random trips: 3 repeats, mean (± standard deviation).

## Chance that a stranger follows you through k junctions

| k | Agent World | Same people, no LLM | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|---|
| 1 | 84.9% | 87.8% | 84.1% ± 0.0 | 73.6% ± 0.2 | 78.0% ± 0.0 | 81.6% ± 0.1 | 83.1% ± 0.0 |
| 2 | 77.0% | 81.6% | 77.9% ± 0.2 | 54.3% ± 0.1 | 65.7% ± 0.1 | 71.8% ± 0.1 | 74.4% ± 0.1 |
| 3 | 68.1% | 74.1% | 70.9% ± 0.2 | 33.9% ± 0.1 | 52.8% ± 0.1 | 61.1% ± 0.1 | 64.8% ± 0.1 |
| 4 | 59.9% | 66.0% | 63.7% ± 0.2 | 17.4% ± 0.1 | 40.2% ± 0.1 | 50.9% ± 0.1 | 55.3% ± 0.0 |
| 5 | 52.6% | 59.9% | 56.2% ± 0.2 | 7.6% ± 0.1 | 28.8% ± 0.0 | 41.3% ± 0.0 | 45.8% ± 0.2 |
| 6 | 46.1% | 50.6% | 48.7% ± 0.3 | 3.0% ± 0.0 | 19.3% ± 0.0 | 32.3% ± 0.2 | 36.6% ± 0.1 |
| 8 | 35.0% | 37.9% | 35.7% ± 0.4 | 0.4% ± 0.0 | 7.7% ± 0.0 | 19.3% ± 0.1 | 22.7% ± 0.1 |
| 10 | 25.9% | 25.6% | 25.8% ± 0.4 | 0.1% ± 0.0 | 2.7% ± 0.1 | 11.6% ± 0.2 | 14.0% ± 0.1 |

Among trips that make at least k decisions:

| k | Agent World | Same people, no LLM | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|---|
| 3 | 73.2% | 80.9% | 71.4% | 36.5% | 56.8% | 65.7% | 69.7% |
| 5 | 60.2% | 71.0% | 57.1% | 8.7% | 33.0% | 47.3% | 52.4% |
| 10 | 38.5% | 45.3% | 27.5% | 0.1% | 4.0% | 17.3% | 20.8% |

## Two people arriving together: same next k decisions

Pairs who arrive at a junction by the same path, one at most 30 m behind the other along the road. The formula is the Markov chain's prediction for the same pairs (the counted chain uses the table of the hour they arrive in); for the chain walkers it checks the code.

| k | Agent World | Counted chain, formula | Momentum, formula | Equal chance, formula | Equal: walkers / formula | Momentum: walkers / formula | Counted: walkers / formula | Imitation: walkers |
|---|---|---|---|---|---|---|---|---|
| 1 | 83.3% | 79.3% | 67.6% | 45.5% | 46.6% / 46.6% | 68.9% / 68.9% | 79.1% / 79.1% | 80.3% |
| 2 | 72.8% | 64.6% | 46.7% | 20.9% | 21.8% / 21.7% | 47.5% / 47.5% | 64.0% / 64.0% | 65.7% |
| 3 | 65.5% | 53.8% | 31.8% | 9.5% | 10.2% / 10.2% | 32.7% / 32.8% | 52.6% / 52.5% | 54.4% |
| 4 | 59.5% | 45.3% | 21.6% | 4.4% | 4.8% / 4.8% | 22.6% / 22.7% | 43.4% / 43.3% | 45.2% |
| 5 | 54.9% | 38.3% | 15.0% | 2.0% | 2.3% / 2.2% | 15.8% / 15.8% | 36.7% / 36.6% | 38.4% |

Agent pairs counted at k = 1: 4,595,251.

## Same next path, by how many paths the junction has

| Paths | Agent pairs | Agent World | Equal chance | Momentum | Counted | Imitation | Random place to place |
|---|---|---|---|---|---|---|---|
| 3 | 3,345,558 | 85.6% | 50.0% | 70.5% | 81.7% | 82.7% | 90.0% |
| 4 | 1,240,481 | 76.9% | 33.3% | 61.6% | 71.1% | 72.8% | 84.7% |
| 5 | 9,212 | 85.2% | 24.4% | 49.9% | 77.4% | 82.2% | 84.0% |

## Is the choice at each junction equal chance? (chi-square)

Goodness of fit of the Agent World's counts of each path out, at each junction and path in with at least 30 passes (turning back left out), to equal chance and to momentum. p-values corrected over all of them (Benjamini-Hochberg). Calibration: the same test on the equal-chance walkers' counts, which do follow equal chance, so after the correction it should reject almost none.

| Counts tested against | Junction and path-in pairs | Rejected at 5% | Median effect size w | Calibration: rejected |
|---|---|---|---|---|
| Equal chance | 4,849 | 71.3% | 0.51 | 0.0% |
| Momentum (kappa 2) | 4,849 | 82.8% | 0.68 |  |

w = sqrt(chi-square / passes): about 0.1 is a small difference, 0.3 medium, 0.5 large. Passes by the same person on different trips are not independent, so p-values are too small; the effect size does not have that problem.

## Sweeps

| What | Value | P_3 | P_5 | q_3 formula on agent pairs |
|---|---|---|---|---|
| momentum, kappa | 0.5 | 36.6% | 9.7% | 11.4% |
| momentum, kappa | 1 | 41.5% | 14.9% | 16.4% |
| momentum, kappa | 2 | 52.4% | 28.9% | 31.8% |
| momentum, kappa | 4 | 63.7% | 45.9% | 57.3% |
| imitation, rho | 0 | 61.0% | 41.0% |  |
| imitation, rho | 0.1 | 62.2% | 42.7% |  |
| imitation, rho | 0.3 | 64.6% | 45.7% |  |
| imitation, rho | 0.5 | 67.8% | 50.0% |  |
| following distance, Agent World | 15 | 58.2% | 40.6% |  |
| following distance, Markov: counted | 15 | 49.9% | 29.0% |  |
| following distance, Agent World | 30 | 68.1% | 52.6% |  |
| following distance, Markov: counted | 30 | 61.1% | 41.3% |  |
| following distance, Agent World | 60 | 74.4% | 60.6% |  |
| following distance, Markov: counted | 60 | 69.5% | 51.7% |  |

## Who follows whom in the Agent World

Of 38,945 trips with a stranger following for 3+ junctions, the stranger started within 150 m of where you started on 80.5%, was going to within 150 m of your destination on 66.3%, both on 53.2%, and was in your group on 47.4%.

Tables: following_pk.csv, following_qk.csv, following_by_roads.csv, following_by_hour.csv, following_sweeps.csv, following_chi2.csv, decision_table.csv (shares of each path out per junction and path in, with equal-chance and momentum probabilities, and the share that stop there).