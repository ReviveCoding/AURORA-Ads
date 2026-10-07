"""FP64 fixed-policy estimators and finite-horizon reference likelihoods."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


def conditional_exponential_cdf(age: ArrayLike, rate: ArrayLike, horizon: float = 7.) -> np.ndarray:
    age, rate = np.broadcast_arrays(np.asarray(age, dtype=np.float64), np.asarray(rate, dtype=np.float64))
    if not math.isfinite(horizon) or horizon <= 0 or not np.all(np.isfinite(age)) or not np.all(np.isfinite(rate)) or np.any(age < 0) or np.any(rate <= 0):
        raise ValueError("Invalid delay parameters")
    return -np.expm1(-rate * np.minimum(age, horizon)) / -np.expm1(-rate * horizon)


def censored_log_likelihood(q: ArrayLike, masses: ArrayLike, age: ArrayLike, event_bin: ArrayLike, edges: ArrayLike) -> np.ndarray:
    """One row per origin; bin0 is an atom at zero, later bins uniform within-bin."""
    q = np.asarray(q, dtype=np.float64)
    masses = np.asarray(masses, dtype=np.float64)
    age = np.asarray(age, dtype=np.float64)
    event_bin = np.asarray(event_bin)
    edges = np.asarray(edges, dtype=np.float64)
    if q.ndim != 1 or masses.shape != (len(q), len(edges)) or age.shape != q.shape or event_bin.shape != q.shape:
        raise ValueError("Shape mismatch")
    if edges.ndim != 1 or len(edges) < 2 or edges[0] != 0 or np.any(np.diff(edges) <= 0) or not np.all(np.isfinite(edges)):
        raise ValueError("Invalid predeclared bin edges")
    if not np.all(np.isfinite(q)) or np.any((q < 0) | (q > 1)) or not np.all(np.isfinite(masses)) or np.any(masses < 0) or not np.allclose(masses.sum(1), 1, atol=1e-12, rtol=0) or not np.all(np.isfinite(age)) or np.any(age < 0):
        raise ValueError("Invalid probability/age")
    if np.any(event_bin != event_bin.astype(int)) or np.any((event_bin < -1) | (event_bin >= len(edges))):
        raise ValueError("Invalid event index")
    fractions = np.column_stack([np.ones(len(q)), *(np.clip((age - left) / (right - left), 0, 1) for left, right in zip(edges[:-1], edges[1:]))])
    cdf = np.clip(np.sum(masses * fractions, axis=1), 0, 1)
    observed = event_bin >= 0
    if np.any(age[observed] < edges[np.maximum(event_bin[observed].astype(int) - 1, 0)]):
        raise ValueError("Future event supplied to fitting snapshot")
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.log1p(-q * cdf)
        index = np.flatnonzero(observed)
        result[index] = np.log(q[index]) + np.log(masses[index, event_bin[index].astype(int)])
    return result


@dataclass(frozen=True)
class OPEResult:
    dm: float
    ips: float
    snips: float
    dr: float
    ess: float
    max_weight: float
    n: int
    estimand: str = "fixed_policy_one_step_value; not adaptive_episode"


def fixed_policy_ope(actions: ArrayLike, reward: ArrayLike, propensity: ArrayLike, target: ArrayLike, prediction: ArrayLike) -> OPEResult:
    actions = np.asarray(actions)
    reward = np.asarray(reward, dtype=np.float64)
    propensity = np.asarray(propensity, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    prediction = np.asarray(prediction, dtype=np.float64)
    n = len(actions)
    if not n or actions.ndim != 1 or reward.shape != (n,) or propensity.shape != (n,) or target.ndim != 2 or target.shape != prediction.shape or target.shape[0] != n:
        raise ValueError("Shape mismatch/empty evidence")
    if np.any(actions != actions.astype(int)) or np.any((actions < 0) | (actions >= target.shape[1])):
        raise ValueError("Invalid executed action")
    if not all(np.all(np.isfinite(x)) for x in (reward, propensity, target, prediction)) or np.any((propensity <= 0) | (propensity > 1)) or np.any(target < 0) or not np.allclose(target.sum(1), 1, atol=1e-12, rtol=0):
        raise ValueError("Invalid probabilities/support")
    ix = np.arange(n)
    weights = target[ix, actions.astype(int)] / propensity
    if weights.sum() <= 0:
        raise ValueError("No target support in evaluation sample")
    dm_rows = (target * prediction).sum(1)
    return OPEResult(float(dm_rows.mean()), float(np.mean(weights * reward)), float(np.dot(weights, reward) / weights.sum()), float(np.mean(dm_rows + weights * (reward - prediction[ix, actions.astype(int)]))), float(weights.sum()**2 / np.dot(weights, weights)), float(weights.max()), n)


def projected_distribution(probabilities: ArrayLike, mapping: ArrayLike, actions: int) -> np.ndarray:
    probabilities = np.asarray(probabilities, dtype=np.float64)
    mapping = np.asarray(mapping)
    if probabilities.ndim != 1 or mapping.shape != probabilities.shape or np.any(mapping != mapping.astype(int)) or actions <= 0 or np.any(mapping < 0) or np.any(mapping >= actions) or not np.all(np.isfinite(probabilities)) or np.any(probabilities < 0) or not np.isclose(probabilities.sum(), 1, atol=1e-12, rtol=0):
        raise ValueError("Invalid categorical projection")
    # Normalize the actual floating-point categorical vector before and after
    # pushforward. In particular, all proposals mapping to one fallback must
    # log exactly1, not1.0000000000000002 from accumulation roundoff.
    probabilities = probabilities / probabilities.sum()
    result = np.bincount(mapping.astype(int), weights=probabilities, minlength=actions)
    return result / result.sum()
