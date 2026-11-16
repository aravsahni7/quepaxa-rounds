# quepaxa-rounds

**Inspired by [Choosing QuePaxa, an unusual consensus algorithm](https://blog.cloudflare.com/choosing-quepaxa/)**, João Pedro Leite, Bob Halley and James Larisch, Cloudflare, 11 Nov 2026.

Status: Monday scaffold. The hypothesis below was written before any code, and it stays here unedited whatever the week finds.

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

## Modelling choices still open (Tuesday)

The post describes the phases in prose, not pseudocode, and the paper (Tennage, Băsescu et al., 2023) cannot be read from the cloud sandbox. Every guess goes here and none of them is credited to Cloudflare.

- What a recorder returns in phase 2: the highest priority it stored in phase 1, or across phases.
- Whether proposers start a round at the same instant or with jitter.
- Priority range. Drawn from a small range, priorities can tie, so the range is an explicit arm and ties are counted.
- Whether a proposer that decides keeps sending messages that other proposers can see in the same round.

## Planned layout

- `sim.py`: zero-dependency, seeded discrete-event simulator of the four phases
- `test_sim.py`: harness tests, including the zero-spread and single-proposer cases that must decide every round
- `results/`: raw sweep output, written Thursday

## Finding, Method, Repro, What was wrong first, Limits

Not yet. These get written after Friday tries to break the result.
