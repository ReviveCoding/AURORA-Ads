"""D3 conditional-on-H exponential baseline with explicit immediate-event atom."""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F


class ConditionalExponentialDelay(nn.Module):
    """Linear incidence/rate/zero-atom heads; no neural hidden tower.

    The zero atom handles source-recorded immediate conversions without inventing
    subsecond times or changing q=P(recorded conversion within7days).
    """
    def __init__(self, features: int):
        super().__init__()
        self.heads = nn.Linear(features, 3)

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        output = self.heads(features)
        return output[:, 0], output[:, 1], output[:, 2]


def conditional_cdf(age: torch.Tensor, log_rate: torch.Tensor, *, horizon: float = 7.) -> torch.Tensor:
    if not math.isfinite(horizon) or horizon <= 0 or age.shape != log_rate.shape or torch.any(age < 0) or not torch.isfinite(age).all() or not torch.isfinite(log_rate).all():
        raise ValueError("Finite aligned age/rate and positive horizon required")
    rate = F.softplus(log_rate.double()) + torch.finfo(torch.float64).tiny
    return -torch.expm1(-rate * torch.clamp(age.double(), max=horizon)) / -torch.expm1(-rate * horizon)


def exponential_log_likelihood(q_logit: torch.Tensor, log_rate: torch.Tensor,
                               zero_atom_logit: torch.Tensor, age: torch.Tensor,
                               observed_delay: torch.Tensor, *, horizon: float = 7.) -> torch.Tensor:
    if q_logit.ndim != 1 or any(value.shape != q_logit.shape for value in (log_rate, zero_atom_logit, age, observed_delay)):
        raise ValueError("One coherent as-of snapshot per origin required")
    if not all(torch.isfinite(value).all() for value in (q_logit, log_rate, zero_atom_logit, age, observed_delay)):
        raise ValueError("Nonfinite predictor or observed snapshot")
    positive = observed_delay >= 0
    if torch.any(observed_delay[positive] > torch.minimum(age[positive], torch.full_like(age[positive], horizon))) or torch.any(observed_delay[~positive] != -1):
        raise ValueError("Future/out-of-horizon event or invalid missing sentinel")
    q, atom = q_logit.double(), zero_atom_logit.double()
    # Validate age/rate using the independent CDF path before constructing the
    # survival branch. Never differentiate log(1-F(H)) at F(H)=1: masked NaNs
    # would otherwise contaminate the rate gradient of mature negatives.
    conditional_cdf(age, log_rate, horizon=horizon)
    rate = F.softplus(log_rate.double()) + torch.finfo(torch.float64).tiny
    # Mix never-within-H with the survival of a within-H positive event. This
    # remains stable at complete maturation and vanishing rate limits.
    partial = ~positive & (age < horizon)
    safe_age = torch.where(partial, age.double(), torch.zeros_like(age.double()))
    log_survival = (F.logsigmoid(-atom) - rate * safe_age
                    + torch.log(-torch.expm1(-rate * (horizon - safe_age)))
                    - torch.log(-torch.expm1(-rate * horizon)))
    censored = torch.logaddexp(F.logsigmoid(-q), F.logsigmoid(q) + log_survival)
    result = torch.where(partial, censored, F.logsigmoid(-q))
    immediate = positive & (observed_delay == 0)
    later = positive & ~immediate
    result = torch.where(immediate, F.logsigmoid(q) + F.logsigmoid(atom), result)
    log_density = (F.logsigmoid(q) + F.logsigmoid(-atom) + torch.log(rate)
                   - rate * observed_delay.double() - torch.log(-torch.expm1(-rate * horizon)))
    result = torch.where(later, log_density, result)
    return result
