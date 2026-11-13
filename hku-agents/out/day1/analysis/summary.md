# Same-route analysis: day1

57223 trips by 9995 agents; 5000 trips used as 'you'. A stranger shares a turn with you when you both pass the same junction the same way in and out, each within 90 s of the other.

| Same turns in a row (k) | Quickest path (this run) | Random turns (baseline) |
|---|---|---|
| 1 | 95.6% | 98.8% |
| 2 | 91.1% | 97.7% |
| 3 | 85.4% | 95.9% |
| 4 | 79.7% | 93.1% |
| 5 | 73.9% | 88.9% |
| 6 | 68.5% | 82.6% |
| 8 | 57.6% | 61.2% |
| 10 | 47.7% | 35.9% |

All turns recorded: left 26%, right 27%, straight 47%, back 1%.
Baseline: the same 57223 trips re-walked with softmax turns (beta=0.01 per second of detour).

Busiest segments are in segment_usage.csv; per-junction turn shares are in turns_by_junction.csv.

## By group

| Group | People | Trips each | Walking min each | Left | Right | Straight | Stranger shares 5+ turns |
|---|---|---|---|---|---|---|---|
| Undergrads in halls | 2201 | 7.28 | 67.4 | 26.8% | 27.2% | 45.4% | 76% |
| Commuting undergrads | 3983 | 6.01 | 48.2 | 25.9% | 26.5% | 47.0% | 77% |
| Postgrads in halls | 177 | 7.6 | 73.0 | 27.0% | 27.7% | 44.6% | 73% |
| Commuting postgrads | 1013 | 5.94 | 47.3 | 26.1% | 26.7% | 46.6% | 77% |
| Staff | 1008 | 4.03 | 38.5 | 23.4% | 23.8% | 52.1% | 81% |
| Local residents | 1618 | 3.61 | 35.0 | 26.7% | 26.5% | 46.2% | 49% |

Per road: road_usage.csv (walkers by group, peak hour) and road_decisions.csv (what each group did at the end of each road, by direction). Who shares your turns: share_matrix.csv.