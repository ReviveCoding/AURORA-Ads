from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.delay import (
    BIN_EDGES,
    feedback_log_likelihood,
    neural_log_likelihood,
    observed_binary_targets,
)
from aurora.interfaces import (
    FiniteHorizonForecast,
    ForecastIdentity,
    OriginClock,
    compose_expected_value,
)
from aurora.measurement import censored_log_likelihood
from aurora.value import DirectValue, TwoPartValue


class DelayInterfaceTests(unittest.TestCase):
    def test_continuous_feedback_reference_and_finite_horizon_censoring(self):
        predictor = torch.zeros(4, dtype=torch.float64, requires_grad=True)
        lograte = torch.zeros(4, dtype=torch.float64, requires_grad=True)
        ages = torch.tensor([1.0, 7.0, 99.0, 2.0], dtype=torch.float64)
        delay = torch.tensor([-1.0, -1.0, -1.0, 1.0], dtype=torch.float64)
        actual = feedback_log_likelihood(predictor, lograte, ages, delay)
        rate = np.log(2.0)
        expected = np.array(
            [
                np.log(0.5 + 0.5 * np.exp(-rate)),
                np.log(0.5 + 0.5 * np.exp(-7 * rate)),
                np.log(0.5 + 0.5 * np.exp(-7 * rate)),
                np.log(0.5 * rate) - rate,
            ]
        )
        np.testing.assert_allclose(
            actual.detach().numpy(), expected, rtol=0, atol=1e-12
        )
        (-actual.mean()).backward()
        self.assertTrue(
            torch.isfinite(predictor.grad).all() and torch.isfinite(lograte.grad).all()
        )
        with self.assertRaises(ValueError):
            feedback_log_likelihood(
                predictor, lograte, ages, torch.tensor([2.0, -1.0, -1.0, 1.0])
            )

    def test_value_models_require_observed_mature_targets_and_separate_smearing(self):
        x = np.arange(12.0, dtype=float).reshape(6, 2)
        y = np.array([0.0, 3.0, 0.0, 5.0, 0.0, 7.0])
        mature = np.ones(6, dtype=bool)
        direct = DirectValue().fit(x, y, mature)
        self.assertTrue(np.all(direct.predict(x) >= 0))
        identifiers = ["train" + str(number) for number in range(6)]
        cal_identifiers = ["cal" + str(number) for number in range(6)]
        two = TwoPartValue().fit(
            x,
            y,
            mature,
            origin_ids=identifiers,
            calibration_origin_ids=cal_identifiers,
            calibration_features=x + 1,
            calibration_value=y + 1,
            calibration_matured=mature,
        )
        q, v = two.components(x)
        np.testing.assert_allclose(two.predict(x), q * v, rtol=0, atol=0)
        self.assertTrue(np.all((q >= 0) & (q <= 1)) and np.all(v > 0))
        pending = mature.copy()
        pending[0] = False
        with self.assertRaises(ValueError):
            DirectValue().fit(x, y, pending)
        with self.assertRaises(ValueError):
            TwoPartValue().fit(
                x,
                y,
                mature,
                origin_ids=identifiers,
                calibration_origin_ids=identifiers,
                calibration_features=x,
                calibration_value=y,
                calibration_matured=mature,
            )

    def test_neural_likelihood_matches_independent_numpy_and_has_finite_gradients(self):
        q = torch.tensor(
            [-100.0, 0.0, 100.0, 0.3, -2.0], dtype=torch.float64, requires_grad=True
        )
        logits = torch.zeros(
            (5, len(BIN_EDGES)), dtype=torch.float64, requires_grad=True
        )
        age = torch.tensor([7.0, 0.0, 7.0, 1.25, 2.0], dtype=torch.float64)
        event = torch.tensor([-1, -1, -1, -1, 4])
        measured = neural_log_likelihood(q, logits, age, event)
        # Extreme q=1 rounding has a valid stable lognotq=-100, not clipped eps.
        self.assertAlmostEqual(float(measured[2].detach()), -100.0, places=10)
        interior = np.array([1, 3, 4])
        reference = censored_log_likelihood(
            torch.sigmoid(q.detach()[interior]).numpy(),
            np.full((3, len(BIN_EDGES)), 1 / len(BIN_EDGES)),
            age[interior].numpy(),
            event[interior].numpy(),
            BIN_EDGES,
        )
        np.testing.assert_allclose(
            measured.detach().numpy()[interior], reference, atol=1e-12, rtol=0
        )
        (-measured.mean()).backward()
        self.assertTrue(
            torch.isfinite(q.grad).all() and torch.isfinite(logits.grad).all()
        )

    def test_pending_negative_is_diagnostic_not_mature_observed_reward(self):
        eligible, targets = observed_binary_targets(
            np.array([1.0, 7.0, 8.0]), np.array([-1, -1, 2]), mature_only=True
        )
        np.testing.assert_array_equal(eligible, [False, True, True])
        np.testing.assert_array_equal(targets, [0, 0, 1])

    def test_occurrence_is_not_reporting_availability(self):
        event = OriginClock(0.0, 7.0, 2.0, 5.0, "MEASURED")
        self.assertFalse(event.event_available(3.0))
        self.assertTrue(event.event_available(5.0))
        with self.assertRaises(ValueError):
            OriginClock(0.0, 7.0, 2.0, None, "UNKNOWN").event_available(3.0)

    def test_unrelated_source_probability_products_are_rejected(self):
        def identity(domain):
            return ForecastIdentity(
                domain, "fixture", "a" * 64, "7day", 41.0, "b" * 64, "UNCALIBRATED"
            )

        q = FiniteHorizonForecast(identity("R1"), 0.2)
        value = FiniteHorizonForecast(
            identity("R3"), 0.1, 100.0, "fixture synthetic value"
        )
        with self.assertRaises(ValueError):
            compose_expected_value(q, value)
