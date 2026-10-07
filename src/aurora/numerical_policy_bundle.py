"""Prospective25-field numerical bundle; old24-field agent provider untouched."""
from __future__ import annotations

import math

import numpy as np

from .numerical_policy_state import numerical_features
from .policy_support_bundle import WeightedSupportBundle
from .policies import PolicyBundle


class NumericalPolicyBundle(WeightedSupportBundle):
    """Requires freshly fitted25-state/31-state-action models and support.

    Shape admission is necessary, not sufficient for evidence admission. An
    empirical loader must additionally bind the selected bidder, training/
    calibration cohorts, support qualification and model artifact identities.
    There is deliberately no fallback to the frozen agent's old warmstart.
    """
    def __init__(self, fitted: PolicyBundle, support: dict, *, observed_value_per_exposure_prior: float):
        prior = observed_value_per_exposure_prior
        if not math.isfinite(prior) or prior < 0:
            raise ValueError("Finite mature-training-only exposure value prior required")
        if np.asarray(fitted.mean).shape != (25,) or np.asarray(fitted.scale).shape != (25,) or not np.isfinite(fitted.mean).all() or not np.isfinite(fitted.scale).all() or np.any(np.asarray(fitted.scale) <= 0):
            raise ValueError("Fresh25-field numerical-state normalization required")
        if any(getattr(model, "n_features_in_", None) != 31 for model in (fitted.gross, fitted.spend)):
            raise ValueError("Fresh31-field state/action models required; no old24-state substitution")
        if getattr(support["tree"], "m", None) != 25:
            raise ValueError("Fresh25-field support neighborhood required")
        super().__init__(fitted, support)
        self.observed_value_per_exposure_prior = prior

    def state(self, snapshot, remove_delay=False):
        raw = numerical_features(snapshot, observed_value_per_exposure_prior=self.observed_value_per_exposure_prior,
                                 receipt_delay_cdf=self.delay_cdf, remove_delay=remove_delay)
        return raw, (raw - self.mean) / self.scale

    def pending_nowcast(self, snapshot):
        return float(self.state(snapshot)[0][-1])
