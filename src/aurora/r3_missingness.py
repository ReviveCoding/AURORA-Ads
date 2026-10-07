"""Partial-identification score bounds; unknown horizon labels are never zeros."""
from __future__ import annotations

import numpy as np

from .prediction import probability


def binary_score_bounds(label: np.ndarray, prediction: np.ndarray) -> dict:
    label = np.asarray(label, dtype=float)
    prediction = probability(prediction)
    if label.shape != prediction.shape or label.ndim != 1 or not len(label) or not np.all(np.isnan(label) | np.isin(label, [0, 1])):
        raise ValueError("Binary/unknown labels and finite probability required")
    known = np.isfinite(label)
    unknown = ~known
    loss0, loss1 = -np.log1p(-prediction), -np.log(prediction)
    observed = np.where(label[known] == 1, loss1[known], loss0[known]).sum()
    return {"full_cohort_n": len(label), "known_outcome_n": int(known.sum()),
            "unknown_outcome_n": int(unknown.sum()),
            "complete_case_logloss": float(observed / known.sum()) if known.any() else None,
            "full_cohort_logloss_lower": float((observed + np.minimum(loss0[unknown], loss1[unknown]).sum()) / len(label)),
            "full_cohort_logloss_upper": float((observed + np.maximum(loss0[unknown], loss1[unknown]).sum()) / len(label)),
            "prevalence_lower": float(np.nansum(label) / len(label)),
            "prevalence_upper": float((np.nansum(label) + unknown.sum()) / len(label)),
            "identification_assumption": "none for binary unknown labels; extrema may differ by model",
            "not_confidence_interval": True}


def paired_logloss_bounds(label: np.ndarray, candidate: np.ndarray, comparator: np.ndarray) -> tuple[float, float]:
    label = np.asarray(label, dtype=float)
    candidate, comparator = probability(candidate), probability(comparator)
    binary_score_bounds(label, candidate)
    binary_score_bounds(label, comparator)
    known = np.isfinite(label)
    difference0 = -np.log1p(-candidate) + np.log1p(-comparator)
    difference1 = -np.log(candidate) + np.log(comparator)
    observed = np.where(label[known] == 1, difference1[known], difference0[known]).sum()
    return (float((observed + np.minimum(difference0[~known], difference1[~known]).sum()) / len(label)),
            float((observed + np.maximum(difference0[~known], difference1[~known]).sum()) / len(label)))
