#!/usr/bin/env python3
"""Read-only track audit with hashed artifacts; never advances E16 or rescoring."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.completion import completion_matrix
from aurora.studies import Study


def main() -> int:
    started = time.perf_counter()
    study = Study(ROOT, "implementation_completion_audit")
    state = study.ledger.read()
    registry = ROOT / "config/experiments.json"
    report = completion_matrix(json.loads(registry.read_text())["nodes"], state)
    artifacts = {}
    for row in report["rows"]:
        for reference in row["artifacts"]:
            path = Path(reference["path"])
            resolved = path.resolve()
            if not resolved.is_relative_to(ROOT / "reports") and not resolved.is_relative_to(study.runtime / "runs"):
                raise ValueError("Evidence reference outside owned report/runtime scope")
            if path.is_symlink() or not path.is_file() or digest(path) != reference["sha256"]:
                raise ValueError("Ledger artifact bytes do not match their recorded SHA")
            artifacts[str(path)] = reference["sha256"]
    report.update(status="READ_ONLY_COMPLETION_AUDIT_EXECUTED", registry_sha256=digest(registry), captured_state=state, verified_artifacts_sha256=artifacts, state_mutations=0, final_outcomes_rescored=0, wall_seconds=time.perf_counter() - started, limitations=["Point-in-time ledger read; active runs may advance after capture", "Artifact identity is checked, not scientific superiority or full requirement-level qualification", "No final raw/prediction arrays loaded; only artifact file hashes"])
    artifact = ROOT / "reports/analysis" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/analysis/COMPLETION_AUDIT.json", {"artifact": str(artifact), "sha256": digest(artifact), "overall_project_complete": report["overall_project_complete"]})
    print(json.dumps({"artifact": str(artifact), "overall_project_complete": report["overall_project_complete"], "unfinished": report["unfinished_or_repair_required"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
