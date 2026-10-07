import unittest
from types import SimpleNamespace

import numpy as np

from aurora.policy_score_units import posterior_net_score
from aurora.policy_support_bundle import WeightedSupportBundle
from aurora.policies import PolicyBundle, BanditController, PolicyParameters
from aurora.simulator import Snapshot
from aurora.state import Action


class PolicyRepairTest(unittest.TestCase):
    def test_all_posterior_net_baselines_use_single_operation_charge(self):
        mean = np.zeros(6)
        mean[1] = .00005  # $0.005 NET improvement; already includes operation.
        bundle = SimpleNamespace(mean=np.zeros(24), neural_transform=lambda x: x[:, :2], delay_cdf=np.ones(11), estimates=lambda snapshot, remove_delay: (np.zeros(6), np.zeros(6), np.zeros(6), np.full(6, 10.), np.ones(25)))
        posterior = SimpleNamespace(predict=lambda x: (mean.copy(), np.zeros(6)))
        random = SimpleNamespace(uniform=lambda: .99, normal=lambda size: np.zeros(size))
        snapshot = Snapshot(0, 0, 1000000, 0, 0, 0., 0, 0., 0, initial_budget_units=1000000)
        for method in ("epsilon_greedy", "LinUCB", "neural_linear_TS", "delay_TS_primal_dual", "support_gated_delay_TS"):
            controller = BanditController(bundle, PolicyParameters(method))
            controller.posterior = posterior
            controller.neural_posterior = posterior
            controller.random = random
            self.assertEqual(controller.choose(snapshot), tuple(Action)[1], method)

    def test_net_convention_charges_operation_only_in_reward(self):
        gross, spend, operating = 4., 2., .01
        mean = np.full(6, (gross - spend - operating) / 100)
        score = posterior_net_score(mean, np.zeros(6), np.full(6, spend), scarcity=.5)
        np.testing.assert_allclose(score, gross - spend - operating - .5 * spend)
        self.assertGreater(score[1], gross - spend - 2 * operating - .5 * spend)

    def test_weighted_adapter_without_mutating_original(self):
        from sklearn.neighbors import KDTree
        class Constant:
            def __init__(self, value):
                self.value = value

            def predict(self, x):
                return np.full(len(x), self.value)
        actions = np.resize(np.arange(6), 64)
        tree = KDTree(np.zeros((64, 24)))
        original = PolicyBundle(Constant(4.), Constant(2.), np.zeros(24), np.ones(24), tree, actions, np.ones(6), np.linspace(0, 1, 11))
        support = {"tree": tree, "actions": actions, "propensities": np.linspace(.1, .9, 64), "maximum_distance": 1e6, "neighborhood_size": 64}
        repaired = WeightedSupportBundle(original, support)
        snapshot = Snapshot(0, 0, 10000, 0, 0, 0., 0, 0., 0)
        before = original.estimates(snapshot)
        actual = repaired.estimates(snapshot)
        after = original.estimates(snapshot)
        for old, new in zip(before, after):
            np.testing.assert_array_equal(old, new)
        np.testing.assert_array_equal(actual[0], before[0])
        np.testing.assert_array_equal(actual[1], before[1])
        self.assertTrue(np.all(actual[3] < before[3]))


if __name__ == "__main__":
    unittest.main()
