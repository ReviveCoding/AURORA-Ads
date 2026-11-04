import unittest
from types import SimpleNamespace

import numpy as np
from scipy.integrate import quad
from scipy.stats import lognorm

from aurora.auction_learning import (
    AuctionObservation,
    CensoredLognormalMarket,
    batch_grid_bid,
)
from aurora.auction_settlement import settle_variable_bids
from aurora.bidder import GRID, grid_bid_forecast
from aurora.fast_bidder import LearnedBidder, RandomizedGridBidder
from aurora.simulator import settle_reference
from aurora.state import Action


class AuctionLearningTest(unittest.TestCase):
    def test_common_slow_multiplier_against_independent_quadrature(self):
        values, mus = np.array([0.0, 0.3, 1.7]), np.array([-0.3, 0.1, 0.5])
        for mode in ("first_price", "second_price"):
            for multiplier in (0.9, 1.1):
                actual = batch_grid_bid(
                    values,
                    mus,
                    0.4,
                    payment_mode=mode,
                    scarcity=0.5,
                    multiplier=multiplier,
                )
                expected = []
                for value, mu in zip(values, mus):
                    market = lognorm(s=0.4, scale=np.exp(mu))
                    grid = GRID * multiplier
                    payment = (
                        grid * market.cdf(grid)
                        if mode == "first_price"
                        else np.array(
                            [
                                quad(
                                    lambda m: m * market.pdf(m), 0.0, bid, epsabs=1e-10
                                )[0]
                                for bid in grid
                            ]
                        )
                    )
                    score = value * market.cdf(grid) - 1.5 * payment
                    expected.append(GRID[np.argmax(score)])
                np.testing.assert_array_equal(actual, expected)

    def test_empty_opportunity_batch_never_calls_predictors(self):
        class NotCalled:
            def predict(self, _):
                raise AssertionError("No opportunities, no predictor call")

        bidder = LearnedBidder("grid_utility", NotCalled(), NotCalled())
        result = bidder.propose(
            np.empty((0, 7)), SimpleNamespace(), Action.NO_CHANGE, 1.0, 0.0
        )
        self.assertEqual(len(result.base_bids), 0)

    def test_bid_sampling_is_keyed_not_consumption_dependent(self):
        bidder = RandomizedGridBidder("unit-world")
        snapshot = SimpleNamespace(campaign=0, interval=12)
        before = bidder.propose(
            np.zeros((16, 7)), snapshot, Action.NO_CHANGE, 1.0, 0.0
        ).base_bids
        bidder.propose(
            np.zeros((100, 7)),
            SimpleNamespace(campaign=0, interval=11),
            Action.NO_CHANGE,
            1.0,
            0.0,
        )
        after = bidder.propose(
            np.zeros((16, 7)), snapshot, Action.NO_CHANGE, 1.0, 0.0
        ).base_bids
        np.testing.assert_array_equal(before, after)

    def test_variable_bid_guards_match_independent_reference(self):
        generator = np.random.default_rng(616)
        for mode in ("first_price", "second_price"):
            bids = generator.choice([0.0, 0.25, 1.0, 3.0], 300)
            market = generator.lognormal(0.0, 0.6, 300)
            admission = generator.uniform(size=300) < 0.6
            actual = settle_variable_bids(bids, market, admission, 40000, mode)
            wins, payment, balance = settle_reference(
                bids, market, admission, 40000, mode
            )
            np.testing.assert_array_equal(actual.wins, wins)
            np.testing.assert_array_equal(actual.payments, payment)
            self.assertEqual(actual.balance, balance)
        # An unaffordable large bid must NOT prevent a later affordable bid.
        actual = settle_variable_bids(
            np.array([3.0, 0.25]),
            np.array([2.0, 0.1]),
            np.array([True, True]),
            2500,
            "second_price",
            uniform_grid_multiplier=1.0,
        )
        self.assertFalse(actual.eligible[0])
        self.assertTrue(actual.wins[1])
        self.assertEqual(actual.executed_probabilities[0], 7 / 8)
        self.assertEqual(actual.executed_probabilities[1], 1 / 8)
        skipped = settle_variable_bids(
            np.array([1.0]),
            np.array([0.1]),
            np.array([False]),
            50000,
            "second_price",
            uniform_grid_multiplier=1.0,
        )
        self.assertEqual(skipped.executed_probabilities[0], 1.0)

    def test_batch_kernel_is_scalar_reference_for_both_prices(self):
        values = np.array([0.0, 0.1, 0.7, 2.0, 10.0])
        mus = np.array([-1.0, 0.0, 0.2, -0.2, 1.0])
        for mode in ("first_price", "second_price"):
            for scarcity in (0.0, 2.0):
                actual = batch_grid_bid(
                    values, mus, 0.4, payment_mode=mode, scarcity=scarcity
                )
                expected = [
                    grid_bid_forecast(
                        value_if_exposed=v,
                        log_price_mean=m,
                        log_price_sd=0.4,
                        payment_mode=mode,
                        scarcity_price=scarcity,
                    ).choice
                    for v, m in zip(values, mus)
                ]
                np.testing.assert_array_equal(actual, expected)

    def test_observable_schema_rejects_pending_and_loser_truth(self):
        kwargs = dict(
            cohort_id="fixture",
            origin_interval=0,
            observed_at_day=7 + 1 / 96,
            context=np.zeros((2, 7)),
            submitted_bid=np.ones(2),
            eligible=np.ones(2, dtype=bool),
            won=np.array([True, False]),
            payment=np.array([0.5, 0.0]),
            observed_gross=np.array([200.0, 0.0]),
        )
        AuctionObservation(**kwargs)
        with self.assertRaises(ValueError):
            AuctionObservation(**(kwargs | {"observed_at_day": 7.0}))
        with self.assertRaises(ValueError):
            AuctionObservation(**(kwargs | {"payment": np.array([0.5, 0.7])}))
        with self.assertRaises(ValueError):
            AuctionObservation(
                **(kwargs | {"observed_gross": np.array([200.0, 200.0])})
            )

    def test_censored_model_on_numerical_fixture_not_empirical_evidence(self):
        generator = np.random.default_rng(714)
        context = generator.normal(size=(1200, 7))
        price = np.exp(0.2 * context[:, 1] + 0.4 * generator.normal(size=1200))
        bids = generator.choice([0.5, 0.75, 1.0, 1.5, 2.0], 1200)
        wins = bids >= price
        for mode in ("first_price", "second_price"):
            payments = np.where(
                wins,
                np.ceil((price if mode == "second_price" else bids) * 10000) / 10000,
                0.0,
            )
            model = CensoredLognormalMarket(mode).fit(context, bids, wins, payments)
            mu, sd = model.predict(context)
            self.assertLess(np.sqrt(np.mean((mu - 0.2 * context[:, 1]) ** 2)), 0.1)
            self.assertLess(abs(sd - 0.4), 0.08)
            self.assertTrue(model.fit_diagnostics["optimizer_success"])


if __name__ == "__main__":
    unittest.main()
