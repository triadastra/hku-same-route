# Following at junctions: live_census

2,896 trips, 85,536 decisions at 2,372 junctions. A stranger is following you for k decisions if the same person, at most 30 m behind you along the road each time, arrives at and leaves k of your junctions in a row by your paths. Chain walkers and random trips: 3 repeats, mean (± standard deviation).

## Chance that a stranger follows you through k junctions

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 1 | 26.0% | 33.5% ± 1.7 | 13.8% ± 0.5 | 20.2% ± 0.2 | 26.0% ± 1.3 | 29.9% ± 0.6 |
| 2 | 14.8% | 26.6% ± 1.0 | 5.3% ± 0.3 | 11.8% ± 0.2 | 14.5% ± 0.4 | 19.2% ± 0.0 |
| 3 | 9.4% | 20.1% ± 1.1 | 1.7% ± 0.2 | 6.7% ± 0.6 | 7.8% ± 0.3 | 12.3% ± 0.2 |
| 4 | 6.0% | 14.6% ± 0.5 | 0.7% ± 0.1 | 3.2% ± 0.3 | 4.1% ± 0.3 | 8.0% ± 0.1 |
| 5 | 3.9% | 10.3% ± 0.5 | 0.2% ± 0.1 | 1.8% ± 0.2 | 2.2% ± 0.3 | 5.0% ± 0.3 |
| 6 | 2.2% | 7.7% ± 0.2 | 0.0% ± 0.1 | 0.9% ± 0.1 | 1.3% ± 0.2 | 3.0% ± 0.2 |
| 8 | 0.8% | 4.1% ± 0.2 | 0.0% ± 0.0 | 0.3% ± 0.1 | 0.4% ± 0.1 | 1.2% ± 0.2 |
| 10 | 0.4% | 2.4% ± 0.4 | 0.0% ± 0.0 | 0.1% ± 0.1 | 0.1% ± 0.1 | 0.5% ± 0.2 |

Among trips that make at least k decisions:

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 3 | 10.1% | 20.2% | 1.9% | 7.2% | 8.4% | 13.2% |
| 5 | 4.4% | 10.5% | 0.2% | 2.0% | 2.5% | 5.7% |
| 10 | 0.5% | 2.5% | 0.0% | 0.1% | 0.2% | 0.6% |

## Two people arriving together: same next k decisions

Pairs who arrive at a junction by the same path, one at most 30 m behind the other along the road. The formula is the Markov chain's prediction for the same pairs (the counted chain uses the table of the hour they arrive in); for the chain walkers it checks the code.

| k | Agent World | Counted chain, formula | Momentum, formula | Equal chance, formula | Equal: walkers / formula | Momentum: walkers / formula | Counted: walkers / formula | Imitation: walkers |
|---|---|---|---|---|---|---|---|---|
| 1 | 65.7% | 63.0% | 67.1% | 46.0% | 45.6% / 45.1% | 67.4% / 68.8% | 60.6% / 61.2% | 72.2% |
| 2 | 46.7% | 41.0% | 46.4% | 21.2% | 20.4% / 20.4% | 46.4% / 47.7% | 37.1% / 38.3% | 52.4% |
| 3 | 34.8% | 26.9% | 32.1% | 9.6% | 9.4% / 9.3% | 30.9% / 32.7% | 23.1% / 24.2% | 37.8% |
| 4 | 26.0% | 17.6% | 22.1% | 4.4% | 4.7% / 4.2% | 20.3% / 22.5% | 14.8% / 15.5% | 27.3% |
| 5 | 20.1% | 11.5% | 15.3% | 2.0% | 1.4% / 1.9% | 13.8% / 15.9% | 9.4% / 10.0% | 19.7% |

Agent pairs counted at k = 1: 4,130.

## Same next path, by how many paths the junction has

| Paths | Agent pairs | Agent World | Equal chance | Momentum | Counted | Imitation | Random place to place |
|---|---|---|---|---|---|---|---|
| 3 | 3,140 | 67.8% | 50.0% | 69.7% | 62.8% | 74.0% | 88.7% |
| 4 | 981 | 59.0% | 35.2% | 60.3% | 53.8% | 66.7% | 83.9% |
| 5 | 9 | 66.7% | 12.5% | 40.0% | 10.0% | 83.3% | 66.7% |

## Is the choice at each junction equal chance? (chi-square)

Goodness of fit of the Agent World's counts of each path out, at each junction and path in with at least 30 passes (turning back left out), to equal chance and to momentum. p-values corrected over all of them (Benjamini-Hochberg). Calibration: the same test on the equal-chance walkers' counts, which do follow equal chance, so after the correction it should reject almost none.

| Counts tested against | Junction and path-in pairs | Rejected at 5% | Median effect size w | Calibration: rejected |
|---|---|---|---|---|
| Equal chance | 649 | 81.7% | 0.64 | 0.5% |
| Momentum (kappa 2) | 649 | 71.0% | 0.64 |  |

w = sqrt(chi-square / passes): about 0.1 is a small difference, 0.3 medium, 0.5 large. Passes by the same person on different trips are not independent, so p-values are too small; the effect size does not have that problem.

## Sweeps

| What | Value | P_3 | P_5 | q_3 formula on agent pairs |
|---|---|---|---|---|
| momentum, kappa | 0.5 | 2.2% | 0.2% | 11.5% |
| momentum, kappa | 1 | 3.1% | 0.5% | 16.7% |
| momentum, kappa | 2 | 6.0% | 1.9% | 32.1% |
| momentum, kappa | 4 | 12.5% | 5.8% | 57.1% |
| imitation, rho | 0 | 8.4% | 2.6% |  |
| imitation, rho | 0.1 | 8.5% | 2.5% |  |
| imitation, rho | 0.3 | 12.5% | 4.2% |  |
| imitation, rho | 0.5 | 16.1% | 7.3% |  |
| following distance, Agent World | 15 | 5.2% | 1.9% |  |
| following distance, Markov: counted | 15 | 3.6% | 0.8% |  |
| following distance, Agent World | 30 | 9.4% | 3.9% |  |
| following distance, Markov: counted | 30 | 7.9% | 2.0% |  |
| following distance, Agent World | 60 | 15.2% | 7.0% |  |
| following distance, Markov: counted | 60 | 14.1% | 4.5% |  |

## Who follows whom in the Agent World

Of 273 trips with a stranger following for 3+ junctions, the stranger started within 150 m of where you started on 59.3%, was going to within 150 m of your destination on 60.8%, both on 35.2%.

Tables: following_pk.csv, following_qk.csv, following_by_roads.csv, following_by_hour.csv, following_sweeps.csv, following_chi2.csv, decision_table.csv (shares of each path out per junction and path in, with equal-chance and momentum probabilities, and the share that stop there).