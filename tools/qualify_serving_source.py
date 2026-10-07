#!/usr/bin/env python3
"""CPU artifact integrity only; never an isolated serving latency benchmark."""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import torch
from aurora.artifacts import atomic_json, digest
from aurora.serving_models import load_frozen_mean
from aurora.studies import Study


def main():
    study = Study(ROOT, "e14_serving_source_cpu_integrity")
    started = time.perf_counter()
    report = {"status": "RUNNING", "evidence_domain": "CPU_ARTIFACT_INTEGRITY", "not_latency_or_GPU_qualification": True}
    try:
        model, identity, requests = load_frozen_mean(ROOT)
        model2, identity2, requests2 = load_frozen_mean(ROOT)
        if identity != identity2:
            raise ValueError("Serving posterior reconstruction identity is not reproducible")
        np.testing.assert_array_equal(requests, requests2)
        with torch.inference_mode():
            values = model(model.encode(requests))
            replay = model2(model2.encode(requests2))
        torch.testing.assert_close(values, replay, rtol=0, atol=0)
        if values.shape != (512, 6) or not torch.isfinite(values).all():
            raise ValueError("Finite complete six-candidate fixture required")
        report.update(status="CPU_SOURCE_INTEGRITY_PASSED", passed=True, model_identity=identity, fixture_rows=len(requests), exact_cpu_reconstruction=True, eager_scripted_embedding_parity=True, fully_matured_unique_training_cohorts=True)
    except Exception as error:
        report.update(status="CPU_SOURCE_INTEGRITY_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/serving" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    if report["passed"]:
        atomic_json(ROOT / "reports/serving/SOURCE_INTEGRITY_LATEST.json", {"artifact": str(artifact), "sha256": digest(artifact), "model_sha256": report["model_identity"]["model_sha256"], "not_serving_measurement": True})
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
