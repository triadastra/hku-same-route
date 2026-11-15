# Following at junctions: census_run

42,161 trips, 1,131,770 decisions at 2,372 junctions. A stranger is following you for k decisions if the same person, at most 30 m behind you along the road each time, arrives at and leaves k of your junctions in a row by your paths. Chain walkers and random trips: 3 repeats, mean (± standard deviation).

## Chance that a stranger follows you through k junctions

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 1 | 73.8% | 80.9% ± 0.2 | 58.8% ± 0.0 | 67.7% ± 0.3 | 70.3% ± 0.1 | 73.2% ± 0.1 |
| 2 | 61.5% | 73.0% ± 0.2 | 33.2% ± 0.1 | 50.9% ± 0.1 | 55.0% ± 0.2 | 60.4% ± 0.2 |
| 3 | 49.1% | 63.5% ± 0.1 | 14.6% ± 0.2 | 35.0% ± 0.3 | 40.4% ± 0.2 | 47.1% ± 0.1 |
| 4 | 39.0% | 53.1% ± 0.2 | 5.6% ± 0.1 | 22.0% ± 0.2 | 28.3% ± 0.1 | 35.0% ± 0.2 |
| 5 | 30.9% | 43.2% ± 0.3 | 2.0% ± 0.0 | 13.0% ± 0.3 | 19.3% ± 0.1 | 25.4% ± 0.3 |
| 6 | 24.8% | 34.5% ± 0.2 | 0.7% ± 0.1 | 7.4% ± 0.2 | 13.0% ± 0.2 | 17.8% ± 0.3 |
| 8 | 16.4% | 22.2% ± 0.2 | 0.1% ± 0.0 | 2.3% ± 0.1 | 6.1% ± 0.1 | 8.7% ± 0.2 |
| 10 | 11.1% | 14.4% ± 0.1 | 0.0% ± 0.0 | 0.7% ± 0.0 | 3.0% ± 0.1 | 4.3% ± 0.2 |

Among trips that make at least k decisions:

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 3 | 51.7% | 63.9% | 15.4% | 36.9% | 42.6% | 49.6% |
| 5 | 34.3% | 43.9% | 2.2% | 14.4% | 21.4% | 28.2% |
| 10 | 15.6% | 15.3% | 0.0% | 1.0% | 4.3% | 6.1% |

## Two people arriving together: same next k decisions

Pairs who arrive at a junction by the same path, one at most 30 m behind the other along the road. The formula is the Markov chain's prediction for the same pairs (the counted chain uses the table of the hour they arrive in); for the chain walkers it checks the code.

| k | Agent World | Counted chain, formula | Momentum, formula | Equal chance, formula | Equal: walkers / formula | Momentum: walkers / formula | Counted: walkers / formula | Imitation: walkers |
|---|---|---|---|---|---|---|---|---|
| 1 | 78.7% | 73.8% | 66.2% | 43.9% | 45.0% / 45.0% | 68.0% / 67.9% | 72.7% / 72.6% | 77.1% |
| 2 | 66.5% | 56.0% | 45.1% | 19.6% | 20.3% / 20.3% | 46.5% / 46.1% | 54.5% / 54.3% | 60.1% |
| 3 | 58.6% | 43.6% | 30.6% | 8.8% | 9.3% / 9.2% | 31.7% / 31.3% | 41.6% / 41.4% | 47.3% |
| 4 | 52.9% | 34.6% | 20.8% | 4.0% | 4.2% / 4.2% | 21.6% / 21.3% | 32.3% / 32.0% | 37.5% |
| 5 | 48.8% | 27.9% | 14.2% | 1.8% | 1.9% / 1.9% | 14.9% / 14.6% | 25.5% / 25.2% | 30.1% |

Agent pairs counted at k = 1: 739,607.

## Same next path, by how many paths the junction has

| Paths | Agent pairs | Agent World | Equal chance | Momentum | Counted | Imitation | Random place to place |
|---|---|---|---|---|---|---|---|
| 3 | 471,547 | 82.7% | 50.0% | 70.4% | 77.3% | 81.0% | 89.3% |
| 4 | 266,187 | 71.7% | 33.3% | 62.4% | 63.9% | 69.5% | 84.1% |
| 5 | 1,873 | 63.0% | 22.7% | 44.7% | 47.6% | 51.6% | 83.1% |

## Is the choice at each junction equal chance? (chi-square)

Goodness of fit of the Agent World's counts of each path out, at each junction and path in with at least 30 passes (turning back left out), to equal chance and to momentum. p-values corrected over all of them (Benjamini-Hochberg). Calibration: the same test on the equal-chance walkers' counts, which do follow equal chance, so after the correction it should reject almost none.

| Counts tested against | Junction and path-in pairs | Rejected at 5% | Median effect size w | Calibration: rejected |
|---|---|---|---|---|
| Equal chance | 6,059 | 75.0% | 0.49 | 0.0% |
| Momentum (kappa 2) | 6,059 | 83.2% | 0.66 |  |

w = sqrt(chi-square / passes): about 0.1 is a small difference, 0.3 medium, 0.5 large. Passes by the same person on different trips are not independent, so p-values are too small; the effect size does not have that problem.

## Sweeps

| What | Value | P_3 | P_5 | q_3 formula on agent pairs |
|---|---|---|---|---|
| momentum, kappa | 0.5 | 16.4% | 2.6% | 10.4% |
| momentum, kappa | 1 | 21.8% | 4.8% | 15.1% |
| momentum, kappa | 2 | 34.8% | 13.0% | 30.6% |
| momentum, kappa | 4 | 51.0% | 29.5% | 58.9% |
| imitation, rho | 0 | 40.3% | 19.3% |  |
| imitation, rho | 0.1 | 42.4% | 21.1% |  |
| imitation, rho | 0.3 | 47.0% | 25.3% |  |
| imitation, rho | 0.5 | 52.0% | 31.1% |  |
| following distance, Agent World | 15 | 35.4% | 18.6% |  |
| following distance, Markov: counted | 15 | 26.6% | 10.3% |  |
| following distance, Agent World | 30 | 49.1% | 30.9% |  |
| following distance, Markov: counted | 30 | 40.4% | 19.4% |  |
| following distance, Agent World | 60 | 60.4% | 42.4% |  |
| following distance, Markov: counted | 60 | 53.5% | 30.8% |  |

## Who follows whom in the Agent World

Of 20,688 trips with a stranger following for 3+ junctions, the stranger started within 150 m of where you started on 70.0%, was going to within 150 m of your destination on 51.7%, both on 36.4%, and was in your group on 66.7%.

Tables: following_pk.csv, following_qk.csv, following_by_roads.csv, following_by_hour.csv, following_sweeps.csv, following_chi2.csv, decision_table.csv (shares of each path out per junction and path in, with equal-chance and momentum probabilities, and the share that stop there).