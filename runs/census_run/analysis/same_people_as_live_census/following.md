# Following at junctions: census_run

4,240 trips, 115,774 decisions at 2,372 junctions. A stranger is following you for k decisions if the same person, at most 30 m behind you along the road each time, arrives at and leaves k of your junctions in a row by your paths. Chain walkers and random trips: 3 repeats, mean (± standard deviation).

## Chance that a stranger follows you through k junctions

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 1 | 28.3% | 31.6% ± 0.4 | 14.6% ± 0.6 | 21.3% ± 0.4 | 23.1% ± 0.5 | 26.4% ± 0.3 |
| 2 | 19.7% | 24.6% ± 0.7 | 5.7% ± 0.5 | 12.1% ± 0.6 | 14.4% ± 0.6 | 17.8% ± 0.2 |
| 3 | 13.1% | 18.6% ± 0.5 | 1.8% ± 0.3 | 6.7% ± 0.3 | 8.6% ± 0.9 | 11.3% ± 0.6 |
| 4 | 9.7% | 13.1% ± 0.5 | 0.6% ± 0.0 | 3.7% ± 0.3 | 4.9% ± 0.5 | 7.1% ± 0.5 |
| 5 | 7.2% | 8.8% ± 0.3 | 0.2% ± 0.1 | 1.8% ± 0.1 | 2.8% ± 0.4 | 4.4% ± 0.4 |
| 6 | 5.7% | 6.3% ± 0.1 | 0.0% ± 0.0 | 1.0% ± 0.0 | 1.6% ± 0.3 | 2.7% ± 0.2 |
| 8 | 3.3% | 3.6% ± 0.1 | 0.0% ± 0.0 | 0.3% ± 0.0 | 0.5% ± 0.1 | 1.1% ± 0.0 |
| 10 | 2.0% | 1.9% ± 0.3 | 0.0% ± 0.0 | 0.1% ± 0.0 | 0.1% ± 0.0 | 0.5% ± 0.0 |

Among trips that make at least k decisions:

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 3 | 13.7% | 18.8% | 1.9% | 7.0% | 9.0% | 11.9% |
| 5 | 7.9% | 8.9% | 0.2% | 2.0% | 3.1% | 4.9% |
| 10 | 2.7% | 2.0% | 0.0% | 0.1% | 0.2% | 0.6% |

## Two people arriving together: same next k decisions

Pairs who arrive at a junction by the same path, one at most 30 m behind the other along the road. The formula is the Markov chain's prediction for the same pairs (the counted chain uses the table of the hour they arrive in); for the chain walkers it checks the code.

| k | Agent World | Counted chain, formula | Momentum, formula | Equal chance, formula | Equal: walkers / formula | Momentum: walkers / formula | Counted: walkers / formula | Imitation: walkers |
|---|---|---|---|---|---|---|---|---|
| 1 | 78.7% | 70.5% | 66.8% | 44.3% | 45.7% / 45.4% | 69.4% / 68.1% | 69.6% / 69.4% | 76.3% |
| 2 | 66.0% | 50.2% | 45.5% | 19.8% | 21.1% / 20.5% | 47.9% / 46.4% | 47.9% / 48.6% | 58.0% |
| 3 | 57.2% | 36.2% | 31.0% | 8.9% | 9.9% / 9.4% | 32.8% / 31.6% | 33.5% / 34.4% | 43.9% |
| 4 | 51.6% | 26.3% | 21.1% | 4.0% | 4.5% / 4.3% | 22.3% / 21.7% | 23.6% / 24.6% | 32.7% |
| 5 | 48.0% | 19.2% | 14.5% | 1.8% | 1.9% / 1.9% | 15.2% / 14.9% | 16.9% / 17.8% | 24.6% |

Agent pairs counted at k = 1: 7,819.

## Same next path, by how many paths the junction has

| Paths | Agent pairs | Agent World | Equal chance | Momentum | Counted | Imitation | Random place to place |
|---|---|---|---|---|---|---|---|
| 3 | 5,149 | 81.6% | 49.5% | 73.0% | 73.6% | 79.4% | 90.1% |
| 4 | 2,656 | 73.2% | 35.8% | 59.8% | 62.3% | 70.1% | 84.3% |
| 5 | 14 | 78.6% | 14.3% | 56.2% | 55.6% | 57.1% | 80.0% |

## Is the choice at each junction equal chance? (chi-square)

Goodness of fit of the Agent World's counts of each path out, at each junction and path in with at least 30 passes (turning back left out), to equal chance and to momentum. p-values corrected over all of them (Benjamini-Hochberg). Calibration: the same test on the equal-chance walkers' counts, which do follow equal chance, so after the correction it should reject almost none.

| Counts tested against | Junction and path-in pairs | Rejected at 5% | Median effect size w | Calibration: rejected |
|---|---|---|---|---|
| Equal chance | 1,086 | 87.9% | 0.77 | 0.0% |
| Momentum (kappa 2) | 1,086 | 66.7% | 0.52 |  |

w = sqrt(chi-square / passes): about 0.1 is a small difference, 0.3 medium, 0.5 large. Passes by the same person on different trips are not independent, so p-values are too small; the effect size does not have that problem.

## Sweeps

| What | Value | P_3 | P_5 | q_3 formula on agent pairs |
|---|---|---|---|---|
| momentum, kappa | 0.5 | 1.7% | 0.2% | 10.6% |
| momentum, kappa | 1 | 3.0% | 0.5% | 15.4% |
| momentum, kappa | 2 | 6.6% | 1.9% | 31.0% |
| momentum, kappa | 4 | 14.0% | 6.3% | 58.4% |
| imitation, rho | 0 | 8.7% | 3.1% |  |
| imitation, rho | 0.1 | 9.3% | 3.1% |  |
| imitation, rho | 0.3 | 12.5% | 5.1% |  |
| imitation, rho | 0.5 | 14.7% | 6.8% |  |
| following distance, Agent World | 15 | 8.0% | 3.7% |  |
| following distance, Markov: counted | 15 | 4.3% | 1.3% |  |
| following distance, Agent World | 30 | 13.1% | 7.2% |  |
| following distance, Markov: counted | 30 | 8.6% | 2.9% |  |
| following distance, Agent World | 60 | 20.1% | 12.1% |  |
| following distance, Markov: counted | 60 | 14.7% | 5.6% |  |

## Who follows whom in the Agent World

Of 557 trips with a stranger following for 3+ junctions, the stranger started within 150 m of where you started on 74.3%, was going to within 150 m of your destination on 45.4%, both on 30.7%, and was in your group on 60.7%.

Tables: following_pk.csv, following_qk.csv, following_by_roads.csv, following_by_hour.csv, following_sweeps.csv, following_chi2.csv, decision_table.csv (shares of each path out per junction and path in, with equal-chance and momentum probabilities, and the share that stop there).