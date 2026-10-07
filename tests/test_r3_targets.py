import unittest

import numpy as np

from aurora.r3_targets import asof_targets


class R3TargetTests(unittest.TestCase):
    def test_future_conversions_not_supplied_to_fitting_and_afterH_negative(self):
        result = asof_targets(np.array([40, 30, 30, 30, 30]), np.array([1, 1, 0, 1, 1]),
            np.array([2, 8, -1, 0, 2]), np.array([10, 50, -1, -1, 10]), cutoff_day=41)
        np.testing.assert_array_equal(result.observed_event_bin, [-1, -1, -1, 0, 5])
        self.assertFalse(result.mature[0])
        self.assertTrue(np.isnan(result.within_horizon_label[0]))
        np.testing.assert_array_equal(result.within_horizon_label[1:], [0, 0, 1, 1])
        self.assertEqual(result.available_value[1], 0)
        self.assertEqual(result.available_value[2], 0)
        self.assertTrue(np.isnan(result.available_value[3]))
        self.assertEqual(result.available_value[4], 10)

    def test_missing_conversion_delay_not_zero_filled_and_reporting_lag_distinct(self):
        result = asof_targets(np.array([35, 33]), np.array([1, 1]), np.array([2, -1]),
            np.array([10, 10]), cutoff_day=41, reporting_lag_days=5)
        self.assertEqual(result.observed_event_bin[0], -1)
        self.assertFalse(result.mature[0])
        self.assertFalse(result.valid_delay[1])
        self.assertTrue(np.isnan(result.within_horizon_label[1]))

    def test_future_origin_rejected(self):
        with self.assertRaises(ValueError):
            asof_targets(np.array([42]), np.array([0]), np.array([-1]), np.array([-1]), cutoff_day=41)
