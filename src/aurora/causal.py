"""Released-benchmark assignment contrasts; no individual CATE ground truth."""
from __future__ import annotations

import numpy as np
from scipy.stats import t


def dr_scores(y, treatment, propensity, mu0, mu1):
    y, treatment, propensity, mu0, mu1 = np.broadcast_arrays(*[np.asarray(value, dtype=np.float64) for value in (y, treatment, propensity, mu0, mu1)])
    if not all(np.isfinite(value).all() for value in (y, treatment, propensity, mu0, mu1)) or np.any((propensity <= 0) | (propensity >= 1)) or np.any((treatment != 0) & (treatment != 1)):
        raise ValueError("Invalid binary assignment/support")
    v0 = mu0 + (1 - treatment) * (y - mu0) / (1 - propensity)
    v1 = mu1 + treatment * (y - mu1) / propensity
    return v0, v1


def cluster_mean(values, groups):
    values = np.asarray(values, dtype=np.float64)
    groups = np.asarray(groups)
    if not len(values) or len(values) != len(groups) or not np.isfinite(values).all():
        raise ValueError("Invalid cluster observations")
    unique, index = np.unique(groups, return_inverse=True)
    estimate = float(values.mean())
    sums = np.bincount(index, weights=values - estimate)
    g = len(unique)
    se = float(np.sqrt(g / (g - 1) * np.dot(sums, sums)) / len(values)) if g > 1 else None
    half = float(t.ppf(.975, g - 1) * se) if se is not None else None
    return {"estimate": estimate, "ci95": [estimate - half, estimate + half] if half is not None else None, "se": se, "n_rows": len(values), "n_profile_clusters": g, "uncertainty_method": "exact-profile cluster sandwich t; independent-profile assumption, not identified users"}


def capacity_policy(scores, group_tiebreak, capacity):
    """Outcome-blind fixed batch quota rule with deterministic profile tie-break."""
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or not np.isfinite(scores).all() or not 0 <= capacity <= 1 or len(group_tiebreak) != len(scores):
        raise ValueError("Invalid quota/scores")
    order = np.lexsort((np.asarray(group_tiebreak), -scores))
    policy = np.zeros(len(scores))
    policy[order[:int(np.floor(capacity * len(scores)))]] = 1
    return policy
