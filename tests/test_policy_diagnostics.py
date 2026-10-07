import unittest

import numpy as np

from aurora.policies import BanditController, PolicyParameters
from aurora.policy_diagnostics import DiagnosticController
from aurora.simulator import MaturedObservation, Snapshot, WorldSpec, run_world


class Bundle:
    mean = np.zeros(2)
    scale = np.ones(2)
    neural_transform = None
    delay_cdf = np.linspace(0, 1, 11)
    detector = staticmethod(lambda x: .3)

    def state(self, snapshot, remove_delay=False):
        return np.zeros(2), np.zeros(2)

    def estimates(self, snapshot, remove_delay=False):
        return np.arange(6.), np.arange(6.) / 2, np.ones(6), np.ones(6) * 3, np.array([1., 0., 0.])


class DiagnosticTests(unittest.TestCase):
    def test_trace_preserves_actions_state_and_posterior(self):
        parameters = PolicyParameters("MSCP_v2", eta=.01, lambda_max=5, beta=1)
        plain, traced = BanditController(Bundle(), parameters), DiagnosticController(Bundle(), parameters)
        for interval in range(4):
            snapshot = Snapshot(interval, 0, 100000, 0, 0, 0., 0, 0., 0, initial_budget_units=100000)
            action = plain.choose(snapshot)
            self.assertEqual(action, traced.choose(snapshot))
            for controller in (plain, traced):
                controller.executed(snapshot, action, None, .2, .01)
                controller.observe(MaturedObservation(str(interval), interval, 0, 8., snapshot, action, None, 1., 1, .2, .01, 1))
            np.testing.assert_array_equal(plain.dual, traced.dual)
            np.testing.assert_array_equal(plain.posterior.b, traced.posterior.b)
            np.testing.assert_array_equal(plain.posterior.inverse, traced.posterior.inverse)
        report = traced.diagnostics()
        self.assertEqual(report["pending_predictions"], 0)
        self.assertEqual(report["matured_prediction_count"], 4)
        self.assertEqual(sum(report["executed_actions"].values()), 4)

    def test_duplicate_matured_reward_still_rejected(self):
        controller = DiagnosticController(Bundle(), PolicyParameters("MSCP_v2"))
        snapshot = Snapshot(0, 0, 10000, 0, 0, 0., 0, 0., 0)
        action = controller.choose(snapshot)
        controller.executed(snapshot, action, None, 0., 0.)
        observation = MaturedObservation("same", 0, 0, 8., snapshot, action, None, 0., 0, 0., 0., 0)
        controller.observe(observation)
        with self.assertRaises(ValueError):
            controller.observe(observation)

    def test_complete_smoke_world_matches_with_host_projection_and_flush(self):
        parameters = PolicyParameters("MSCP_v2", eta=.01, lambda_max=5, beta=1)
        plain, traced = BanditController(Bundle(), parameters), DiagnosticController(Bundle(), parameters)
        world = WorldSpec("trace-reference-only", "weak_or_no_heterogeneity", campaigns=1,
                          intervals=12, nominal_arrivals=2, stage="smoke")
        self.assertEqual(run_world(world, plain), run_world(world, traced))
        self.assertEqual(traced.diagnostics()["pending_predictions"], 0)
