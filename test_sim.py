"""Tests on the harness itself, since a bug in the simulator invalidates the
number. Run with: python3 -m unittest -v test_sim
"""

import unittest

from sim import Recorder, best, draw_delay, per_round_rates, run_trial
from sweep import run_row, wilson

import random


class DelayTests(unittest.TestCase):
    def test_no_spread_is_constant(self):
        rng = random.Random(1)
        self.assertEqual({draw_delay(rng, 2.0, 1.0) for _ in range(50)}, {2.0})

    def test_spread_bounds(self):
        # The slowest message must be at most spread times the fastest,
        # since that is how spread is defined in the README.
        rng = random.Random(2)
        ds = [draw_delay(rng, 1.0, 16.0) for _ in range(5000)]
        self.assertGreaterEqual(min(ds), 0.25)
        self.assertLess(max(ds), 4.0)
        self.assertGreater(max(ds) / min(ds), 12.0)

    def test_median_holds(self):
        rng = random.Random(3)
        ds = sorted(draw_delay(rng, 1.0, 16.0) for _ in range(4001))
        self.assertAlmostEqual(ds[2000], 1.0, delta=0.1)


class BestTests(unittest.TestCase):
    def test_none_and_order(self):
        a, b = (5, 0, "a"), (7, 1, "b")
        self.assertEqual(best(None, a), a)
        self.assertEqual(best(a, None), a)
        self.assertEqual(best(a, b), b)

    def test_tie_breaks_on_pid(self):
        self.assertEqual(best((5, 0, "a"), (5, 2, "c")), (5, 2, "c"))

    def test_value_does_not_break_ties(self):
        # Only (priority, pid) count, so equal keys keep the first argument.
        self.assertEqual(best((5, 1, "x"), (5, 1, "y")), (5, 1, "x"))


class RecorderTests(unittest.TestCase):
    def test_max_mode_reports_highest(self):
        r = Recorder("max")
        r.receive(0, (3, 0, "a"))
        ok, step, view, prev = r.receive(0, (9, 1, "b"))
        self.assertTrue(ok)
        self.assertEqual(view, (9, 1, "b"))
        ok, step, view, prev = r.receive(0, (1, 2, "c"))
        self.assertEqual(view, (9, 1, "b"))

    def test_first_mode_reports_first(self):
        r = Recorder("first")
        r.receive(0, (3, 0, "a"))
        ok, step, view, prev = r.receive(0, (9, 1, "b"))
        self.assertEqual(view, (3, 0, "a"))

    def test_late_step_rejected_and_frozen(self):
        r = Recorder("max")
        r.receive(0, (3, 0, "a"))
        r.receive(1, (3, 0, "a"))
        ok, step, view, prev = r.receive(0, (99, 1, "b"))
        self.assertFalse(ok)
        self.assertEqual(step, 1)
        # The frozen step 0 summary must not have absorbed the late proposal.
        self.assertEqual(r.prev_max, (3, 0, "a"))

    def test_prev_only_for_adjacent_step(self):
        r = Recorder("max")
        r.receive(0, (3, 0, "a"))
        r.receive(1, (4, 0, "a"))
        self.assertEqual(r.prev_max, (3, 0, "a"))
        ok, step, view, prev = r.receive(3, (5, 0, "a"))
        self.assertIsNone(prev)


class RatesTests(unittest.TestCase):
    def test_conditional_rates(self):
        fake = [{"first_round": x} for x in (1, 1, 2, 3, None)]
        rates = per_round_rates(fake, 3)
        self.assertEqual(rates[0], (1, 5, 2 / 5))
        self.assertEqual(rates[1], (2, 3, 1 / 3))
        self.assertEqual(rates[2], (3, 2, 1 / 2))

    def test_wilson(self):
        lo, hi = wilson(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)
        self.assertEqual(wilson(0, 0), (None, None))
        self.assertEqual(wilson(10, 10)[1], 1.0)


