import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from aurora.causal import capacity_policy, cluster_mean, dr_scores


class CausalTests(unittest.TestCase):
    def test_dr_independent_hand_fixture(self):
        v0, v1 = dr_scores([1, 0], [1, 0], [.5, .5], [.2, .2], [.4, .4])
        np.testing.assert_allclose(v0, [.2, -.2])
        np.testing.assert_allclose(v1, [1.6, .4])

    def test_quota_and_ties(self):
        np.testing.assert_array_equal(capacity_policy([1, 1, 0, 0], [8, 2, 1, 3], .25), [0, 1, 0, 0])

    def test_exact_profiles_not_rows_are_clusters(self):
        measured = cluster_mean([0, 0, 1, 1], [0, 0, 1, 1])
        self.assertEqual(measured["n_profile_clusters"], 2)
        self.assertAlmostEqual(measured["se"], .5)
        with self.assertRaises(ValueError):
            dr_scores([1], [1], [0], [0], [0])
