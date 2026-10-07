#!/usr/bin/env python3
"""Static pre-confirmation finding; leave the active policy sweep untouched."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main():
    study = Study(ROOT, "policy_cost_score_static_audit")
    progress = json.loads((ROOT / "reports/policy/DEVELOPMENT_PROGRESS.json").read_text())
    protocol_path = Path(progress["runtime_directory"]) / "development_protocol.json"
    if not protocol_path.resolve().is_relative_to(study.runtime / "runs") or digest(protocol_path) != progress["protocol_sha256"]:
        raise ValueError("Active development protocol identity mismatch")
    protocol = json.loads(protocol_path.read_text())
    policy_path = ROOT / "src/aurora/policies.py"
    if digest(policy_path) != protocol["controller_sha256"]:
        raise ValueError("Original controller already changed; do not relabel a different source audit")
    code = policy_path.read_text()
    excerpt = [{"line": number, "text": line.strip()} for number, line in enumerate(code.splitlines(), 1) if "reward =" in line or "score =" in line and ("mean" in line or "posterior_mean" in line)]
    already_net, operational = .005, .01
    report = {"status": "IMPLEMENTATION_CORRECTION_REQUIRED_BEFORE_POLICY_FREEZE", "scope": "Static source/unit audit, not an inspected policy result", "controller_sha256": digest(policy_path), "original_development_protocol_sha256": digest(protocol_path), "original_development_study": progress["study_id"], "original_sweep_restarted_or_delayed": False, "policy_final_outcomes_loaded": 0, "source_excerpts": excerpt, "independent_scalar_unit_fixture": {"already_net_prediction": already_net, "included_operational_cost": operational, "old_double_penalty_score": already_net - operational, "correct_single_cost_score": already_net}, "affected_methods": ["epsilon_greedy", "LinUCB", "neural_linear_TS", "delay_TS_primal_dual", "support_gated_delay_TS"], "preserved": "All original world artifacts, utility ledgers, negative results and selection report remain; no edit to running simulator/controller", "next_action": "After the existing sweep completes, archive original source, remove only duplicate posterior-score overhead, qualify independent tests, run all affected development recipes as a supplemental study, then reselect before pilot/freeze", "interpretation": "Completed-episode cost accounting is not invalidated; original scoring comparison is development-only and cannot be the final principal baseline without repair"}
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/policy" / (study.name + ".json")
    atomic_json(export, report)
    study.ledger.update("E15_POLICY_FREEZE", "CHECKPOINTED", artifacts=(export, ROOT / "reports/design/POLICY_COST_SCORE_AUDIT.md"), reason=report["next_action"], capabilities={"POLICY_SCORE_UNITS_QUALIFIED": False})
    study.export_state()
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
