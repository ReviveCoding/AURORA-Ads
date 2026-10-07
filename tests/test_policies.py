import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np

from aurora.policies import LinearPosterior


class PolicyTests(unittest.TestCase):
    def test_sequential_posterior_matches_independent_batch_reference(self):
        random = np.random.default_rng(71)
        x = random.normal(size=(40, 5))
        y = random.normal(size=40)
        posterior = LinearPosterior(5, ridge=10.)
        for row, value in zip(x, y):
            posterior.update(2, row, value)
        inverse = np.linalg.inv(10 * np.eye(5) + x.T @ x)
        np.testing.assert_allclose(posterior.inverse[2], inverse, atol=1e-12, rtol=1e-12)
        probe = random.normal(size=5)
        means, sd = posterior.predict(probe)
        self.assertAlmostEqual(means[2], probe @ inverse @ x.T @ y)
        self.assertAlmostEqual(sd[2]**2, probe @ inverse @ probe)
