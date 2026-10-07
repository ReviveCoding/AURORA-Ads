#!/usr/bin/env python3
"""Close E14 without promoting CPU components to GPU/full-agent qualification."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study
from serving_study import active_project_compute


def main() -> int:
    if active_project_compute():
        raise ValueError("Systems disposition requires all owned empirical processes terminal")
    study = Study(ROOT, "e14_partial_CPU_systems_terminal_disposition")
    state = study.ledger.read()
    if state["nodes"]["E15_POLICY"]["execution_status"] != "EXECUTED":
        raise ValueError("Frozen confirmation must be terminal first")
    if state["nodes"]["E14"]["execution_status"] != "CHECKPOINTED":
        raise ValueError("Exactly the new CPU measurement checkpoint must be closed")
    if state["capabilities"].get("CURRENT_HEAVY_GPU_MONITOR_QUALIFIED", True):
        raise ValueError("This disposition is specific to the preserved GPU monitor hold")
    refs = []
    reports = {}
    for name in ("CPU_COMPONENT_MEASUREMENTS", "MCP_RECOVERY_QUALIFICATION"):
        pointer = json.loads((ROOT / "reports/serving" / (name + ".json")).read_text())
        path = Path(pointer["artifact"])
        if path.is_symlink() or digest(path) != pointer["sha256"]:
            raise ValueError("Systems evidence identity failed")
        refs.append(path)
        reports[name] = json.loads(path.read_text())
    cpu = reports["CPU_COMPONENT_MEASUREMENTS"]
    if not cpu["passed"] or cpu["protocol"]["CUDA_execution"] or not cpu["CPU_HTTP_recovery"]["restart_same_model_outputs"]:
        raise ValueError("CPU measurements/recovery must actually pass")
    unavailable = ["matched CUDA component/network latency", "CUDA allocator OOM/recovery",
                   "full adaptive policy feature-to-authorized-decision latency", "complete LLM agent task latency"]
    reason = "Isolated CPU component/HTTP/recovery executed; full E14 remains BLOCKED_HARDWARE under preserved GPU monitoring hold. Unavailable: " + "; ".join(unavailable) + ". No CPU fallback or production SLO claim."
    report = {"execution_status": "BLOCKED_HARDWARE", "scientific_outcome": "BLOCKED_HARDWARE",
              "CPU_measured": True, "MCP_correctness_preserved": True, "unavailable_domains": unavailable,
              "reason": reason, "source_reports": [{"path": str(p), "sha256": digest(p)} for p in refs],
              "code_sha256": digest(Path(__file__)), "scope": "Partial local systems evidence, not full qualification"}
    artifact = ROOT / "reports/serving" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    previous = tuple(Path(item["path"]) for item in state["nodes"]["E14"]["artifacts"])
    study.ledger.update("E14", "BLOCKED_HARDWARE", science="BLOCKED_HARDWARE", artifacts=tuple(dict.fromkeys(previous + tuple(refs) + (artifact,))), reason=reason)
    study.export_state()
    atomic_json(ROOT / "reports/serving/E14_TERMINAL_DISPOSITION.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"artifact": str(artifact), "status": "BLOCKED_HARDWARE", "CPU_measurements_retained": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
