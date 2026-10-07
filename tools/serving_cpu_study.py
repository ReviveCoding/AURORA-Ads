#!/usr/bin/env python3
"""Explicit isolated CPU component measurement; GPU/LLM domains remain blocked."""
from __future__ import annotations

import asyncio
import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.resources import storage_admission
from aurora.serving_models import load_frozen_mean
from aurora.studies import Study
from serving_study import active_project_compute, launch_server, model_bench, network_bench, payload, stop_server


def assert_readonly_match(reference: dict, repeated: dict) -> None:
    import numpy as np
    if reference["model_sha256"] != repeated["model_sha256"] or any(row["state_mutations"] != 0 for row in (reference, repeated)):
        raise ValueError("Same-model read-only response required")
    if any(len(row["scores"]) != 6 or row["decision_scope"] != "frozen mean-head ranking only; not authorized, host-guarded or adaptive campaign decision" for row in (reference, repeated)):
        raise ValueError("Unchanged bounded provisional component scope required")
    np.testing.assert_allclose(reference["scores"], repeated["scores"], rtol=1e-4, atol=.002)
    if reference["provisional_candidate_index"] != repeated["provisional_candidate_index"]:
        raise ValueError("Deterministic provisional ranking changed on retry/restart")


async def cpu_recovery(study, identity, requests, health_check):
    """Actual owned HTTP child cancellation/retry/reload, not economic idempotency."""
    import httpx
    processes = []
    records = {"fixture_delay_seconds": .1, "not_ordinary_latency_evidence": True,
        "cancellation_scope": "client request task cancelled; backend interruption is NOT assumed",
        "budget_scope": "read-only component has no reservation/commit API; economic idempotency is separate MCP evidence"}
    reference = None
    for ordinal in (100, 101):
        health_check()
        process, stream, url, metadata = await launch_server(study, "cpu", ordinal, delay=.1)
        try:
            async with httpx.AsyncClient(timeout=10.) as client:
                sent = payload(identity, requests[0], "readonly_retry", 5.)
                first = await client.post(url + "/predict", json=sent)
                if first.status_code != 200:
                    raise ValueError("Recovery fixture initial inference failed")
                response = first.json()
                if reference is None:
                    reference = response
                else:
                    assert_readonly_match(reference, response)
                duplicate = await client.post(url + "/predict", json=sent)
                if duplicate.status_code != 200:
                    raise ValueError("Read-only duplicate retry failed")
                assert_readonly_match(reference, duplicate.json())
                metadata["initial_response"] = response
                metadata["duplicate_response"] = duplicate.json()
                if ordinal == 100:
                    cancelled = asyncio.create_task(client.post(url + "/predict",
                        json=payload(identity, requests[0], "client_cancel", 5.)))
                    await asyncio.sleep(.025)
                    if cancelled.done():
                        raise ValueError("Client cancellation was not actually exercised")
                    cancelled.cancel()
                    try:
                        await cancelled
                    except asyncio.CancelledError:
                        records["client_cancelled_error_observed"] = True
                    else:
                        raise ValueError("Expected client task cancellation missing")
                    recovered = await client.post(url + "/predict", json=sent)
                    if recovered.status_code != 200:
                        raise ValueError("Post-client-cancel inference failed")
                    assert_readonly_match(reference, recovered.json())
                    records["post_cancel_response"] = recovered.json()
        finally:
            await stop_server(process, stream, metadata)
            processes.append(metadata)
            atomic_json(study.directory / "CPU_recovery_process_costs.json", processes)
    records.update(processes=processes, distinct_owned_children_created=2, restart_same_model_outputs=True,
        duplicate_readonly_outputs=True, economic_double_spend_test="existing independent MCP crash/replay qualification, not this fixture")
    atomic_json(study.directory / "CPU_HTTP_recovery_fixtures.json", records)
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-model-measurements", type=Path)
    args = parser.parse_args()
    latest = ROOT / "reports/serving/CPU_COMPONENT_MEASUREMENTS.json"
    if latest.exists():
        raise ValueError("Completed CPU measurements must be verified/reused, not rerun")
    if active_project_compute():
        raise RuntimeError("Isolated CPU performance requires no owned training/simulation/conversion/test run")
    study = Study(ROOT, "e14_explicit_CPU_component_serving")
    started = time.perf_counter()
    contract = json.loads((ROOT / "config/resources.json").read_text())
    storage = storage_admission(study.runtime, ROOT, expected_growth_bytes=2**30, contract=contract)
    import torch
    import psutil
    torch.set_num_threads(2)
    cache = study.runtime / "cache/serving_compile" / study.name
    os.environ.update(TORCHINDUCTOR_CACHE_DIR=str(cache / "inductor"), TRITON_CACHE_DIR=str(cache / "triton"),
                      TORCHINDUCTOR_COMPILE_THREADS="2")
    protocol = {"frozen_before_measurement": True, "devices": ["cpu"], "CUDA_execution": False,
        "scope": "Frozen observed-only numerical mean component, not selected adaptive policy or LLM",
        "batches": [1, 16, 64], "compiled": [False, True], "inference_repetitions": 100,
        "HTTP_connections": [1, 4], "HTTP_windows": 3, "offered_rates": [10, 100, 200],
        "seconds_per_window_rate": 10, "cold": "new process/first call; OS cache not cleared",
        "failure_fixtures": ["bounded injected queue saturation", "deadline", "stale model", "client cancellation", "read-only duplicate retry", "owned process restart"],
        "GPU_OOM_fixture": "NOT_RUN_RESOURCE_HOLD", "complete_agent_task": "NOT_RUN_RESOURCE_HOLD",
        "time_cap_seconds": 1800, "storage_admission": storage, "threads": 2,
        "argv": sys.argv, "started_at_unix": time.time(), "python": sys.version,
        "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json"),
        "source_hashes": {name: digest(ROOT / name) for name in ("tools/serving_cpu_study.py",
            "tools/serving_study.py", "tools/prediction_server.py", "src/aurora/serving_models.py", "src/aurora/serving.py")},
        "config_hashes": {p.name: digest(p) for p in (ROOT / "config").glob("*.json")},
        "warmstart_pointer_sha256": digest(ROOT / "reports/policy/WARMSTART_LATEST.json")}
    import importlib.metadata
    protocol["current_packages"] = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
    protocol["dependency_repair"] = "Pinned sniffio1.3.1 to avoid HTTPcore optional-import stat storm; historical environment lock unchanged"
    if importlib.metadata.version("sniffio") != "1.3.1":
        raise ValueError("Pinned HTTP async dependency must be qualified before measurements")
    atomic_json(study.directory / "protocol_before_measurement.json", protocol)
    samples = []
    report = {"protocol": protocol, "passed": False,
        "limitations": ["Explicit CPU-only component result, not CPU fallback for GPU-qualified inference",
            "Feature-to-provisional ranking is not host-authorized full policy decision",
            "Local convenience windows, not production latency/availability guarantees",
            "Injected faults are reliability fixtures, not ordinary latency evidence",
            "Complete LLM tasks, GPU matching/OOM and full adaptive-policy timing remain unavailable"]}
    def health_check():
        if time.perf_counter() - started > protocol["time_cap_seconds"]:
            raise RuntimeError("Bounded CPU measurement time cap reached")
        process = psutil.Process()
        resident = process.memory_info().rss + sum(p.memory_info().rss for p in process.children(recursive=True) if p.is_running())
        sample = {"elapsed_seconds": time.perf_counter() - started, "resident_parent_children_bytes": resident,
                  "available_ram_bytes": psutil.virtual_memory().available, "cpu_load": list(os.getloadavg())}
        samples.append(sample)
        atomic_json(study.directory / "resource_progress.json", samples)
        if resident > contract["host_app_ram_target_gib"] * 2**30:
            raise RuntimeError("Declared host RAM envelope exceeded")
    try:
        loading = time.perf_counter()
        model, identity, requests = load_frozen_mean(ROOT)
        report["model_startup_seconds"] = time.perf_counter() - loading
        identity_binding = {"model_identity": identity,
            "matched_requests_sha256": hashlib.sha256(requests.tobytes()).hexdigest(), "shape": list(requests.shape)}
        atomic_json(study.directory / "model_requests_before_measurement.json", identity_binding)
        report.update(identity_binding)
        if args.reuse_model_measurements:
            path = args.reuse_model_measurements.resolve()
            if not path.is_relative_to(study.runtime / "runs") or path.name != "model_measurements.json":
                raise ValueError("Only verified owned completed component measurements may be reused")
            failed_pointer = json.loads((ROOT / "reports/serving/CPU_FAILED_ATTEMPT.json").read_text())
            failed_path = Path(failed_pointer["artifact"])
            if digest(failed_path) != failed_pointer["sha256"]:
                raise ValueError("Failed attempt identity changed")
            failed = json.loads(failed_path.read_text())
            if failed["retained_files"][str(path)] != digest(path) or failed["model_identity"] != identity_binding:
                raise ValueError("Reused measurement/model/request identity changed")
            report["model_measurements"] = json.loads(path.read_text())
            report["reused_component_measurements"] = {"path": str(path), "sha256": digest(path), "original_failed_attempt": failed_pointer,
                "scope": "Original six completed model profiles reused; HTTP retry has new pinned async dependency protocol"}
        else:
            report["model_measurements"] = model_bench(model, requests, study.directory, health_check, devices=("cpu",))
        report["network_measurements"], report["process_costs"] = asyncio.run(
            network_bench(study, identity, requests, health_check, devices=("cpu",)))
        report["CPU_HTTP_recovery"] = asyncio.run(cpu_recovery(study, identity, requests, health_check))
        report.update(status="CPU_COMPONENT_MEASURED_NOT_FULL_E14", passed=True)
    except Exception as error:
        report.update(status="CPU_COMPONENT_MEASUREMENT_FAILED", diagnostic={"type": type(error).__name__,
            "message": str(error), "traceback": traceback.format_exc()[-5000:]})
    report.update(resource_samples=samples, wall_seconds=time.perf_counter()-started, finished_at_unix=time.time())
    artifact = ROOT / "reports/serving" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    if report["passed"]:
        atomic_json(latest, {"artifact": str(artifact), "sha256": digest(artifact)})
        previous = tuple(Path(item["path"]) for item in study.ledger.read()["nodes"]["E14"]["artifacts"])
        study.ledger.update("E14", "CHECKPOINTED", artifacts=previous + (artifact,),
            reason="Isolated CPU component timings; remaining GPU/LLM/full-policy domains unqualified")
        study.export_state()
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
