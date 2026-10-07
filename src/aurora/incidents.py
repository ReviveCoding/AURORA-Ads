"""Detector public feature catalog; synthetic labels live only in evaluators."""
from __future__ import annotations

import numpy as np

from .simulator import Snapshot
from .state import SCALE

FEATURE_NAMES = ("remaining_fraction", "spend_velocity", "supply", "wins", "auction_loss_fraction", "observed_click_rate", "received_value_per_interval", "matured_value_per_cohort", "pending_count", "elapsed_fraction", *(f"context_mean{i}" for i in range(6)), *(f"pending_age{i}" for i in range(8)))


def features(snapshot: Snapshot) -> np.ndarray:
    initial = max(snapshot.initial_budget_units, SCALE)
    values = [snapshot.available_budget_units / initial, snapshot.last_spend_units / max(initial / 1344, SCALE), snapshot.last_supply / 32, snapshot.last_wins / 32, snapshot.last_auction_losses / max(snapshot.last_supply, 1), snapshot.observed_clicks / max((snapshot.interval + 1) * 32, 1), snapshot.received_value / max(snapshot.interval + 1, 1) / 100, snapshot.matured_exposure_value / max(snapshot.matured_cohort_count, 1) / 100, snapshot.pending_exposures / 1000, snapshot.interval / 1344, *snapshot.last_context_mean, *[value / 1000 for value in snapshot.pending_age_counts]]
    array = np.asarray(values, dtype=np.float32)
    if array.shape != (len(FEATURE_NAMES),) or not np.isfinite(array).all():
        raise ValueError("Nonfinite/wrong public detector features")
    return array


def rule_scores(x: np.ndarray):
    if x.shape[1] != len(FEATURE_NAMES):
        raise ValueError("Unknown detector feature catalog")
    impression_only = 1 / (1 + np.exp(np.clip(8 * (x[:, 2] - .5), -40, 40)))
    losses = np.clip((x[:, 4] - .25) * 2, 0, 1)
    slow_pending = np.clip(x[:, -1] + x[:, -2] + x[:, -3], 0, 1)
    multi_signal = np.maximum(impression_only, np.maximum(losses, slow_pending))
    return impression_only, multi_signal


def temporal_sequences(x, campaign, interval, length=8):
    """Past/current features within campaign only; never future/other-campaign rows."""
    sequences = np.zeros((len(x), length, x.shape[1]), dtype=np.float32)
    for identity in np.unique(campaign):
        positions = np.flatnonzero(campaign == identity)
        order = positions[np.argsort(interval[positions], kind="stable")]
        for lag in range(min(length, len(order))):
            sequences[order[lag:], length - 1 - lag] = x[order[:len(order) - lag]]
    return sequences


def temporal_model(hidden):
    from torch import nn

    class TemporalDetector(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = nn.GRU(len(FEATURE_NAMES), hidden, batch_first=True)
            self.head = nn.Linear(hidden, 3)

        def forward(self, x):
            sequence, _ = self.encoder(x)
            return self.head(sequence[:, -1])

    return TemporalDetector()
