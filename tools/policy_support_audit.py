#!/usr/bin/env python3
"""Static original-sweep support audit; no outcomes or active-controller edits."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main():
    study = Study(ROOT, "policy_support_static_audit")
    progress = json.loads((ROOT / "reports/policy/DEVELOPMENT_PROGRESS.json").read_text())
    protocol_path = Path(progress["runtime_directory"]) / "development_protocol.json"
    if not protocol_path.resolve().is_relative_to(study.runtime / "runs") or digest(protocol_path) != progress["protocol_sha256"]:
        raise ValueError("Original development protocol changed")
    protocol = json.loads(protocol_path.read_text())
    controller = ROOT / "src/aurora/policies.py"
    if digest(controller) != protocol["controller_sha256"]:
        raise ValueError("Running sweep's declared source was changed")
    excerpts = [{"line": number, "text": line.strip()} for number, line in enumerate(controller.read_text().splitlines(), 1) if "distances" in line or "counts =" in line or "support =" in line]
    report = {"status": "SUPPORT_REPAIR_REQUIRED_BEFORE_POLICY_FREEZE", "original_study": progress["study_id"], "original_protocol_sha256": digest(protocol_path), "controller_sha256": digest(controller), "source_excerpts": excerpts, "policy_outcomes_loaded": 0, "original_sweep_altered": False, "finding": "64-neighbor per-action count and hardcoded distance12, not inverse-logged-propensity ESS with an executed validation-threshold artifact", "repair": "Exact executed-p inverse-weight ESS in unchanged fixed representation; fixed95th higher quantile on validation-only public state distances; same estimator/threshold for MSCP and conventional support-gated comparator", "next_action": "After original sweep finishes, bind qualified support artifacts and run supplemental development for all affected cost/support recipes before reselection/pilot/freeze", "numerical_implementation_sha256": digest(ROOT / "src/aurora/support.py"), "no_primary_estimand_or_DGP_change": True}
    artifact = ROOT / "reports/policy" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    study.ledger.update("E15_POLICY_FREEZE", "CHECKPOINTED", artifacts=(artifact, ROOT / "reports/design/POLICY_SUPPORT_AUDIT.md"), capabilities={"POLICY_SUPPORT_QUALIFIED": False}, reason=report["next_action"])
    study.export_state()
    print(json.dumps({"artifact": str(artifact), "status": report["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
