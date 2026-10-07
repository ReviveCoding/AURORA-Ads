import unittest

import numpy as np

from aurora.r3_feedback_shift import auxiliary_labels, feedback_weights


class FeedbackShiftTests(unittest.TestCase):
    def test_known_weights_restore_risk_without_false_negative_as_truth(self):
        prediction = .37
        for q in (.1, .7):
            for observed_fraction in (.05, 1.):
                seen = q * observed_fraction
                weights = feedback_weights(np.array([1, 0]), np.array([1., 1.]),
                    np.full(2, observed_fraction), np.full(2, (1-q)/(1-seen)))
                risk = seen*weights[0]*-np.log(prediction)+(1-seen)*weights[1]*-np.log(1-prediction)
                self.assertAlmostEqual(risk, q*-np.log(prediction)+(1-q)*-np.log(1-prediction))

    def test_auxiliary_cutoff_is_historical_and_half_open(self):
        result = auxiliary_labels(np.array([30., 33., 34., 35.]), np.array([1., 1., 0., np.nan]),
                                  np.array([2., 2., -1., -1.]))
        self.assertEqual(result["cutoff"], 34.)
        np.testing.assert_array_equal(result["eligible"], [True, True, False, False])
        np.testing.assert_array_equal(result["positive_aux_target"], [1, 0])
        np.testing.assert_array_equal(result["negative_aux_target"], [0])

    def test_mature_identity_and_unsupported_weights(self):
        np.testing.assert_array_equal(feedback_weights(np.array([1, 0]), np.array([7., 20.]),
            np.zeros(2), np.zeros(2)), np.ones(2))
        with self.assertRaises(ValueError):
            feedback_weights(np.ones(1), np.ones(1), np.zeros(1), np.ones(1))


if __name__ == "__main__":
    unittest.main()
