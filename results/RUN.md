# Thursday run, 19 Nov 2026

- Command: `python3 sweep.py --full --out results/sweep.csv`
- Code: sim.py and sweep.py as of commit 809ba14, unchanged today. `python3 -m unittest test_sim` passed (24 tests) before the run.
- Python 3.11.18, cloud sandbox, one process. Wall time 2 min 32 s for 96 rows.
- Each row is 4 seed blocks of 500 trials, 2000 trials per row, 192000 trials in all. Seeds are base 0, trial i of block b uses b * 1000000 + i.
- Grid: reply mode (max, first) by recorders (3, 5) by proposers (1, 2, 3, 5) by spread (1, 2, 4, 8, 16, 64). FIFO links, prio_range 2**32, decided proposers continue.

`sweep.csv` is the raw output, not edited. Reading it is Friday's job.
