from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.simulator import Snapshot, StaticController, WorldSpec, rng, run_world, settle_constant_bid, settle_reference
from aurora.state import Action


class SimulatorTests(unittest.TestCase):
    def test_matured_callback_exact_probability_and_no_duplicate_reward(self):
        class Logger:
            def __init__(self):
                self.rows = []
                self.actions = []

            def probabilities(self, snapshot):
                return np.array([0., 0., 1., 0., 0., 0.])

            def executed(self, snapshot, action, probability, spend, overhead):
                self.actions.append((action, probability))

            def observe(self, row):
                self.rows.append(row)

        logger = Logger()
        spec = WorldSpec("cohorts", "weak_or_no_heterogeneity", campaigns=1, intervals=4, nominal_arrivals=20, stage="smoke")
        run_world(spec, logger)
        self.assertEqual(logger.actions, [(Action.BID_MULTIPLIER_UP, 1.), (Action.NO_CHANGE, 1.), (Action.BID_MULTIPLIER_UP, 1.), (Action.NO_CHANGE, 1.)])
        self.assertEqual(len(logger.rows), 4)
        self.assertEqual(len({row.cohort_id for row in logger.rows}), 4)
        self.assertTrue(all(row.observed_at_day >= (row.origin_interval + 1) / 96 + 7 for row in logger.rows))
        self.assertTrue(all(sum(row.observed_delay_counts) == row.observed_purchase_count for row in logger.rows))
        self.assertFalse({"organic_value", "delta", "family", "true_reward"} & set(logger.rows[0].__dataclass_fields__))
    def test_rng_channel_and_call_order_invariance(self):
        first = rng("fixture", 0, 0, "purchase").uniform(size=20)
        rng("fixture", 0, 0, "irrelevant").normal(size=999)
        np.testing.assert_array_equal(first, rng("fixture", 0, 0, "purchase").uniform(size=20))
        self.assertNotEqual(first[0], rng("fixture", 0, 1, "purchase").uniform())

    def test_budget_vectorized_vs_independent_sequential(self):
        random = np.random.default_rng(91)
        for mode in ("first_price", "second_price"):
            for _ in range(30):
                bid = float(random.choice([.25, .5, 1, 1.5, 3]))
                market = random.lognormal(0, .4, 50)
                admitted = random.uniform(size=50) < .6
                balance = int(random.integers(0, 250000))
                vector = settle_constant_bid(bid, market, admitted, balance, mode)
                reference = settle_reference(np.full(50, bid), market, admitted, balance, mode)
                for result, expected in zip(vector, reference):
                    np.testing.assert_array_equal(result, expected)

    def test_same_arm_no_ad_zero_effect_and_truth_isolation(self):
        spec = WorldSpec("fixture", "weak_or_no_heterogeneity", campaigns=1, intervals=4, nominal_arrivals=100, effect_override=0, stage="smoke")
        first = run_world(spec, StaticController())
        self.assertEqual(first, run_world(spec, StaticController()))
        self.assertEqual(first.unique_purchase_value, first.no_ad_purchase_value)
        self.assertLessEqual(first.utility, 0)
        no_ad = run_world(spec, StaticController(), no_ad=True)
        self.assertEqual(no_ad.utility, 0)
        self.assertEqual(no_ad.spend, 0)
        self.assertEqual(no_ad.snapshot_reward_updates_before_day7, 0)
        self.assertEqual(no_ad.final_pending_exposures, 0)
        self.assertFalse({"family", "fault", "true_effect", "purchase_draw"} & set(Snapshot.__dataclass_fields__))

    def test_effect_sign_unique_occasion_and_unfrozen_final_rejection(self):
        spec = WorldSpec("sign", "weak_or_no_heterogeneity", campaigns=1, intervals=4, nominal_arrivals=1000, budget_per_campaign=10000, effect_override=1, stage="smoke")
        positive = run_world(spec, StaticController())
        negative = run_world(replace(spec, effect_override=-1), StaticController())
        self.assertGreaterEqual(positive.purchases, positive.no_ad_purchases)
        self.assertLessEqual(negative.purchases, negative.no_ad_purchases)
        self.assertLessEqual(positive.purchases, positive.opportunities)
        with self.assertRaises(ValueError):
            replace(spec, stage="final")
