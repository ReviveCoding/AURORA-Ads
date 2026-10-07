"""Fixed-policy reward features and cluster-aware one-step OPE diagnostics."""
from __future__ import annotations

from dataclasses import asdict

import numpy as np
from scipy.stats import t
from sklearn.feature_extraction import FeatureHasher

from .measurement import fixed_policy_ope


def reward_features(context: np.ndarray, actions: np.ndarray):
    if context.ndim != 2 or len(context) != len(actions) or context.shape[1] != 4:
        raise ValueError("Four source pretreatment user features required")
    rows = ([f"action={int(action)}", *(f"user{j}={value}" for j, value in enumerate(row)), *(f"action={int(action)}:user{j}={value}" for j, value in enumerate(row))] for row, action in zip(context, actions))
    return FeatureHasher(n_features=4096, input_type="string", alternate_sign=False).transform(rows)


def all_rewards(model, context: np.ndarray, n_actions: int = 34) -> np.ndarray:
    outputs = []
    for start in range(0, len(context), 1024):
        chunk = context[start:start + 1024]
        repeated = np.repeat(chunk, n_actions, axis=0)
        actions = np.tile(np.arange(n_actions), len(chunk))
        outputs.append(model.predict_proba(reward_features(repeated, actions))[:, 1].reshape(len(chunk), n_actions))
    return np.concatenate(outputs)


def epsilon_target(prediction: np.ndarray, epsilon: float = .1) -> np.ndarray:
    if prediction.ndim != 2 or not np.all(np.isfinite(prediction)) or not 0 < epsilon <= 1:
        raise ValueError("Invalid reward predictions/epsilon")
    target = np.full(prediction.shape, epsilon / prediction.shape[1], dtype=np.float64)
    target[np.arange(len(target)), np.argmax(prediction, axis=1)] += 1 - epsilon
    return target


def estimate_with_clusters(actions, reward, propensity, target, prediction, clusters, *, clip: float | None = None):
    """Student-t interval on cluster mean influence, not independent-row fiction.

    Unequal-size clusters use cluster totals divided by the full row count;
    intervals condition on the realized partition/population and fixed models.
    With too few clusters these remain explicitly underpowered diagnostics.
    """
    actions = np.asarray(actions, dtype=int)
    reward = np.asarray(reward, dtype=float)
    propensity = np.asarray(propensity, dtype=float)
    clusters = np.asarray(clusters)
    raw = asdict(fixed_policy_ope(actions, reward, propensity, target, prediction))
    weights = target[np.arange(len(actions)), actions] / propensity
    if clip is not None:
        if clip <= 0:
            raise ValueError("Positive clipping bound required")
        weights = np.minimum(weights, clip)
    dm = np.sum(target * prediction, axis=1)
    rows = {"dm": dm, "ips": weights * reward, "dr": dm + weights * (reward - prediction[np.arange(len(actions)), actions])}
    ids = np.unique(clusters)
    output = {"estimates": raw, "weight_quantiles": np.quantile(weights, [0, .5, .9, .99, 1]).tolist(), "clusters": int(len(ids)), "clip": clip, "intervals": {}, "scientific_outcome": "UNDERPOWERED" if len(ids) < 20 else "NOT_ESTABLISHED", "independent_unit": "UTC calendar-day cluster (serial-dependence assumption; not proven independent users)"}
    output["estimates"].update(ips=float(rows["ips"].mean()), dr=float(rows["dr"].mean()), snips=float(np.dot(weights, reward) / weights.sum()), ess=float(weights.sum()**2 / np.dot(weights, weights)), max_weight=float(weights.max()))
    for name, values in rows.items():
        estimate = float(values.mean())
        contributions = np.array([np.sum(values[clusters == group] - estimate) for group in ids])
        se = float(np.sqrt(len(ids) / (len(ids) - 1) * np.dot(contributions, contributions)) / len(values)) if len(ids) > 1 else None
        width = float(t.ppf(.975, len(ids) - 1) * se) if se is not None else None
        output["intervals"][name] = {"estimate": estimate, "se": se, "ci95": [estimate - width, estimate + width] if width is not None else None, "method": "calendar-cluster sandwich t interval; small-cluster diagnostic only"}
    output["clipping_limitation"] = "Clipped IPS/DR are bias-sensitive diagnostics, not the primary estimand" if clip is not None else None
    return output
