# quepaxa-rounds

**Inspired by [Choosing QuePaxa, an unusual consensus algorithm](https://blog.cloudflare.com/choosing-quepaxa/)**, João Pedro Leite, Bob Halley and James Larisch, Cloudflare, 11 Nov 2026.

Status: Wednesday, harness tests and sweep written, full sweep not run yet. The hypothesis below was written before any code, and it stays here unedited whatever the week finds.

## The question

The post says the QuePaxa paper predicts each round has a 50% chance of deciding, "but in practice, that probability is much higher, thanks to convergence". It gives no number and no conditions. The post also says two things that pull in opposite directions: "as more proposers submit proposals, the more likely they are to converge", and "the more proposers there are ... the more likely it is that replicas fail to decide in a round". This project measures the per-round decision rate on the slow path (no leader fast path) in a seeded simulation, swept over proposer count, recorder count and message-delay spread, to find where "much higher" holds and where it does not.

The framing as a sweep over delay spread is ours, not the post's.

## Hypothesis

I believe the slow-path decision rate is far above 50% when link delays are similar, because every proposer then sees roughly the same majority and adopts the same top priority in phase 0. I also believe it falls as delay spread grows, since spread is what lets different proposers see different majorities, and that it falls with more proposers at high spread, so the "fail to decide" sentence wins over the "converge" sentence once the network is uneven.

If true I would see:

1. Round 1 decision rate of at least 0.9 for 2 to 5 proposers when delays vary by under 2x across links.
2. The rate dropping as spread grows, and reaching 0.5 or below somewhere in the swept range for 3 or more proposers.
3. A round that follows a failed round deciding more often than round 1, because phase 3 carries the best proposal forward. This is the "convergence" the post credits.

What would show I am wrong: a round 1 rate near 0.5 at low spread, a rate that rises with proposer count at high spread, or round 2 deciding no more often than round 1.

## Definitions to hold fixed

- **Round decides**: at least one proposer decides in phase 2 of that round. Safety means any others decide the same value.
- **Slow path**: no proposer has the leader's reserved top priority, so phase 0 cannot decide. This models round 2 onwards or a dead leader.
- **Delay spread**: one-way link delays drawn per message from a distribution with a fixed median and a swept ratio between its high and low ends. Zero spread is the degenerate case where the rate is 1 by construction, so it is a sanity check and not a result.

## Modelling choices (Tuesday)

The post describes the phases in prose, not pseudocode, and the paper (Tennage, Băsescu et al., 2023) cannot be read from the cloud sandbox. Every guess is ours and none of it is credited to Cloudflare. The full list lives in `MODEL_CHOICES` in `sim.py`. The ones that matter most:

- A step is `4*round + phase`. A recorder freezes a step when it first sees a later one and rejects late messages for it, and the rejected proposer jumps forward to the recorder's step. Without the freeze, a slow proposer can still push a higher proposal into a phase another proposer already decided on.
- Phase 0 and 1 replies carry the recorder's highest proposal so far in that step (`reply_mode="max"`, from the post's wording) or the first one (`"first"`, which the paper may use). Both are arms.
- Phase 2 and 3 replies carry the frozen highest proposal of the previous step. Phase 2 decides when every reply in the majority equals the proposer's own proposal.
- Each round, a proposer gives its carried value a fresh random priority, so a value several proposers carry gets several draws. This is our reading of "convergence".
- Priorities come from `range(prio_range)`, ties break on proposer id and are counted.
- Links are FIFO per pair by default (`fifo=True`), as over one TCP connection.
- A proposer that decides keeps running phases with its value at a reserved top priority (`decided_continue=True`).
- Proposers start with jitter uniform in `[0, 0.5 * median)`. Delay per message is `median * spread**(u - 0.5)`.

## Notes from building it (Tuesday)

These came out of smoke runs while writing the simulator. They are about the model, not the result, and they go into "What was wrong first" on Saturday.

- With non-FIFO links a lone proposer failed round 1 in some trials at spread 16, which cannot be right for one proposer. A recorder that got the step 2 message before the step 1 message had no step 1 summary to report. FIFO links fixed it: 1 proposer decides in round 1 in every trial at every spread tried.
- When a proposer stopped as soon as it decided, other proposers sometimes decided a different value in a later round (for example 7 of 400 trials at 3 proposers, spread 16). Same-round agreement never broke. Keeping decided proposers running at a reserved top priority gave 0 disagreements in 2000 trials each at 2, 3 and 5 proposers, spread 16, FIFO. With non-FIFO links there was still 1 in 2000 at 3 and at 5 proposers, so carry-forward in this model is not proven safe, only not caught failing.
- Round 1 rate, the week's metric, does not depend on the `decided_continue` choice, since it only looks at the first decision.

## Harness (Wednesday)

- `test_sim.py`, 24 tests, `python3 -m unittest -v test_sim`, under 3 seconds. They cover delay bounds, the recorder freeze and reply modes, the conditional rate arithmetic, the Wilson interval, determinism per seed, distinct seeds giving distinct runs, 1 proposer and spread 1 always deciding in round 1, agreement over 900 trials at spread 16, eventual decision at spread 64, the tie counter, and that round 1 can fail at spread 16 so the metric is not fixed by construction.
- To check the tests bite, five bugs were planted in `sim.py` one at a time: no step freeze, a quorum of 1, a skewed delay draw, no tie counting, and stopping decided proposers. Each one failed at least one test.
- `sweep.py` emits the number. Each row runs 4 seed blocks with disjoint seeds and reports the round 1 rate with a Wilson 95% interval and the lowest and highest block, the round 2 rate given round 1 failed, the pooled rate (decisions over rounds run), agreement violations, undecided trials and priority ties. `python3 sweep.py` runs a 4 row check grid. `python3 sweep.py --full --out results/sweep.csv` runs 96 rows: reply mode (max, first) by recorders (3, 5) by proposers (1, 2, 3, 5) by spread (1, 2, 4, 8, 16, 64). That run is Thursday's.

First output of the check grid, 400 trials per row, 5 recorders, `reply_mode="max"`. Not the result, since Thursday runs the full grid:

| proposers | spread | round 1 rate (95% CI) | round 2 rate given round 1 failed |
|---|---|---|---|
| 2 | 1 | 1.000 (0.991 to 1.000) | none reached |
| 2 | 16 | 0.915 (0.884 to 0.939) | 0.794 (34 trials) |
| 3 | 1 | 1.000 (0.991 to 1.000) | none reached |
| 3 | 16 | 0.915 (0.884 to 0.939) | 0.676 (34 trials) |

Round 2 decided less often than round 1 here, against hypothesis 3. With 34 trials that is weak, and it may be selection, since the trials that fail round 1 are the ones whose delays put proposers out of step. Friday should check it.

## Layout

- `sim.py`: zero-dependency, seeded discrete-event simulator of the four phases. `python3 sim.py 500` prints a smoke table, not a result.
- `test_sim.py`: harness tests
- `sweep.py`: the sweep that emits the number
- `results/`: raw sweep output, written Thursday

## Finding, Method, Repro, What was wrong first, Limits

Not yet. These get written after Friday tries to break the result.
