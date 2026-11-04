import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from aurora.measurement import projected_distribution
from aurora.ope import epsilon_target, estimate_with_clusters, reward_features


class OPEStudyTests(unittest.TestCase):
    def test_uniform_identity_and_cluster_count(self):
        a = np.tile(np.arange(2), 6)
        r = np.array([0, 1] * 6)
        target = np.full((12, 2), 0.5)
        result = estimate_with_clusters(
            a,
            r,
            np.full(12, 0.5),
            target,
            np.full((12, 2), 0.2),
            np.repeat(np.arange(3), 4),
        )
        self.assertEqual(result["estimates"]["ips"], 0.5)
        self.assertEqual(result["estimates"]["dr"], 0.5)
        self.assertEqual(result["estimates"]["ess"], 12)
        self.assertEqual(result["clusters"], 3)
        self.assertEqual(result["scientific_outcome"], "UNDERPOWERED")

    def test_target_has_exact_feasible_support(self):
        probability = epsilon_target(np.array([[0.3, 0.4], [0.8, 0.1]]))
        np.testing.assert_allclose(probability, [[0.05, 0.95], [0.95, 0.05]])
        with self.assertRaises(ValueError):
            epsilon_target(np.array([[np.nan, 0]]))
        proposed = np.full(6, 0.1 / 6)
        proposed[0] += 0.9
        actual = projected_distribution(proposed, np.zeros(6), 6)
        self.assertEqual(actual[0], 1.0)
        self.assertEqual(actual.sum(), 1.0)

    def test_features_action_context_interaction(self):
        context = np.array([["a", "b", "c", "d"], ["a", "b", "c", "d"]])
        features = reward_features(context, np.array([0, 1]))
        self.assertEqual(features.shape, (2, 4096))
        self.assertGreater((features[0] != features[1]).nnz, 0)
