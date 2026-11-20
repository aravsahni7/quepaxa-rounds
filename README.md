# quepaxa-rounds

**Inspired by [Choosing QuePaxa, an unusual consensus algorithm](https://blog.cloudflare.com/choosing-quepaxa/)**, João Pedro Leite, Bob Halley and James Larisch, Cloudflare, 11 Nov 2026.

Status: Friday done. Two model bugs found and fixed, the sweep rerun, and two rival explanations checked. Saturday rewrites this README around what survived. The hypothesis below was written before any code, and it stays here unedited whatever the week finds.

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

## Raw sweep (Thursday)

96 rows, 2000 trials each, from `results/sweep.csv`. These are what the sweep printed, not yet results.

- Round 1 rate ranges from 0.7665 (5 recorders, 5 proposers, spread 64, `reply_mode="first"`) to 1.000. Every row at spread 1 and 2 is 1.000 or 0.9995, and every 1 proposer row is 1.000. No row is near 0.5, so hypothesis 2 (0.5 or below for 3 or more proposers somewhere in range) did not show up in this grid.
- `reply_mode="first"` gives lower round 1 rates than `"max"` once there are 3 or more proposers, for example 0.7890 against 0.9005 at 3 recorders, 5 proposers, spread 16.
- Round 2 given round 1 failed was below round 1 in 48 of the 49 rows where round 2 was reached. The one exception had 1 trial behind it. This is against hypothesis 3, but selection is still the obvious rival explanation.
- **Agreement broke.** 129 of 192000 trials had two proposers decide different values, in 26 of 96 rows, 39 under `"max"` and 90 under `"first"`, all with FIFO links and decided proposers continuing. The worst row is 17 of 2000 (3 recorders, 5 proposers, spread 64, `"first"`). Wednesday's tests only checked 900 trials at spread 16. A model that violates safety may also be wrong about how often rounds decide, so this has to be explained before any rate is reported.
- The 2 proposer rows are identical between `"max"` and `"first"` in every column. That may be correct for two proposers or may mean the reply mode is not reaching the code path that matters. Friday checks which.
- Priority ties: 0 in every row, so no tiebreak decided anything at `prio_range=2**32`. Undecided trials: 0 in every row.

## Friday: what broke and what survived

### What was wrong first

- **The model broke agreement.** Thursday's sweep had two proposers decide different values in 129 of 192000 trials. Tracing seed 2000057 (5 proposers, 3 recorders, spread 64, `first` replies) showed how: proposers 0 and 2 decided value 1 in round 1, while proposer 3 picked up value 4 at a higher priority from one recorder's reply during phase 1, carried it into phase 2, and phase 3 then carried value 4 into round 2 over the decided value. The post says phase 1 only spreads, so adopting there was our bug, not the protocol's.
- **A second rule broke it too.** A proposer that got rejected jumped to the recorder's step but kept its own proposal when that beat the recorder's. That lets a value skip phase 1 and land in phase 2 or a later round. On the worst Thursday row (2000 trials) the jump rule alone broke agreement 28 times and phase 1 adoption alone once. With both fixed, 0. Both old rules stay as arms (`jump_adopt="best"`, `phase1_adopt=True`) and a test pins a breaking seed for each.
- **My own check had a bug as well.** The first version of the Friday patch let phase 1 fall through to the phase 3 branch, which made it look like the fixes did not work (4 violations left). Caught by tracing a violating seed before believing it.
- **Wednesday's agreement test was too small to see it.** It ran 900 trials at spread 16, where the rate was about 1 in 2000. It now also runs the 2000 seeds of Thursday's worst row.
- **Round 2 below round 1 was mostly our start jitter.** Thursday had round 2 below round 1 in 48 of 49 rows. Delays are drawn fresh per message, so there is no lasting bad network per trial to select on. What differs is alignment: round 1 starts proposers within 0.5 median of each other, which is our choice, while round 2 starts wherever round 1 left them. Sweeping start jitter (`results/fri_jitter.csv`, 72 rows x 1000 trials) moves round 1 from about 0.99 at jitter 0 down to 0.77 to 0.89 at jitter 2, and at jitter 2 the mean gap between round 1 and round 2 is 0.000 (round 2 higher in 6 of 12 rows). At the other jitters round 2 is still lower, by 0.05 to 0.10 on average. On the fixed model at jitter 0.5, round 2 is below round 1 in 33 of 49 rows.
- **The 2 proposer rows being identical between `max` and `first` is correct.** A reply is built when the proposer's own message arrives, so with two proposers the other proposal is either already there, which makes it both the first and the max over our own, or not there at all. A test now checks this and checks that 3 proposers do differ.

### What survived

- On the fixed model, round 1 decides in 0.7765 (Wilson 95% 0.758 to 0.794) to 1.000 of trials across the 96 row grid, 0 agreement violations in 192000 trials (`results/sweep_fri.csv`). Rates moved at most 0.026 from Thursday's broken model.
- The rate is not pinned above 0.5 by construction. With 20 proposers and `first` replies it reaches 0.5825 (0.534 to 0.630) at spread 16 (`results/fri_many_proposers.csv`).
- **The reply rule decides which of the post's two sentences wins.** With `max` replies, round 1 rises slightly with proposer count at spread 16 (0.93, 0.93, 0.95 at 8, 12, 20 proposers), which is "the more likely they are to converge". With `first` replies it falls (0.73, 0.64, 0.58), which is "the more likely it is that replicas fail to decide". We cannot read the paper from here, so we do not know which rule QuePaxa uses. That is the honest headline so far.
- Hypothesis 3 (round 2 decides more often than round 1, from convergence) did not show up at any start jitter tried. Hypothesis 2 (0.5 or below for 3 or more proposers) did not show up in the 1 to 5 proposer grid and only came close at 20 proposers with `first` replies.

### Still weak

- The protocol is our reading of a blog post. Two of our rules were already unsafe, so others may be wrong in ways that do not break agreement but do move the rate.
- Round 1 rate depends on start jitter, which the post says nothing about, by up to 0.135 within one configuration (5 proposers, spread 4, `first` replies: 0.955 at jitter 0, 0.820 at jitter 2).
- No leader and no hedge timeout are modelled, so this is the slow path only, as stated at the top.

## Layout

- `sim.py`: zero-dependency, seeded discrete-event simulator of the four phases. `python3 sim.py 500` prints a smoke table, not a result.
- `test_sim.py`: harness tests
- `sweep.py`: the sweep that emits the number
- `checks/`: Friday's jitter and many-proposer checks, each prints CSV
- `results/`: raw output. `sweep.csv` is Thursday's run on the broken model, `sweep_fri.csv` the same grid on the fixed one, `fri_*.csv` the checks. `RUN.md` and `RUN_fri.md` say how each was produced.

## Finding, Method, Repro, Limits

Saturday's job, written around "What survived" above.
