"""Repaired local support adapter; never mutates the frozen agent model provider."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from .artifacts import digest
from .policies import PolicyBundle
from .policy_registry import load_bundle
from .support import neighborhood_support


class WeightedSupportBundle(PolicyBundle):
    def __init__(self, original: PolicyBundle, support: dict):
        super().__init__(original.gross, original.spend, original.mean, original.scale, support["tree"], support["actions"], original.residual_scale, original.delay_cdf, neural_transform=original.neural_transform, detector=original.detector)
        self.propensities = np.asarray(support["propensities"], dtype=float)
        self.maximum_distance = float(support["maximum_distance"])
        self.neighborhood_size = int(support["neighborhood_size"])
        if self.propensities.shape != self.support_actions.shape or self.neighborhood_size != 64 or len(self.propensities) < 64:
            raise ValueError("Qualified64-neighbor aligned support artifact required")

    def estimates(self, snapshot, remove_delay=False):
        _, z = self.state(snapshot, remove_delay)
        matrix = np.column_stack([np.repeat(z[None], 6, axis=0), np.eye(6)])
        gross = np.maximum(0, self.gross.predict(matrix))
        spend = np.maximum(0, self.spend.predict(matrix))
        distances, neighbors = self.support_tree.query(z[None], k=self.neighborhood_size)
        indexes = neighbors[0]
        local = neighborhood_support(self.support_actions[indexes], self.propensities[indexes], distances[0], maximum_distance=self.maximum_distance)
        # A residual-scale heuristic, NOT a calibrated confidence bound. Keep
        # zero-support arms finite until controller applies its own shared gate.
        uncertainty = self.residual_scale / np.sqrt(np.maximum(1., local.action_ess))
        return gross, spend, uncertainty, local.action_ess, np.r_[1., z]


def load_weighted_bundle(root: Path, *, warm_path: Path | None = None, qualification_path: Path | None = None):
    warm_path = warm_path or root / "reports/policy/WARMSTART_LATEST.json"
    pointer_path = qualification_path or root / "reports/policy/SUPPORT_V2_QUALIFICATION.json"
    pointer = json.loads(pointer_path.read_text())
    report_path = Path(pointer["artifact"])
    if not pointer["passed"] or digest(report_path) != pointer["sha256"]:
        raise ValueError("Qualified support report identity changed")
    report = json.loads(report_path.read_text())
    support_path = Path(report["support_artifact"]["path"])
    if report["warm_report_sha256"] != digest(warm_path) or digest(support_path) != report["support_artifact"]["sha256"]:
        raise ValueError("Support is not qualified for this numerical warmstart")
    original, training, warm = load_bundle(root, warm_path)
    support = joblib.load(support_path)
    return WeightedSupportBundle(original, support), training, warm
