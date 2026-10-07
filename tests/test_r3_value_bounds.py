import importlib.util
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r3_value_fixture", ROOT / "tools/r3_value_study.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class R3ValueBoundsTests(unittest.TestCase):
    def test_unknown_amount_not_zero_imputed_and_bounds_are_exact(self):
        report = MODULE.value_bounds([1., 0.], [2., 1.], [3.], [10.])
        np.testing.assert_allclose(report["full_cohort_MSE_identification_bounds"], [11 / 3, 51 / 3])
        np.testing.assert_allclose(report["full_cohort_MAE_identification_bounds"], [5 / 3, 9 / 3])
        self.assertTrue(report["not_confidence_intervals"])

    def test_missing_revenue_has_no_invented_upper_bound(self):
        report = MODULE.value_bounds([0.], [1.], [3.], [-1.])
        self.assertIsNone(report["full_cohort_MSE_identification_bounds"][1])
        self.assertEqual(report["unknown_amount_rows"], 1)
        with self.assertRaises(ValueError):
            MODULE.value_bounds([0.], [np.nan], [], [])