class TrialTests(unittest.TestCase):
    def test_deterministic(self):
        for seed in range(20):
            self.assertEqual(run_trial(seed, n_prop=3, spread=16.0),
                             run_trial(seed, n_prop=3, spread=16.0))

    def test_seeds_differ(self):
        # Fixture exhaustion check: different seeds must give different runs,
        # not one recycled execution.
        outs = {run_trial(s, n_prop=3, spread=16.0)["values"][0]
                for s in range(200)}
        self.assertGreater(len(outs), 1)
        rounds = {run_trial(s, n_prop=3, spread=16.0)["first_round"]
                  for s in range(300)}
        self.assertGreater(len(rounds), 1)

    def test_single_proposer_always_round_one(self):
        for spread in (1.0, 4.0, 16.0, 64.0):
            for n_rec in (3, 5):
                for seed in range(100):
                    x = run_trial(seed, n_prop=1, n_rec=n_rec, spread=spread)
                    self.assertEqual(x["first_round"], 1)

    def test_equal_delays_decide_round_one(self):
        # Spread 1 is the degenerate case: everyone sees the same majority,
        # so the rate is 1 by construction. A sanity check, not a result.
        for n_prop in (2, 3, 5):
            for seed in range(100):
                x = run_trial(seed, n_prop=n_prop, spread=1.0)
                self.assertEqual(x["first_round"], 1)

    def test_metric_is_not_fixed_by_construction(self):
        # If round 1 always decided at high spread, the sweep would measure
        # nothing. It must be able to fail.
        r1 = [run_trial(s, n_prop=3, spread=16.0)["first_round"]
              for s in range(400)]
        self.assertLess(r1.count(1), 400)

    def test_agreement_holds(self):
        for n_prop in (2, 3, 5):
            for seed in range(300):
                x = run_trial(seed, n_prop=n_prop, spread=16.0)
                self.assertTrue(x["agree"], (n_prop, seed))

    def test_agreement_holds_on_thursday_worst_row(self):
        # Thursday's sweep broke agreement 17 times in this row. Same seeds.
        for seed in [b * 1_000_000 + i for b in range(4) for i in range(500)]:
            x = run_trial(seed, n_prop=5, n_rec=3, spread=64.0,
                          reply_mode="first")
            self.assertTrue(x["agree"], seed)

    def test_tuesday_rules_break_agreement(self):
        # Each old rule on its own breaks agreement on a known seed, so the
        # test above would catch either one coming back.
        cfg = dict(n_prop=5, n_rec=3, spread=64.0, reply_mode="first")
        self.assertFalse(run_trial(357, jump_adopt="best", **cfg)["agree"])
        self.assertFalse(run_trial(3000446, phase1_adopt=True,
                                   **cfg)["agree"])
        self.assertFalse(run_trial(357, phase1_adopt=True, jump_adopt="best",
                                   **cfg)["agree"])

    def test_two_proposers_reply_mode_cannot_matter(self):
        # A reply is built when the proposer's own message lands, so with two
        # proposers the other proposal is either already there, which makes
        # it both first and the max over our own, or absent. Same trial.
        for seed in range(300):
            a = run_trial(seed, n_prop=2, spread=16.0, reply_mode="max")
            b = run_trial(seed, n_prop=2, spread=16.0, reply_mode="first")
            self.assertEqual(a, b, seed)
        diff = sum(run_trial(s, n_prop=3, spread=16.0, reply_mode="max")
                   != run_trial(s, n_prop=3, spread=16.0, reply_mode="first")
                   for s in range(300))
        self.assertGreater(diff, 0)

    def test_decided_value_was_proposed(self):
        # Values are proposer ids, so a decided value must be one of them.
        for seed in range(200):
            x = run_trial(seed, n_prop=3, spread=16.0)
            for v in x["values"]:
                self.assertIn(v, (None, 0, 1, 2))

    def test_everyone_eventually_decides(self):
        for seed in range(200):
            x = run_trial(seed, n_prop=5, spread=64.0)
            self.assertNotIn(None, x["decide_rounds"])

    def test_tiny_prio_range_counts_ties(self):
        # With one possible priority every extra proposer collides each
        # round, so the tie counter must see at least n_prop - 1 per trial.
        x = run_trial(0, n_prop=3, prio_range=1, spread=1.0)
        self.assertGreaterEqual(x["ties"], 2)
        self.assertEqual(run_trial(0, n_prop=3, spread=1.0)["ties"], 0)


class SweepTests(unittest.TestCase):
    def test_row_shape(self):
        row = run_row(n_prop=1, n_rec=3, spread=16.0, trials=20, blocks=2)
        self.assertEqual(row["trials"], 40)
        self.assertEqual(row["r1"], 1.0)
        self.assertEqual(row["pooled"], 1.0)
        self.assertIsNone(row["r2"])
        self.assertEqual(row["viol"], 0)

    def test_blocks_use_distinct_seeds(self):
        a = run_row(n_prop=3, n_rec=5, spread=16.0, trials=50, blocks=1,
                    base_seed=0)
        b = run_row(n_prop=3, n_rec=5, spread=16.0, trials=50, blocks=1,
                    base_seed=1_000_000)
        two = run_row(n_prop=3, n_rec=5, spread=16.0, trials=50, blocks=2)
        hits = round(a["r1"] * 50) + round(b["r1"] * 50)
        self.assertAlmostEqual(two["r1"], hits / 100)

    def test_pooled_is_inverse_mean_rounds(self):
        row = run_row(n_prop=3, n_rec=5, spread=16.0, trials=100, blocks=2)
        self.assertEqual(row["undec"], 0)
        self.assertGreater(row["pooled"], 0.0)
        # A trial that misses round 1 needs at least two rounds, so
        # mean rounds >= r1 + 2 * (1 - r1) and pooled <= 1 / (2 - r1).
        self.assertLessEqual(row["pooled"], 1 / (2 - row["r1"]) + 1e-12)


if __name__ == "__main__":
    unittest.main()
