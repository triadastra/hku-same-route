# Following at junctions: live_census

3,169 trips, 95,953 decisions at 2,372 junctions. A stranger is following you for k decisions if the same person, at most 30 m behind you along the road each time, arrives at and leaves k of your junctions in a row by your paths. Chain walkers and random trips: 3 repeats, mean (± standard deviation).

## Chance that a stranger follows you through k junctions

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 1 | 26.4% | 32.5% ± 1.5 | 14.2% ± 0.5 | 20.2% ± 0.1 | 25.9% ± 0.4 | 29.5% ± 1.0 |
| 2 | 15.3% | 25.9% ± 1.3 | 5.6% ± 0.2 | 11.9% ± 0.5 | 14.9% ± 0.7 | 19.1% ± 0.1 |
| 3 | 9.9% | 20.0% ± 1.2 | 1.8% ± 0.2 | 6.7% ± 0.7 | 7.7% ± 0.8 | 11.7% ± 0.2 |
| 4 | 6.3% | 14.2% ± 1.1 | 0.7% ± 0.2 | 3.4% ± 0.3 | 4.3% ± 0.6 | 7.3% ± 0.4 |
| 5 | 4.2% | 10.2% ± 1.2 | 0.2% ± 0.2 | 1.9% ± 0.2 | 2.2% ± 0.5 | 4.3% ± 0.2 |
| 6 | 2.4% | 7.3% ± 0.8 | 0.0% ± 0.1 | 0.9% ± 0.1 | 1.2% ± 0.2 | 2.6% ± 0.1 |
| 8 | 0.9% | 4.2% ± 0.5 | 0.0% ± 0.0 | 0.3% ± 0.1 | 0.3% ± 0.0 | 0.9% ± 0.0 |
| 10 | 0.4% | 2.5% ± 0.4 | 0.0% ± 0.0 | 0.1% ± 0.0 | 0.1% ± 0.0 | 0.3% ± 0.1 |

Among trips that make at least k decisions:

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 3 | 10.6% | 20.2% | 2.0% | 7.2% | 8.2% | 12.5% |
| 5 | 4.7% | 10.4% | 0.2% | 2.1% | 2.5% | 4.8% |
| 10 | 0.6% | 2.7% | 0.0% | 0.1% | 0.2% | 0.4% |

## Two people arriving together: same next k decisions

Pairs who arrive at a junction by the same path, one at most 30 m behind the other along the road. The formula is the Markov chain's prediction for the same pairs (the counted chain uses the table of the hour they arrive in); for the chain walkers it checks the code.

| k | Agent World | Counted chain, formula | Momentum, formula | Equal chance, formula | Equal: walkers / formula | Momentum: walkers / formula | Counted: walkers / formula | Imitation: walkers |
|---|---|---|---|---|---|---|---|---|
| 1 | 66.1% | 62.8% | 67.2% | 45.9% | 45.5% / 45.3% | 67.3% / 68.8% | 61.5% / 61.5% | 69.5% |
| 2 | 47.2% | 40.6% | 46.4% | 21.0% | 20.4% / 20.5% | 46.5% / 47.6% | 39.2% / 38.4% | 48.3% |
| 3 | 35.3% | 26.5% | 32.1% | 9.6% | 9.1% / 9.3% | 31.3% / 32.7% | 25.4% / 24.2% | 32.6% |
| 4 | 26.5% | 17.2% | 22.1% | 4.4% | 4.4% / 4.2% | 20.6% / 22.5% | 16.5% / 15.4% | 22.2% |
| 5 | 20.6% | 11.2% | 15.3% | 2.0% | 1.3% / 1.9% | 14.0% / 15.9% | 10.5% / 9.9% | 15.5% |

Agent pairs counted at k = 1: 4,639.

## Same next path, by how many paths the junction has

| Paths | Agent pairs | Agent World | Equal chance | Momentum | Counted | Imitation | Random place to place |
|---|---|---|---|---|---|---|---|
| 3 | 3,492 | 68.2% | 49.7% | 69.7% | 62.9% | 71.1% | 90.6% |
| 4 | 1,137 | 59.5% | 35.1% | 59.9% | 57.4% | 64.8% | 84.3% |
| 5 | 10 | 70.0% | 11.1% | 57.1% | 33.3% | 44.4% | 91.7% |

## Is the choice at each junction equal chance? (chi-square)

Goodness of fit of the Agent World's counts of each path out, at each junction and path in with at least 30 passes (turning back left out), to equal chance and to momentum. p-values corrected over all of them (Benjamini-Hochberg). Calibration: the same test on the equal-chance walkers' counts, which do follow equal chance, so after the correction it should reject almost none.

| Counts tested against | Junction and path-in pairs | Rejected at 5% | Median effect size w | Calibration: rejected |
|---|---|---|---|---|
| Equal chance | 772 | 81.0% | 0.66 | 0.0% |
| Momentum (kappa 2) | 772 | 71.2% | 0.64 |  |

w = sqrt(chi-square / passes): about 0.1 is a small difference, 0.3 medium, 0.5 large. Passes by the same person on different trips are not independent, so p-values are too small; the effect size does not have that problem.

## Sweeps

| What | Value | P_3 | P_5 | q_3 formula on agent pairs |
|---|---|---|---|---|
| momentum, kappa | 0.5 | 2.3% | 0.3% | 11.4% |
| momentum, kappa | 1 | 3.3% | 0.6% | 16.5% |
| momentum, kappa | 2 | 6.2% | 2.1% | 32.1% |
| momentum, kappa | 4 | 13.3% | 6.6% | 57.7% |
| imitation, rho | 0 | 7.6% | 2.1% |  |
| imitation, rho | 0.1 | 8.0% | 2.6% |  |
| imitation, rho | 0.3 | 12.7% | 4.4% |  |
| imitation, rho | 0.5 | 14.6% | 6.9% |  |
| following distance, Agent World | 15 | 5.7% | 2.1% |  |
| following distance, Markov: counted | 15 | 4.2% | 0.9% |  |
| following distance, Agent World | 30 | 9.9% | 4.2% |  |
| following distance, Markov: counted | 30 | 8.2% | 2.6% |  |
| following distance, Agent World | 60 | 15.7% | 7.3% |  |
| following distance, Markov: counted | 60 | 14.5% | 5.1% |  |

## Who follows whom in the Agent World

Of 313 trips with a stranger following for 3+ junctions, the stranger started within 150 m of where you started on 62.0%, was going to within 150 m of your destination on 55.0%, both on 32.3%.

Tables: following_pk.csv, following_qk.csv, following_by_roads.csv, following_by_hour.csv, following_sweeps.csv, following_chi2.csv, decision_table.csv (shares of each path out per junction and path in, with equal-chance and momentum probabilities, and the share that stop there).