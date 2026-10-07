import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np

from aurora.prediction import hashed_features, neural_model, probability, proper_scores


class PredictionTests(unittest.TestCase):
    def test_proper_scores_analytical_and_reliability_partition(self):
        score, losses = proper_scores([0, 1], [.25, .75])
        np.testing.assert_allclose(losses, -np.log(.75))
        self.assertAlmostEqual(score["brier"], .0625)
        score, _ = proper_scores(np.arange(11) % 2, np.arange(11) / 10)
        self.assertEqual(sum(row["n"] for row in score["reliability"]), 11)
        with self.assertRaises(ValueError):
            probability([np.nan])

    def test_feature_fields_and_neural_gradients(self):
        import torch
        codes = np.array([[1, 2], [1, 3]])
        self.assertEqual(hashed_features(codes).shape, (2, 65536))
        for cross in (False, True):
            torch.manual_seed(91)
            model = neural_model(2, 4, 8, cross)
            loss = model(torch.tensor(codes)).square().mean()
            loss.backward()
            self.assertTrue(torch.isfinite(loss))
            self.assertTrue(all(parameter.grad is not None and torch.isfinite(parameter.grad).all() for parameter in model.parameters()))
