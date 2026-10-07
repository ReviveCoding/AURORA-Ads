"""Observable S1 auction interfaces; latent simulator prices/outcomes are absent."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.special import ndtr, log_ndtr
from sklearn.preprocessing import StandardScaler

from .bidder import GRID, censored_market_nll

CONTEXT_NAMES = ("x0", "x1", "x2", "x3", "segment", "time_sine", "elapsed_day_fraction")


@dataclass(frozen=True)
class AuctionObservation:
    """A complete origin interval's *observable* auction and mature reward rows.

    Gross is zero for nonexposures as an absent observation, not an estimated
    losing-auction outcome. Value fitting must select wins. No market-price or
    no-ad counterfactual field is accepted. Eligibility is decided before price
    comparison; budget-ineligible opportunities are not randomized price losses.
    """
    cohort_id: str
    origin_interval: int
    observed_at_day: float
    context: NDArray[np.float64]
    submitted_bid: NDArray[np.float64]
    eligible: NDArray[np.bool_]
    won: NDArray[np.bool_]
    payment: NDArray[np.float64]
    observed_gross: NDArray[np.float64]
    executed_bid_probability: NDArray[np.float64] | None = None

    def __post_init__(self) -> None:
        n = len(self.submitted_bid)
        if not self.cohort_id or self.origin_interval < 0 or not np.isfinite(self.observed_at_day) or self.observed_at_day < (self.origin_interval + 1) / 96 + 7:
            raise ValueError("Unique, fully matured origin interval required")
        if self.context.shape != (n, len(CONTEXT_NAMES)) or not np.isfinite(self.context).all():
            raise ValueError("Finite public opportunity context required")
        for field in (self.submitted_bid, self.payment, self.observed_gross):
            if field.shape != (n,) or not np.isfinite(field).all() or np.any(field < 0):
                raise ValueError("Finite nonnegative observable auction arrays required")
        if self.eligible.shape != (n,) or self.won.shape != (n,) or self.eligible.dtype != bool or self.won.dtype != bool or np.any(self.won & ~self.eligible):
            raise ValueError("Pre-auction eligibility and observed exposure masks required")
        if np.any(self.payment[~self.won] != 0) or np.any(self.observed_gross[~self.won] != 0) or np.any(self.payment > self.submitted_bid + 1e-4 + 1e-10):
            raise ValueError("Unobserved loser prices/rewards or over-reservation payments")
        probability = self.executed_bid_probability
        if probability is not None and (probability.shape != (n,) or not np.isfinite(probability).all() or np.any(probability <= 0) or np.any(probability > 1)):
            raise ValueError("Exact executed bid probabilities or explicit None required")


class CensoredLognormalMarket:
    """Bounded regularized context model, using only eligible submitted auctions.

    The likelihood respects the payment mode. Bounds/ridge are model choices,
    not knowledge of simulator parameters. No unqualified calibrated label.
    """
    def __init__(self, payment_mode: Literal["first_price", "second_price"], ridge: float = .001):
        if payment_mode not in {"first_price", "second_price"} or not np.isfinite(ridge) or ridge < 0:
            raise ValueError("Declared payment mode and nonnegative ridge required")
        self.payment_mode = payment_mode
        self.ridge = ridge
        self.scaler = StandardScaler()
        self.coefficients: NDArray[np.float64] | None = None
        self.sd: float | None = None
        self.fit_diagnostics: dict = {}

    def fit(self, context: NDArray, bids: NDArray, wins: NDArray, payments: NDArray) -> CensoredLognormalMarket:
        context = np.asarray(context, dtype=float)
        if context.ndim != 2 or context.shape[1] != len(CONTEXT_NAMES) or not np.isfinite(context).all() or len(context) < 100 or not np.any(wins) or np.all(wins):
            raise ValueError("Both observed auction classes and nonempty public context required")
        design = np.column_stack([np.ones(len(context)), self.scaler.fit_transform(context)])
        # Strict observable-array validation before optimization.
        censored_market_nll(np.zeros(len(context)), .6, bids, wins, payments, payment_mode=self.payment_mode)
        initial = np.zeros(design.shape[1] + 1)
        initial[-1] = np.log(.6)

        def objective(parameters):
            nll = censored_market_nll(design @ parameters[:-1], float(np.exp(parameters[-1])), bids, wins, payments, payment_mode=self.payment_mode)
            return nll + self.ridge * float(parameters[1:-1] @ parameters[1:-1]) / 2

        result = minimize(objective, initial, method="L-BFGS-B", bounds=[(-10., 10.)] * design.shape[1] + [(np.log(.05), np.log(2.))], options={"maxiter": 150, "ftol": 1e-9, "maxls": 40})
        if not result.success or not np.isfinite(result.fun):
            raise ValueError(f"Observable market fit did not converge: {result.message}")
        self.coefficients = np.asarray(result.x[:-1], dtype=float)
        self.sd = float(np.exp(result.x[-1]))
        self.fit_diagnostics = {"eligible_positive_bid_rows": len(context), "optimizer_success": bool(result.success), "iterations": int(result.nit), "objective": float(result.fun), "payment_mode": self.payment_mode, "ridge": self.ridge, "sd_bounds": [.05, 2.], "coefficient_bounds": [-10., 10.], "not_calibration_certificate": True}
        return self

    def predict(self, context: NDArray) -> tuple[NDArray[np.float64], float]:
        if self.coefficients is None or self.sd is None:
            raise ValueError("Observable market fit required")
        context = np.asarray(context, dtype=float)
        if context.ndim != 2 or context.shape[1] != len(CONTEXT_NAMES) or not np.isfinite(context).all():
            raise ValueError("Finite public prediction context required")
        design = np.column_stack([np.ones(len(context)), self.scaler.transform(context)])
        return design @ self.coefficients, self.sd


def batch_grid_bid(value: NDArray, log_price_mean: NDArray, log_price_sd: float, *, payment_mode: Literal["first_price", "second_price"], scarcity: float = 0., multiplier: float = 1.) -> NDArray[np.float64]:
    """Same finite-grid utility kernel, vectorized across public opportunities."""
    value, mu = np.asarray(value, dtype=float), np.asarray(log_price_mean, dtype=float)
    if value.ndim != 1 or mu.shape != value.shape or not np.isfinite(value).all() or not np.isfinite(mu).all() or np.any(value < 0) or not np.isfinite(log_price_sd) or not .05 <= log_price_sd <= 2. or not np.isfinite(scarcity) or scarcity < 0 or not np.isfinite(multiplier) or multiplier <= 0 or payment_mode not in {"first_price", "second_price"}:
        raise ValueError("Finite admitted per-opportunity forecasts required")
    actual_grid = GRID * multiplier
    z = (np.log(actual_grid[1:])[None] - mu[:, None]) / log_price_sd
    cdf = ndtr(z)
    if payment_mode == "first_price":
        payment = actual_grid[None, 1:] * cdf
    else:
        payment = np.exp(np.minimum(mu[:, None] + log_price_sd**2 / 2 + log_ndtr(z - log_price_sd), np.log(actual_grid[1:])[None]))
    score = np.column_stack([np.zeros(len(value)), value[:, None] * cdf - (1 + scarcity) * payment])
    if not np.isfinite(score).all() or np.any(payment > actual_grid[None, 1:] * cdf + 1e-10):
        raise FloatingPointError("Invalid finite-grid forecast")
    return GRID[np.argmax(score, axis=1)].copy()
