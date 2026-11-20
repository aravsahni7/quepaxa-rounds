# Friday runs, 20 Nov 2026

All on the fixed model (commit c45d077 onward: `phase1_adopt=False`, `jump_adopt="recorder"`). `python3 -m unittest test_sim` passed (27 tests) before each run. Python 3.11, cloud sandbox, one process each.

- `sweep_fri.csv`: `python3 sweep.py --full --trials 500 --out results/sweep_fri.csv`. Same grid and seeds as Thursday's `sweep.csv`, 96 rows x 2000 trials. Wall time 3 min 42 s. Thursday's `sweep.csv` stays as the record of what the broken model said.
- `fri_jitter.csv`: `python3 checks/jitter.py`. 5 recorders, 3 and 5 proposers, spread 4, 16, 64, both reply modes, start jitter 0 to 8 medians. 1000 trials per row (4 blocks of 250). 1 min 10 s.
- `fri_many_proposers.csv`: `python3 checks/many_proposers.py`. 5 recorders, 8, 12 and 20 proposers, spread 16 and 64, both reply modes, 400 trials per row (4 blocks of 100). 38 s.

None of these files are edited by hand.
