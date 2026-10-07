"""Explicit score conventions; ordinary costs are not charged twice."""
from __future__ import annotations

import math

import numpy as np


def posterior_net_score(mean, exploration, spend, *, scarcity: float):
    """Posterior reward=(gross-spend-operation)/100; dual is extra spend price."""
    mean, exploration, spend = (np.asarray(value, dtype=float) for value in (mean, exploration, spend))
    if mean.shape != (6,) or exploration.shape != mean.shape or spend.shape != mean.shape or not all(np.isfinite(value).all() for value in (mean, exploration, spend)) or np.any(spend < 0) or not math.isfinite(scarcity) or scarcity < 0:
        raise ValueError("Finite six-action net posterior/spend and nonnegative scarcity required")
    return (mean + exploration) * 100 - scarcity * spend
