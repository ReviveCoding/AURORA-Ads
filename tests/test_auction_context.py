from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.auction_context import public_auction_context


class AuctionContextTests(unittest.TestCase):
    def test_event_clocks_and_empty_batches_have_exact_public_width(self):
        x = np.array([[.1, .2, .3, .4], [-.1, -.2, -.3, -.4]])
        origin = np.array([1., 1. + .5 / 96])
        context = public_auction_context(x, np.array([0, 4]), origin, interval=96, decision_intervals=1344)
        np.testing.assert_array_equal(context[:, :4], x)
        np.testing.assert_array_equal(context[:, 4], [0, 4])
        np.testing.assert_allclose(context[:, 5], np.sin(2 * np.pi * origin))
        np.testing.assert_allclose(context[:, 6], origin / 14)
        empty = public_auction_context(np.empty((0, 4)), np.empty(0, dtype=int), np.empty(0), interval=0, decision_intervals=1344)
        self.assertEqual(empty.shape, (0, 7))

    def test_next_cohort_or_fabricated_segment_and_latent_arguments_refused(self):
        x = np.zeros((1, 4))
        for segment, origin in ((np.array([0]), np.array([1 / 96])), (np.array([5]), np.array([0.])), (np.array([1.5]), np.array([0.]))):
            with self.assertRaises(ValueError):
                public_auction_context(x, segment, origin, interval=0, decision_intervals=1344)
        with self.assertRaises(TypeError):
            public_auction_context(x, np.array([0]), np.array([0.]), interval=0, decision_intervals=1344, market=np.array([1.]))
