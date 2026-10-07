import unittest
from types import SimpleNamespace

import numpy as np

from aurora.numerical_policy_state import pending_value_nowcast


class NumericalPolicyStateTest(unittest.TestCase):
    def test_day_zero_cdf_and_mature_exposure_rate(self):
        snapshot = SimpleNamespace(matured_exposure_count=10, matured_exposure_value=20., pending_age_counts=(3, 2, 0, 0, 0, 0, 0, 0), pending_exposures=5)
        cdf = np.array([.5, .7, .8, .9, .95, .98, 1., 1., 1., 1., 1.])
        self.assertEqual(pending_value_nowcast(snapshot, observed_value_per_exposure_prior=99., receipt_delay_cdf=cdf), (3+2*.5)*2)
        snapshot.matured_exposure_count = 0
        snapshot.matured_exposure_value = 0.
        self.assertEqual(pending_value_nowcast(snapshot, observed_value_per_exposure_prior=1., receipt_delay_cdf=cdf), 4.)

    def test_missing_exposure_count_and_pending_mismatch_rejected(self):
        snapshot = SimpleNamespace(matured_exposure_value=0., pending_age_counts=(1,)*8, pending_exposures=8)
        with self.assertRaises(ValueError):
            pending_value_nowcast(snapshot, observed_value_per_exposure_prior=1., receipt_delay_cdf=np.ones(11))
        snapshot.matured_exposure_count = 0
        snapshot.pending_exposures = 7
        with self.assertRaises(ValueError):
            pending_value_nowcast(snapshot, observed_value_per_exposure_prior=1., receipt_delay_cdf=np.ones(11))


if __name__ == "__main__":
    unittest.main()
