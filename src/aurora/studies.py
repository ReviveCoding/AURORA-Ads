"""Shared study admission, provenance, typed result records and atomic progress."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .artifacts import atomic_json, digest
from .workflow import Ledger


class Study:
    def __init__(self, root: Path, name: str):
        self.root = root
        self.runtime = Path.home() / ".local/share/aurora-ads"
        if json.loads((self.runtime / "AURORA_RUNTIME.json").read_text())["repo_wsl"] != str(root):
            raise ValueError("Runtime ownership mismatch")
        self.name = f"{name}_{time.time_ns()}"
        self.directory = self.runtime / "runs" / self.name
        self.directory.mkdir()
        self.ledger = Ledger(root / "config/experiments.json", self.runtime / "state/experiment_state.json")

    def source(self, source_id: str) -> dict[str, Any]:
        admission = json.loads((self.root / "reports/data/ANALYSIS_ADMISSION.json").read_text())
        item = admission["sources"][source_id]
        if not item["analysis_admitted"]:
            raise ValueError(f"Source not admitted: {source_id}")
        return item

    def finish(self, node: str, report: dict[str, Any], family: str, *, science: str = "NOT_ESTABLISHED", capabilities: dict[str, bool] | None = None) -> Path:
        report["study_id"] = self.name
        report["active_config_hashes"] = {path.name: digest(path) for path in (self.root / "config").glob("*.json")}
        runtime_path = self.directory / "result.json"
        atomic_json(runtime_path, report)
        export = self.root / "reports" / family / (self.name + ".json")
        atomic_json(export, report)
        self.ledger.update(node, "EXECUTED", science=science, artifacts=(export,), capabilities=capabilities)
        self.export_state()
        return export

    def export_state(self) -> None:
        atomic_json(self.root / "reports/state/experiment_state.json", self.ledger.read())
        for path in (self.runtime / "state/events").glob("*.json"):
            atomic_json(self.root / "reports/state/events" / path.name, json.loads(path.read_text()))


def metric_record(*, domain: str, population: str, estimand: str, comparison: str, candidate: str, baseline: str, metric: str, estimate: float, unit: str, horizon: str, n: int, independent_unit: str, uncertainty: str, source_hashes: list[str], config_hash: str, model_id: str, ci: tuple[float, float] | None = None, difference: float | None = None, outcome: str = "NOT_ESTABLISHED", limitations: list[str] | None = None) -> dict[str, Any]:
    return {"record_status": "MEASURED", "evidence_domain": domain, "estimand_id": estimand, "comparison_id": comparison, "candidate": candidate, "baseline": baseline, "population": population, "metric": metric, "estimate": estimate, "difference": difference, "unit": unit, "horizon": horizon, "n_independent_units": n, "independent_unit": independent_unit, "uncertainty_method": uncertainty, "ci_lower": ci[0] if ci else None, "ci_upper": ci[1] if ci else None, "source_hashes": source_hashes, "config_hash": config_hash, "model_calibrator_id": model_id, "scientific_outcome": outcome, "execution_status": "EXECUTED", "scope_limits": limitations or [], "missingness_handling": "source-valid observed rows only; exclusions retained in admission funnel"}
