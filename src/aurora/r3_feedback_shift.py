"""Finite-H feedback-shift weights with a real earlier as-of cutoff.

Method relation: Yasui et al.2020 FSIW, adapted to recorded C_H, not eventual
conversion or a claimed reproduction of their production experiment.
"""
from __future__ import annotations

import numpy as np


def auxiliary_labels(origin: np.ndarray, horizon_label: np.ndarray, observed_delay: np.ndarray,
                     *, fit_cutoff: float = 41., horizon: float = 7.) -> dict:
    origin, label, delay = [np.asarray(item, dtype=float) for item in (origin, horizon_label, observed_delay)]
    if origin.ndim != 1 or label.shape != origin.shape or delay.shape != origin.shape or not np.isfinite(origin).all() or not np.isfinite(fit_cutoff) or not np.isfinite(horizon) or horizon <= 0 or np.any(origin > fit_cutoff):
        raise ValueError("Coherent historical origins and positive horizon required")
    cutoff = fit_cutoff - horizon
    eligible = (origin < cutoff) & np.isfinite(label)
    if not np.isin(label[eligible], [0, 1]).all():
        raise ValueError("Known finite-H labels only")
    if np.any((label[eligible] == 1) & ((delay[eligible] < 0) | (delay[eligible] > horizon) | ~np.isfinite(delay[eligible]))):
        raise ValueError("Mature positive must have an observed within-H event")
    age = cutoff - origin
    observed_then = eligible & (label == 1) & (delay <= age)
    positive_aux = eligible & (label == 1)
    negative_aux = eligible & ~observed_then
    return {"eligible": eligible, "age": age, "positive_aux": positive_aux,
            "positive_aux_target": observed_then[positive_aux].astype(int),
            "negative_aux": negative_aux,
            "negative_aux_target": (label[negative_aux] == 0).astype(int), "cutoff": cutoff}


def feedback_weights(observed: np.ndarray, age: np.ndarray, true_positive_probability: np.ndarray,
                     true_negative_probability: np.ndarray, *, horizon: float = 7.) -> np.ndarray:
    y, age, tp, tn = [np.asarray(item, dtype=float) for item in
                      (observed, age, true_positive_probability, true_negative_probability)]
    if y.ndim != 1 or any(item.shape != y.shape for item in (age, tp, tn)) or not all(np.isfinite(item).all() for item in (y, age, tp, tn)) or not np.isin(y, [0, 1]).all() or np.any(age < 0) or any(np.any((item < 0) | (item > 1)) for item in (tp, tn)) or horizon <= 0:
        raise ValueError("Aligned valid observed labels, ages and nuisance probabilities required")
    if not np.isfinite(horizon):
        raise ValueError("Finite horizon required")
    pending = age < horizon
    positive = pending & (y == 1)
    if np.any(tp[positive] <= 0):
        raise ValueError("Unsupported positive observation: no weight clipping/fallback")
    weights = np.ones(len(y))
    weights[positive] = 1 / tp[positive]
    weights[pending & (y == 0)] = tn[pending & (y == 0)]
    if not np.isfinite(weights).all():
        raise ValueError("Nonfinite raw importance weight")
    return weights
