import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np

from aurora.incidents import FEATURE_NAMES, features, temporal_sequences
from aurora.simulator import Snapshot


class IncidentTests(unittest.TestCase):
    def test_public_only_features(self):
        snapshot = Snapshot(0, 0, 10000, 0, 0, 0, 0, 0, 0)
        self.assertEqual(features(snapshot).shape, (24,))
        self.assertFalse({"family", "fault", "label", "true_effect"} & set(FEATURE_NAMES))

    def test_temporal_asof_and_campaign_isolation(self):
        x = np.array([[1], [8], [2], [9]], dtype=np.float32)
        sequence = temporal_sequences(x, [0, 1, 0, 1], np.array([0, 0, 1, 1]), length=8)
        np.testing.assert_array_equal(sequence[2, -2:, 0], [1, 2])
        np.testing.assert_array_equal(sequence[3, -2:, 0], [8, 9])
        self.assertEqual(sequence[0, :-1].sum(), 0)
