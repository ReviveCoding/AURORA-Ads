"""Dependence-unit statistics; rows, prompts and repeated seeds are not units."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import nct, t


def superiority_power(units: int, standard_deviation: float, *, alternative: float, null_boundary: float, alpha: float = .05) -> float:
    """P(lower two-sided CI > boundary) under a prospective paired-t model."""
    if units < 2 or standard_deviation <= 0 or not all(math.isfinite(value) for value in (standard_deviation, alternative, null_boundary)) or not 0 < alpha < 1:
        raise ValueError("Finite planning assumptions and at least two units required")
    noncentrality = math.sqrt(units) * (alternative - null_boundary) / standard_deviation
    return float(nct.sf(t.ppf(1 - alpha / 2, units - 1), units - 1, noncentrality))


def pilot_sample_size(paired_effects: np.ndarray, *, minimum: int = 40, maximum: int = 200, target_power: float = .8, alternative: float = .02, null_boundary: float = .01) -> dict:
    """Use pilot variance only, not its mean, for the frozen policy N decision."""
    effects = np.asarray(paired_effects, dtype=float)
    if effects.shape != (20,) or not np.isfinite(effects).all() or not 2 <= minimum <= maximum or minimum % 4 or maximum % 4 or not 0 < target_power < 1 or alternative <= null_boundary:
        raise ValueError("Twenty independent pilot-world effects and fixed four-family allocation required")
    sd = float(effects.std(ddof=1))
    if sd == 0:
        return {"selected_worlds": minimum, "pilot_sd": sd, "planning_power": None, "scientific_status": "UNDERPOWERED", "reason": "Constant pilot is not proof of zero population variance; power not estimable", "pilot_mean_used_for_selection": False}
    selected = maximum
    for units in range(minimum, maximum + 1, 4):
        if superiority_power(units, sd, alternative=alternative, null_boundary=null_boundary) >= target_power:
            selected = units
            break
    power = superiority_power(selected, sd, alternative=alternative, null_boundary=null_boundary)
    return {"selected_worlds": selected, "pilot_sd": sd, "planning_power": power, "scientific_status": "NOT_ESTABLISHED" if power >= target_power else "UNDERPOWERED", "target_power": target_power, "alternative": alternative, "null_boundary": null_boundary, "pilot_mean_used_for_selection": False, "assumption": "Pilot SD plug-in; finite20-world uncertainty remains and requires sensitivity reporting"}


@dataclass(frozen=True)
class ClusterEstimate:
    mean: float
    lower: float
    upper: float
    independent_units: int
    repetitions_per_unit: int
    per_unit: tuple[float, ...]
    bootstrap_draws: int


def paired_cluster_estimate(unit_ids: list[str], candidate: np.ndarray, baseline: np.ndarray, *, strata: list[str] | None = None, bootstrap_draws: int = 10000, seed: int = 514) -> ClusterEstimate:
    """Average declared repeated seeds within unit before a paired bootstrap.

    With strata, the endpoint weights mechanism strata equally; bootstrap draws
    resample whole units within each fixed stratum. Without strata, each unit
    has equal weight. This assumes exchangeable units within declared strata,
    not that a convenience taxonomy is a random operator-workflow population.
    """
    candidate, baseline = np.asarray(candidate, dtype=float), np.asarray(baseline, dtype=float)
    if candidate.ndim != 2 or candidate.shape != baseline.shape or candidate.shape[0] != len(unit_ids) or candidate.shape[1] < 1 or len(unit_ids) < 2 or len(set(unit_ids)) != len(unit_ids) or not all(np.isfinite(value).all() for value in (candidate, baseline)) or bootstrap_draws < 100:
        raise ValueError("Unique paired dependence units and finite matched seed matrix required")
    effects = (candidate - baseline).mean(axis=1)
    strata = strata if strata is not None else ["all"] * len(unit_ids)
    if len(strata) != len(unit_ids) or not all(isinstance(item, str) and item for item in strata):
        raise ValueError("Explicit stratum identity per whole unit required")
    groups = [np.flatnonzero(np.asarray(strata) == name) for name in sorted(set(strata))]
    if any(len(group) < 2 for group in groups):
        raise ValueError("Cannot estimate within-stratum uncertainty with one independent unit")
    random = np.random.default_rng(seed)
    means = []
    draws = np.zeros(bootstrap_draws)
    for group in groups:
        values = effects[group]
        means.append(values.mean())
        draws += values[random.integers(len(values), size=(bootstrap_draws, len(values)))].mean(axis=1) / len(groups)
    lower, upper = np.quantile(draws, [.025, .975])
    return ClusterEstimate(float(np.mean(means)), float(lower), float(upper), len(unit_ids), candidate.shape[1], tuple(float(value) for value in effects), bootstrap_draws)


def zero_event_family_bound(families: int, *, alpha: float = .05) -> float:
    if families < 1 or not 0 < alpha < 1:
        raise ValueError("Independent family count and explicit tail probability required")
    return float(-math.expm1(math.log(alpha) / families))


def holm_adjust(pvalues: np.ndarray) -> np.ndarray:
    values = np.asarray(pvalues, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("Finite predeclared family of p-values required")
    order = np.argsort(values, kind="stable")
    adjusted = np.empty_like(values)
    adjusted[order] = np.minimum(1., np.maximum.accumulate(values[order] * np.arange(len(values), 0, -1)))
    return adjusted
