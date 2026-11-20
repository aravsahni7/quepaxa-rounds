"""Seeded discrete-event simulator of QuePaxa's slow path.

Zero dependencies. Models proposers and recorders exchanging messages with
random one-way delays, following the four phases as the Cloudflare post
describes them in prose. Every guess about details the post leaves out is
listed in MODEL_CHOICES, so none of it gets credited to the post.

There is no leader here: every proposer draws a random priority each round,
so phase 0 can never decide and the only way to decide is phase 2.
"""

import heapq
import random

PHASES = 4

MODEL_CHOICES = [
    "A step is 4*round + phase. A recorder keeps one current step and the "
    "highest proposal it accepted in that step and the step before it.",
    "A recorder freezes a step as soon as it sees a message for a later step. "
    "Messages for a frozen step are rejected and the reply tells the proposer "
    "the recorder's current step, so a proposer never waits forever.",
    "A proposer that gets a rejection jumps to the recorder's step, takes the "
    "recorder's best proposal for that step as its own, and broadcasts again "
    "(jump_adopt='recorder'). The Tuesday model kept its own proposal when it "
    "beat the recorder's (jump_adopt='best'), which lets a value that never "
    "went through phase 1 into a later step and broke agreement.",
    "Phase 0 and phase 1 replies carry the recorder's highest proposal so far "
    "in the current step ('max'), or the first one it accepted in that step "
    "('first'). Which one is an arm, since the post says 'highest' and the "
    "paper may use first.",
    "Proposers adopt the best reply in phase 0 only. Phase 1 only spreads, as "
    "the post describes it (phase1_adopt=False). The Tuesday model also "
    "adopted in phase 1 (phase1_adopt=True), which can carry a value into "
    "phase 2 that a majority never recorded in phase 1.",
    "Phase 2 and phase 3 replies carry the frozen highest proposal of the "
    "previous step. Phase 2 decides when every reply in the majority equals "
    "the proposer's own adopted proposal.",
    "At the start of every round a proposer gives its carried value a fresh "
    "random priority, so a value held by several proposers gets several draws.",
    "Priorities are integers drawn from range(prio_range). Ties break on "
    "proposer id, and ties are counted, since a small range makes the "
    "tiebreak decide the outcome.",
    "A proposer that decides stops proposing (decided_continue=False), or "
    "keeps running phases with its decided value at a reserved top priority "
    "(decided_continue=True). Either way the others keep going, so agreement "
    "can be checked across rounds.",
    "Links are FIFO per (sender, receiver) pair when fifo=True, as over one "
    "TCP connection. With fifo=False a later step can overtake an earlier one.",
    "Each message's one-way delay is median * spread**(u - 0.5), u uniform "
    "in [0, 1), so the slowest message is spread times the fastest.",
    "Proposers start round 1 at a time uniform in [0, start_jitter * median).",
]


def draw_delay(rng, median, spread):
    if spread <= 1.0:
        return median
    return median * spread ** (rng.random() - 0.5)


