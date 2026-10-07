#!/usr/bin/env python3
"""Close only evidence paths with already documented source/terms blockers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main():
    study = Study(ROOT, "source_dependent_terminal_audit")
    r3 = ROOT / "reports/data/R3_BLOCKED_SOURCE.json"
    diagnostic = json.loads(r3.read_text())
    if diagnostic["status"] != "BLOCKED_SOURCE" or diagnostic["payload_bytes_transferred"] != 0:
        raise ValueError("Unexpected source diagnostic; do not propagate inferred blocker")
    source_config = json.loads((ROOT / "config/datasets.json").read_text())
    optional = next(item for item in source_config["datasets"] if item["id"] == "ipinyou")
    if optional["acquisition"] != "manual" or optional["license"] != "IPINYOU-NONCOMMERCIAL":
        raise ValueError("Manual optional-source gate changed")
    report = {"r3_diagnostic": {"path": str(r3), "sha256": digest(r3)}, "r3": diagnostic, "ipinyou": {"status": "BLOCKED_SOURCE", "configured_license": optional["license"], "acquisition": "manual", "downloaded": False, "authorized_licenses": ["CC-BY-NC-SA-4.0", "CC-BY-4.0"], "reason": "Configured source requires manual publisher/terms review and verified archive. User explicitly did not authorize additional terms or source substitution.", "next_action": "Optional future work: user-provided publisher-verified archive and explicit applicable terms authorization; not required for core tracks."}, "not_blocked_by_this_audit": ["R1", "R2", "R4", "S1", "A1", "E14"], "old_metrics_imported": False}
    export = ROOT / "reports/data" / (study.name + ".json")
    atomic_json(export, report)
    for node in ("E15_R3_FREEZE", "E15_R3"):
        current = study.ledger.read()["nodes"][node]["execution_status"]
        if current not in {"PENDING", "BLOCKED_SOURCE"}:
            raise ValueError("Dependent node already has execution; manual reconciliation required")
        study.ledger.update(node, "BLOCKED_SOURCE", science="BLOCKED_SOURCE", artifacts=(export, r3), reason="No admitted R3 labels: official object exceeds unchanged acquisition ceiling. M41+C54 freeze and final scoring cannot be executed. See source diagnostic next action.")
    study.ledger.update("E06", "BLOCKED_SOURCE", science="BLOCKED_SOURCE", artifacts=(export,), reason=report["ipinyou"]["reason"] + " " + report["ipinyou"]["next_action"])
    study.export_state()
    print(json.dumps({"artifact": str(export), "terminal_nodes": ["E06", "E15_R3_FREEZE", "E15_R3"], "independent_tracks_preserved": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
