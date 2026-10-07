#!/usr/bin/env python3
"""Preserve and stop only the diagnosed owned CPU serving attempt."""
import json
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest


def main():
    directory = Path.home() / ".local/share/aurora-ads/runs/e14_explicit_CPU_component_serving_1790971439803282442"
    process = psutil.Process(316)
    if process.cwd() != str(ROOT) or "tools/serving_cpu_study.py" not in process.cmdline():
        raise ValueError("Original owned CPU driver identity differs")
    children = process.children(recursive=True)
    owned = [process] + children
    if any(p.cwd() != str(ROOT) for p in owned):
        raise ValueError("Unexpected unrelated descendant")
    report = {"status": "CPU_HTTP_ATTEMPT_STOPPED_IMPORT_STAT_STORM", "passed": False,
        "diagnosis": "httpcore1.0.9 current_async_library repeatedly imports absent sniffio; observed stat storm over sys.path via bounded intrusive strace; not a proven kernel deadlock",
        "intrusive_diagnostic_seconds": 5, "remaining_latency_not_valid_for_clean_isolation": True,
        "source": "Installed httpcore/_synchronization.py; sniffio spec None; anyio4.15.1 does not require sniffio",
        "protocol": json.loads((directory / "protocol_before_measurement.json").read_text()),
        "model_measurements": json.loads((directory / "model_measurements.json").read_text()),
        "model_identity": json.loads((directory / "model_requests_before_measurement.json").read_text()),
        "network_partial": json.loads((directory / "network_progress.json").read_text()),
        "resources": json.loads((directory / "resource_progress.json").read_text()),
        "owned_processes_before_stop": [{"pid": p.pid, "create_time": p.create_time(), "argv": p.cmdline()} for p in owned],
        "wall_seconds_observed": time.time() - process.create_time(), "pending_HTTP_outcomes": "UNKNOWN_NOT_SERIALIZED",
        "retained_files": {str(p): digest(p) for p in directory.glob("*.json")}, "code_sha256": digest(Path(__file__))}
    atomic_json(directory / "failed_attempt_before_stop.json", report)
    for p in reversed(owned):
        try:
            p.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owned, timeout=5)
    for p in alive:
        if p.create_time() != next(r["create_time"] for r in report["owned_processes_before_stop"] if r["pid"] == p.pid):
            raise ValueError("PID reused; do not kill")
        p.kill()
    _, alive = psutil.wait_procs(alive, timeout=5)
    report["remaining_owned_pids"] = [p.pid for p in alive if p.status() != psutil.STATUS_ZOMBIE]
    artifact = ROOT / "reports/serving" / (directory.name + "_FAILED.json")
    atomic_json(directory / "failed_attempt.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/serving/CPU_FAILED_ATTEMPT.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"artifact": str(artifact), "remaining_owned_pids": report["remaining_owned_pids"]}))


if __name__ == "__main__":
    main()
