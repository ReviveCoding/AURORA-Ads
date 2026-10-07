"""Sequential common auction guards for variable public bid proposals."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .bidder import GRID
from .state import SCALE


@dataclass(frozen=True)
class AuctionSettlement:
    executed_bids: NDArray[np.float64]
    eligible: NDArray[np.bool_]
    wins: NDArray[np.bool_]
    payments: NDArray[np.int64]
    balance: int
    executed_probabilities: NDArray[np.float64] | None


def settle_variable_bids(bids: NDArray, market: NDArray, admission: NDArray, balance: int, mode: str, *, uniform_grid_multiplier: float | None = None) -> AuctionSettlement:
    """Evaluator-only settlement: bidder already returned bids before M is read.

    Eligibility precedes market comparison. A failed reservation maps to zero,
    not an ordinary observed loss. Optional probabilities are for an actual
    uniform8-grid proposal, projected through admission/reservation at EACH
    contemporaneous balance. Deterministic/nonuniform bidders return None.
    """
    bids, market, admission = np.asarray(bids, dtype=float), np.asarray(market, dtype=float), np.asarray(admission)
    if bids.ndim != 1 or market.shape != bids.shape or admission.shape != bids.shape or admission.dtype != bool or not np.isfinite(bids).all() or not np.isfinite(market).all() or np.any(bids < 0) or np.any(market <= 0) or not isinstance(balance, int) or balance < 0 or mode not in {"first_price", "second_price"}:
        raise ValueError("Valid finite auction inputs and integer available balance required")
    probabilities = None
    grid_reserves = None
    if uniform_grid_multiplier is not None:
        if not math.isfinite(uniform_grid_multiplier) or uniform_grid_multiplier <= 0 or not np.all(np.any(bids[:, None] == GRID[None] * uniform_grid_multiplier, axis=1)):
            raise ValueError("Exact uniform-grid proposals required for logged probabilities")
        grid_reserves = np.ceil(GRID * uniform_grid_multiplier * SCALE).astype(np.int64)
        probabilities = np.zeros(len(bids))
    executed = np.zeros(len(bids))
    eligible = np.zeros(len(bids), dtype=bool)
    wins = np.zeros(len(bids), dtype=bool)
    payments = np.zeros(len(bids), dtype=np.int64)
    for index, bid in enumerate(bids):
        reserve = math.ceil(float(bid) * SCALE)
        admitted = bool(admission[index])
        can_submit = admitted and bid > 0 and reserve <= balance
        eligible[index] = can_submit
        if probabilities is not None:
            zero_mass = 1. if not admitted else float((np.count_nonzero(grid_reserves > balance) + 1) / len(GRID))
            probabilities[index] = 1 / len(GRID) if can_submit else zero_mass
        if not can_submit:
            continue
        executed[index] = bid
        if bid >= market[index]:
            payment = math.ceil(float(market[index] if mode == "second_price" else bid) * SCALE)
            if payment > reserve:
                raise ValueError("Actual payment exceeds conservative reservation")
            wins[index] = True
            payments[index] = payment
            balance -= payment
    return AuctionSettlement(executed, eligible, wins, payments, balance, probabilities)
