#!/usr/bin/env python3
"""Isolated matched component serving, open-loop HTTP and actual process recovery."""
from __future__ import annotations

import asyncio
import gc
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np

from aurora.artifacts import atomic_json, digest
from aurora.resources import check_gpu_room, cuda_lease, storage_admission, telemetry
from aurora.serving_models import load_frozen_mean
from aurora.studies import Study


def active_project_compute():
    names = ("agent_study.py", "agent_validation.py", "policy_study.py", "policy_repair_study.py", "fast_bidder_study.py", "numerical_policy_study.py", "predictive_study.py", "incident_study.py", "causal_study.py", "ope_study.py", "statistics_qualification.py", "qualify_agent_model.py", "qualify_trained_restart.py", "qualify_agent_inference.py", "attribution_study.py", "qualify_cpu.py", "audit_sources.py", "admit_source.py", "batch_admit.py", "model_prepare.py")
    names += ("policy_ablation_study.py", "policy_pilot_study.py", "policy_confirmation_study.py",
              "r3_cpu_baselines.py", "r3_value_study.py", "r3_parametric_delay_study.py", "r3_feedback_shift_study.py",
              "prepare_r3_development.py", "convert_r3_source.py", "admit_r3_clock.py",
              "recover_r3_source.py", "inspect_r3_container.py", "agent_confirmation.py", "agent_ablation_study.py")
    names += ("serving_study.py", "serving_cpu_study.py", "mcp_recovery_study.py")
    identifiers = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if (entry / "cwd").resolve() != ROOT:
                continue
            arguments = (entry / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if compute_arguments(arguments, ROOT, names):
            identifiers.append(int(entry.name))
    return identifiers  # Never print unrelated process command lines/tokens.


def compute_arguments(arguments, root, names):
    return any(str(root / "tools" / name).encode() in arguments or ("tools/" + name).encode() in arguments for name in names)


def quantiles(seconds):
    values = np.asarray(seconds, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("Finite nonnegative observed latency samples required")
    return {"n": len(values), "p50_ms": float(np.quantile(values, .5) * 1000), "p95_ms": float(np.quantile(values, .95) * 1000), "p99_ms": float(np.quantile(values, .99) * 1000), "maximum_ms": float(values.max() * 1000), "percentiles": "empirical, not population confidence bounds"}


def qualified_devices(devices):
    if devices not in (("cpu",), ("cpu", "cuda")):
        raise ValueError("Explicit CPU-only or matched CPU-then-CUDA profile required")
    return devices


def model_bench(model, requests, directory, health_check, *, devices=("cpu", "cuda")):
    import torch
    records = []
    reference = None
    for device in qualified_devices(devices):
        health_check()
        model.to(device)
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            predictions = model(model.encode(requests)).cpu().numpy()
        if device == "cpu":
            reference = predictions
        else:
            np.testing.assert_allclose(predictions, reference, rtol=1e-4, atol=.002)
        for compiled in (False, True):
            candidate = torch.compile(model, fullgraph=True) if compiled else model
            for batch in (1, 16, 64):
                health_check()
                raw = requests[:batch]
                encoded = model.encode(raw)
                if device == "cuda":
                    torch.cuda.synchronize()
                startup = time.perf_counter()
                with torch.inference_mode():
                    output = candidate(encoded)
                if device == "cuda":
                    torch.cuda.synchronize()
                first = time.perf_counter() - startup
                health_check()
                with torch.inference_mode():
                    torch.testing.assert_close(output, model(encoded), rtol=1e-4, atol=.002)
                inference, complete = [], []
                for index in range(100):
                    if index % 25 == 0:
                        health_check()
                    if device == "cuda":
                        torch.cuda.synchronize()
                    begin = time.perf_counter()
                    with torch.inference_mode():
                        candidate(encoded)
                    if device == "cuda":
                        torch.cuda.synchronize()
                    inference.append(time.perf_counter() - begin)
                    begin = time.perf_counter()
                    with torch.inference_mode():
                        result = candidate(model.encode(raw))
                        result.argmax(dim=1).cpu()
                    if device == "cuda":
                        torch.cuda.synchronize()
                    complete.append(time.perf_counter() - begin)
                records.append({"device": device, "dtype": "float32", "batch": batch, "compile": compiled, "first_call_including_compile_seconds": first, "inference_only": quantiles(inference), "feature_to_provisional_ranking": quantiles(complete), "raw_inference_seconds": inference, "raw_feature_ranking_seconds": complete, "candidate_count": 6, "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None, "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved() if device == "cuda" else None})
                atomic_json(directory / "model_measurements_progress.json", records)
            del candidate, encoded, output, result
            gc.collect()
    model.cpu()
    if "cuda" in devices:
        torch.cuda.empty_cache()
    atomic_json(directory / "model_measurements.json", records)
    return records


async def launch_server(study, device, ordinal, *, delay=0., capacity=16, oom=False):
    import httpx
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    log_path = study.directory / f"server_{ordinal}_{device}.txt"
    stream = log_path.open("x")
    command = [sys.executable, str(ROOT / "tools/prediction_server.py"), "--port", str(port), "--device", device, "--queue-capacity", str(capacity), "--fixture-backend-delay-seconds", str(delay)]
    if device == "cuda":
        command += ["--lease-owner-pid", str(os.getpid())]
    if oom:
        command += ["--fixture-gpu-oom-once"]
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=os.environ | {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "TORCHINDUCTOR_COMPILE_THREADS": "2", "PYTHONDONTWRITEBYTECODE": "1"})
    url = f"http://127.0.0.1:{port}"
    try:
        async with httpx.AsyncClient(timeout=1.) as client:
            for _ in range(600):
                if process.poll() is not None:
                    raise RuntimeError("Owned service exited during startup; retained log: " + str(log_path))
                try:
                    response = await client.get(url + "/health")
                    if response.status_code == 200 and response.json()["ready"]:
                        return process, stream, url, {"command": command, "pid": process.pid, "startup_until_ready_seconds": time.perf_counter() - started, "health": response.json(), "log": str(log_path)}
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(.1)
        raise TimeoutError("Service readiness deadline")
    except Exception:
        process.terminate()  # Exact child created above; never unrelated apps.
        await asyncio.to_thread(process.wait, 10)
        stream.close()
        raise


async def stop_server(process, stream, metadata):
    began = time.perf_counter()
    process.terminate()
    try:
        await asyncio.to_thread(process.wait, 15)
    except subprocess.TimeoutExpired:
        process.kill()  # Only this owned benchmark child, recorded as a failure.
        await asyncio.to_thread(process.wait, 5)
        metadata["forced_owned_process_kill"] = True
    metadata.update(shutdown_seconds=time.perf_counter() - began, exit_code=process.returncode)
    stream.close()
    metadata["log_sha256"] = digest(Path(metadata["log"]))


def payload(identity, features, identifier, deadline=1.):
    return {"request_id": identifier, "expected_model_sha256": identity["model_sha256"], "features": features.tolist(), "deadline_seconds": deadline}


async def open_loop(url, identity, requests, *, rate, count, connections):
    import httpx
    records = []
    start = time.perf_counter() + .1
    async with httpx.AsyncClient(timeout=6., limits=httpx.Limits(max_connections=connections, max_keepalive_connections=connections)) as client:
        async def send(index):
            arrival = start + index / rate
            await asyncio.sleep(max(0., arrival - time.perf_counter()))
            sent = time.perf_counter()
            status, response, diagnostic = None, None, None
            try:
                reply = await client.post(url + "/predict", json=payload(identity, requests[index % len(requests)], str(index)))
                status = reply.status_code
                response = reply.json()
            except httpx.HTTPError as error:
                diagnostic = type(error).__name__
            finished = time.perf_counter()
            records.append({"index": index, "scheduled_arrival_offset_seconds": index / rate, "client_dispatch_delay_seconds": sent - arrival, "scheduled_arrival_to_response_seconds": finished - arrival, "send_to_response_seconds": finished - sent, "http_status": status, "error": status != 200, "above50ms": finished - arrival > .05, "response": response, "diagnostic": diagnostic})
        await asyncio.gather(*(send(index) for index in range(count)))
    records.sort(key=lambda row: row["index"])
    return records


async def network_bench(study, identity, requests, health_check, *, devices=("cpu", "cuda")):
    import httpx
    summaries, processes = [], []
    ordinal = 0
    for device in qualified_devices(devices):
        for connections in (1, 4):
            for window in range(3):
                health_check()
                ordinal += 1
                process, stream, url, metadata = await launch_server(study, device, ordinal)
                try:
                    if metadata["health"]["model_sha256"] != identity["model_sha256"]:
                        raise ValueError("Matched model identity changed across CPU/GPU/restarts")
                    first = await open_loop(url, identity, requests, rate=1, count=1, connections=1)
                    if first[0]["http_status"] != 200:
                        raise RuntimeError("First request failed; preserve startup/failure costs and stop this profile")
                    warm = await open_loop(url, identity, requests, rate=100, count=20, connections=connections)
                    metadata["first_request"] = first
                    metadata["warmup_errors_retained"] = sum(row["error"] for row in warm)
                    for rate in (10, 100, 200):
                        health_check()
                        count = rate * 10
                        rows = await open_loop(url, identity, requests, rate=rate, count=count, connections=connections)
                        output = study.directory / f"http_{device}_concurrency{connections}_window{window}_rate{rate}.json"
                        atomic_json(output, rows)
                        summary = {"device": device, "connections": connections, "window": window, "offered_rps": rate, "requests": count, "all_requests_latency": quantiles([row["scheduled_arrival_to_response_seconds"] for row in rows]), "error_fraction": sum(row["error"] for row in rows) / count, "above50ms_fraction": sum(row["above50ms"] for row in rows) / count, "raw_records": str(output), "sha256": digest(output), "errors_not_removed_from_percentiles": True}
                        summary["observed_local_target_met"] = rate == 100 and summary["all_requests_latency"]["p95_ms"] <= 50 and summary["error_fraction"] <= .001
                        summaries.append(summary)
                        atomic_json(study.directory / "network_progress.json", summaries)
                        health_check()
                        if any(row.get("response", {}).get("detail") == "RESOURCE_ENVELOPE_LOST" for row in rows if isinstance(row.get("response"), dict)):
                            raise RuntimeError("Latched serving GPU resource violation; preserve failure, no automatic hardware retry")
                finally:
                    await stop_server(process, stream, metadata)
                    processes.append(metadata)
                    atomic_json(study.directory / "process_costs.json", processes)
    # Bounded CPU injection: exercise actual HTTP queue saturation/timeout, not
    # mistake sleep-injected latency for ordinary model performance.
    ordinal += 1
    process, stream, url, metadata = await launch_server(study, "cpu", ordinal, delay=.1, capacity=1)
    try:
        overload = await open_loop(url, identity, requests, rate=200, count=50, connections=16)
        if not any(row["http_status"] == 503 for row in overload):
            raise ValueError("Expected queue saturation was not exercised")
        async with httpx.AsyncClient(timeout=2.) as client:
            timed = await client.post(url + "/predict", json=payload(identity, requests[0], "deadline", .005))
            if timed.status_code != 504:
                raise ValueError("Expected actual deadline path was not exercised")
            stale = payload(identity, requests[0], "stale") | {"expected_model_sha256": "f" * 64}
            denied = await client.post(url + "/predict", json=stale)
            if denied.status_code != 409:
                raise ValueError("Stale model was not blocked")
        atomic_json(study.directory / "http_failure_fixtures.json", {"delay_injected_seconds": .1, "overload": overload, "deadline_http_status": timed.status_code, "stale_model_http_status": denied.status_code, "not_performance_evidence": True})
    finally:
        await stop_server(process, stream, metadata)
        processes.append(metadata)
    if "cuda" not in devices:
        atomic_json(study.directory / "process_costs.json", processes)
        return summaries, processes
    ordinal += 1
    process, stream, url, metadata = await launch_server(study, "cuda", ordinal, oom=True)
    try:
        async with httpx.AsyncClient(timeout=10.) as client:
            failed = await client.post(url + "/predict", json=payload(identity, requests[0], "oom"))
            recovered = await client.post(url + "/predict", json=payload(identity, requests[0], "post_oom"))
            if failed.status_code != 503 or failed.json().get("detail") != "BACKEND_RESOURCE_EXHAUSTED" or recovered.status_code != 200:
                raise ValueError("Actual allocator-limited CUDA OOM/recovery path failed")
            np.testing.assert_allclose(recovered.json()["scores"], first[0]["response"]["scores"], rtol=1e-4, atol=.002)
        atomic_json(study.directory / "cuda_allocator_oom_recovery.json", {"first_response": failed.json(), "recovery_response": recovered.json(), "fixture": "Actual PyTorch CUDA allocator64MiB limit with128MiB requested; never fill physical GPU", "not_device_loss_or_full_VRAM_exhaustion": True})
    finally:
        await stop_server(process, stream, metadata)
        processes.append(metadata)
    atomic_json(study.directory / "process_costs.json", processes)
    return summaries, processes


def main():
    study = Study(ROOT, "e14_isolated_component_serving")
    report = {"status": "RUNNING", "evidence_domain": "LOCAL_ENGINEERING", "limitations": ["Frozen observed-only surrogate, not selected adaptive policy or production deployment", "Feature-to-provisional ranking is not host-authorized prepare/commit latency", "Cold means new process/first call; OS/driver filesystem caches are not forcibly cleared", "Temporal windows are a small local convenience sample, not a production risk guarantee", "Complete agent-task and selected adaptive policy latencies remain separate qualification"]}
    started = time.perf_counter()
    try:
        active = active_project_compute()
        if active:
            raise RuntimeError("Isolated benchmark requires no concurrent project training/simulation: owned process IDs " + str(active))
        contract = json.loads((ROOT / "config/resources.json").read_text())
        report["storage_admission"] = storage_admission(study.runtime, ROOT, expected_growth_bytes=1024**3, contract=contract)
        report["telemetry_before"] = check_gpu_room(8)
        # Compile caches are project-owned runtime data, not global ~/.cache.
        cache = study.runtime / "cache" / "serving_compile" / study.name
        os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(cache / "inductor")
        os.environ["TRITON_CACHE_DIR"] = str(cache / "triton")
        report["compile_cache_profile"] = {"path": str(cache), "initially_empty_per_study": not cache.exists(), "subsequent_shapes_warm_within_study": True}
        prior_wall = 0.
        accounted = ("serving_study", "qualify_serving_source", "statistics_qualification", "qualify_mcp", "simulator_study")
        for name in accounted:
            for path in (ROOT / "reports/execution").glob("execution_" + name + "_*/execution.json"):
                recorded = json.loads(path.read_text())
                prior_wall += recorded.get("wall_seconds", 0.)
        cap = contract["gpu_hours_caps"]["evaluation_systems"] * 3600
        report["allocation_accounting"] = {"prior_actual_wall_seconds": prior_wall, "accounted_wrapped_studies": accounted, "cap_seconds": cap, "includes_failed_runs_and_CPU_reference_wall_conservatively": True, "agent_validation_accounted_separately_in_agent_allocation": True}
        report["resource_samples"] = []
        target = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())["device_reported_target_c"]
        def health_check():
            import psutil
            if prior_wall + time.perf_counter() - started >= cap:
                raise RuntimeError("Evaluation/systems serving allocation exhausted; no silent expansion")
            current = telemetry()
            process = psutil.Process()
            resident = process.memory_info().rss + sum(child.memory_info().rss for child in process.children(recursive=True) if child.is_running())
            report["resource_samples"].append(current | {"owned_parent_child_resident_bytes": resident})
            atomic_json(study.directory / "resource_progress.json", report["resource_samples"])
            if current["temperature_c"] >= target or current["total_mib"] - current["used_mib"] < 2048 or resident > contract["host_app_ram_target_gib"] * 1024**3:
                raise RuntimeError("Serving resource envelope unavailable; preserve measurements and stop")
        import torch
        torch.set_num_threads(2)
        os.environ["TORCHINDUCTOR_COMPILE_THREADS"] = "2"
        with cuda_lease(study.runtime):
            torch.cuda.set_per_process_memory_fraction(4 * 1024**3 / torch.cuda.get_device_properties(0).total_memory)
            model_start = time.perf_counter()
            model, identity, requests = load_frozen_mean(ROOT)
            report["model_startup_and_posterior_reconstruction_seconds"] = time.perf_counter() - model_start
            report["model_identity"] = identity
            report["model_measurements"] = model_bench(model, requests, study.directory, health_check)
            report["network_measurements"], report["process_startup_shutdown_costs"] = asyncio.run(network_bench(study, identity, requests, health_check))
            report["telemetry_after"] = telemetry()
        report.update(status="COMPONENT_SERVING_MEASURED_NOT_FULL_E14", passed=True, latency_domains_complete={"inference_only": True, "feature_to_provisional_decision": True, "network_end_to_end": True, "selected_policy_guarded_feature_to_decision": False, "complete_agent_task": False})
    except Exception as error:
        report.update(status="FAILED_COMPONENT_SERVING", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/serving" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    if report["passed"]:
        study.ledger.update("E14", "CHECKPOINTED", artifacts=(artifact,), reason="Actual component measurements; selected policy/agent and remaining recovery paths still required")
        study.export_state()
    print(json.dumps({"status": report["status"], "artifact": str(artifact)}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
