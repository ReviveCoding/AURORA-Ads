"""Small CPU reference functions for design sanity checks, NOT AURORA trained models."""
from __future__ import annotations
import math
from typing import Sequence


def _prob(x: float) -> None:
    if not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError('invalid probability')


def conditional_exp_cdf(age: float, rate: float, horizon: float) -> float:
    if not all(map(math.isfinite, (age, rate, horizon))) or rate <= 0 or horizon <= 0 or age < 0:
        raise ValueError('invalid time/rate')
    u = min(age, horizon)
    return (-math.expm1(-rate*u)) / (-math.expm1(-rate*horizon))


def delayed_probability(q: float, masses: Sequence[float], *, event_bin: int | None,
                        completed_bins: int) -> float:
    _prob(q)
    if not masses or any(not math.isfinite(p) or p < 0 for p in masses):
        raise ValueError('invalid masses')
    if not math.isclose(math.fsum(masses), 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError('mass must sum to one')
    if not 0 <= completed_bins <= len(masses):
        raise ValueError('invalid age')
    if event_bin is not None:
        if not 0 <= event_bin < completed_bins:
            raise ValueError('event must already be observable')
        return q*masses[event_bin]
    return 1-q*math.fsum(masses[:completed_bins])


def projected_probabilities(probabilities: Sequence[float], mapping: Sequence[int], n_actions: int) -> list[float]:
    if len(probabilities) != len(mapping) or n_actions <= 0:
        raise ValueError('shape')
    for p in probabilities: _prob(p)
    if not math.isclose(math.fsum(probabilities),1.0,abs_tol=1e-12):
        raise ValueError('probabilities must sum to one')
    out=[0.0]*n_actions
    for p,a in zip(probabilities,mapping):
        if not isinstance(a,int) or not 0<=a<n_actions: raise ValueError('invalid action')
        out[a]+=p
    return out


def dr_value(actions: Sequence[int], rewards: Sequence[float], logging: Sequence[float],
             target: Sequence[Sequence[float]], q: Sequence[Sequence[float]]) -> float:
    n=len(actions)
    if n == 0 or not all(len(x)==n for x in (rewards,logging,target,q)):
        raise ValueError('shape')
    total=0.0
    for a,r,b,pi,qi in zip(actions,rewards,logging,target,q):
        if not 0<b<=1 or not math.isfinite(r): raise ValueError('support or reward')
        if len(pi)!=len(qi) or not 0<=a<len(pi): raise ValueError('shape')
        for p in pi: _prob(p)
        if not math.isclose(math.fsum(pi),1.0,abs_tol=1e-12): raise ValueError('target mass')
        if not all(map(math.isfinite,qi)): raise ValueError('nonfinite q')
        total += math.fsum(p*v for p,v in zip(pi,qi)) + pi[a]/b*(r-qi[a])
    return total/n


def net_score(gross: float, spend: float, scarcity: float, uncertainty: float=0,
              beta: float=0, operational: float=0) -> float:
    values=(gross,spend,scarcity,uncertainty,beta,operational)
    if not all(map(math.isfinite,values)) or min(spend,scarcity,uncertainty,beta,operational)<0:
        raise ValueError('invalid economics')
    return gross-(1+scarcity)*spend-operational-beta*uncertainty


def required_paired_worlds(sd: float, null_margin: float, design_alternative: float,
                           z_alpha: float=1.959963984540054, z_power: float=1.2815515655446004) -> int:
    """Normal-approximation PLANNING aid; not achieved power or final inference."""
    if not all(map(math.isfinite,(sd,null_margin,design_alternative,z_alpha,z_power))) or sd<0 or z_alpha<=0 or z_power<=0 or design_alternative<=null_margin:
        raise ValueError('invalid planning effect')
    return max(2, math.ceil(((z_alpha+z_power)*sd/(design_alternative-null_margin))**2))
