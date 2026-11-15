# The Q-learning follower: census_run

41,708 Agent World trips of 9,949 people. The people are split in two at random: followers are trained behind the 20,952 trips of one half and tested behind the 20,756 trips of the other. A follower starts 5 s behind its target at the first junction of the target's trip; its destination and pace are those of a trip of a different, randomly chosen person. Reward for closeness, R (1 - gap / 30 s) with R = 1, each time it takes its target's road while the target is in view (no separate reward for catching it); penalty 0.5 x^2 for a road that leaves it x beyond the closest it has been to its destination, x in units of 100 m. While it follows it chooses its speed: walk 1, fast walk 1.3, jog 1.54, run 2.61, sprint 4.33 times its own walking speed. Only going faster than a run drains its stamina bar (130 m above critical speed), and using the whole bar costs 1. Q-learning: 150 epochs, gamma 1, 3 trainings; the tables below use the training with the best test score. Device: cpu.

## Score per follower on the test people (rewards minus penalties)

| Walker | Score | Came within 5 s of its target | Junctions passed | Junctions where it followed | Arrived |
|---|---|---|---|---|---|
| Never follows | 2.162 | 100.0% | 30.7 | 2.7 | 100.0% |
| Rule, walking | 8.428 | 100.0% | 40.6 | 12.7 | 100.0% |
| Rule, with speed | 12.753 | 100.0% | 44.3 | 17.2 | 100.0% |
| Q-learning | 12.622 | 100.0% | 45.3 | 18.0 | 100.0% |
| Always follows, running | -138.383 | 100.0% | 57.4 | 26.8 | 100.0% |

Q-learning scores at least as well as the walkers that never follow, always follow, or follow by the walking rule, as it should.
Against the rule with speed it scores -0.131. That rule is told when its target will reach the next junction and sets its speed to match; the learner only sees its gap and whether it is closing.

## Share of walkers trailing the same stranger through k junctions

At most 30 m behind along the road each time. In brackets: 95% bootstrap interval, resampling people.

| k | Agent World (coincidence) | Never follows | Rule, walking | Rule, with speed | Q-learning | Always follows, running |
|---|---|---|---|---|---|---|
| 1 | 74.6% (73.8% to 75.2%) | 89.5% (89.1% to 89.9%) | 99.9% (99.9% to 100.0%) | 99.9% (99.9% to 100.0%) | 100.0% (99.9% to 100.0%) | 100.0% (100.0% to 100.0%) |
| 2 | 62.6% (61.9% to 63.4%) | 78.8% (78.3% to 79.4%) | 98.4% (98.2% to 98.6%) | 98.9% (98.7% to 99.0%) | 99.1% (99.0% to 99.2%) | 99.4% (99.3% to 99.6%) |
| 3 | 50.1% (49.3% to 50.8%) | 67.3% (66.7% to 68.0%) | 94.4% (94.1% to 94.7%) | 96.5% (96.2% to 96.7%) | 97.2% (96.9% to 97.4%) | 98.1% (97.9% to 98.3%) |
| 4 | 40.0% (39.3% to 40.8%) | 56.6% (56.0% to 57.3%) | 89.0% (88.6% to 89.5%) | 93.3% (93.0% to 93.7%) | 94.5% (94.1% to 94.8%) | 96.2% (95.9% to 96.5%) |
| 5 | 31.9% (31.1% to 32.6%) | 46.2% (45.6% to 47.0%) | 81.8% (81.2% to 82.4%) | 89.1% (88.7% to 89.6%) | 90.7% (90.3% to 91.1%) | 93.6% (93.3% to 94.0%) |
| 6 | 25.7% (25.0% to 26.3%) | 37.4% (36.8% to 38.2%) | 73.3% (72.7% to 74.0%) | 83.4% (82.8% to 83.9%) | 85.4% (84.8% to 85.9%) | 89.9% (89.4% to 90.3%) |
| 8 | 17.1% (16.5% to 17.7%) | 25.4% (24.7% to 25.9%) | 57.8% (57.1% to 58.6%) | 72.0% (71.4% to 72.7%) | 74.1% (73.4% to 74.7%) | 81.4% (80.8% to 82.0%) |
| 10 | 11.7% (11.2% to 12.2%) | 17.3% (16.8% to 17.9%) | 45.2% (44.4% to 46.0%) | 60.8% (60.2% to 61.6%) | 62.4% (61.7% to 63.1%) | 73.5% (72.7% to 74.1%) |

