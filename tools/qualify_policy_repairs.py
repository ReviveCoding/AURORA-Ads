#!/usr/bin/env python3
"""CPU integrity of actual registered models with the separate support adapter."""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from aurora.artifacts import atomic_json, digest
from aurora.policy_score_units import posterior_net_score
from aurora.policy_support_bundle import load_weighted_bundle
from aurora.simulator import Snapshot
from aurora.state import SCALE
from aurora.studies import Study


def main():
    study = Study(ROOT, "policy_repair_components_cpu_integrity")
    started = time.perf_counter()
    warm_path = ROOT / "reports/policy/WARMSTART_LATEST.json"
    original_controller = ROOT / "src/aurora/policies.py"
    before = {"warm": digest(warm_path), "controller": digest(original_controller)}
    report = {"status": "RUNNING", "not_policy_value_or_GPU_evidence": True, "no_final_worlds_or_outcomes_loaded": True}
    try:
        bundle, training, warm = load_weighted_bundle(ROOT)
        fixtures = []
        for budget in (4000, 10000, 20000):
            snapshot = Snapshot(672, 0, budget * SCALE // 2, budget * SCALE // 2, 100, 1000., 672, 1000., 500, initial_budget_units=budget * SCALE, last_spend_units=2 * SCALE, last_supply=32, last_wins=16, last_auction_losses=16, pending_age_counts=(64, 64, 62, 62, 62, 62, 62, 62))
            gross, spend, uncertainty, support, design = bundle.estimates(snapshot)
            # XGBoost emits float32; construct BOTH algebra sides in FP64 before
            # any subtraction. This is reference arithmetic, not model refitting.
            gross, spend = np.asarray(gross, dtype=np.float64), np.asarray(spend, dtype=np.float64)
            if not all(np.isfinite(value).all() for value in (gross, spend, uncertainty, support, design)) or np.any(support < 0) or np.any(support > 64):
                raise ValueError("Nonfinite/invalid actual registered weighted-support outputs")
            net = (gross - spend - np.array([0., .01, .01, .01, .01, .01])) / 100
            np.testing.assert_allclose(posterior_net_score(net, np.zeros(6), spend, scarcity=.5), gross - 1.5 * spend - np.array([0., .01, .01, .01, .01, .01]), rtol=1e-12, atol=1e-12)
            fixtures.append({"budget": budget, "support_ESS": support.tolist(), "gross": gross.tolist(), "spend": spend.tolist(), "residual_heuristic_uncertainty": uncertainty.tolist(), "not_world_performance": True})
        if before != {"warm": digest(warm_path), "controller": digest(original_controller)}:
            raise ValueError("Original controller/provider changed during independent integrity check")
        report.update(status="POLICY_REPAIR_COMPONENTS_CPU_PASSED_NOT_SUPPLEMENT", passed=True, source_hashes=before, support_qualification_sha256=digest(ROOT / "reports/policy/SUPPORT_V2_QUALIFICATION.json"), training_cohorts=len(training["x"]), fixture_outputs=fixtures, original_controller_and_agent_provider_unchanged=True, model_domain=warm["source_domain"], limitations=["Public-state numerical fixtures using actual registered models; not complete world runs or calibrated confidence intervals", "Original sweep still uses old score/support implementation; correction integration and supplemental comparisons remain required", "Fast-bidder empirical roster and selected-kernel warmstart applicability still pending"])
    except Exception as error:
        report.update(status="POLICY_REPAIR_COMPONENTS_CPU_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/policy" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    if report["passed"]:
        study.ledger.update("E15_POLICY_FREEZE", "CHECKPOINTED", artifacts=(artifact,), capabilities={"POLICY_REPAIR_COMPONENTS_READY": True, "POLICY_SCORE_UNITS_QUALIFIED": False, "POLICY_SUPPORT_QUALIFIED": False}, reason="Actual registered CPU components tested; do not freeze until source integration, supplemental development and other gates execute")
        study.export_state()
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
