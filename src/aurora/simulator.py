"""Evaluator-owned S1 reference world. No real-data/production causal claims."""
from __future__ import annotations

import hashlib
import math
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Callable, TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from .state import Action, SCALE
from .measurement import projected_distribution
from .artifacts import digest

if TYPE_CHECKING:
    from .fast_bidder import BidProposal
    from .auction_learning import AuctionObservation

FAMILIES = ("weak_or_no_heterogeneity", "nonlinear_heterogeneity", "fatigue_carryover", "reporting_competition_shift")
BLOCK_STAGES = {"train": (0, 16), "validation": (16, 32), "calibration": (32, 48), "final": (48, 64), "pilot": (64, 80)}
OOD_MECHANISMS = {"nonlinear_feature_change", "stronger_fatigue", "value_dependent_reporting_loss", "supply_collapse", "additive_misspecified"}


def rng(world: str, campaign: int, interval: int, channel: str) -> np.random.Generator:
    seed = int.from_bytes(hashlib.sha256(f"{world}|{campaign}|{interval}|{channel}".encode()).digest()[:16], "little")
    return np.random.Generator(np.random.Philox(seed))


def sigmoid(value):
    return 1 / (1 + np.exp(-value))


@dataclass(frozen=True)
class WorldSpec:
    world_id: str
    family: str
    budget_per_campaign: int = 10_000
    campaigns: int = 8
    intervals: int = 14 * 96
    nominal_arrivals: float = 32.
    effect_override: float | None = None
    slow_delay: bool = True
    payment_mode: str = "second_price"
    stage: str = "development"
    parameter_index: int | None = None
    ood_mechanism: str | None = None
    final_manifest: str | None = None

    def __post_init__(self):
        if self.family not in FAMILIES or self.stage not in {"smoke", "development", "ood", *BLOCK_STAGES}:
            raise ValueError("Unknown family or unfrozen final-world generation")
        if self.stage == "final":
            if not self.final_manifest:
                raise ValueError("Final generation requires an actual frozen manifest")
            manifest = json.loads(Path(self.final_manifest).read_text())
            if not manifest.get("frozen") or manifest.get("simulator_sha256") != digest(Path(__file__)):
                raise ValueError("Final manifest does not bind current simulator code")
        if self.stage in BLOCK_STAGES:
            lo, hi = BLOCK_STAGES[self.stage]
            if self.parameter_index is None or not lo <= self.parameter_index < hi:
                raise ValueError("Stage parameter block missing/overlapping")
        if self.ood_mechanism and (self.stage != "ood" or self.ood_mechanism not in OOD_MECHANISMS):
            raise ValueError("OOD mechanism cannot enter primary mixture")
        if self.payment_mode not in {"first_price", "second_price"} or self.campaigns <= 0 or self.intervals <= 0 or not math.isfinite(self.nominal_arrivals) or self.nominal_arrivals <= 0 or self.budget_per_campaign <= 0:
            raise ValueError("Invalid world")
        if self.effect_override is not None and not math.isfinite(self.effect_override):
            raise ValueError("Invalid effect override")


@dataclass(frozen=True)
class Snapshot:
    """Only contemporaneous public channels. No family/fault/latent truth fields."""
    interval: int
    campaign: int
    available_budget_units: int
    spent_units: int
    observed_clicks: int
    received_value: float
    matured_cohort_count: int
    matured_exposure_value: float
    pending_exposures: int
    horizon_days: int = 7
    initial_budget_units: int = 0
    last_spend_units: int = 0
    last_supply: int = 0
    last_wins: int = 0
    last_auction_losses: int = 0
    last_context_mean: tuple[float, ...] = (0., 0., 0., 0., 0., 0.)
    pending_age_counts: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0)
    matured_exposure_count: int | None = None


@dataclass(frozen=True)
class MaturedObservation:
    """Only completed observed origin-cohort outcomes; never organic/oracle truth."""
    cohort_id: str
    origin_interval: int
    campaign: int
    observed_at_day: float
    origin_snapshot: Snapshot
    executed_action: Action
    executed_probability: float | None
    observed_gross_value: float
    observed_purchase_count: int
    actual_spend: float
    operational_cost: float
    exposures: int
    horizon_complete: bool = True
    receipt_available: bool = True
    observed_delay_counts: tuple[int, ...] = (0,) * 11


@dataclass(frozen=True)
class PendingCohort:
    available_at: float
    observation: MaturedObservation


