"""Strict contemporaneous seven-field public opportunity feature construction."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from aurora.auction_learning import CONTEXT_NAMES


def public_auction_context(x: NDArray, segment: NDArray, origin_day: NDArray, *, interval: int, decision_intervals: int) -> NDArray[np.float64]:
    """Context at each auction's public origin time, not latent market/outcomes.

    Each independent row gets its own event clock. No batch-level ranking or
    future-context aggregation is exposed; model/scaler parameters are fixed.
    Half-open origin intervals prevent accidentally feeding next-cohort times.
    This function does not create or adjust source/simulator timestamps.
    """
    x, segment, origin = np.asarray(x, dtype=float), np.asarray(segment), np.asarray(origin_day, dtype=float)
    if type(interval) is not int or type(decision_intervals) is not int or not 0 <= interval < decision_intervals:
        raise ValueError("Valid decision interval and declared horizon required")
    if x.ndim != 2 or x.shape[1] != 4 or not np.isfinite(x).all():
        raise ValueError("Exactly four finite public context channels required")
    n = len(x)
    if segment.shape != (n,) or not np.issubdtype(segment.dtype, np.integer) or np.any((segment < 0) | (segment >= 5)):
        raise ValueError("Source-defined five-category public segment required; no fabricated identities")
    if origin.shape != (n,) or not np.isfinite(origin).all() or np.any(origin < interval / 96) or np.any(origin >= (interval + 1) / 96):
        raise ValueError("Public opportunity clocks must lie in their exact half-open origin interval")
    result = np.column_stack([x, segment, np.sin(2 * np.pi * origin), origin / (decision_intervals / 96)])
    if result.shape != (n, len(CONTEXT_NAMES)):
        raise ValueError("Declared seven-field feature ABI changed")
    return result
