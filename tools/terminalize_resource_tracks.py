#!/usr/bin/env python3
"""Close diagnosed resource-dependent tracks; never stop independent CPU work."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.resource_dispositions import blocked_track_plan
from aurora.studies import Study


def main() -> int:
    if (ROOT / "reports/analysis/RESOURCE_TERMINAL_DISPOSITIONS.json").exists():
        raise ValueError("Existing dispositions must be verified/reused, not repeated")
    study = Study(ROOT, "v21_diagnosed_resource_track_dispositions")
    state = study.ledger.read()
    pointer_path = ROOT / "reports/agent/SFT_INFERENCE_DUTY_EXHAUSTED.json"
    pointer = json.loads(pointer_path.read_text())
    source = Path(pointer["artifact"])
    if digest(source) != pointer["sha256"]:
        raise ValueError("Resource exhaustion artifact identity changed")
    exhausted = json.loads(source.read_text())
    plan = blocked_track_plan(state, exhausted)
    for row in exhausted["attempts"]:
        path = Path(row["path"])
        if digest(path) != row["sha256"]:
            raise ValueError("Failed qualification history changed")
        attempt = json.loads(path.read_text())
        if attempt["passed"] or attempt["final_tasks_loaded"] or attempt["semantic_task_scoring"]:
            raise ValueError("Resource-only failed history required")
    preserved = {}
    for node in plan:
        preserved[node] = state["nodes"][node]
        for row in preserved[node]["artifacts"]:
            if digest(Path(row["path"])) != row["sha256"]:
                raise ValueError("Previous node artifact changed")
    report = {"status": "DIAGNOSED_RESOURCE_DISPOSITIONS", "captured_generation": state["generation"],
        "recorded_at_unix": time.time(), "argv": sys.argv, "source_exhaustion": pointer,
        "source_exhaustion_pointer_sha256": digest(pointer_path), "plan": plan, "prior_records_preserved": preserved,
        "diagnosis_sha256": digest(ROOT / "reports/design/INFERENCE_MONITOR_TIMEOUT_DIAGNOSIS.md"),
        "trained_pointers": exhausted["preserved_training_pointers"],
        "blocked_scope": "Safe under-load resource/monitor qualification, not proven hardware damage",
        "next_action": "Separate prospective under-load monitoring/hardware qualification before any renewed GPU work; preserve3s timeout/2s cadence/87C target/2GiB reserve and no replays of failed original SFT profiles. No unrelated applications, drivers or power settings changed.",
        "optional": {"E11": "NOT_APPLICABLE: no qualified common inference duty/finalist; optional GRPO adds cost without closing primary evidence",
            "Qwen3-4B": "NOT_APPLICABLE: no development-selected trained1.7B finalist; bounded update/reload never certified sustained training"},
        "independent_work_retained": ["active frozen200-pair policy confirmation", "isolated CPU component systems measurements when idle", "final reporting after terminal tracks"],
        "semantic_results": "UNSCORED", "prospective_agent_power_status": "UNDERPOWERED", "primary_agent_dependence_groups": 9,
        "scientific_conclusions_not_inferred": ["MSCP confirmation until all fixed worlds complete", "SFT/DPO/IPO task improvement", "H_delay effect", "production safety/lift"],
        "code_hashes": {p: digest(ROOT / p) for p in ("tools/terminalize_resource_tracks.py", "src/aurora/resource_dispositions.py")}}
    artifact = ROOT / "reports/analysis" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    for node, disposition in plan.items():
        current = study.ledger.read()["nodes"][node]
        retained = tuple(Path(item["path"]) for item in current["artifacts"])
        study.ledger.update(node, disposition["execution_status"], science=disposition["scientific_outcome"],
            artifacts=retained + (artifact, source), reason=disposition["reason"] + " " + report["next_action"])
    current = study.ledger.read()["nodes"]["E11"]
    if current["execution_status"] != "PENDING":
        raise ValueError("Optional GRPO already has evidence; cannot overwrite")
    study.ledger.update("E11", "NOT_APPLICABLE", science="NOT_RUN", artifacts=(artifact,), reason=report["optional"]["E11"])
    atomic_json(ROOT / "reports/analysis/RESOURCE_TERMINAL_DISPOSITIONS.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    study.export_state()
    print(json.dumps({"artifact": str(artifact), "terminal_nodes": list(plan) + ["E11"], "independent_policy_confirmation_preserved": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
