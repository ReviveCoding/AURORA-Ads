from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.inference import (
    holm_adjust,
    paired_cluster_estimate,
    pilot_sample_size,
    superiority_power,
    zero_event_family_bound,
)


class InferenceTests(unittest.TestCase):
    def test_seeds_do_not_inflate_units_and_duplicate_ids_fail(self):
        candidate = np.array(
            [[1.0, 2.0, 3.0], [2.0, 3.0, 4.0], [3.0, 4.0, 5.0], [4.0, 5.0, 6.0]]
        )
        baseline = np.zeros_like(candidate)
        result = paired_cluster_estimate(list("abcd"), candidate, baseline)
        self.assertEqual(result.independent_units, 4)
        self.assertEqual(result.repetitions_per_unit, 3)
        self.assertEqual(result.per_unit, (2.0, 3.0, 4.0, 5.0))
        with self.assertRaises(ValueError):
            paired_cluster_estimate(list("aabc"), candidate, baseline)

    def test_pilot_mean_cannot_select_sample_size(self):
        effects = np.linspace(-0.04, 0.04, 20)
        first = pilot_sample_size(effects)
        second = pilot_sample_size(effects + 0.1)
        self.assertEqual(first["selected_worlds"], second["selected_worlds"])
        self.assertAlmostEqual(
            first["planning_power"], second["planning_power"], places=12
        )
        self.assertFalse(first["pilot_mean_used_for_selection"])
        self.assertEqual(
            pilot_sample_size(np.ones(20))["scientific_status"], "UNDERPOWERED"
        )

    def test_taxonomy_planning_and_nonzero_zero_event_risk(self):
        self.assertAlmostEqual(
            superiority_power(9, 0.25, alternative=0.1, null_boundary=0.0),
            0.18417932690627692,
            places=12,
        )
        bound = zero_event_family_bound(9)
        self.assertAlmostEqual((1 - bound) ** 9, 0.05, places=12)
        self.assertGreater(bound, 0.28)
        np.testing.assert_allclose(
            holm_adjust(np.array([0.03, 0.001, 0.02])), [0.04, 0.003, 0.04], atol=1e-14
        )

    def test_equal_stratum_weight_not_row_weight(self):
        values = np.array([[0.0], [0.0], [0.0], [0.0], [1.0], [1.0]])
        result = paired_cluster_estimate(
            list("abcdef"), values, np.zeros_like(values), strata=["a"] * 4 + ["b"] * 2
        )
        self.assertEqual(result.mean, 0.5)
        self.assertEqual((result.lower, result.upper), (0.5, 0.5))
