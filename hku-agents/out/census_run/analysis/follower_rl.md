# The Q-learning follower: census_run

41,708 Agent World trips of 9,949 people. The people are split in two at random: followers are trained behind the 20,952 trips of one half and tested behind the 20,756 trips of the other. A follower starts 5 s behind its target at the first junction of the target's trip; its destination and pace are those of a trip of a different, randomly chosen person. Reward R = 1 for taking its target's road while the target is at most 30 s in front; penalty 0.5 x^2 for a road that leaves it x beyond the closest it has been to its destination, x in units of 100 m. Q-learning: 100 epochs, gamma 1, 3 trainings; the tables below use the training with the best test score. Device: cpu.

## Score per follower on the test people (rewards minus penalties)

| Walker | Score | Junctions passed | Junctions where it followed | Arrived |
|---|---|---|---|---|
| Never follows | 2.682 | 30.7 | 2.7 | 100.0% |
| Rule (one junction ahead) | 10.395 | 41.3 | 13.2 | 100.0% |
| Q-learning | 10.674 (trainings: 10.662 ± 0.017) | 41.2 | 13.2 | 100.0% |
| Always follows | -72.222 | 49.1 | 18.9 | 100.0% |

Q-learning scores at least as well as every fixed walker, as it should.

## Share of walkers trailing the same stranger through k junctions

At most 30 m behind along the road each time. In brackets: 95% bootstrap interval, resampling people.

| k | Agent World (coincidence) | Never follows | Rule (one junction ahead) | Q-learning | Always follows |
|---|---|---|---|---|---|
| 1 | 74.6% (73.8% to 75.2%) | 89.5% (89.1% to 89.9%) | 99.9% (99.9% to 100.0%) | 100.0% (99.9% to 100.0%) | 100.0% (100.0% to 100.0%) |
| 2 | 62.6% (61.9% to 63.4%) | 78.8% (78.3% to 79.4%) | 98.6% (98.4% to 98.7%) | 98.6% (98.4% to 98.7%) | 99.0% (98.9% to 99.1%) |
| 3 | 50.1% (49.3% to 50.8%) | 67.3% (66.7% to 68.0%) | 95.0% (94.7% to 95.3%) | 95.1% (94.8% to 95.4%) | 96.2% (95.9% to 96.4%) |
| 4 | 40.0% (39.3% to 40.8%) | 56.6% (56.0% to 57.3%) | 89.9% (89.4% to 90.3%) | 90.0% (89.5% to 90.4%) | 91.8% (91.4% to 92.2%) |
| 5 | 31.9% (31.1% to 32.6%) | 46.2% (45.6% to 47.0%) | 83.1% (82.5% to 83.6%) | 83.2% (82.6% to 83.8%) | 86.2% (85.7% to 86.7%) |
| 6 | 25.7% (25.0% to 26.3%) | 37.4% (36.8% to 38.2%) | 75.0% (74.4% to 75.7%) | 75.2% (74.6% to 75.8%) | 79.4% (78.8% to 80.0%) |
| 8 | 17.1% (16.5% to 17.7%) | 25.4% (24.7% to 25.9%) | 59.6% (58.9% to 60.4%) | 59.4% (58.6% to 60.1%) | 65.6% (64.9% to 66.3%) |
| 10 | 11.7% (11.2% to 12.2%) | 17.3% (16.8% to 17.9%) | 46.9% (46.1% to 47.6%) | 46.1% (45.4% to 46.9%) | 54.7% (53.9% to 55.5%) |

Q-learning, T_3 over the 3 trainings: 95.1%, 95.1%, 95.1%.

## What the follower learned

Where a test follower had a real choice (its target took a road other than its quickest road), the share of those choices in which the learned table says follow:

| The target's road would leave it beyond its closest point by | Choices | Follows |
|---|---|---|
| 0 m (not beyond its closest point) | 22,084 | 100.0% |
| 0 to 25 m | 44,065 | 100.0% |
| 25 to 50 m | 24,630 | 100.0% |
| 50 to 100 m | 32,063 | 100.0% |
| 100 to 150 m | 20,500 | 97.7% |
| 150 to 200 m | 8,774 | 61.6% |
| 200 to 300 m | 2,891 | 0.0% |
| over 300 m | 402 | 1.0% |

The one-junction rule follows up to 141 m and never beyond.

Tables: follower_rl_tk.csv, follower_rl_curve.csv (learning curve), follower_rl_policy.csv, follower_rl_q.npy (the learned table). Figure: graphs/follower-rl.pdf.