class Controller(Protocol):
    def choose(self, snapshot: Snapshot) -> Action: ...


class OpportunityBidder(Protocol):
    def propose(self, context: NDArray, snapshot: Snapshot, action: Action, multiplier: float, scarcity: float) -> BidProposal: ...


@dataclass(frozen=True)
class StaticController:
    action: Action = Action.NO_CHANGE

    def choose(self, snapshot: Snapshot) -> Action:
        return self.action


@dataclass(frozen=True)
class Evaluation:
    world_id: str
    family: str
    unique_purchase_value: float
    no_ad_purchase_value: float
    spend: float
    operating_cost: float
    initial_budget: float
    opportunities: int
    purchases: int
    no_ad_purchases: int
    matured_cohorts: int
    snapshot_reward_updates_before_day7: int
    final_pending_exposures: int
    receipt_flush_day: float
    stage: str

    @property
    def utility(self) -> float:
        return (self.unique_purchase_value - self.no_ad_purchase_value - self.spend - self.operating_cost) / self.initial_budget


def settle_reference(bids: NDArray, market: NDArray, admission: NDArray, balance: int, mode: str) -> tuple[NDArray, NDArray, int]:
    """Independent CPU sequential reference; reserve max payment before each auction."""
    wins = np.zeros(len(bids), dtype=bool)
    payments = np.zeros(len(bids), dtype=np.int64)
    for index in range(len(bids)):
        reserve = math.ceil(float(bids[index]) * SCALE)
        if not admission[index] or bids[index] <= 0 or reserve > balance:
            continue
        if bids[index] >= market[index]:
            payment = math.ceil(float(market[index] if mode == "second_price" else bids[index]) * SCALE)
            if payment > reserve:
                raise ValueError("Payment exceeds reservation")
            wins[index] = True
            payments[index] = payment
            balance -= payment
    return wins, payments, balance


def settle_constant_bid(bid: float, market: NDArray, admission: NDArray, balance: int, mode: str) -> tuple[NDArray, NDArray, int]:
    """Vectorized constant-bid settlement, qualified against independent sequential reference."""
    if not math.isfinite(bid) or bid < 0 or mode not in {"first_price", "second_price"} or balance < 0:
        raise ValueError("Invalid auction")
    reserve = math.ceil(bid * SCALE)
    candidate = admission & (market <= bid) & (bid > 0)
    payments = np.where(candidate, np.ceil((market if mode == "second_price" else np.full(len(market), bid)) * SCALE), 0).astype(np.int64)
    prior_spend = np.cumsum(payments) - payments
    allowed = prior_spend + reserve <= balance
    wins = candidate & allowed
    payments = np.where(wins, payments, 0)
    return wins, payments, balance - int(payments.sum())


