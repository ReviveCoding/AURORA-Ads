"""Single-origin M41 snapshots with distinct occurrence and assumed receipt clocks."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .delay import BIN_EDGES


@dataclass(frozen=True)
class R3Targets:
    age_days: np.ndarray
    observed_event_bin: np.ndarray
    observed_delay_days: np.ndarray
    mature: np.ndarray
    within_horizon_label: np.ndarray
    available_value: np.ndarray
    valid_delay: np.ndarray


def asof_targets(origin_days: np.ndarray, sale: np.ndarray, delay_days: np.ndarray,
                 amount: np.ndarray, *, cutoff_day: float, reporting_lag_days: float = 0.) -> R3Targets:
    origin, sale, delay, amount = [np.asarray(value, dtype=float) for value in (origin_days, sale, delay_days, amount)]
    if origin.ndim != 1 or any(value.shape != origin.shape for value in (sale, delay, amount)):
        raise ValueError("One coherent source row per origin required")
    if not np.isfinite(origin).all() or not np.isin(sale, [0, 1]).all() or not np.isfinite(cutoff_day) or not np.isfinite(reporting_lag_days) or reporting_lag_days < 0:
        raise ValueError("Invalid origin, binary sale or assumed receipt clock")
    age = cutoff_day - origin
    if np.any(age < 0):
        raise ValueError("Future origins cannot enter fitting snapshot")
    valid_delay = ((sale == 0) & (delay == -1)) | ((sale == 1) & np.isfinite(delay) & (delay >= 0))
    within = valid_delay & (sale == 1) & (delay <= 7)
    observed = within & (delay + reporting_lag_days <= age)
    bins = np.full(len(origin), -1, dtype=np.int64)
    bins[observed] = np.searchsorted(np.asarray(BIN_EDGES), delay[observed], side="left")
    mature = (age >= 7 + reporting_lag_days) & valid_delay
    binary = np.full(len(origin), np.nan)
    binary[mature] = within[mature].astype(float)
    value = np.full(len(origin), np.nan)
    value[mature & ~within] = 0.
    amount_observed = observed & np.isfinite(amount) & (amount >= 0)
    value[amount_observed] = amount[amount_observed]
    # An observed partial positive remains a censored origin cohort for value
    # learning. Caller must use mature mask for the primary full-cohort target.
    return R3Targets(age, bins, np.where(observed, delay, -1), mature, binary, value, valid_delay)
