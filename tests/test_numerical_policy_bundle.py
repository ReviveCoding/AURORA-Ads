import unittest
from dataclasses import asdict
from types import SimpleNamespace

import numpy as np
from scipy.spatial import cKDTree

from aurora.numerical_policy_bundle import NumericalPolicyBundle
from aurora.policies import PolicyBundle
from aurora.simulator import Snapshot


class Model:
    n_features_in_ = 31
    def predict(self, values):
        if values.shape != (6, 31):
            raise AssertionError("Exact fresh numerical model input required")
        return np.zeros(6)


def fitted(width=25):
    return PolicyBundle(Model(), Model(), np.zeros(width), np.ones(width), None, [],
                        np.ones(6), np.ones(11))


def support(width=25):
    return {"tree": cKDTree(np.zeros((64, width))), "actions": np.arange(64) % 6,
            "propensities": np.ones(64) / 6, "maximum_distance": 1e6, "neighborhood_size": 64}


class NumericalPolicyBundleTest(unittest.TestCase):
    def test_nowcast_enters_actual_model_state_but_delay_ablation_removes_it(self):
        snapshot = SimpleNamespace(**asdict(Snapshot(0, 0, 10000, 0, 0, 0., 0, 0., 3,
                                   initial_budget_units=10000, pending_age_counts=(3, 0, 0, 0, 0, 0, 0, 0),
                                   matured_exposure_count=0)))
        bundle = NumericalPolicyBundle(fitted(), support(), observed_value_per_exposure_prior=2.)
        self.assertEqual(bundle.pending_nowcast(snapshot), 6.)
        self.assertEqual(bundle.state(snapshot, remove_delay=True)[0][-1], 0.)
        gross, spend, uncertainty, ess, posterior = bundle.estimates(snapshot)
        self.assertEqual(posterior.shape, (26,))
        self.assertEqual(posterior[-1], 6.)
        self.assertTrue(np.isfinite(uncertainty).all())
        self.assertTrue(np.all(ess > 0))
        np.testing.assert_array_equal(gross + spend, np.zeros(6))

    def test_old_shapes_and_fake_exposure_denominator_are_rejected(self):
        with self.assertRaises(ValueError):
            NumericalPolicyBundle(fitted(24), support(), observed_value_per_exposure_prior=0.)
        with self.assertRaises(ValueError):
            NumericalPolicyBundle(fitted(), support(24), observed_value_per_exposure_prior=0.)
        bundle = NumericalPolicyBundle(fitted(), support(), observed_value_per_exposure_prior=0.)
        with self.assertRaises(ValueError):
            bundle.state(Snapshot(0, 0, 10000, 0, 0, 0., 0, 0., 0))


if __name__ == "__main__":
    unittest.main()
