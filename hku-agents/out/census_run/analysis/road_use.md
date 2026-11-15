# Road use under each method: census_run

4,835 segments. A walk is its list of junction choices; each choice adds one pass to every segment between that junction and the next, for every method alike. Use is given as walkers in 1,000.

| Method | Walks | Walking on the busiest 5% of segments | Unevenness (Gini) | Segments never used | Walking on stairs | Km per walk | Rank correlation with the Agent World |
|---|---|---|---|---|---|---|---|
| Markov: equal chance | 41,708 | 29.3% | 0.60 | 0.0% | 5.6% | 0.97 | 0.64 |
| Markov: momentum | 41,708 | 38.1% | 0.68 | 0.0% | 3.6% | 1.07 | 0.54 |
| Markov: counted shares | 41,708 | 39.5% | 0.70 | 2.9% | 4.0% | 0.78 | 0.96 |
| Markov: imitation | 41,708 | 39.5% | 0.70 | 2.8% | 4.0% | 0.79 | 0.95 |
| Random start and end | 42,114 | 55.9% | 0.82 | 16.7% | 2.0% | 1.13 | 0.73 |
| Agent World | 41,708 | 40.5% | 0.70 | 2.3% | 3.8% | 0.76 | 1.00 |
| Q-learning follower | 20,754 | 50.8% | 0.79 | 6.7% | 3.2% | 1.32 | 0.97 |

Unevenness is the Gini coefficient of metres walked per segment: 0 if every segment carried the same, 1 if one segment carried everything. The rank correlation (Spearman) compares each method's use of every segment with the Agent World's.

## The busiest segments in the Agent World

| Street | Markov: equal chance | Markov: momentum | Markov: counted shares | Markov: imitation | Random start and end | Agent World | Q-learning follower |
|---|---|---|---|---|---|---|---|
| 皇后大道西 Queen's Road West | 8 | 11 | 13 | 13 | 40 | 15 | 37 |
| 薄扶林道 Pok Fu Lam Road | 6 | 10 | 9 | 9 | 16 | 11 | 22 |
| 德輔道西 Des Voeux Road West | 7 | 9 | 7 | 7 | 16 | 6 | 12 |
| 般咸道 Bonham Road | 7 | 10 | 7 | 7 | 8 | 7 | 13 |
| 卑路乍街 Belcher's Street | 8 | 10 | 16 | 15 | 74 | 18 | 44 |
| 仲賢路 Lee Chung Yin Road | 14 | 15 | 15 | 14 | 12 | 16 | 29 |
| 第三街 Third Street | 6 | 7 | 7 | 7 | 21 | 9 | 22 |
| 大學街 University Street | 24 | 17 | 38 | 39 | 15 | 32 | 49 |
| 西邊街 Western Street | 6 | 7 | 8 | 8 | 9 | 10 | 19 |
| 大學道 University Drive | 17 | 47 | 23 | 24 | 26 | 18 | 29 |
| 堅彌地城海旁 Praya, Kennedy Town | 10 | 10 | 12 | 12 | 43 | 14 | 29 |
| 士美菲路 Smithfield | 6 | 8 | 5 | 5 | 6 | 4 | 6 |

Walkers in 1,000 on an average metre of the street.

Table: road_use.csv (every segment). Figure: graphs/road-use-methods.pdf.
