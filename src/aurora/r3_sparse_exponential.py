"""Sparse CPU D3 likelihood; linear incidence/rate, conditional on fixed H.

This is the declared parametric baseline, not a neural/GPU fallback.
"""
from __future__ import annotations

import numpy as np
from scipy.special import expit


def _difference_g(rate: np.ndarray, first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """first/expm1(rate*first) minus second/expm1(rate*second)."""
    small = rate * np.maximum(first, second) < 1e-3
    result = np.empty_like(rate)
    r, a, b = rate[small], first[small], second[small]
    result[small] = (b - a) / 2 + r * (a*a - b*b) / 12 - r**3 * (a**4 - b**4) / 720
    r, a, b = rate[~small], first[~small], second[~small]
    # exp(-z)/(1-exp(-z)) avoids overflow for large positive rates.
    result[~small] = a * np.exp(-r*a) / -np.expm1(-r*a) - b * np.exp(-r*b) / -np.expm1(-r*b)
    return result


def likelihood_gradient(q_logit: np.ndarray, rate_logit: np.ndarray, age: np.ndarray,
                        observed_delay: np.ndarray, *, horizon: float = 7.) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a, b, u, delay = [np.asarray(item, dtype=float) for item in (q_logit, rate_logit, age, observed_delay)]
    if a.ndim != 1 or any(item.shape != a.shape for item in (b, u, delay)) or not all(np.isfinite(item).all() for item in (a, b, u, delay)) or horizon <= 0 or not np.isfinite(horizon) or np.any(u < 0):
        raise ValueError("Finite coherent single-snapshot inputs required")
    positive = delay >= 0
    if np.any(delay[positive] <= 0) or np.any(delay[positive] > np.minimum(u[positive], horizon)) or np.any(delay[~positive] != -1):
        raise ValueError("No zero atom in this positive-delay source recipe; future/invalid events forbidden")
    rate = np.logaddexp(0., b) + np.finfo(float).tiny
    q = expit(a)
    loss = np.logaddexp(0., a)
    dq, db = q.copy(), np.zeros_like(q)
    log_z = np.log(-np.expm1(-rate * horizon))
    p_rate, p_delay = rate[positive], delay[positive]
    loss[positive] = np.logaddexp(0., -a[positive]) - np.log(p_rate) + p_rate*p_delay + log_z[positive]
    dq[positive] -= 1
    small = p_rate * horizon < 1e-3
    density_derivative = np.empty_like(p_rate)
    density_derivative[small] = horizon/2 - p_delay[small] - p_rate[small]*horizon**2/12 + p_rate[small]**3*horizon**4/720
    r = p_rate[~small]
    density_derivative[~small] = 1/r - p_delay[~small] - horizon*np.exp(-r*horizon)/-np.expm1(-r*horizon)
    db[positive] = -density_derivative * expit(b[positive])
    partial = ~positive & (u < horizon)
    r, t = rate[partial], u[partial]
    log_survival = -r*t + np.log(-np.expm1(-r*(horizon-t))) - log_z[partial]
    log_q, log_not_q = -np.logaddexp(0., -a[partial]), -np.logaddexp(0., a[partial])
    log_likelihood = np.logaddexp(log_not_q, log_q + log_survival)
    responsibility = np.exp(log_q + log_survival - log_likelihood)
    loss[partial] = -log_likelihood
    dq[partial] -= responsibility
    derivative = -t + _difference_g(r, horizon-t, np.full_like(t, horizon))
    db[partial] = -responsibility * derivative * expit(b[partial])
    if not all(np.isfinite(item).all() for item in (loss, dq, db)):
        raise ValueError("Nonfinite conditional-exponential likelihood/gradient")
    return loss, dq, db


def sparse_objective(weights: np.ndarray, matrix, age: np.ndarray, delay: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    dimension = matrix.shape[1]
    if weights.shape != (2*(dimension+1),) or alpha < 0 or not np.isfinite(alpha) or matrix.shape[0] == 0:
        raise ValueError("Two linear heads and nonnegative regularization required")
    heads = weights.reshape(2, dimension+1)
    logits = np.asarray(matrix @ heads[:, :-1].T) + heads[:, -1]
    loss, dq, db = likelihood_gradient(logits[:, 0], logits[:, 1], age, delay)
    derivative = np.column_stack((dq, db)) / len(age)
    gradient = np.column_stack((np.asarray(matrix.T @ derivative).T, derivative.sum(0)))
    gradient[:, :-1] += alpha * heads[:, :-1]
    value = float(loss.mean() + .5*alpha*np.sum(heads[:, :-1]**2))
    return value, gradient.ravel()
