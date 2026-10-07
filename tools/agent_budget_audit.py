#!/usr/bin/env python3
"""Hash-bound actual completed agent command costs; no quota/state mutation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.agent_budget import completed_agent_wall_seconds
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification-report", type=Path)
    args = parser.parse_args()
    study = Study(ROOT, "completed_agent_command_cost_audit")
    report = completed_agent_wall_seconds(ROOT / "reports/execution")
    report["cap_seconds"] = json.loads((ROOT / "config/resources.json").read_text())["gpu_hours_caps"]["agent"] * 3600
    report["inputs_sha256"] = {item["artifact"]: digest(Path(item["artifact"])) for item in report["commands"]}
    report["code_sha256"] = {relative: digest(ROOT / relative) for relative in ("src/aurora/agent_budget.py", "tools/agent_budget_audit.py", "config/resources.json")}
    report["status"] = "COMPLETED_COMMAND_COSTS_AUDITED_NOT_CURRENT_JOB_ADMISSION"
    if args.qualification_report:
        original = args.qualification_report.resolve()
        if not original.is_relative_to(ROOT / "reports/agent") or original.is_symlink():
            raise ValueError("Require an owned immutable qualification report")
        qualification = json.loads(original.read_text())
        omitted = [item for item in report["commands"] if item["command"] == "qualify_preference_restart"]
        correction = sum(item["full_wall_seconds"] for item in omitted)
        prior = qualification["allocation_accounting"]["prior_actual_wall_seconds_including_failures"]
        report["qualification_accounting_companion"] = {
            "original_artifact": str(original), "original_sha256": digest(original),
            "original_prior_wall_seconds": prior,
            "omitted_completed_restart_wall_seconds": correction,
            "corrected_prior_wall_seconds": prior + correction,
            "original_report_not_modified": True,
            "scope": "Prospective reader correction; no model outcome, learning input or resource cap change",
        }
    report["limitations"] = ["Current live-job elapsed is not in this completed-only sum; never treat this as full admission on its own", "Interrupted/unexported commands require reconciliation before a further heavy run", "Full wrapper wall is conservative allocation, not measured GPU-busy occupancy", "Existing reader omitted preference restart; do not rewrite prior recorded accounting; connect repaired reader after active qualification ends"]
    artifact = ROOT / "reports/environment" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/environment/AGENT_COMMAND_COST_AUDIT.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"artifact": str(artifact), "completed_full_wall_seconds": report["completed_full_wall_seconds"], "current_elapsed_not_included": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
