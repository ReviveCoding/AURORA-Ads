#!/usr/bin/env python3
"""Export the ext4 execution ledger; preparation design remains unchanged."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json
from aurora.workflow import Ledger


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--record-progress", action="store_true")
    args = parser.parse_args()
    runtime = Path.home() / ".local/share/aurora-ads"
    if json.loads((runtime / "AURORA_RUNTIME.json").read_text())["repo_wsl"] != str(ROOT):
        raise ValueError("Runtime ownership mismatch")
    ledger = Ledger(ROOT / "config/experiments.json", runtime / "state/experiment_state.json")
    if args.inventory:
        ledger.update("E00", "EXECUTED", artifacts=(args.inventory,), reason="Read-only inventory executed; heavy hardware/environment qualification remains pending", capabilities={"readonly_host_inventory": True, "GPU_QUALIFIED": False})
    if args.record_progress:
        if (ROOT / "reports/data/ANALYSIS_ADMISSION.json").exists():
            raise ValueError("Legacy partial checkpoint cannot overwrite completed per-source admission. Export without --record-progress or record scoped current milestones.")
        audits = sorted((ROOT / "reports/data").glob("source_audit_*.json"))
        source_artifacts = tuple(sorted((ROOT / "reports/data").glob("admit_*.json"))) + (audits[-1],)
        ledger.update("E01", "CHECKPOINTED", artifacts=source_artifacts, reason="Three sources have full container/schema scans and clock/profile/item audits. Prior exposure/split lineage and final admission unresolved; R3 payload exceeds unchanged source ceiling. No background process is running.", capabilities={"R1_CONTAINER_SCHEMA_VALID": True, "R2_CONTAINER_SCHEMA_VALID": True, "R4_CONTAINER_SCHEMA_VALID": True, "R1_ANALYSIS_ADMITTED": False, "R2_ANALYSIS_ADMITTED": False, "R4_ANALYSIS_ADMITTED": False, "R3_ANALYSIS_ADMITTED": False})
        source_blocker = ROOT / "reports/data/R3_BLOCKED_SOURCE.json"
        atomic_json(source_blocker, {"status": "BLOCKED_SOURCE", "source_id": "criteo_search", "observed_content_length_bytes": 2002864638, "configured_source_ceiling_bytes": 700000000, "payload_bytes_transferred": 0, "diagnostic_basis": "Official endpoint header probe plus acquisition ledger", "next_action": "Review current official object identity, archive size and source contract in a separately versioned storage/source review. Do not raise cap or substitute source silently."})
        ledger.update("E03", "BLOCKED_SOURCE", science="BLOCKED_SOURCE", artifacts=(source_blocker,), reason="R3 official payload exceeds the configured acquisition ceiling; no admitted R3 labels. Dependent confirmation cannot proceed.")
        simulator = sorted((ROOT / "reports/simulator").glob("simulator_reference_*.json"))[-1]
        qualification = sorted((ROOT / "reports/environment").glob("cpu_qualification_*.json"))[-1]
        ledger.update("E07", "CHECKPOINTED", artifacts=(simulator, qualification), reason="Reference implementation and four full-horizon development worlds executed; mechanism-block splits, randomized action-value data and full falsification coverage pending. No background process is running.")
        ledger.update("E10_TOOLS", "PENDING", artifacts=(qualification,), reason="Nine local host interfaces and transaction fixtures implemented; E07 qualification, MCP transport, executable semantic-family tasks and complete tools remain pending.")
    state = ledger.read()
    atomic_json(ROOT / "reports/state/experiment_state.json", state)
    for path in (runtime / "state/events").glob("*.json"):
        atomic_json(ROOT / "reports/state/events" / path.name, json.loads(path.read_text()))
    print(json.dumps({"generation": state["generation"], "dependency_ready_nodes": ledger.ready(), "notice": "Additional source/resource capabilities must pass before running dependent science"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
