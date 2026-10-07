"""Read-only observed-channel tracing; no truth, draws or scoring alterations."""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from .policies import ACTIONS, BanditController
from .state import SCALE


class ObservedBundleTrace:
    def __init__(self, bundle: Any):
        self.bundle = bundle
        self.last: tuple | None = None
        self.reliability = 0.

    def __getattr__(self, name: str) -> Any:
        if name == "detector" and self.bundle.detector is not None:
            def detect(values):
                result = self.bundle.detector(values)
                self.reliability = float(result)
                return result
            return detect
        return getattr(self.bundle, name)

    def estimates(self, snapshot, remove_delay=False):
        values = self.bundle.estimates(snapshot, remove_delay)
        self.last = tuple(np.asarray(value).copy() for value in values)
        return values


class DiagnosticController(BanditController):
    """Tracing consumes only outputs already computed by the actual controller."""
    def __init__(self, bundle, parameters, *warm):
        traced = ObservedBundleTrace(bundle)
        super().__init__(traced, parameters, *warm)
        self.trace_bundle = traced
        self.proposals: Counter = Counter()
        self.executions: Counter = Counter()
        self.predictions: dict[tuple[int, int], tuple[Any, Any]] = {}
        self.decisions = self.support_gated = self.projected = 0
        self.ess_sum = np.zeros(6)
        self.ess_min = np.full(6, np.inf)
        self.penalty_sum = np.zeros(6)
        self.predicted_gross = self.realized_gross = 0.
        self.predicted_spend = self.realized_spend = 0.
        self.gross_error_square = self.spend_error_square = 0.
        self.calibration_count = 0
        self.daily: list[dict] = []
        self.proposed = None

    def choose(self, snapshot):
        action = super().choose(snapshot)
        gross, spend, uncertainty, support, x = self.trace_bundle.last
        mean, _ = self.posterior.predict(x)
        adjusted = .5 * gross + .5 * np.maximum(0, mean * 100 + spend + np.array([0, .01, .01, .01, .01, .01]))
        self.predictions[(snapshot.campaign, snapshot.interval)] = (adjusted, spend)
        self.decisions += 1
        self.proposals[action.value] += 1
        self.proposed = action
        self.ess_sum += support
        self.ess_min = np.minimum(self.ess_min, support)
        if not self.parameters.remove_support:
            self.support_gated += int(np.any(support[1:] < self.parameters.support_min))
        if not self.parameters.remove_uncertainty:
            self.penalty_sum += self.parameters.beta * uncertainty * (1 + self.trace_bundle.reliability)
        return action

    def executed(self, snapshot, action, probability, spend, operational):
        self.executions[action.value] += 1
        self.projected += int(action != self.proposed)
        gross, predicted_spend = self.predictions[(snapshot.campaign, snapshot.interval)]
        index = ACTIONS.index(action)
        self.predictions[(snapshot.campaign, snapshot.interval)] = (float(gross[index]), float(predicted_spend[index]))
        super().executed(snapshot, action, probability, spend, operational)
        if snapshot.interval % 96 == 0:
            self.daily.append({"interval": snapshot.interval, "campaign": snapshot.campaign,
                               "dual_after": float(self.dual[snapshot.campaign]),
                               "available_budget": snapshot.available_budget_units / SCALE,
                               "spent_before": snapshot.spent_units / SCALE,
                               "interval_spend": spend, "operational": operational})

    def observe(self, observation):
        super().observe(observation)
        prediction = self.predictions.pop((observation.campaign, observation.origin_interval))
        gross, spend = prediction
        self.predicted_gross += gross
        self.realized_gross += observation.observed_gross_value
        self.predicted_spend += spend
        self.realized_spend += observation.actual_spend
        self.gross_error_square += (gross - observation.observed_gross_value) ** 2
        self.spend_error_square += (spend - observation.actual_spend) ** 2
        self.calibration_count += 1

    def diagnostics(self) -> dict:
        denominator = max(self.decisions, 1)
        return {"proposed_actions": dict(self.proposals), "executed_actions": dict(self.executions),
                "decisions": self.decisions, "host_projected_proposals": self.projected,
                "support_gate_any_nondefault_fraction": self.support_gated / denominator,
                "mean_weighted_ESS_by_action": (self.ess_sum / denominator).tolist(),
                "minimum_weighted_ESS_by_action": self.ess_min.tolist(),
                "mean_uncertainty_penalty_by_action": (self.penalty_sum / denominator).tolist(),
                "matured_prediction_count": self.calibration_count,
                "pending_predictions": len(self.predictions),
                "predicted_gross_sum": self.predicted_gross, "matured_observed_gross_sum": self.realized_gross,
                "predicted_spend_sum": self.predicted_spend, "actual_spend_sum": self.realized_spend,
                "gross_RMSE": float(np.sqrt(self.gross_error_square / max(self.calibration_count, 1))),
                "spend_RMSE": float(np.sqrt(self.spend_error_square / max(self.calibration_count, 1))),
                "daily_public_budget_dual": self.daily,
                "calibration_target": "observed exposed purchase value, NOT incremental evaluator truth",
                "uncertainty_type": "residual/weighted-ESS heuristic, NOT confidence bound",
                "NO_BID_usage": "unavailable: fixed-bid primary kernel has no learned opportunity bidder"}
