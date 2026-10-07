#!/usr/bin/env python3
"""Record exhausted original duty profiles; never retry or relabel their failures."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main() -> int:
    study = Study(ROOT, "agent_sft_original_duty_exhausted")
    names = ("agent_bounded_decode_duty_qualification_1790939071780222260.json",
             "agent_bounded_decode_duty_qualification_1790940796462018137.json",
             "agent_bounded_decode_duty_qualification_1790941756313819261.json")
    attempts = []
    for name, duty in zip(names, (5., 10., 30.)):
        path = ROOT / "reports/agent" / name
        report = json.loads(path.read_text())
        if report["passed"] or report["recipe"] != "sft" or report["duty_pause_seconds"] != duty or report["final_tasks_loaded"] or report["semantic_task_scoring"]:
            raise ValueError("Not the three failed original TRAIN-only SFT duty profiles")
        attempts.append({"path": str(path), "sha256": digest(path), "duty_pause_seconds": duty,
                         "diagnostic": report["diagnostic"], "completed_decode_lengths": [row["generation_tokens"] for row in report["decodes"]],
                         "trained_parent_sha256": report.get("trained_parent_sha256")})
    report = {"status": "ORIGINAL_SFT_INFERENCE_PROFILES_EXHAUSTED", "qualification_passed": False,
              "execution_blocker": "BLOCKED_HARDWARE", "blocker_scope": "resource monitoring/load qualification, not proven hardware damage",
              "attempts": attempts, "trained_semantic_performance": "UNSCORED_NOT_ESTABLISHED",
              "primary_semantic_dependence_groups": 9, "prospective_primary_power_status": "UNDERPOWERED",
              "preserved_training_pointers": {name: {"path": str(ROOT / "reports/agent" / ("Qwen3-1.7B_" + name + "_seed41_LATEST.json")),
                  "sha256": digest(ROOT / "reports/agent" / ("Qwen3-1.7B_" + name + "_seed41_LATEST.json"))} for name in ("sft", "dpo", "ipo")},
              "no_new_duty_candidate": True, "no_profile_rerun": True, "no_final_semantic_outcomes_loaded": True,
              "remaining_heavy_GPU_work": "Requires defensible under-load monitoring qualification; idle probes alone do not qualify",
              "limitations": ["Missing historical partial completions cannot be recovered after timeout propagation",
                "Typed timeout latch repair preserves future failed evidence; it does not make these profiles pass",
                "Other trained recipes have not yet undergone their inference profiles; do not invent their failures",
                "No four-arm selection or agent primary freeze/confirmation is authorized by this artifact"]}
    artifact = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/agent/SFT_INFERENCE_DUTY_EXHAUSTED.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    previous_refs = tuple(Path(item["path"]) for item in study.ledger.read()["nodes"]["E10"]["artifacts"])
    study.ledger.update("E10", "CHECKPOINTED", artifacts=(*previous_refs, artifact),
        capabilities={"AGENT_SFT_INFERENCE_QUALIFIED": False, "CURRENT_HEAVY_GPU_MONITOR_QUALIFIED": False},
        reason="Successful SFT/DPO/IPO training preserved; original SFT5/10/30 inference profiles exhausted, no semantic scores; GPU monitor/load diagnosis required")
    study.export_state()
    print(json.dumps({"artifact": str(artifact), "status": report["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
