"""Sweep that emits the week's number: QuePaxa's per-round decision rate.

Zero dependencies. Every row runs `blocks` seed blocks of `trials` trials each,
so a row is never one run. The seed for trial i of block b is
base_seed + b * 1_000_000 + i, so blocks never share a seed.

Columns:
  r1        P(some proposer decides in round 1), pooled over all blocks
  r1_lo/hi  Wilson 95% interval on r1
  r1_bmin/bmax  lowest and highest r1 across seed blocks
  r2        P(decide in round 2 | round 1 failed), and r2_n trials behind it
  pooled    decisions / rounds run, the rate a round has of deciding when
            every round is counted, which equals 1 / mean(first_round)
  viol      trials where two proposers decided different values
  undec     trials that hit max_rounds without any decision
  ties      phase 0 priority collisions summed over all trials

Usage:
  python3 sweep.py               small grid, prints CSV, for checking it runs
  python3 sweep.py --full --out results/sweep.csv
"""

import argparse
import csv
import math
import sys

from sim import per_round_rates, run_trial

FIELDS = ["n_prop", "n_rec", "spread", "reply_mode", "prio_range", "fifo",
          "trials", "r1", "r1_lo", "r1_hi", "r1_bmin", "r1_bmax", "r2",
          "r2_n", "pooled", "viol", "undec", "ties", "phase1_adopt",
          "jump_adopt"]


def wilson(hits, n, z=1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


def run_row(n_prop, n_rec, spread, reply_mode="max", prio_range=2 ** 32,
            fifo=True, trials=500, blocks=4, base_seed=0,
            phase1_adopt=False, jump_adopt="recorder"):
    res = []
    block_r1 = []
    for b in range(blocks):
        block = [run_trial(base_seed + b * 1_000_000 + i, n_prop=n_prop,
                           n_rec=n_rec, spread=spread, reply_mode=reply_mode,
                           prio_range=prio_range, fifo=fifo,
                           phase1_adopt=phase1_adopt, jump_adopt=jump_adopt)
                 for i in range(trials)]
        block_r1.append(sum(1 for x in block if x["first_round"] == 1)
                        / trials)
        res.extend(block)
    n = len(res)
    r1_hits = sum(1 for x in res if x["first_round"] == 1)
    lo, hi = wilson(r1_hits, n)
    rates = per_round_rates(res, 2)
    _, r2_n, r2 = rates[1]
    decided = [x["first_round"] for x in res if x["first_round"] is not None]
    # Undecided trials ran every round without deciding, so they add rounds
    # and no decision. max_rounds is the sim default of 50.
    rounds_run = sum(decided) + 50 * (n - len(decided))
    return {
        "n_prop": n_prop, "n_rec": n_rec, "spread": spread,
        "reply_mode": reply_mode, "prio_range": prio_range, "fifo": fifo,
        "trials": n, "r1": r1_hits / n, "r1_lo": lo, "r1_hi": hi,
        "r1_bmin": min(block_r1), "r1_bmax": max(block_r1),
        "r2": r2, "r2_n": r2_n,
        "pooled": len(decided) / rounds_run if rounds_run else None,
        "viol": sum(1 for x in res if not x["agree"]),
        "undec": n - len(decided),
        "ties": sum(x["ties"] for x in res),
        "phase1_adopt": phase1_adopt, "jump_adopt": jump_adopt,
    }


def grid(full):
    if not full:
        for n_prop in (2, 3):
            for spread in (1.0, 16.0):
                yield dict(n_prop=n_prop, n_rec=5, spread=spread)
        return
    for reply_mode in ("max", "first"):
        for n_rec in (3, 5):
            for n_prop in (1, 2, 3, 5):
                for spread in (1.0, 2.0, 4.0, 8.0, 16.0, 64.0):
                    yield dict(n_prop=n_prop, n_rec=n_rec, spread=spread,
                               reply_mode=reply_mode)


def fmt(v):
    if isinstance(v, float):
        return f"{v:.4f}"
    return "" if v is None else str(v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--trials", type=int, default=None)
    ap.add_argument("--blocks", type=int, default=4)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    trials = a.trials or (500 if a.full else 100)
    out = open(a.out, "w", newline="") if a.out else sys.stdout
    w = csv.DictWriter(out, fieldnames=FIELDS)
    w.writeheader()
    for cfg in grid(a.full):
        row = run_row(trials=trials, blocks=a.blocks, **cfg)
        w.writerow({k: fmt(v) for k, v in row.items()})
        out.flush()
    if a.out:
        out.close()


if __name__ == "__main__":
    main()
