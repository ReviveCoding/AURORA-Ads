import unittest

import numpy as np

from aurora.support import neighborhood_support, validation_distance_threshold


class SupportTest(unittest.TestCase):
    def test_weighted_ess_not_raw_count(self):
        result = neighborhood_support([0, 0, 0, 1], [.1, .2, .4, .5], [1., 2., 3., 1.], maximum_distance=3.)
        self.assertAlmostEqual(result.action_ess[0], 17.5**2 / (100 + 25 + 6.25))
        self.assertEqual(result.action_rows[0], 3)
        self.assertLess(result.action_ess[0], result.action_rows[0])
        self.assertEqual(result.action_ess[1], 1.)
        self.assertFalse(result.out_of_domain)

    def test_equal_weights_scale_invariance_and_distance_gate(self):
        result = neighborhood_support([1, 1], [1e-250, 1e-250], [0., 0.], maximum_distance=0.)
        self.assertEqual(result.action_ess[1], 2.)
        result = neighborhood_support([1, 1], [.2, .2], [0., 1.], maximum_distance=.9)
        self.assertTrue(result.out_of_domain)
        np.testing.assert_array_equal(result.action_ess, np.zeros(6))
        self.assertEqual(result.action_rows[1], 2)

    def test_invalid_propensity_and_frozen_label_free_threshold(self):
        for probability in (0., -1., 1.1, float("nan")):
            with self.assertRaises(ValueError):
                neighborhood_support([0], [probability], [0.], maximum_distance=1.)
        self.assertEqual(validation_distance_threshold(np.arange(20.), quantile=.95), 19.)


if __name__ == "__main__":
    unittest.main()
