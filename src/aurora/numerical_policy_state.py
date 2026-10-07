"""Prospective numerical-policy state; frozen agent's24-field provider unchanged."""
from __future__ import annotations

import math

import numpy as np

from .incidents import FEATURE_NAMES, features
from .simulator import Snapshot

NUMERICAL_FEATURE_NAMES = (*FEATURE_NAMES, "pending_recorded_value_nowcast")


def pending_value_nowcast(snapshot: Snapshot, *, observed_value_per_exposure_prior: float, receipt_delay_cdf: np.ndarray) -> float:
    """Mature-only fitted prior/rate × expected remaining recorded receipt share.

    Public matured exposure counts are mandatory; cohort counts cannot silently
    serve as exposure denominators. A receipt nowcast is state, not an observed
    purchase, causal value, learner label or addition to the reward ledger.
    """
    count = getattr(snapshot, "matured_exposure_count", None)
    cdf = np.asarray(receipt_delay_cdf, dtype=float)
    ages = np.asarray(snapshot.pending_age_counts)
    if count is None or not isinstance(count, (int, np.integer)) or count < 0:
        raise ValueError("Explicit observed matured exposure denominator required")
    if cdf.shape != (11,) or not np.isfinite(cdf).all() or np.any(cdf < 0) or np.any(cdf > 1) or np.any(np.diff(cdf) < 0) or not math.isclose(float(cdf[-1]), 1., abs_tol=1e-12) or ages.shape != (8,) or np.any(ages < 0) or np.any(ages != np.floor(ages)) or ages.sum() != snapshot.pending_exposures:
        raise ValueError("Qualified receipt CDF and reconciled public age ledger required")
    prior = observed_value_per_exposure_prior
    if not math.isfinite(prior) or prior < 0 or not math.isfinite(snapshot.matured_exposure_value) or snapshot.matured_exposure_value < 0 or (count == 0 and snapshot.matured_exposure_value != 0):
        raise ValueError("Finite observed mature value/rate required")
    rate = snapshot.matured_exposure_value / count if count else prior
    # Bin0 records delays[0,1), hence F(age=0)=0, NOT cdf[0]=F(1).
    # Lower-edge piecewise approximation is explicitly a nowcasting assumption.
    elapsed_cdf = np.r_[0., cdf[:7]]
    return float(np.dot(ages, 1 - elapsed_cdf) * rate)


def numerical_features(snapshot: Snapshot, *, observed_value_per_exposure_prior: float, receipt_delay_cdf: np.ndarray, remove_delay: bool = False) -> np.ndarray:
    raw = np.r_[features(snapshot).astype(float), pending_value_nowcast(snapshot, observed_value_per_exposure_prior=observed_value_per_exposure_prior, receipt_delay_cdf=receipt_delay_cdf)]
    if remove_delay:
        raw[6:9] = 0
        raw[16:] = 0
    if raw.shape != (25,) or not np.isfinite(raw).all():
        raise ValueError("Finite25-field numerical policy state required")
    return raw
