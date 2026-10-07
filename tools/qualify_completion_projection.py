#!/usr/bin/env python3
"""Compare immutable actual1.7B cached references, not model-quality outcomes."""
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
from aurora.studies import Study

OLD = ROOT / "reports/agent/e10_agent_qualify_dpo_1790902059945832167.json"
OLD_SHA = "6f9be9186e310d3910183dbe5231d138cbf74d918a192edf48b89b2666bcd040"


def main():
    started = time.perf_counter()
    study = Study(ROOT, "completion_projection_actual_reference_integrity")
    report = {"status": "RUNNING", "CUDA_models_loaded": 0, "not_semantic_evaluation_or_gradient_replay": True}
    try:
        pointer = json.loads((ROOT / "reports/agent/Qwen3-1.7B_DPO_DUTY_QUALIFICATION.json").read_text())
        if digest(OLD) != OLD_SHA or digest(Path(pointer["artifact"])) != pointer["sha256"]:
            raise ValueError("Actual reference report identities changed")
        old, new = json.loads(OLD.read_text()), json.loads(Path(pointer["artifact"]).read_text())
        if not old["passed"] or not new["passed"] or new.get("completion_projection") != "full_attended_context_suffix_L_plus_1_v1":
            raise ValueError("New actual projection-specific duty qualification is not terminal/passed")
        for key in ("objective", "model", "revision", "corpus_sha256", "seed", "parameters", "same_sft_parent", "ordered_task_turn_ids"):
            if old[key] != new[key]:
                raise ValueError(f"Reference populations/weights/normalization differ: {key}")
        values = []
        identities = []
        for result in (old, new):
            identity = result["reference_logps"]
            path = Path(identity["path"])
            if not path.resolve().is_relative_to(study.runtime / "runs") or path.is_symlink() or digest(path) != identity["sha256"]:
                raise ValueError("Owned immutable actual reference cache required")
            item = json.loads(path.read_text())
            identities.append({key: value for key, value in item.items() if key != "values"})
            values.append(np.asarray(item["values"], dtype=np.float64))
        if identities[0] != identities[1] or values[0].shape != (16, 2) or not all(np.isfinite(value).all() for value in values):
            raise ValueError("Same16 longest pairs/reference semantics required")
        absolute = np.abs(values[1] - values[0])
        # Existing recomputation tolerance, fixed prospectively here; do not
        # relax after inspecting a discrepancy. CPU gradients have own fixture.
        bound = 1e-4 + 1e-5 * np.abs(values[0])
        passed = bool(np.all(absolute <= bound))
        report.update(status="ACTUAL_CACHED_REFERENCE_NUMERICS_PASSED" if passed else "ACTUAL_CACHED_REFERENCE_NUMERICS_FAILED", passed=passed, old_report_sha256=OLD_SHA, new_report_sha256=pointer["sha256"], old_reference=old["reference_logps"], new_reference=new["reference_logps"], tolerance={"rtol": 1e-5, "atol": 1e-4}, maximum_absolute_difference=float(absolute.max()), failed_scalar_count=int(np.count_nonzero(absolute > bound)), scalar_count=int(absolute.size), corpus_sha256=new["corpus_sha256"], same_sft_parent=new["same_sft_parent"], no_final_tasks_or_outcomes_loaded=True, limitations=["Same actual1.7B TRAIN reference outputs only; not gradients, optimizer trajectory,4B compatibility or scientific task performance", "CPU tiny-Qwen loss/gradient equivalence is separately qualified", "A bounded qualifier still does not guarantee subsequent sustained health"])
    except Exception as error:
        report.update(status="ACTUAL_CACHED_REFERENCE_ADMISSION_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(artifact, report)
    atomic_json(study.directory / "result.json", report)
    if report["passed"]:
        atomic_json(ROOT / "reports/agent/COMPLETION_PROJECTION_REFERENCE_QUALIFICATION.json", report | {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"passed": report["passed"], "artifact": str(artifact)}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
