"""Logged-action local effective sample size, not overlap probabilities."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class LocalSupport:
    action_ess: NDArray[np.float64]
    action_rows: NDArray[np.int64]
    maximum_neighbor_distance: float
    out_of_domain: bool


def neighborhood_support(actions, propensities, distances, *, maximum_distance: float, action_count: int = 6) -> LocalSupport:
    """ESS of inverse exact executed-action propensities in a fixed neighborhood.

    The candidate action is fixed locally, so its target mass is1; weights are
    1/p(a|state). No weight clipping, probability reinterpretation or label use.
    Representation, neighborhood size and distance threshold are externally
    frozen. A distant neighborhood receives zero admitted ESS for every arm.
    """
    actions = np.asarray(actions)
    propensities, distances = np.asarray(propensities, dtype=float), np.asarray(distances, dtype=float)
    if actions.ndim != 1 or propensities.shape != actions.shape or distances.shape != actions.shape or not len(actions) or not np.issubdtype(actions.dtype, np.integer) or np.any((actions < 0) | (actions >= action_count)) or not np.isfinite(propensities).all() or np.any((propensities <= 0) | (propensities > 1)) or not np.isfinite(distances).all() or np.any(distances < 0) or not math.isfinite(maximum_distance) or maximum_distance < 0 or action_count <= 0:
        raise ValueError("Finite valid fixed-neighborhood logged actions/propensities required")
    ess = np.zeros(action_count)
    counts = np.bincount(actions, minlength=action_count).astype(np.int64)
    for action in range(action_count):
        selected = propensities[actions == action]
        if len(selected):
            # Normalize before inverse weighting to avoid overflow with tiny
            # valid propensities. ESS is invariant to this common scale.
            weights = selected.min() / selected
            ess[action] = weights.sum()**2 / np.square(weights).sum()
    maximum = float(distances.max())
    ood = maximum > maximum_distance
    if ood:
        ess[:] = 0.
    return LocalSupport(ess, counts, maximum, ood)


def validation_distance_threshold(distances, *, quantile: float = .95) -> float:
    """Metadata-only empirical higher-quantile threshold; never read outcomes."""
    values = np.asarray(distances, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or np.any(values < 0) or not math.isfinite(quantile) or not 0 < quantile < 1:
        raise ValueError("Nonempty finite validation distances and fixed quantile required")
    return float(np.quantile(values, quantile, method="higher"))
