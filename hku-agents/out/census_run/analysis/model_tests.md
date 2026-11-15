# The three Markov chains against the Agent World: census_run

42,161 Agent World trips. Each chain has one walker per trip, 3 repeats, pooled. Equal chance is left out here; it is in following.md.

## 1. Do the chain's walkers choose paths in the same proportions as the Agent World's people?

One test per junction and path in with at least 30 passes in both: a 2 × (paths out) table of counts, Agent World against the chain's walkers, turning back left out. Pearson chi-square and the G-test (likelihood ratio). p-values corrected over all tests (Benjamini-Hochberg). 'Noise check' is one repeat of the counted chain against another: what the tests give when there is no real difference. 'Half the people against the other half' is the Agent World's people with odd numbers against those with even numbers.

| Chain | Tested | Chi-square: significant at 5% | Same, only tests with all expected counts 5+ | G-test: significant at 5% | Median Cramér's V | Median TVD | Pass-weighted TVD |
|---|---|---|---|---|---|---|---|
| Markov: momentum (kappa 2) | 5,992 | 79.8% | 80.0% of 5,479 | 79.9% | 0.241 | 0.246 | 0.265 |
| Markov: counted | 5,999 | 0.0% | 0.0% of 5,595 | 0.0% | 0.022 | 0.021 | 0.020 |
| Markov: counted + imitation (rho 0.3) | 5,999 | 0.0% | 0.0% of 5,578 | 0.0% | 0.023 | 0.021 | 0.021 |
| Noise check | 5,990 | 0.0% | 0.0% of 5,567 | 0.0% | 0.052 | 0.041 | 0.036 |
| Agent World: half the people against the other half | 4,476 | 0.0% | 0.0% of 3,953 | 0.0% | 0.067 | 0.050 | 0.047 |

Cramér's V runs from 0 (same proportions) to 1. TVD (total variation distance) is the share of choices that would have to change for the two to agree.

How to read it: the counted chain takes its probabilities from the Agent World's own counts (per hour), so its walkers reproduce the shares at each junction by construction, and imitation copies people who were themselves drawn from those shares. A low rejection rate for these two is expected, not a finding. What separates them from the Agent World is not the share at one junction but whether two people choose alike several junctions in a row (section 3).

## 2. All junctions pooled

One table per chain, Agent World against the chain: choices labelled front (within 40° of straight on), left, right or (rarely, at sharp bends) back.

| Chain | Chi-square | G | Degrees of freedom | p | Cramér's V | Front: Agent World / chain | Left | Right |
|---|---|---|---|---|---|---|---|---|
| Markov: momentum (kappa 2) | 82,500 | 80,537 | 3 | < 1e-300 | 0.135 | 50.0% / 64.8% | 24.6% / 17.4% | 24.6% / 17.5% |
| Markov: counted | 613 | 621 | 3 | 1.76e-132 | 0.012 | 50.0% / 48.9% | 24.6% / 25.1% | 24.6% / 25.0% |
| Markov: counted + imitation (rho 0.3) | 651 | 660 | 3 | 1.02e-140 | 0.012 | 50.0% / 48.8% | 24.6% / 25.1% | 24.6% / 25.0% |

## 3. Two people arriving together: do they make the same next k decisions as often as the chain says?

Pairs who arrive at a junction by the same path, one at most 30 m behind the other. A 2 × 2 table per chain and k: same next k decisions or not, Agent World pairs against the chain's pairs (first repeat).

| Chain | k | Agent World | Chain | Difference | Chi-square | G | p | Effect size phi |
|---|---|---|---|---|---|---|---|---|
| Markov: momentum (kappa 2) | 1 | 78.7% | 68.0% | +10.7 points | 14,785 | 14,399 | < 1e-300 | 0.116 |
| Markov: momentum (kappa 2) | 3 | 58.6% | 31.7% | +26.9 points | 61,341 | 62,426 | < 1e-300 | 0.250 |
| Markov: momentum (kappa 2) | 5 | 48.8% | 14.9% | +34.0 points | 89,001 | 97,390 | < 1e-300 | 0.323 |
| Markov: counted | 1 | 78.7% | 72.7% | +6.0 points | 5,872 | 5,815 | < 1e-300 | 0.069 |
| Markov: counted | 3 | 58.6% | 41.6% | +17.0 points | 30,045 | 30,153 | < 1e-300 | 0.166 |
| Markov: counted | 5 | 48.8% | 25.5% | +23.4 points | 51,475 | 53,039 | < 1e-300 | 0.232 |
| Markov: counted + imitation (rho 0.3) | 1 | 78.7% | 77.1% | +1.7 points | 507 | 506 | 4.57e-112 | 0.020 |
| Markov: counted + imitation (rho 0.3) | 3 | 58.6% | 47.3% | +11.3 points | 14,296 | 14,302 | < 1e-300 | 0.111 |
| Markov: counted + imitation (rho 0.3) | 5 | 48.8% | 30.1% | +18.8 points | 35,474 | 36,046 | < 1e-300 | 0.188 |

Agent World pairs at k = 1: 739,607.

Limits: one person passes the same junction on several trips and belongs to many pairs, so the counts are not independent and every p-value is too small. With this many pairs almost any difference is significant; read the difference in points and the effect size (about 0.1 small, 0.3 medium, 0.5 large).

Table per junction and path in: model_tests.csv.
