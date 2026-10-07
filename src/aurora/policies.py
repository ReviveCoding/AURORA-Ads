"""Observed-cohort bandit controllers; common mechanical guards remain in host."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .incidents import features
from .simulator import MaturedObservation, Snapshot
from .state import Action, SCALE
from .policy_score_units import posterior_net_score

ACTIONS = tuple(Action)


@dataclass(frozen=True)
class PolicyParameters:
    name: str
    seed: int = 41
    eta: float = .05
    lambda_max: float = 2.
    beta: float = .5
    support_min: int = 2
    remove_delay: bool = False
    remove_support: bool = False
    remove_uncertainty: bool = False
    remove_dual: bool = False
    remove_reliability: bool = False


class LinearPosterior:
    def __init__(self, dimension, ridge=10.):
        self.inverse = np.repeat((np.eye(dimension) / ridge)[None], 6, axis=0)
        self.b = np.zeros((6, dimension))
        self.count = np.zeros(6, dtype=int)

    def update(self, action, x, value):
        vector = self.inverse[action] @ x
        denominator = 1 + x @ vector
        self.inverse[action] -= np.outer(vector, vector) / denominator
        self.b[action] += x * value
        self.count[action] += 1

    def predict(self, x):
        means = np.einsum("aij,aj,i->a", self.inverse, self.b, x)
        variances = np.einsum("i,aij,j->a", x, self.inverse, x)
        return means, np.sqrt(np.maximum(variances, 0))

    def batch_fit(self, x, actions, target, ridge=10.):
        for action in range(6):
            keep = actions == action
            selected = x[keep]
            self.inverse[action] = np.linalg.inv(ridge * np.eye(x.shape[1]) + selected.T @ selected)
            self.b[action] = selected.T @ target[keep]
            self.count[action] = int(keep.sum())


class PolicyBundle:
    """Frozen S1 observed-value/spend models and public support, no evaluator truth."""
    def __init__(self, gross, spend, mean, scale, support_tree, support_actions, residual_scale, delay_cdf, neural_transform=None, detector=None):
        self.gross = gross
        self.spend = spend
        self.mean = np.asarray(mean)
        self.scale = np.asarray(scale)
        self.support_tree = support_tree
        self.support_actions = np.asarray(support_actions, dtype=int)
        self.residual_scale = np.asarray(residual_scale)
        self.delay_cdf = np.asarray(delay_cdf)
        self.neural_transform = neural_transform
        self.detector = detector

    def state(self, snapshot, remove_delay=False):
        raw = features(snapshot).astype(float)
        if remove_delay:
            raw[6:9] = 0
            raw[16:] = 0
        standardized = (raw - self.mean) / self.scale
        return raw, standardized

    def estimates(self, snapshot, remove_delay=False):
        raw, z = self.state(snapshot, remove_delay)
        matrix = np.column_stack([np.repeat(z[None], 6, axis=0), np.eye(6)])
        gross = np.maximum(0, self.gross.predict(matrix))
        spend = np.maximum(0, self.spend.predict(matrix))
        distances, neighbors = self.support_tree.query(z[None], k=min(64, len(self.support_actions)))
        counts = np.bincount(self.support_actions[neighbors[0]], minlength=6)
        support = counts if np.max(distances) <= 12 else np.zeros(6, dtype=int)
        return gross, spend, self.residual_scale / np.sqrt(np.maximum(1, counts)), support, np.r_[1., z]

    def pending_nowcast(self, snapshot):
        gross, _, _, _, _ = self.estimates(snapshot)
        mean_exposure_value = gross[0] / max(snapshot.last_wins, 1)
        remaining = 1 - self.delay_cdf[:8]
        return float(np.dot(snapshot.pending_age_counts, remaining) * mean_exposure_value)


class BanditController:
    def __init__(self, bundle: PolicyBundle, parameters: PolicyParameters, warm_x=None, warm_actions=None, warm_gross=None, warm_spend=None):
        self.bundle = bundle
        self.parameters = parameters
        self.random = np.random.default_rng(parameters.seed)
        self.posterior = LinearPosterior(len(bundle.mean) + 1)
        self.neural_posterior = None
        self.dual = np.zeros(8)
        self.seen = set()
        self.pending_nowcasts = {}
        self.received_observation_count = 0
        self.early_reward_updates = 0
        if warm_x is not None:
            standard = (warm_x - bundle.mean) / bundle.scale
            reward = (warm_gross - warm_spend) / 100
            self.posterior.batch_fit(np.column_stack([np.ones(len(standard)), standard]), warm_actions, reward)
            if bundle.neural_transform is not None:
                latent = bundle.neural_transform(standard)
                self.neural_posterior = LinearPosterior(latent.shape[1] + 1)
                self.neural_posterior.batch_fit(np.column_stack([np.ones(len(latent)), latent]), warm_actions, reward)

    def choose(self, snapshot: Snapshot) -> Action:
        p = self.parameters
        gross, spend, uncertainty, support, x = self.bundle.estimates(snapshot, p.remove_delay)
        mean, sd = self.posterior.predict(x)
        operational = np.array([0, .01, .01, .01, .01, .01])
        target = snapshot.initial_budget_units / SCALE / 1344
        actual_velocity = snapshot.last_spend_units / SCALE
        elapsed_target = target * (snapshot.interval + 1)
        charged = snapshot.spent_units / SCALE
        # Nowcast is an input only. It is never passed to posterior.update.
        remaining = 1 - self.bundle.delay_cdf[:8]
        self.pending_nowcasts[snapshot.campaign] = float(np.dot(snapshot.pending_age_counts, remaining) * gross[0] / max(snapshot.last_wins, 1)) if not p.remove_delay else 0.
        if p.name == "no_change":
            return Action.NO_CHANGE
        if p.name == "rule_PID":
            error = actual_velocity - target
            cumulative = charged - elapsed_target
            adjustment = .7 * error / max(target, 1) + .3 * cumulative / max(elapsed_target, 1)
            return Action.PACE_DOWN if adjustment > .1 else Action.PACE_UP if adjustment < -.1 else Action.NO_CHANGE
        if p.name == "MPC_pacing":
            remaining_intervals = max(1, 1344 - snapshot.interval)
            per_interval = snapshot.available_budget_units / SCALE / remaining_intervals
            feasible = spend <= per_interval * 1.1
            score = gross - spend - operational
            score[~feasible] = -np.inf
            return ACTIONS[int(np.argmax(score))] if feasible.any() else Action.PAUSE_SEGMENT
        if p.name == "epsilon_greedy":
            if self.random.uniform() < .1:
                return ACTIONS[int(self.random.integers(6))]
            score = posterior_net_score(mean, np.zeros(6), spend, scarcity=0.)
        elif p.name == "LinUCB":
            score = posterior_net_score(mean, .5 * sd, spend, scarcity=0.)
        elif p.name == "neural_linear_TS":
            # Bayesian linear posterior over the frozen learned neural embedding.
            if self.neural_posterior is None:
                raise ValueError("Neural-linear baseline requires trained neural features")
            latent = self.bundle.neural_transform(x[1:][None])[0]
            posterior_mean, posterior_sd = self.neural_posterior.predict(np.r_[1., latent])
            score = posterior_net_score(posterior_mean, self.random.normal(size=6) * posterior_sd, spend, scarcity=0.)
        elif p.name in {"delay_TS_primal_dual", "support_gated_delay_TS"}:
            score = posterior_net_score(mean, self.random.normal(size=6) * sd, spend, scarcity=float(self.dual[snapshot.campaign]))
            if p.name == "support_gated_delay_TS":
                score[support < p.support_min] = -np.inf
                score[0] = mean[0] * 100 - self.dual[snapshot.campaign] * spend[0]
        elif p.name == "MSCP_v2":
            # Online correction uses only the same matured cohort posterior;
            # it is not a nowcast reward or evaluator incremental-value label.
            gross = .5 * gross + .5 * np.maximum(0, mean * 100 + spend + operational)
            reliability = float(self.bundle.detector(features(snapshot))) if self.bundle.detector is not None and not p.remove_reliability else 0.
            penalty = 0 if p.remove_uncertainty else p.beta * uncertainty * (1 + reliability)
            scarcity = 0 if p.remove_dual else self.dual[snapshot.campaign]
            score = gross - (1 + scarcity) * spend - operational - penalty
            if not p.remove_support:
                default_score = score[0]
                score[support < p.support_min] = -np.inf
                score[0] = default_score
        else:
            raise ValueError("Undeclared controller")
        return ACTIONS[int(np.argmax(score))]

    def executed(self, snapshot, action, probability, spend, operational):
        p = self.parameters
        if p.name in {"delay_TS_primal_dual", "support_gated_delay_TS", "MSCP_v2"} and not p.remove_dual:
            target = snapshot.initial_budget_units / SCALE / 1344
            self.dual[snapshot.campaign] = np.clip(self.dual[snapshot.campaign] + p.eta * (spend + operational - target) / max(target, 1.), 0, p.lambda_max)

    def observe(self, observation: MaturedObservation):
        if not observation.horizon_complete or not observation.receipt_available or observation.observed_at_day < (observation.origin_interval + 1) / 96 + 7:
            raise ValueError("Nonmatured observation cannot update primary learner")
        if observation.cohort_id in self.seen:
            raise ValueError("Duplicate cohort reward update")
        self.seen.add(observation.cohort_id)
        self.received_observation_count += 1
        _, z = self.bundle.state(observation.origin_snapshot, self.parameters.remove_delay)
        action = ACTIONS.index(observation.executed_action)
        reward = (observation.observed_gross_value - observation.actual_spend - observation.operational_cost) / 100
        self.posterior.update(action, np.r_[1., z], reward)
        if self.neural_posterior is not None:
            latent = self.bundle.neural_transform(z[None])[0]
            self.neural_posterior.update(action, np.r_[1., latent], reward)
        # Replace pending estimate; never add it to the observed reward ledger.
        self.pending_nowcasts.pop(observation.campaign, None)
