"""One deterministic numerical bidder, not an application LLM/multi-agent system."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray

from .auction_learning import CensoredLognormalMarket, CONTEXT_NAMES, batch_grid_bid
from .bidder import GRID
from .simulator import Snapshot, rng
from .state import Action


class ObservedValueModel(Protocol):
    def predict(self, features: NDArray) -> NDArray: ...


@dataclass(frozen=True)
class BidProposal:
    base_bids: NDArray[np.float64]
    uniform_grid: bool = False

    def __post_init__(self):
        if self.base_bids.ndim != 1 or not np.isfinite(self.base_bids).all() or not np.all(np.any(self.base_bids[:, None] == GRID[None], axis=1)):
            raise ValueError("Exact declared finite-grid base proposals required")


class FixedBidder:
    def __init__(self, bid: float):
        if bid not in GRID:
            raise ValueError("Declared fixed-grid bid required")
        self.bid = bid

    def propose(self, context: NDArray, snapshot: Snapshot, action: Action, multiplier: float, scarcity: float) -> BidProposal:
        return BidProposal(np.full(len(context), self.bid))


class RandomizedGridBidder:
    """Exact uniform proposal before shared mechanical projection; keyed stream."""
    def __init__(self, world_id: str, seed: int = 735):
        self.world_id = world_id
        self.seed = seed

    def propose(self, context: NDArray, snapshot: Snapshot, action: Action, multiplier: float, scarcity: float) -> BidProposal:
        generator = rng(self.world_id, snapshot.campaign, snapshot.interval, f"fast_bid_sampling|{self.seed}")
        return BidProposal(generator.choice(GRID, size=len(context)), uniform_grid=True)


class LearnedBidder:
    def __init__(self, method: Literal["calibrated_linear", "grid_utility"], value_model: ObservedValueModel, market: CensoredLognormalMarket, *, linear_factor: float = 1.):
        if method not in {"calibrated_linear", "grid_utility"} or not math.isfinite(linear_factor) or linear_factor < 0:
            raise ValueError("Declared fitted bidder recipe required")
        self.method = method
        self.value_model = value_model
        self.market = market
        self.linear_factor = linear_factor

    def propose(self, context: NDArray, snapshot: Snapshot, action: Action, multiplier: float, scarcity: float) -> BidProposal:
        if context.shape != (len(context), len(CONTEXT_NAMES)) or not np.isfinite(context).all():
            raise ValueError("Public current opportunity context only")
        if len(context) == 0:
            return BidProposal(np.empty(0, dtype=float))
        value = np.asarray(self.value_model.predict(context), dtype=float)
        if value.shape != (len(context),) or not np.isfinite(value).all() or np.any(value < 0):
            raise ValueError("Finite same-domain recorded value forecasts required")
        if self.method == "calibrated_linear":
            indexes = np.searchsorted(GRID, np.minimum(3., value * self.linear_factor), side="right") - 1
            bids = GRID[indexes]
        else:
            mu, sd = self.market.predict(context)
            bids = batch_grid_bid(value, mu, sd, payment_mode=self.market.payment_mode, scarcity=scarcity, multiplier=multiplier)
        # Simulator/host applies the same multiplier and budget guards to all.
        return BidProposal(np.asarray(bids, dtype=float).copy())
