"""Finite-grid synthetic bidders with explicit price and forecast assumptions."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.special import ndtr, log_ndtr

GRID = np.array([0., .25, .5, .75, 1., 1.5, 2., 3.])


@dataclass(frozen=True)
class BidForecast:
    bids: NDArray[np.float64]
    win_probability: NDArray[np.float64]
    expected_payment: NDArray[np.float64]
    expected_recorded_gross: NDArray[np.float64]
    score: NDArray[np.float64]
    choice: float


def grid_bid_forecast(*, value_if_exposed: float, log_price_mean: float, log_price_sd: float, payment_mode: Literal["first_price", "second_price"], scarcity_price: float = 0.) -> BidForecast:
    """vF(b)-ordinary payment-scarcity payment; no hidden pre-bid market access.

    Inputs are fitted forecasts, not simulator parameters or per-auction truth.
    Conditional price/value independence is an explicit modeling assumption.
    Uncalibrated synthetic forecasts must not be relabeled real-data estimates.
    """
    if not all(math.isfinite(value) for value in (value_if_exposed, log_price_mean, log_price_sd, scarcity_price)) or value_if_exposed < 0 or log_price_sd <= 0 or scarcity_price < 0 or payment_mode not in {"first_price", "second_price"}:
        raise ValueError("Finite admitted nonnegative value/dual and positive price scale required")
    bids = GRID.copy()
    cdf = np.zeros(len(bids))
    z = (np.log(bids[1:]) - log_price_mean) / log_price_sd
    cdf[1:] = ndtr(z)
    if payment_mode == "first_price":
        payment = bids * cdf
    else:
        payment = np.zeros(len(bids))
        # Evaluate in log space; finite-grid truncated expectation stays <=bid
        # even when the untruncated lognormal mean would overflow.
        log_truncated = log_price_mean + log_price_sd**2 / 2 + log_ndtr(z - log_price_sd)
        payment[1:] = np.exp(np.minimum(log_truncated, np.log(bids[1:])))
    if np.any(payment > bids * cdf + 1e-10) or not np.isfinite(payment).all():
        raise FloatingPointError("Forecast payment is not a valid truncated expectation")
    gross = value_if_exposed * cdf
    score = gross - (1 + scarcity_price) * payment
    if not np.isfinite(score).all():
        raise FloatingPointError("Nonfinite grid utility forecast")
    choice = float(bids[int(np.argmax(score))])  # deterministic smallest-bid tie
    return BidForecast(bids, cdf, payment, gross, score, choice)


def calibrated_linear_bid(value_if_exposed: float, *, factor: float = 1.) -> float:
    """Floor a nonnegative calibrated value bid to the declared finite grid."""
    if not all(math.isfinite(value) and value >= 0 for value in (value_if_exposed, factor)):
        raise ValueError("Finite nonnegative calibrated forecast/factor required")
    return float(GRID[np.searchsorted(GRID, min(3., value_if_exposed * factor), side="right") - 1])


def censored_market_nll(log_price_mean, log_price_sd: float, bids, wins, payments, *, payment_mode: Literal["first_price", "second_price"]) -> float:
    """Observable auction likelihood, not a likelihood using hidden loser prices.

    Second-price wins reveal the conservatively rounded payment interval
    (paid-0.0001,paid]. Losses reveal only M>bid. First-price win/loss data reveal
    only M<=bid or M>bid; their payment is not substituted for market price.
    Inputs contain admitted, eligible, actually submitted positive bids only.
    """
    mu = np.asarray(log_price_mean, dtype=float)
    bids, payments, wins = np.asarray(bids, dtype=float), np.asarray(payments, dtype=float), np.asarray(wins)
    if mu.ndim != 1 or not len(mu) or bids.shape != mu.shape or payments.shape != mu.shape or wins.shape != mu.shape or wins.dtype != bool or not all(np.isfinite(value).all() for value in (mu, bids, payments)) or np.any(bids <= 0) or np.any(payments < 0) or np.any(payments[~wins] != 0) or not math.isfinite(log_price_sd) or log_price_sd <= 0 or payment_mode not in {"first_price", "second_price"}:
        raise ValueError("Finite valid observed eligible auction sample required")
    z = (np.log(bids) - mu) / log_price_sd
    ll = log_ndtr(-z)
    if payment_mode == "first_price":
        if np.any(np.abs(payments[wins] - bids[wins]) > 1e-4 + 1e-10):
            raise ValueError("First-price payment is not submitted bid")
        ll[wins] = log_ndtr(z[wins])
    else:
        if np.any(payments[wins] <= 0) or np.any(payments[wins] > bids[wins] + 1e-4 + 1e-10):
            raise ValueError("Second-price observable payment interval invalid")
        # Intersect the revealed quantization interval with observed M<=bid.
        upper = np.minimum(payments[wins], bids[wins])
        lower = np.maximum(0., payments[wins] - 1e-4)
        z_upper = (np.log(upper) - mu[wins]) / log_price_sd
        with np.errstate(divide="ignore"):
            z_lower = (np.log(lower) - mu[wins]) / log_price_sd
        # Right-tail intervals use SF(lower)-SF(upper), avoiding CDF≈1-1.
        right_tail = z_lower >= 0
        log_upper = np.where(right_tail, log_ndtr(-z_lower), log_ndtr(z_upper))
        log_lower = np.where(right_tail, log_ndtr(-z_upper), log_ndtr(z_lower))
        ll[wins] = log_upper + np.log(-np.expm1(np.minimum(0., log_lower - log_upper)))
    if not np.isfinite(ll).all():
        raise FloatingPointError("Censored observation has zero probability under proposed model")
    return float(-ll.mean())
