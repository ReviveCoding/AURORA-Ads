"""Finite-horizon numerical model ladder; R3 empirical execution is source-gated."""
from __future__ import annotations

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

BIN_EDGES = (0., .01, .1, .5, 1., 2., 3., 5., 7.)


def neural_log_likelihood(q_logit: torch.Tensor, mass_logits: torch.Tensor, age: torch.Tensor, event_bin: torch.Tensor, edges: tuple[float, ...] = BIN_EDGES) -> torch.Tensor:
    """One as-of likelihood/origin. Zero is an atom; other bins uniform inside."""
    if q_logit.ndim != 1 or mass_logits.shape != (len(q_logit), len(edges)) or age.shape != q_logit.shape or event_bin.shape != age.shape:
        raise ValueError("One coherent as-of snapshot per origin required")
    if edges[0] != 0 or any(right <= left for left, right in zip(edges[:-1], edges[1:])) or not all(np.isfinite(edges)):
        raise ValueError("Fixed increasing finite-horizon bins required")
    if torch.any(age < 0) or not torch.isfinite(age).all() or torch.any((event_bin < -1) | (event_bin >= len(edges))) or torch.any(event_bin != event_bin.long()):
        raise ValueError("Invalid age/event index")
    q = q_logit.double()
    logq, lognotq = F.logsigmoid(q), F.logsigmoid(-q)
    logmass = F.log_softmax(mass_logits.double(), dim=1)
    result = torch.empty_like(q)
    positive = event_bin >= 0
    if positive.any():
        indices = torch.nonzero(positive).flatten()
        lower = torch.tensor(edges, device=age.device, dtype=age.dtype)[torch.clamp(event_bin[indices].long() - 1, min=0)]
        if torch.any(age[indices] < lower):
            raise ValueError("Future event supplied to fitting cutoff")
        result[indices] = logq[indices] + logmass[indices, event_bin[indices].long()]
    mature = ~positive & (age >= edges[-1])
    result[mature] = lognotq[mature]
    partial = ~positive & ~mature
    if partial.any():
        u = age[partial].double()
        survival_fractions = torch.stack([torch.zeros_like(u), *(1 - torch.clamp((u - left) / (right - left), 0, 1) for left, right in zip(edges[:-1], edges[1:]))], dim=1)
        logsurvival = torch.logsumexp(logmass[partial] + torch.log(survival_fractions), dim=1)
        result[partial] = torch.logaddexp(lognotq[partial], logq[partial] + logsurvival)
    return result


class NeuralFiniteHorizon(nn.Module):
    def __init__(self, features: int, hidden: int = 32):
        super().__init__()
        self.network = nn.Sequential(nn.Linear(features, hidden), nn.SiLU(), nn.Linear(hidden, 1 + len(BIN_EDGES)))

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        outputs = self.network(features)
        return outputs[:, 0], outputs[:, 1:]


def observed_binary_targets(age: np.ndarray, event_bin: np.ndarray, *, mature_only: bool) -> tuple[np.ndarray, np.ndarray]:
    """D0 pending-negative diagnostic or D1 mature-only admissible origin mask."""
    age, event_bin = np.asarray(age), np.asarray(event_bin)
    if age.ndim != 1 or age.shape != event_bin.shape or np.any(age < 0) or not np.isfinite(age).all() or not np.isfinite(event_bin).all() or np.any(event_bin != event_bin.astype(int)) or np.any((event_bin < -1) | (event_bin >= len(BIN_EDGES))):
        raise ValueError("Invalid origin snapshot")
    observed = event_bin >= 0
    if np.any(age[observed] < np.asarray(BIN_EDGES)[np.maximum(event_bin[observed].astype(int) - 1, 0)]):
        raise ValueError("Future event supplied to binary fitting snapshot")
    eligible = age >= BIN_EDGES[-1] if mature_only else np.ones(len(age), dtype=bool)
    return eligible, (event_bin >= 0).astype(np.int64)


class FiniteIncidenceDelay(nn.Module):
    """D3 linear incidence/finite categorical-delay comparator, no deep tower."""
    def __init__(self, features: int):
        super().__init__()
        self.incidence = nn.Linear(features, 1)
        self.delay = nn.Linear(features, len(BIN_EDGES))

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.incidence(features).squeeze(1), self.delay(features)


class FeedbackCorrection(nn.Module):
    """D2 eventual-incidence/exponential model converted explicitly to7day q.

    This is a parametric delayed-feedback comparator, not a measured lifetime
    estimand. R3 admission/as-of clock qualification is still required to fit it.
    """
    def __init__(self, features: int):
        super().__init__()
        self.eventual = nn.Linear(features, 1)
        self.lograte = nn.Linear(features, 1)

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        eventual = torch.sigmoid(self.eventual(features).squeeze(1))
        rate = F.softplus(self.lograte(features).squeeze(1)) + torch.finfo(features.dtype).tiny
        finite = eventual * -torch.expm1(-7 * rate)
        return finite, rate


def feedback_log_likelihood(eventual_logit: torch.Tensor, log_rate: torch.Tensor, age: torch.Tensor, occurrence_delay: torch.Tensor, *, horizon: float = 7.) -> torch.Tensor:
    """D2 continuous exponential-mixture comparator with finite censoring.

    Negative delay denotes no event available at the snapshot. Continuous
    density is not a zero-delay atom or discrete-bin probability; comparisons
    with D3/D4 must use the common finite binary/forecast evaluation endpoint,
    not compare these incompatible likelihood normalizers. No reporting lag is
    inferred here: the caller must admit availability separately.
    """
    if eventual_logit.ndim != 1 or any(value.shape != eventual_logit.shape for value in (log_rate, age, occurrence_delay)) or not np.isfinite(horizon) or horizon <= 0:
        raise ValueError("One finite-horizon snapshot per origin required")
    if not all(torch.isfinite(value).all() for value in (eventual_logit, log_rate, age, occurrence_delay)) or torch.any(age < 0):
        raise ValueError("Nonfinite predictor or invalid snapshot clock")
    positive = occurrence_delay >= 0
    if torch.any(occurrence_delay[positive] > horizon) or torch.any(occurrence_delay[positive] > age[positive]) or torch.any(occurrence_delay[~positive] != -1):
        raise ValueError("Future/out-of-horizon occurrence or invalid missing-event sentinel")
    logeventual = F.logsigmoid(eventual_logit.double())
    lognever = F.logsigmoid(-eventual_logit.double())
    rate = F.softplus(log_rate.double()) + torch.finfo(torch.float64).tiny
    result = torch.logaddexp(lognever, logeventual - rate * torch.clamp(age.double(), max=horizon))
    result = torch.where(positive, logeventual + torch.log(rate) - rate * occurrence_delay.double(), result)
    return result