def best(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return a if a[:2] >= b[:2] else b


class Recorder:
    def __init__(self, reply_mode):
        self.step = -1
        self.cur_max = None
        self.cur_first = None
        self.prev_max = None
        self.reply_mode = reply_mode

    def receive(self, step, prop):
        """Returns (accepted, recorder_step, current_view, prev_max)."""
        if step < self.step:
            return (False, self.step, self.cur_max, self.prev_max)
        if step > self.step:
            # The step we are leaving is frozen. Its max becomes prev only if
            # it is the step right before the new one.
            self.prev_max = self.cur_max if step == self.step + 1 else None
            self.step = step
            self.cur_max = prop
            self.cur_first = prop
        else:
            self.cur_max = best(self.cur_max, prop)
        view = self.cur_first if self.reply_mode == "first" else self.cur_max
        return (True, self.step, view, self.prev_max)


class Proposer:
    def __init__(self, pid):
        self.pid = pid
        self.step = None
        self.prop = None  # (priority, tiebreak, value)
        self.replies = {}
        self.decided = None
        self.decided_round = None


def run_trial(seed, n_prop=3, n_rec=5, spread=4.0, median=1.0,
              start_jitter=0.5, prio_range=2 ** 32, reply_mode="max",
              max_rounds=50, fifo=True, decided_continue=True,
              phase1_adopt=False, jump_adopt="recorder"):
    """Runs one instance until every proposer decides or max_rounds pass.

    Returns a dict with the round each proposer decided in, the values they
    decided, and how many phase-0 priority ties happened.
    """
    rng = random.Random(seed)
    quorum = n_rec // 2 + 1
    recs = [Recorder(reply_mode) for _ in range(n_rec)]
    props = [Proposer(i) for i in range(n_prop)]
    events = []
    seq = 0
    ties = 0
    phase0_draws = {}
    last_arrival = {}
    top = (prio_range, -1)

    def arrival(now, link):
        t = now + draw_delay(rng, median, spread)
        if fifo:
            t = max(t, last_arrival.get(link, 0.0) + 1e-9)
            last_arrival[link] = t
        return t

    def push(t, kind, payload):
        nonlocal seq
        heapq.heappush(events, (t, seq, kind, payload))
        seq += 1

    def new_priority(p, rnd):
        nonlocal ties
        prio = rng.randrange(prio_range)
        draws = phase0_draws.setdefault(rnd, [])
        if prio in draws:
            ties += 1
        draws.append(prio)
        return (prio, p.pid, p.prop[2] if p.prop else p.pid)

    def enter(p, step, now):
        p.step = step
        p.replies = {}
        if step // PHASES >= max_rounds:
            return
        if p.decided is not None:
            p.prop = top + (p.decided,)
        elif step % PHASES == 0:
            p.prop = new_priority(p, step // PHASES)
        for r in range(n_rec):
            push(arrival(now, ("p", p.pid, r)), "to_rec",
                 (r, p.pid, step, p.prop))

    for p in props:
        push(rng.random() * start_jitter * median, "start", p.pid)

    while events:
        if all(p.decided is not None for p in props):
            break
        now, _, kind, payload = heapq.heappop(events)
        if kind == "start":
            enter(props[payload], 0, now)
        elif kind == "to_rec":
            r, pid, step, prop = payload
            reply = recs[r].receive(step, prop)
            push(arrival(now, ("r", r, pid)), "to_prop",
                 (pid, r, step, reply))
        elif kind == "to_prop":
            pid, r, step, (ok, rstep, view, prev) = payload
            p = props[pid]
            if step != p.step:
                continue
            if p.decided is not None and not decided_continue:
                continue
            if not ok:
                if rstep > p.step:
                    if jump_adopt == "best":
                        p.prop = best(p.prop, view)
                    else:
                        p.prop = view
                    enter(p, rstep, now)
                continue
            p.replies[r] = (view, prev)
            if len(p.replies) < quorum:
                continue
            phase = p.step % PHASES
            got = list(p.replies.values())
            if phase == 0 or phase == 1:
                if phase == 0 or phase1_adopt:
                    for v, _ in got:
                        p.prop = best(p.prop, v)
            elif p.decided is not None:
                pass
            elif phase == 2:
                if all(prev is not None and prev[:2] == p.prop[:2]
                       for _, prev in got):
                    if p.decided is None:
                        p.decided = p.prop[2]
                        p.decided_round = p.step // PHASES + 1
                    if not decided_continue:
                        continue
            else:
                for _, prev in got:
                    p.prop = best(p.prop, prev)
            enter(p, p.step + 1, now)

    rounds = [p.decided_round for p in props]
    values = [p.decided for p in props]
    decided_vals = {v for v in values if v is not None}
    first = min((x for x in rounds if x is not None), default=None)
    first_vals = {v for v, x in zip(values, rounds) if x == first}
    return {
        "decide_rounds": rounds,
        "values": values,
        "first_round": min((x for x in rounds if x is not None), default=None),
        "agree": len(decided_vals) <= 1,
        "agree_first_round": len(first_vals) <= 1,
        "ties": ties,
    }


def per_round_rates(results, max_round=5):
    """P(some proposer decides in round r | nobody decided before r)."""
    rates = []
    for r in range(1, max_round + 1):
        reached = [x for x in results
                   if x["first_round"] is None or x["first_round"] >= r]
        if not reached:
            rates.append((r, 0, None))
            continue
        hit = sum(1 for x in reached if x["first_round"] == r)
        rates.append((r, len(reached), hit / len(reached)))
    return rates


if __name__ == "__main__":
    import sys
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    print("n_prop n_rec spread  r1_rate r2_rate(n)  agree_viol undecided")
    for n_prop in (1, 2, 3, 5):
        for spread in (1.0, 2.0, 4.0, 16.0):
            res = [run_trial(seed, n_prop=n_prop, spread=spread)
                   for seed in range(trials)]
            rates = per_round_rates(res, 2)
            viol = sum(1 for x in res if not x["agree"])
            undec = sum(1 for x in res if x["first_round"] is None)
            r2 = rates[1]
            r2s = "-" if r2[2] is None else f"{r2[2]:.3f}"
            print(f"{n_prop:6d} {5:5d} {spread:6.1f}  {rates[0][2]:.3f}   "
                  f"{r2s}({r2[1]})  {viol:10d} {undec:9d}")