## Differences, as matched pairs by person

For every test person: the share of their trips on which one walker trails the same stranger through k junctions, minus the same share for another walker behind the same trips. The table gives the mean difference over people in percentage points, with its 95% t-interval (mean ± t* s / √n). A person is one observation, so several trips by one person are not counted as independent.

| k | Walker | minus | Difference (points) | 95% interval | People |
|---|---|---|---|---|---|
| 3 | Rule, walking | Never follows | +26.0 | +25.3 to +26.7 | 4,974 |
| 3 | Rule, with speed | Never follows | +28.0 | +27.2 to +28.7 | 4,974 |
| 3 | Q-learning | Never follows | +28.6 | +27.9 to +29.4 | 4,974 |
| 3 | Always follows, running | Never follows | +29.5 | +28.8 to +30.2 | 4,974 |
| 3 | Never follows | Agent World (coincidence) | +16.7 | +15.7 to +17.7 | 4,974 |
| 3 | Q-learning | Agent World (coincidence) | +45.3 | +44.5 to +46.2 | 4,974 |
| 3 | Q-learning | Rule, with speed | +0.7 | +0.5 to +0.9 | 4,974 |
| 5 | Rule, walking | Never follows | +34.8 | +34.0 to +35.6 | 4,974 |
| 5 | Rule, with speed | Never follows | +41.7 | +40.9 to +42.5 | 4,974 |
| 5 | Q-learning | Never follows | +43.3 | +42.4 to +44.1 | 4,974 |
| 5 | Always follows, running | Never follows | +46.0 | +45.2 to +46.8 | 4,974 |
| 5 | Never follows | Agent World (coincidence) | +13.4 | +12.4 to +14.4 | 4,974 |
| 5 | Q-learning | Agent World (coincidence) | +56.7 | +55.8 to +57.6 | 4,974 |
| 5 | Q-learning | Rule, with speed | +1.6 | +1.3 to +1.9 | 4,974 |
| 10 | Rule, walking | Never follows | +26.6 | +25.7 to +27.4 | 4,974 |
| 10 | Rule, with speed | Never follows | +41.4 | +40.5 to +42.3 | 4,974 |
| 10 | Q-learning | Never follows | +42.8 | +41.9 to +43.8 | 4,974 |
| 10 | Always follows, running | Never follows | +53.5 | +52.5 to +54.5 | 4,974 |
| 10 | Never follows | Agent World (coincidence) | +5.1 | +4.3 to +5.8 | 4,974 |
| 10 | Q-learning | Agent World (coincidence) | +47.9 | +47.0 to +48.8 | 4,974 |
| 10 | Q-learning | Rule, with speed | +1.4 | +1.0 to +1.8 | 4,974 |

Q-learning, T_3 over the 1 trainings: 97.2%.

## What the follower learned

Where a test follower had a real choice (its target took a road other than its quickest road), the share of those choices in which the learned table says follow:

| The target's road would leave it beyond its closest point by | Choices | Follows |
|---|---|---|
| 0 m (not beyond its closest point) | 29,341 | 100.0% |
| 0 to 25 m | 56,403 | 100.0% |
| 25 to 50 m | 31,073 | 100.0% |
| 50 to 100 m | 43,659 | 100.0% |
| 100 to 150 m | 29,995 | 100.0% |
| 150 to 200 m | 16,806 | 88.7% |
| 200 to 300 m | 5,919 | 0.1% |
| over 300 m | 725 | 0.0% |

The one-junction rule follows up to 141 m when it is right behind its target, less when it is farther back, and never beyond.

## The speed the Q-learning follower chose

Of the stretches on which it followed its target (the speed it asked for; it never overtakes, so it may have gone slower):

| walk | fast walk | jog | run | sprint |
|---|---|---|---|---|
| 1.5% | 26.2% | 13.5% | 29.1% | 29.7% |

Followers who used any of their stamina bar: 28.0%. Average share of the bar used: 3.7%.

Tables: follower_rl_tk.csv, follower_rl_curve.csv (learning curve), follower_rl_policy.csv, follower_rl_q.npy (the learned table). Figure: graphs/follower-rl.pdf.
