# The Q-learning follower: census_run

41,708 Agent World trips of 9,949 people. The people are split in two at random: followers are trained behind the 20,952 trips of one half and tested behind the 20,756 trips of the other. A follower starts 20 s behind its target at the first junction of the target's trip; its destination and pace are those of a trip of a different, randomly chosen person. Reward for closeness, R (1 - gap / 30 s) with R = 1, each time it takes its target's road while the target is in view (no separate reward for catching it); penalty 0.5 x^2 for a road that leaves it x beyond the closest it has been to its destination, x in units of 100 m. While it follows it chooses its speed: walk 1, fast walk 1.3, jog 1.54, run 2.61, sprint 4.33 times its own walking speed. Only going faster than a run drains its stamina bar (130 m above critical speed), and using the whole bar costs 1. Q-learning: 150 epochs, gamma 1, 3 trainings; the tables below use the training with the best test score. Device: cpu.

## Score per follower on the test people (rewards minus penalties)

| Walker | Score | Came within 5 s of its target | Junctions passed | Junctions where it followed | Arrived |
|---|---|---|---|---|---|
| Never follows | 1.195 | 8.6% | 30.7 | 2.4 | 100.0% |
| Rule, walking | 5.489 | 29.5% | 38.8 | 10.7 | 100.0% |
| Rule, with speed | 11.636 | 91.7% | 44.1 | 17.0 | 100.0% |
| Q-learning | 11.563 | 93.2% | 45.4 | 18.0 | 100.0% |
| Always follows, running | -139.545 | 93.4% | 57.4 | 26.7 | 100.0% |

Q-learning scores at least as well as the walkers that never follow, always follow, or follow by the walking rule, as it should.
Against the rule with speed it scores -0.073. That rule is told when its target will reach the next junction and sets its speed to match; the learner only sees its gap and whether it is closing.

## Share of walkers trailing the same stranger through k junctions

At most 30 m behind along the road each time. In brackets: 95% bootstrap interval, resampling people.

| k | Agent World (coincidence) | Never follows | Rule, walking | Rule, with speed | Q-learning | Always follows, running |
|---|---|---|---|---|---|---|
| 1 | 74.6% (73.8% to 75.2%) | 88.5% (88.1% to 89.0%) | 99.2% (99.1% to 99.4%) | 99.5% (99.4% to 99.6%) | 99.8% (99.7% to 99.8%) | 99.8% (99.8% to 99.9%) |
| 2 | 62.6% (61.9% to 63.4%) | 77.5% (77.0% to 78.2%) | 94.8% (94.5% to 95.2%) | 97.9% (97.7% to 98.1%) | 98.7% (98.5% to 98.8%) | 99.1% (99.0% to 99.2%) |
| 3 | 50.1% (49.3% to 50.8%) | 65.3% (64.6% to 66.0%) | 86.5% (86.0% to 87.1%) | 94.8% (94.5% to 95.1%) | 96.4% (96.2% to 96.7%) | 97.4% (97.2% to 97.7%) |
| 4 | 40.0% (39.3% to 40.8%) | 53.9% (53.2% to 54.6%) | 76.7% (76.0% to 77.4%) | 91.1% (90.7% to 91.5%) | 93.2% (92.8% to 93.6%) | 95.3% (95.0% to 95.6%) |
| 5 | 31.9% (31.1% to 32.6%) | 43.0% (42.3% to 43.7%) | 66.6% (65.8% to 67.4%) | 86.5% (86.0% to 87.0%) | 89.0% (88.5% to 89.4%) | 92.5% (92.1% to 93.0%) |
| 6 | 25.7% (25.0% to 26.3%) | 34.3% (33.6% to 35.0%) | 57.2% (56.4% to 58.1%) | 80.8% (80.3% to 81.5%) | 83.5% (82.9% to 84.1%) | 88.6% (88.1% to 89.1%) |
| 8 | 17.1% (16.5% to 17.7%) | 23.0% (22.5% to 23.6%) | 43.3% (42.6% to 44.2%) | 69.3% (68.7% to 70.1%) | 71.8% (71.2% to 72.5%) | 79.9% (79.2% to 80.4%) |
| 10 | 11.7% (11.2% to 12.2%) | 15.6% (15.1% to 16.0%) | 34.2% (33.5% to 35.0%) | 58.7% (58.0% to 59.4%) | 60.8% (60.2% to 61.6%) | 72.0% (71.2% to 72.6%) |

