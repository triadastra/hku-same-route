# Who follows whom in the Agent World: census_run

42,161 trips; 20,688 are followed by a stranger through 3 or more junctions (at most 30 m behind along the road each time). For each, the stranger who followed longest is counted. Nobody in the Agent World can see anybody, so this is who ends up behind whom, not who chooses to follow whom.

- The person behind is of the same kind as the person in front in 50.3% of pairs. If the kind behind did not depend on the kind in front, it would be 19.2%: 2.6 times as often as chance.
- Chi-square test of independence: chi-square = 25,574, 121 degrees of freedom, p < 0.001; Cramér's V = 0.34 (0 no association, 1 complete). Trips by one person are not independent, so the p-value is too small; the ratios below are the result.

## Same kind in front and behind

| Kind of person | Pairs with this kind in front | Followed by the same kind | Expected by chance | Observed / expected |
|---|---|---|---|---|
| Works outside C&W | 2,151 | 50.9% | 10.0% | 5.1 |
| Works in C&W | 2,168 | 29.4% | 10.3% | 2.8 |
| No fixed workplace | 1,115 | 16.9% | 4.6% | 3.6 |
| Works at home | 162 | 1.2% | 0.8% | 1.6 |
| Domestic helper | 1,179 | 16.5% | 4.8% | 3.4 |
| School pupil | 1,465 | 65.1% | 7.9% | 8.2 |
| College student | 341 | 10.3% | 1.6% | 6.5 |
| Retired | 1,773 | 38.2% | 10.4% | 3.7 |
| Home-maker | 455 | 8.1% | 2.1% | 3.9 |
| Unpaid carer | 338 | 6.5% | 1.8% | 3.6 |
| Not working | 1,707 | 20.3% | 7.7% | 2.6 |
| HKU | 7,834 | 79.3% | 37.9% | 2.1 |

## Every pair: observed / expected

Rows: the kind of person in front. Columns: the kind of person behind.

| | Works outside C&W | Works in C&W | No fixed workplace | Works at home | Domestic helper | School pupil | College student | Retired | Home-maker | Unpaid carer | Not working | HKU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Works outside C&W | 5.1 | 2.3 | 0.2 | 0.6 | 0.3 | 0.4 | 5.3 | 0.3 | 0.4 | 0.3 | 0.3 | 0.1 |
| Works in C&W | 2.2 | 2.8 | 1.1 | 1.2 | 0.7 | 0.6 | 1.8 | 0.7 | 1.0 | 0.9 | 1.0 | 0.3 |
| No fixed workplace | 0.3 | 1.0 | 3.6 | 1.1 | 1.4 | 0.6 | 0.2 | 1.2 | 1.6 | 2.1 | 2.2 | 0.5 |
| Works at home | 0.3 | 1.1 | 1.1 | 1.6 | 2.0 | 0.8 | 0.4 | 1.8 | 1.5 | 3.7 | 1.4 | 0.6 |
| Domestic helper | 0.2 | 0.7 | 1.4 | 1.9 | 3.4 | 1.7 | 0.5 | 1.8 | 2.6 | 1.6 | 1.3 | 0.4 |
| School pupil | 0.3 | 0.5 | 0.7 | 0.8 | 1.5 | 8.2 | 0.4 | 0.3 | 0.2 | 0.2 | 0.4 | 0.2 |
| College student | 4.9 | 1.9 | 0.3 | 0.4 | 0.4 | 0.4 | 6.5 | 0.3 | 0.1 | 0.2 | 0.5 | 0.2 |
| Retired | 0.3 | 0.8 | 1.1 | 1.8 | 1.8 | 0.3 | 0.2 | 3.7 | 2.3 | 1.1 | 1.5 | 0.4 |
| Home-maker | 0.3 | 0.9 | 1.0 | 2.3 | 2.4 | 0.4 | 0.1 | 2.9 | 3.9 | 1.3 | 1.6 | 0.3 |
| Unpaid carer | 0.4 | 1.0 | 2.8 | 2.0 | 1.2 | 0.4 | 0.2 | 1.4 | 1.7 | 3.6 | 2.5 | 0.5 |
| Not working | 0.3 | 1.0 | 2.0 | 1.8 | 1.3 | 0.5 | 0.1 | 1.5 | 1.8 | 2.5 | 2.6 | 0.6 |
| HKU | 0.1 | 0.3 | 0.5 | 0.5 | 0.4 | 0.2 | 0.1 | 0.4 | 0.4 | 0.6 | 0.5 | 2.1 |

Table: who_follows.csv. Figure: graphs/who-follows-whom.pdf.
