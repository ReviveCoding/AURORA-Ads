"""Mature observable S1 auction rows, not counterfactual or public-data joins."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .auction_learning import AuctionObservation, CONTEXT_NAMES


@dataclass(frozen=True)
class AuctionDataset:
    context: NDArray[np.float64]
    submitted_bid: NDArray[np.float64]
    eligible: NDArray[np.bool_]
    won: NDArray[np.bool_]
    payment: NDArray[np.float64]
    observed_gross: NDArray[np.float64]
    origin_ids: tuple[str, ...]
    cohort_ids: tuple[str, ...]
    executed_bid_probability: NDArray[np.float64] | None

    def market_inputs(self) -> tuple[NDArray, NDArray, NDArray, NDArray]:
        # Unaffordable/unsubmitted opportunities have no price censoring event.
        mask = self.eligible & (self.submitted_bid > 0)
        return tuple(array[mask].copy() for array in
                     (self.context, self.submitted_bid, self.won, self.payment))

    def value_inputs(self) -> tuple[NDArray, NDArray, NDArray, list[str]]:
        # A losing opportunity's zero is missing exposure value, not a label.
        mask = self.won
        ids = [identity for identity, selected in zip(self.origin_ids, mask) if selected]
        return self.context[mask].copy(), self.observed_gross[mask].copy(), np.ones(int(mask.sum()), dtype=bool), ids


class AuctionCollector:
    """Copy mature callback rows once; duplicate cohort replay is an error.

    Cohort names are executable S1 lineage, not people or fabricated joins. The
    local row suffix distinguishes opportunities *within* that observed cohort.
    Empty cohorts remain in the lineage manifest, even when they supply no rows.
    """
    def __init__(self) -> None:
        self._cohorts: dict[str, AuctionObservation] = {}
        self._probability_known: bool | None = None

    def observe_auction(self, observation: AuctionObservation) -> None:
        if observation.cohort_id in self._cohorts:
            raise ValueError("Duplicate mature auction cohort; no double-counting")
        known = observation.executed_bid_probability is not None
        if self._probability_known is not None and self._probability_known != known:
            raise ValueError("Do not silently mix known and unavailable logging probabilities")
        # Revalidate owned copies: callers cannot mutate a frozen dataclass's
        # arrays after admission to change the later dataset.
        owned = AuctionObservation(
            observation.cohort_id, observation.origin_interval, observation.observed_at_day,
            observation.context.copy(), observation.submitted_bid.copy(), observation.eligible.copy(),
            observation.won.copy(), observation.payment.copy(), observation.observed_gross.copy(),
            None if not known else observation.executed_bid_probability.copy(),
        )
        for array in (owned.context, owned.submitted_bid, owned.eligible, owned.won,
                      owned.payment, owned.observed_gross, owned.executed_bid_probability):
            if array is not None:
                array.setflags(write=False)
        self._cohorts[owned.cohort_id] = owned
        self._probability_known = known

    def dataset(self) -> AuctionDataset:
        if not self._cohorts:
            raise ValueError("No mature auction callbacks received")
        records = list(self._cohorts.values())
        def concatenate(name):
            return np.concatenate([getattr(row, name) for row in records], axis=0)
        context = concatenate("context")
        if context.shape[1] != len(CONTEXT_NAMES):
            raise ValueError("Public context width changed")
        # Length-prefixed cohort identifiers avoid delimiter ambiguities.
        identities = tuple(f"{len(row.cohort_id)}:{row.cohort_id}:{index}"
                           for row in records for index in range(len(row.submitted_bid)))
        return AuctionDataset(context, concatenate("submitted_bid"), concatenate("eligible"),
                              concatenate("won"), concatenate("payment"), concatenate("observed_gross"),
                              identities, tuple(self._cohorts),
                              concatenate("executed_bid_probability") if self._probability_known else None)


def require_disjoint_cohorts(*datasets: AuctionDataset) -> None:
    seen: set[str] = set()
    for dataset in datasets:
        current = set(dataset.cohort_ids)
        if len(current) != len(dataset.cohort_ids) or seen & current:
            raise ValueError("Training/calibration/selection cohort lineage overlaps")
        seen.update(current)