## Differences, as matched pairs by person

For every test person: the share of their trips on which one walker trails the same stranger through k junctions, minus the same share for another walker behind the same trips. The table gives the mean difference over people in percentage points, with its 95% t-interval (mean ± t* s / √n). A person is one observation, so several trips by one person are not counted as independent.

| k | Walker | minus | Difference (points) | 95% interval | People |
|---|---|---|---|---|---|
| 3 | Rule, walking | Never follows | +20.9 | +20.2 to +21.6 | 4,974 |
| 3 | Rule, with speed | Never follows | +28.4 | +27.7 to +29.1 | 4,974 |
| 3 | Q-learning | Never follows | +29.9 | +29.1 to +30.6 | 4,974 |
| 3 | Always follows, running | Never follows | +30.8 | +30.1 to +31.6 | 4,974 |
| 3 | Never follows | Agent World (coincidence) | +14.7 | +13.7 to +15.7 | 4,974 |
| 3 | Q-learning | Agent World (coincidence) | +44.6 | +43.8 to +45.5 | 4,974 |
| 3 | Q-learning | Rule, with speed | +1.5 | +1.2 to +1.7 | 4,974 |
| 5 | Rule, walking | Never follows | +23.2 | +22.3 to +24.0 | 4,974 |
| 5 | Rule, with speed | Never follows | +41.9 | +41.1 to +42.8 | 4,974 |
| 5 | Q-learning | Never follows | +44.3 | +43.5 to +45.2 | 4,974 |
| 5 | Always follows, running | Never follows | +47.6 | +46.8 to +48.5 | 4,974 |
| 5 | Never follows | Agent World (coincidence) | +10.5 | +9.5 to +11.5 | 4,974 |
| 5 | Q-learning | Agent World (coincidence) | +54.8 | +53.9 to +55.7 | 4,974 |
| 5 | Q-learning | Rule, with speed | +2.4 | +2.0 to +2.7 | 4,974 |
| 10 | Rule, walking | Never follows | +17.6 | +16.8 to +18.4 | 4,974 |
| 10 | Rule, with speed | Never follows | +40.9 | +39.9 to +41.8 | 4,974 |
| 10 | Q-learning | Never follows | +42.8 | +41.8 to +43.7 | 4,974 |
| 10 | Always follows, running | Never follows | +53.5 | +52.5 to +54.5 | 4,974 |
| 10 | Never follows | Agent World (coincidence) | +3.3 | +2.6 to +4.1 | 4,974 |
| 10 | Q-learning | Agent World (coincidence) | +46.1 | +45.2 to +47.0 | 4,974 |
| 10 | Q-learning | Rule, with speed | +1.9 | +1.5 to +2.3 | 4,974 |

Q-learning, T_3 over the 1 trainings: 96.4%.

## What the follower learned

Where a test follower had a real choice (its target took a road other than its quickest road), the share of those choices in which the learned table says follow:

| The target's road would leave it beyond its closest point by | Choices | Follows |
|---|---|---|
| 0 m (not beyond its closest point) | 29,453 | 100.0% |
| 0 to 25 m | 56,523 | 100.0% |
| 25 to 50 m | 31,060 | 100.0% |
| 50 to 100 m | 43,688 | 100.0% |
| 100 to 150 m | 30,034 | 100.0% |
| 150 to 200 m | 17,034 | 90.1% |
| 200 to 300 m | 6,103 | 0.4% |
| over 300 m | 742 | 0.7% |

The one-junction rule follows up to 141 m when it is right behind its target, less when it is farther back, and never beyond.

## The speed the Q-learning follower chose

Of the stretches on which it followed its target (the speed it asked for; it never overtakes, so it may have gone slower):

| walk | fast walk | jog | run | sprint |
|---|---|---|---|---|
| 0.6% | 26.3% | 12.3% | 39.6% | 21.2% |

Followers who used any of their stamina bar: 70.5%. Average share of the bar used: 6.0%.

Tables: follower_rl_tk.csv, follower_rl_curve.csv (learning curve), follower_rl_policy.csv, follower_rl_q.npy (the learned table). Figure: graphs/follower-rl.pdf.
