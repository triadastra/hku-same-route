# Following at junctions: census_run, the first 1,000 people, trips finished by 16:22 (the hours the live world covers)

3,223 trips, 93,580 decisions at 2,372 junctions. A stranger is following you for k decisions if the same person, at most 30 m behind you along the road each time, arrives at and leaves k of your junctions in a row by your paths. Chain walkers and random trips: 3 repeats, mean (± standard deviation).

## Chance that a stranger follows you through k junctions

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 1 | 26.7% | 34.1% ± 1.0 | 13.7% ± 0.8 | 20.2% ± 0.2 | 23.5% ± 1.0 | 26.1% ± 0.3 |
| 2 | 17.8% | 26.2% ± 1.5 | 5.3% ± 0.6 | 10.9% ± 0.7 | 14.0% ± 0.7 | 17.4% ± 0.3 |
| 3 | 11.3% | 19.4% ± 1.4 | 1.7% ± 0.4 | 5.8% ± 0.5 | 8.0% ± 0.2 | 10.9% ± 0.3 |
| 4 | 8.2% | 13.3% ± 0.6 | 0.6% ± 0.1 | 3.1% ± 0.6 | 4.3% ± 0.2 | 6.5% ± 0.4 |
| 5 | 5.5% | 8.9% ± 0.4 | 0.2% ± 0.1 | 1.6% ± 0.2 | 2.3% ± 0.1 | 4.1% ± 0.5 |
| 6 | 4.1% | 6.2% ± 0.4 | 0.1% ± 0.0 | 0.8% ± 0.2 | 1.2% ± 0.3 | 2.4% ± 0.5 |
| 8 | 2.3% | 3.3% ± 0.2 | 0.0% ± 0.0 | 0.2% ± 0.0 | 0.4% ± 0.2 | 0.7% ± 0.2 |
| 10 | 1.3% | 2.0% ± 0.2 | 0.0% ± 0.0 | 0.1% ± 0.0 | 0.1% ± 0.0 | 0.3% ± 0.1 |

Among trips that make at least k decisions:

| k | Agent World | Random place to place | Markov: equal chance | Markov: momentum (kappa 2) | Markov: counted | Markov: counted + imitation (rho 0.3) |
|---|---|---|---|---|---|---|
| 3 | 11.9% | 19.5% | 1.8% | 6.1% | 8.5% | 11.4% |
| 5 | 6.1% | 9.1% | 0.2% | 1.7% | 2.5% | 4.5% |
| 10 | 1.8% | 2.2% | 0.0% | 0.1% | 0.2% | 0.4% |

## Two people arriving together: same next k decisions

Pairs who arrive at a junction by the same path, one at most 30 m behind the other along the road. The formula is the Markov chain's prediction for the same pairs (the counted chain uses the table of the hour they arrive in); for the chain walkers it checks the code.

| k | Agent World | Counted chain, formula | Momentum, formula | Equal chance, formula | Equal: walkers / formula | Momentum: walkers / formula | Counted: walkers / formula | Imitation: walkers |
|---|---|---|---|---|---|---|---|---|
| 1 | 74.9% | 68.7% | 66.6% | 44.1% | 46.5% / 45.0% | 67.6% / 68.3% | 69.2% / 67.8% | 75.2% |
| 2 | 60.6% | 47.8% | 45.4% | 19.7% | 22.2% / 20.2% | 45.7% / 46.5% | 48.3% / 46.4% | 56.6% |
| 3 | 51.0% | 33.6% | 30.7% | 8.8% | 10.8% / 9.1% | 30.3% / 31.6% | 34.1% / 31.9% | 42.7% |
| 4 | 45.1% | 24.0% | 20.8% | 4.0% | 4.9% / 4.1% | 19.9% / 21.7% | 24.3% / 22.2% | 32.2% |
| 5 | 41.0% | 17.2% | 14.2% | 1.8% | 2.2% / 1.9% | 13.4% / 14.9% | 17.1% / 15.4% | 23.7% |

Agent pairs counted at k = 1: 4,843.

## Same next path, by how many paths the junction has

| Paths | Agent pairs | Agent World | Equal chance | Momentum | Counted | Imitation | Random place to place |
|---|---|---|---|---|---|---|---|
| 3 | 3,134 | 78.0% | 50.6% | 71.5% | 74.9% | 78.3% | 88.4% |
| 4 | 1,706 | 69.2% | 37.1% | 57.3% | 58.5% | 69.2% | 84.1% |
| 5 | 3 | 33.3% | 16.7% | 66.7% | 35.3% | 75.0% | 100.0% |

## Is the choice at each junction equal chance? (chi-square)

Goodness of fit of the Agent World's counts of each path out, at each junction and path in with at least 30 passes (turning back left out), to equal chance and to momentum. p-values corrected over all of them (Benjamini-Hochberg). Calibration: the same test on the equal-chance walkers' counts, which do follow equal chance, so after the correction it should reject almost none.

| Counts tested against | Junction and path-in pairs | Rejected at 5% | Median effect size w | Calibration: rejected |
|---|---|---|---|---|
| Equal chance | 757 | 88.0% | 0.75 | 0.0% |
| Momentum (kappa 2) | 757 | 62.0% | 0.50 |  |

w = sqrt(chi-square / passes): about 0.1 is a small difference, 0.3 medium, 0.5 large. Passes by the same person on different trips are not independent, so p-values are too small; the effect size does not have that problem.

## Sweeps

| What | Value | P_3 | P_5 | q_3 formula on agent pairs |
|---|---|---|---|---|
| momentum, kappa | 0.5 | 1.4% | 0.2% | 10.4% |
| momentum, kappa | 1 | 2.5% | 0.3% | 15.2% |
| momentum, kappa | 2 | 5.8% | 1.6% | 30.7% |
| momentum, kappa | 4 | 11.8% | 4.8% | 58.4% |
| imitation, rho | 0 | 8.3% | 2.1% |  |
| imitation, rho | 0.1 | 8.7% | 2.7% |  |
| imitation, rho | 0.3 | 10.2% | 3.8% |  |
| imitation, rho | 0.5 | 14.0% | 6.6% |  |
| following distance, Agent World | 15 | 6.1% | 2.4% |  |
| following distance, Markov: counted | 15 | 3.8% | 0.8% |  |
| following distance, Agent World | 30 | 11.3% | 5.5% |  |
| following distance, Markov: counted | 30 | 8.2% | 2.3% |  |
| following distance, Agent World | 60 | 17.8% | 10.0% |  |
| following distance, Markov: counted | 60 | 15.0% | 5.6% |  |

## Who follows whom in the Agent World

Of 364 trips with a stranger following for 3+ junctions, the stranger started within 150 m of where you started on 64.6%, was going to within 150 m of your destination on 50.0%, both on 30.2%.

Tables: following_pk.csv, following_qk.csv, following_by_roads.csv, following_by_hour.csv, following_sweeps.csv, following_chi2.csv, decision_table.csv (shares of each path out per junction and path in, with equal-chance and momentum probabilities, and the share that stop there).