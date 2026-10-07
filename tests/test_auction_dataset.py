import unittest

import numpy as np

from aurora.auction_dataset import AuctionCollector, require_disjoint_cohorts
from aurora.auction_learning import AuctionObservation


def fixture(name="numerical-fixture"):
    return AuctionObservation(name, 0, 7 + 1 / 96, np.zeros((4, 7)),
                              np.array([1., 1., 0., 3.]), np.array([True, True, False, False]),
                              np.array([True, False, False, False]), np.array([.5, 0., 0., 0.]),
                              np.array([200., 0., 0., 0.]), np.full(4, .125))


class AuctionDatasetTest(unittest.TestCase):
    def test_only_submitted_eligible_prices_and_exposed_values(self):
        collector = AuctionCollector()
        source = fixture()
        collector.observe_auction(source)
        source.observed_gross[0] = 900.
        dataset = collector.dataset()
        market = dataset.market_inputs()
        np.testing.assert_array_equal(market[1], [1., 1.])
        np.testing.assert_array_equal(market[2], [True, False])
        context, value, mature, ids = dataset.value_inputs()
        self.assertEqual(context.shape, (1, 7))
        np.testing.assert_array_equal(value, [200.])
        self.assertTrue(mature.all())
        self.assertEqual(len(ids), 1)
        with self.assertRaises(ValueError):
            collector.observe_auction(fixture())

    def test_cohort_disjointness_and_unknown_probability_not_fabricated(self):
        first = AuctionCollector()
        first.observe_auction(fixture("train"))
        second = AuctionCollector()
        second.observe_auction(fixture("calibration"))
        require_disjoint_cohorts(first.dataset(), second.dataset())
        with self.assertRaises(ValueError):
            require_disjoint_cohorts(first.dataset(), first.dataset())
        known = fixture("known")
        unknown = AuctionObservation("unknown", 0, known.observed_at_day, known.context,
                                     known.submitted_bid, known.eligible, known.won, known.payment,
                                     known.observed_gross)
        with self.assertRaises(ValueError):
            first.observe_auction(unknown)
        third = AuctionCollector()
        third.observe_auction(unknown)
        self.assertIsNone(third.dataset().executed_bid_probability)

    def test_empty_cohort_is_preserved_not_fake_exposure(self):
        collector = AuctionCollector()
        collector.observe_auction(AuctionObservation("empty", 0, 7 + 1 / 96,
                                  np.empty((0, 7)), np.empty(0), np.empty(0, dtype=bool),
                                  np.empty(0, dtype=bool), np.empty(0), np.empty(0)))
        dataset = collector.dataset()
        self.assertEqual(dataset.cohort_ids, ("empty",))
        self.assertEqual(dataset.value_inputs()[0].shape, (0, 7))
        self.assertEqual(len(dataset.market_inputs()[0]), 0)


if __name__ == "__main__":
    unittest.main()
