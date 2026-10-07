from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.serving_models import FrozenNeuralLinearMean


class ServingModelTests(unittest.TestCase):
    def test_fixed_net_head_reference_and_preprocessing(self):
        torch.manual_seed(413)
        embedding = torch.nn.Linear(24, 16).float()
        weights = np.arange(102., dtype=float).reshape(17, 6) / 102
        mean, scale = np.ones(24), np.full(24, 2.)
        model = FrozenNeuralLinearMean(embedding, weights, mean, scale)
        raw = np.arange(48., dtype=np.float32).reshape(2, 24) / 24
        with torch.inference_mode():
            encoded = model.encode(raw)
            torch.testing.assert_close(encoded, torch.from_numpy((raw - 1.) / 2.), rtol=0, atol=0)
            latent = embedding(encoded).numpy()
            reference = np.column_stack([np.ones(2, dtype=np.float32), latent]) @ weights.astype(np.float32) * 100
            np.testing.assert_allclose(model(encoded).numpy(), reference, rtol=1e-6, atol=1e-4)
        with self.assertRaises(ValueError):
            model.encode(np.zeros((1, 25)))
