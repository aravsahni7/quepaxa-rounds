# quepaxa-rounds

**Inspired by [Choosing QuePaxa, an unusual consensus algorithm](https://blog.cloudflare.com/choosing-quepaxa/)**, João Pedro Leite, Bob Halley and James Larisch, Cloudflare, 11 Nov 2026.

The post says the QuePaxa paper predicts each round has a 50% chance of deciding, "but in practice, that probability is much higher, thanks to convergence". It gives no number and no conditions. It also says two things that pull in opposite directions: "as more proposers submit proposals, the more likely they are to converge", and "the more proposers there are ... the more likely it is that replicas fail to decide in a round". This project puts a number on the first claim for the slow path (no leader fast path) in a seeded simulation of our reading of the protocol, swept over proposer count, recorder count and message delay spread, and finds that which of the two sentences holds depends on a detail the post does not give. The sweep framing and every protocol rule in the simulator are ours, not Cloudflare's.

## Finding

In this model the slow path decides in round 1 in 78% to 100% of trials for 1 to 5 proposers, never near 50%. Whether more proposers help or hurt depends on what a recorder sends back when several proposals reach it in one phase: the highest one so far (`max`) or the first one it saw (`first`). The post does not say which QuePaxa does, and we could not read the paper from where this was built.

Round 1 decision rate, 5 recorders, 2000 trials per cell (4 blocks of 500 with disjoint seeds), from `results/sweep_fri.csv`:

| proposers | reply | spread 1 | 2 | 4 | 8 | 16 | 64 |
|---|---|---|---|---|---|---|---|
| 2 | either | 1.000 | 1.000 | 0.979 | 0.949 | 0.924 | 0.933 |
| 3 | `max` | 1.000 | 1.000 | 0.978 | 0.934 | 0.913 | 0.903 |
| 3 | `first` | 1.000 | 1.000 | 0.965 | 0.904 | 0.876 | 0.870 |
| 5 | `max` | 1.000 | 1.000 | 0.988 | 0.950 | 0.915 | 0.875 |
| 5 | `first` | 1.000 | 1.000 | 0.940 | 0.817 | 0.795 | 0.779 |

Spread is the ratio between the slowest and fastest possible one way delay. With 2 proposers the two reply rules give identical results, which is correct (see "What was wrong first"). The lowest cell across the whole 96 row grid, which also covers 1 proposer and 3 recorders, is 0.7765 (Wilson 95% 0.758 to 0.794), at 3 recorders, 5 proposers, spread 64, `first`. Every 1 proposer row is 1.000. Across 192000 trials no two proposers decided different values and every trial eventually decided.

Pushing past the grid, 5 recorders, 400 trials per cell, from `results/fri_many_proposers.csv`:

| proposers | `max`, spread 16 | `first`, spread 16 | `max`, spread 64 | `first`, spread 64 |
|---|---|---|---|---|
| 8 | 0.930 | 0.725 | 0.835 | 0.678 |
| 12 | 0.933 | 0.643 | 0.848 | 0.668 |
| 20 | 0.950 | 0.583 (0.534 to 0.630) | 0.853 | 0.630 |

Under `max` replies more proposers leave round 1 about flat or slightly better, which reads like the post's "converge" sentence. Under `first` replies it falls toward 0.58, which reads like its "fail to decide" sentence. `max` beats `first` in all 16 grid rows with 3 or 5 proposers and spread 4 or more.

### Against the hypothesis

The hypothesis was written on Monday before any code and is kept as written:

> I believe the slow-path decision rate is far above 50% when link delays are similar, because every proposer then sees roughly the same majority and adopts the same top priority in phase 0. I also believe it falls as delay spread grows, since spread is what lets different proposers see different majorities, and that it falls with more proposers at high spread, so the "fail to decide" sentence wins over the "converge" sentence once the network is uneven.
>
> If true I would see:
>
> 1. Round 1 decision rate of at least 0.9 for 2 to 5 proposers when delays vary by under 2x across links.
> 2. The rate dropping as spread grows, and reaching 0.5 or below somewhere in the swept range for 3 or more proposers.
> 3. A round that follows a failed round deciding more often than round 1, because phase 3 carries the best proposal forward. This is the "convergence" the post credits.
>
> What would show I am wrong: a round 1 rate near 0.5 at low spread, a rate that rises with proposer count at high spread, or round 2 deciding no more often than round 1.

1. Held, but cheaply. At spread 1 and 2 every row is 1.000 or 0.9995. Spread 1 decides by construction, so only the spread 2 rows say anything.
2. Half held. The rate falls with spread up to 16 in every 3 and 5 proposer row, then mostly levels off. It never reaches 0.5 in the grid. With 20 proposers and `first` replies it gets to 0.58.
3. Not supported. Round 2, given round 1 failed, decides less often than round 1 in 33 of the 49 rows where it was reached. Most of that gap comes from our start jitter, not from the protocol (see below), and at no jitter we tried does round 2 come out ahead on average.

The "rises with proposer count" kill condition happened under `max` replies and did not under `first`, which is the finding above.

## Method

- `sim.py` is a zero dependency, seeded discrete event simulator of the four phases as the post describes them in prose. A step is `4*round + phase`. A recorder freezes a step when it first sees a later one and rejects late messages for it, and a rejected proposer jumps to the recorder's step taking the recorder's proposal. Phase 0 and 1 replies carry the recorder's highest or first proposal in that step (the two arms). Phase 2 and 3 replies carry the frozen highest proposal of the previous step. Phase 2 decides when every reply in the majority equals the proposer's own proposal. Phase 1 only spreads.
- Each round a proposer gives its carried value a fresh random priority from `range(2**32)`, so a value several proposers carry gets several draws. Ties break on proposer id and are counted: 0 ties in every row, so no tiebreak decided anything.
- Links are FIFO per pair, as over one TCP connection. Delay per message is `median * spread**(u - 0.5)` with `u` uniform, drawn fresh per message. Proposers start with jitter uniform in `[0, 0.5 * median)`.
- A proposer that decides keeps running with its value at a reserved top priority, so the others can still finish. Round 1 rate does not depend on this choice, since it only looks at the first decision.
- **Round decides** means at least one proposer decides in phase 2 of that round. No leader and no hedge timeout are modelled. The full list of choices is `MODEL_CHOICES` in `sim.py`.
- `sweep.py` runs each row as 4 seed blocks with disjoint seeds and reports the round 1 rate with a Wilson 95% interval, the lowest and highest block, round 2 given round 1 failed, agreement violations, undecided trials and ties.
- `test_sim.py` has 27 tests on the harness itself: delay bounds, the recorder freeze and both reply modes, the rate arithmetic, the Wilson interval, determinism per seed, 1 proposer and spread 1 always deciding, agreement over the 2000 seeds of the worst Thursday row, a pinned breaking seed for each old unsafe rule, and that round 1 can fail so the metric is not fixed by construction. Five bugs planted one at a time in `sim.py` each failed at least one test.

## Repro

Python 3.11, no packages.

    python3 -m unittest -v test_sim                                   # 27 tests, about 5 s
    python3 sweep.py --full --trials 500 --out results/sweep_fri.csv  # 96 rows x 2000 trials, about 4 min
    python3 checks/many_proposers.py > results/fri_many_proposers.csv # about 40 s
    python3 checks/jitter.py > results/fri_jitter.csv                 # about 70 s

Same seeds give the same files. `results/RUN.md` and `results/RUN_fri.md` record how each committed file was produced. `results/sweep.csv` is Thursday's run on the broken model, kept as the record of what it said.

## What was wrong first

Each of these looked like a result or a working model before it was caught.

- **Non-FIFO links made a lone proposer fail.** One proposer must always decide in round 1, but with messages free to overtake each other it sometimes did not, since a recorder that got the step 2 message before the step 1 message had no step 1 summary to report. FIFO links fixed it, and a test pins it.
- **Stopping a proposer once it decided let others decide something else later**, 7 of 400 trials at 3 proposers, spread 16. Keeping decided proposers running fixed that in the checks we ran, but see the next two bullets.
- **The model broke agreement anyway.** Thursday's full sweep had two proposers decide different values in 129 of 192000 trials. Tracing one seed showed a proposer adopting a higher proposal from a reply during phase 1 and carrying it into phase 2 and the next round, over a value already decided. The post says phase 1 only spreads, so that was our bug.
- **A second rule broke it too.** A rejected proposer jumped to the recorder's step but kept its own proposal when that beat the recorder's, letting a value skip phase 1. On Thursday's worst row this rule alone broke agreement 28 times in 2000 trials and phase 1 adoption alone once. With both fixed, 0 in 192000. Both old rules stay as arms (`jump_adopt="best"`, `phase1_adopt=True`) with a test each. Round 1 rates moved by at most 0.026 between the broken and fixed models.
- **My first fix had a bug of its own.** The patch let phase 1 fall through to the phase 3 branch, which left 4 violations and made it look like the fixes did not work. Caught by tracing a violating seed before believing it.
- **Wednesday's agreement test was too small to see any of this.** 900 trials at spread 16, where the failure rate was about 1 in 2000. It now runs Thursday's worst row in full.
- **Round 2 below round 1 looked like evidence against convergence.** Thursday had round 2 below round 1 in 48 of 49 rows. Delays are drawn fresh per message, so there is no lasting bad network per trial to select on. What differs is alignment: round 1 starts proposers within half a median of each other, which is our choice, while round 2 starts wherever round 1 left them. With start jitter at 2 medians (`results/fri_jitter.csv`) the mean gap is 0.000, with round 2 higher in 6 of 12 rows. At the other jitters round 2 is still lower by 0.05 to 0.10 on average, so hypothesis 3 still fails, but the Thursday gap was mostly our setup.
- **The 2 proposer rows are identical under `max` and `first`.** This looked like the reply rule not reaching the code that matters. It is correct: a reply is built when the proposer's own message arrives, so the other proposal is either already there, which makes it both first and max over ours, or not there at all. A test checks this and checks that 3 proposers do differ.

## Limits

- **The protocol is our reading of a blog post, not the paper or Cloudflare's code.** Two of our rules were already unsafe and were only caught because agreement broke. Other rules may be wrong in ways that leave agreement intact but move the rate, and the headline is itself about a rule we had to guess.
- Round 1 rate depends on start jitter, which the post says nothing about, by up to 0.135 in one configuration (5 proposers, spread 4, `first` replies: 0.955 at jitter 0, 0.820 at jitter 2, 0.899 at jitter 8). Every grid number above uses jitter 0.5 median.
- This is the slow path only. No leader fast path, no hedge timeout, no crashes, no lost messages. Cloudflare runs QuePaxa with a leader and a hedge timeout, so these numbers are not how often their system decides a round.
- The delay model draws each message independently. Real networks have slow links that stay slow, which may matter more for round 2 than round 1.
- The many proposer rows have 400 trials each, so their 95% intervals are up to about plus or minus 0.05. The 2000 trial grid stops at 5 proposers.
- "Much higher than 50%" is matched by any number in this range, so the finding is not that the post is right. It is that the size of "much higher", and whether more proposers help, hang on a reply rule the post leaves out.
- Nothing here tests the paper's 50% figure. The post only quotes it, and we have not read the paper, so we do not know what model it assumes.

## Layout

- `sim.py`: the simulator. `python3 sim.py 500` prints a smoke table, not a result.
- `test_sim.py`: harness tests
- `sweep.py`: the sweep that emits the number
- `checks/`: Friday's jitter and many proposer checks, each prints CSV
- `results/`: raw output, never edited by hand
