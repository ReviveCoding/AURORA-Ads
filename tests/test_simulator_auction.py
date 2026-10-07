from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.auction_dataset import AuctionCollector
from aurora.fast_bidder import FixedBidder, RandomizedGridBidder
from aurora.simulator import StaticController, WorldSpec, run_world
from aurora.state import Action


class SimulatorAuctionTests(unittest.TestCase):
    def test_fixed_callback_physics_and_observed_matured_rows(self):
        for mode in ("first_price", "second_price"):
            spec = WorldSpec("auction_fixture_" + mode, "weak_or_no_heterogeneity", campaigns=1, intervals=4, nominal_arrivals=40, stage="smoke", payment_mode=mode)
            collector = AuctionCollector()
            result = run_world(spec, StaticController(Action.BID_MULTIPLIER_UP), bidder=FixedBidder(.75), auction_observer=collector.observe_auction)
            self.assertEqual(result, run_world(spec, StaticController(Action.BID_MULTIPLIER_UP), base_bid=.75))
            data = collector.dataset()
            self.assertEqual(len(data.cohort_ids), 4)
            self.assertIsNone(data.executed_bid_probability)
            self.assertTrue(np.all(data.observed_gross[~data.won] == 0))
            self.assertAlmostEqual(float(data.payment.sum()), result.spend)
            self.assertNotIn("market", data.__dataclass_fields__)

    def test_public_context_dual_and_exact_probability_projection(self):
        class Controller:
            dual = np.array([2.])
            parameters = SimpleNamespace(remove_dual=True)
            def choose(self, snapshot):
                return Action.NO_CHANGE
        class InspectBidder:
            def propose(self, context, snapshot, action, multiplier, scarcity):
                self_seen.append((context.shape[1], context.flags.writeable, scarcity))
                return random_bidder.propose(context, snapshot, action, multiplier, scarcity)
        self_seen = []
        spec = WorldSpec("uniform_bid_fixture", "weak_or_no_heterogeneity", campaigns=1, intervals=3, nominal_arrivals=50, budget_per_campaign=1, stage="smoke")
        random_bidder = RandomizedGridBidder(spec.world_id)
        collector = AuctionCollector()
        result = run_world(spec, Controller(), bidder=InspectBidder(), auction_observer=collector.observe_auction)
        self.assertEqual(self_seen, [(7, False, 0.)] * 3)
        data = collector.dataset()
        self.assertTrue(np.all((data.executed_bid_probability > 0) & (data.executed_bid_probability <= 1)))
        self.assertTrue(np.all(data.submitted_bid[~data.eligible] == 0))
        self.assertLessEqual(result.spend + result.operating_cost, result.initial_budget)

    def test_mature_exposure_denominator_is_observed_not_cohort_count(self):
        class Controller:
            def choose(self, snapshot):
                snapshots.append(snapshot)
                return Action.NO_CHANGE
            def observe(self, observation):
                matured.append(observation)
        snapshots, matured = [], []
        spec = WorldSpec("mature_exposure_fixture", "weak_or_no_heterogeneity", campaigns=1, intervals=674, nominal_arrivals=3, stage="smoke")
        run_world(spec, Controller())
        for snapshot in snapshots[-2:]:
            expected = sum(row.exposures for row in matured if row.observed_at_day <= snapshot.interval / 96)
            self.assertEqual(snapshot.matured_exposure_count, expected)
        self.assertEqual(len(matured), 674)