def run_world(spec: WorldSpec, controller: Controller, *, base_bid: float = 1., no_ad: bool = False, bidder: OpportunityBidder | None = None, auction_observer: Callable[[AuctionObservation], None] | None = None) -> Evaluation:
    """Full 14+7 clocks available; smoke workload reduction is explicitly labeled."""
    balances = np.full(spec.campaigns, spec.budget_per_campaign * SCALE, dtype=np.int64)
    clicks = np.zeros(spec.campaigns, dtype=np.int64)
    fatigue = np.zeros(spec.campaigns)
    received = np.zeros(spec.campaigns)
    matured_value = np.zeros(spec.campaigns)
    mature_count = np.zeros(spec.campaigns, dtype=np.int64)
    mature_exposures = np.zeros(spec.campaigns, dtype=np.int64)
    pending = np.zeros(spec.campaigns, dtype=np.int64)
    # Each interval cohort is unique (campaign, origin interval); each positive
    # receipt appears once. Pending estimates are never reward observations.
    cohorts: list[list[PendingCohort]] = [[] for _ in range(spec.campaigns)]
    auction_cohorts: list[list[tuple[float, AuctionObservation]]] = [[] for _ in range(spec.campaigns)]
    receipts: list[list[tuple[float, float]]] = [[] for _ in range(spec.campaigns)]
    previous_action = [Action.NO_CHANGE] * spec.campaigns
    last_spend = np.zeros(spec.campaigns, dtype=np.int64)
    last_supply = np.zeros(spec.campaigns, dtype=np.int64)
    last_wins = np.zeros(spec.campaigns, dtype=np.int64)
    last_auction_losses = np.zeros(spec.campaigns, dtype=np.int64)
    last_context = [(0.,) * 6 for _ in range(spec.campaigns)]
    total_y = no_ad_y = overhead = 0.
    purchases = no_ad_purchases = opportunities = early_updates = 0
    decisions_end = spec.intervals / 96
    receipt_flush = decisions_end + 7 + (3 if spec.family == "reporting_competition_shift" else 0)
    for interval in range(math.ceil(receipt_flush * 96) + 1):
        now = interval / 96
        for campaign in range(spec.campaigns):
            available = [row for row in receipts[campaign] if row[0] <= now]
            received[campaign] += sum(row[1] for row in available)
            receipts[campaign] = [row for row in receipts[campaign] if row[0] > now]
            complete = [row for row in cohorts[campaign] if row.available_at <= now]
            matured_value[campaign] += sum(row.observation.observed_gross_value for row in complete)
            mature_count[campaign] += len(complete)
            mature_exposures[campaign] += sum(row.observation.exposures for row in complete)
            pending[campaign] -= sum(row.observation.exposures for row in complete)
            cohorts[campaign] = [row for row in cohorts[campaign] if row.available_at > now]
            observe = getattr(controller, "observe", None)
            if observe:
                for row in complete:
                    observe(row.observation)
            if auction_observer is not None:
                for available_at, auction_row in auction_cohorts[campaign]:
                    if available_at <= now:
                        auction_observer(auction_row)
                auction_cohorts[campaign] = [(at, row) for at, row in auction_cohorts[campaign] if at > now]
            if now < 7:
                early_updates += len(complete)
            if interval >= spec.intervals:
                continue
            age_counts = [0] * 8
            for row in cohorts[campaign]:
                age = min(7, int(max(0, now - row.observation.origin_interval / 96)))
                age_counts[age] += row.observation.exposures
            snapshot = Snapshot(interval, campaign, int(balances[campaign]), spec.budget_per_campaign * SCALE - int(balances[campaign]), int(clicks[campaign]), float(received[campaign]), int(mature_count[campaign]), float(matured_value[campaign]), int(pending[campaign]), initial_budget_units=spec.budget_per_campaign * SCALE, last_spend_units=int(last_spend[campaign]), last_supply=int(last_supply[campaign]), last_wins=int(last_wins[campaign]), last_auction_losses=int(last_auction_losses[campaign]), last_context_mean=last_context[campaign], pending_age_counts=tuple(age_counts), matured_exposure_count=int(mature_exposures[campaign]))
            distribution = getattr(controller, "probabilities", None)
            executed_probability = None
            if distribution:
                proposed = np.asarray(distribution(snapshot), dtype=float)
                actions = tuple(Action)
                mapping = np.arange(len(actions))
                if previous_action[campaign] != Action.NO_CHANGE or balances[campaign] < 100:
                    mapping[1:] = 0
                actual_distribution = projected_distribution(proposed, mapping, len(actions))
                sampled = int(rng(spec.world_id, campaign, interval, "policy_sampling|" + str(getattr(controller, "policy_seed", 0))).choice(len(actions), p=actual_distribution))
                action = actions[sampled]
                executed_probability = float(actual_distribution[sampled])
            else:
                action = controller.choose(snapshot)
            if not isinstance(action, Action):
                raise ValueError("Controller returned an unknown action")
            # Common cooldown: consecutive non-default actions project to default.
            if action != Action.NO_CHANGE and previous_action[campaign] != Action.NO_CHANGE:
                action = Action.NO_CHANGE
            previous_action[campaign] = action
            operating_units = 100 if action != Action.NO_CHANGE and not no_ad else 0
            if operating_units > balances[campaign]:
                action = Action.NO_CHANGE
                operating_units = 0
            balances[campaign] -= operating_units
            overhead += operating_units / SCALE
            multiplier = 1.1 if action == Action.BID_MULTIPLIER_UP else .9 if action == Action.BID_MULTIPLIER_DOWN else 1.
            pace = .7 if action == Action.PACE_UP else .5 if action == Action.PACE_DOWN else 0. if action == Action.PAUSE_SEGMENT else .6
            shock = float(rng(spec.world_id, -1, interval, "shared_shock").normal(0, .1))
            supply_factor = .1 if spec.ood_mechanism == "supply_collapse" and now >= 7 else 1.
            n = int(rng(spec.world_id, campaign, interval, "arrivals").poisson(spec.nominal_arrivals * math.exp(shock) * supply_factor))
            opportunities += n
            x = rng(spec.world_id, campaign, interval, "context").uniform(-1, 1, (n, 4))
            segment = rng(spec.world_id, campaign, interval, "segment").integers(0, 5, n)
            origin = now + rng(spec.world_id, campaign, interval, "origin").uniform(0, 1, n) / 96
            time_feature = np.sin(2 * np.pi * origin)
            catalog_key = "AURORA_PARAMETER_CATALOG_V1"
            organic_campaign_shock = float(rng(catalog_key, campaign, spec.parameter_index, "organic_campaign_shock").uniform(-.03, .03)) if spec.parameter_index is not None else 0.
            organic_logit = -5.3 + .4 * x[:, 0] - .3 * x[:, 1] + .2 * time_feature + shock + organic_campaign_shock
            family_parameters = rng(catalog_key, campaign, spec.parameter_index, "campaign_parameters") if spec.parameter_index is not None else rng(spec.world_id, campaign, -1, "campaign_parameters")
            if spec.effect_override is not None:
                delta = np.full(n, spec.effect_override)
            elif spec.family == "weak_or_no_heterogeneity":
                delta = np.full(n, family_parameters.choice([-.25, 0, .25]))
            elif spec.family == "fatigue_carryover":
                delta = .5 + .3 * x[:, 0] - .8 * fatigue[campaign]
            else:
                offsets = family_parameters.uniform(-.2, .2, 5)
                delta = .6 * np.tanh(2 * x[:, 0] * x[:, 1]) + .35 * x[:, 2] + offsets[segment]
            if spec.ood_mechanism == "nonlinear_feature_change":
                delta = .5 * np.sin(np.pi * x[:, 0]) + .4 * x[:, 1]**2 - .2
            elif spec.ood_mechanism == "stronger_fatigue":
                delta = .5 + .3 * x[:, 0] - 1.6 * fatigue[campaign]
            elif spec.ood_mechanism == "additive_misspecified":
                delta = .15 + .2 * x[:, 0] - .1 * x[:, 1]
            shifted = spec.family == "reporting_competition_shift" and now >= 7
            public_context = None
            proposal = None
            if bidder is not None or auction_observer is not None:
                from .auction_context import public_auction_context
                public_context = public_auction_context(x, segment, origin, interval=interval, decision_intervals=spec.intervals)
                public_context.setflags(write=False)
            if bidder is not None:
                # No actual market price, purchase/organic draw, effect or family
                # is supplied. Context has its own copy, not evaluator x storage.
                dual = getattr(controller, "dual", None)
                remove_dual = getattr(getattr(controller, "parameters", None), "remove_dual", False)
                scarcity = 0. if dual is None or remove_dual else float(dual[campaign])
                if not math.isfinite(scarcity) or scarcity < 0:
                    raise ValueError("Nonnegative finite additional scarcity price required")
                proposal = bidder.propose(public_context, snapshot, action, multiplier, scarcity)
                from .fast_bidder import BidProposal
                if not isinstance(proposal, BidProposal) or proposal.base_bids.shape != (n,):
                    raise ValueError("Typed finite-grid opportunity proposals required")
            market = np.exp(.25 * x[:, 1] + shock + (.4 if shifted else 0) + .4 * rng(spec.world_id, campaign, interval, "market").normal(size=n))
            admitted = rng(spec.world_id, campaign, interval, "admission").uniform(size=n) < (0 if no_ad else pace)
            initial_balance = int(balances[campaign])
            if proposal is None:
                wins, payments, balances[campaign] = settle_constant_bid(base_bid * multiplier, market, admitted, initial_balance, spec.payment_mode)
                if auction_observer is not None:
                    eligible = admitted & (base_bid * multiplier > 0) & (np.cumsum(payments) - payments + math.ceil(base_bid * multiplier * SCALE) <= initial_balance)
                    submitted = np.where(eligible, base_bid * multiplier, 0.)
                    bid_probability = None
            else:
                from .auction_settlement import settle_variable_bids
                settlement = settle_variable_bids(proposal.base_bids * multiplier, market, admitted, initial_balance, spec.payment_mode, uniform_grid_multiplier=multiplier if proposal.uniform_grid else None)
                wins, payments, balances[campaign] = settlement.wins, settlement.payments, settlement.balance
                submitted, eligible, bid_probability = settlement.executed_bids, settlement.eligible, settlement.executed_probabilities
            fatigue[campaign] = .8 * fatigue[campaign] + .2 * (float(wins.mean()) if n else 0)
            click_draw = rng(spec.world_id, campaign, interval, "click").uniform(size=n)
            clicks[campaign] += int(np.sum(wins & (click_draw < sigmoid(-3.2 + .6 * x[:, 0] + .2 * x[:, 2] + shock))))
            purchase_draw = rng(spec.world_id, campaign, interval, "purchase").uniform(size=n)
            organic = purchase_draw < sigmoid(organic_logit)
            purchased = purchase_draw < sigmoid(organic_logit + wins * delta)
            value = rng(spec.world_id, campaign, interval, "value").lognormal(math.log(200), .4, n)
            total_y += float(np.sum(value[purchased]))
            no_ad_y += float(np.sum(value[organic]))
            purchases += int(purchased.sum())
            no_ad_purchases += int(organic.sum())
            # Strictly observed exposed purchases; evaluator endpoint includes all
            # unique occasions, including unobserved organic purchases.
            observed = purchased & wins
            if spec.ood_mechanism == "value_dependent_reporting_loss":
                recorded = rng(spec.world_id, campaign, interval, "permanent_receipt_missingness").uniform(size=n) > np.where(value > 220, .6, .1)
                observed = observed & recorded
            rate = (1 / 3 if spec.slow_delay else 2.) * np.exp(np.clip(.2 * x[:, 0], -.2, .2))
            delay_draw = rng(spec.world_id, campaign, interval, "delay").uniform(size=n)
            delay = -np.log1p(-delay_draw * -np.expm1(-rate * 7)) / rate
            reporting_lag = 3. if shifted and now < 9 else 0.
            receipt_time = origin + delay + reporting_lag
            receipts[campaign].extend(zip(receipt_time[observed].tolist(), value[observed].tolist()))
            exposure_count = int(wins.sum())
            pending[campaign] += exposure_count
            available_at = (interval + 1) / 96 + 7 + reporting_lag
            recorded_delay_bins = np.minimum(10, np.floor(delay[observed] + reporting_lag).astype(int))
            delay_counts = tuple(np.bincount(recorded_delay_bins, minlength=11).tolist())
            observation = MaturedObservation(f"{spec.world_id}|{campaign}|{interval}", interval, campaign, available_at, snapshot, action, executed_probability, float(value[observed].sum()), int(observed.sum()), float(payments.sum()) / SCALE, operating_units / SCALE, exposure_count, observed_delay_counts=delay_counts)
            cohorts[campaign].append(PendingCohort(available_at, observation))
            if auction_observer is not None:
                from .auction_learning import AuctionObservation
                auction_row = AuctionObservation(observation.cohort_id, interval, available_at, public_context, submitted, eligible, wins, payments.astype(float) / SCALE, np.where(observed, value, 0.), bid_probability)
                for field in (auction_row.context, auction_row.submitted_bid, auction_row.eligible, auction_row.won, auction_row.payment, auction_row.observed_gross, auction_row.executed_bid_probability):
                    if field is not None:
                        field.setflags(write=False)
                auction_cohorts[campaign].append((available_at, auction_row))
            executed = getattr(controller, "executed", None)
            if executed:
                executed(snapshot, action, executed_probability, float(payments.sum()) / SCALE, operating_units / SCALE)
            last_spend[campaign] = int(payments.sum()) + operating_units
            last_supply[campaign] = n
            last_wins[campaign] = exposure_count
            last_auction_losses[campaign] = int(np.sum(admitted & ~wins))
            last_context[campaign] = tuple(np.r_[x.mean(axis=0), segment.mean(), time_feature.mean()].tolist()) if n else (0.,) * 6
    total_charged = spec.campaigns * spec.budget_per_campaign - float(balances.sum()) / SCALE
    if any(cohorts) or any(receipts) or any(auction_cohorts) or np.any(pending != 0):
        raise ValueError("Incomplete outcome/receipt flush")
    return Evaluation(spec.world_id, spec.family, total_y, no_ad_y, total_charged - overhead, overhead, spec.campaigns * spec.budget_per_campaign, opportunities, purchases, no_ad_purchases, int(mature_count.sum()), early_updates, int(pending.sum()), receipt_flush, spec.stage)
