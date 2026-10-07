"""One CUDA owner; resource checks are per workload, not a global safety assertion."""
from __future__ import annotations

import fcntl
import json
import math
import os
import subprocess
import shutil
import time
from contextlib import contextmanager
from pathlib import Path


def telemetry() -> dict:
    command = ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw,pstate", "--format=csv,noheader,nounits"]
    process = subprocess.run(command, text=True, capture_output=True, check=True)
    fields = [value.strip() for value in process.stdout.strip().split(",")]
    return {"at_unix": time.time(), "name": fields[0], "total_mib": float(fields[1]), "used_mib": float(fields[2]), "utilization_pct": float(fields[3]), "temperature_c": float(fields[4]), "power_w": float(fields[5]), "pstate": fields[6]}


@contextmanager
def cuda_lease(runtime: Path):
    # A historical bounded GPU PASS cannot override a later latched admission
    # failure. Enforce the current hold before any owned CUDA lease is acquired.
    state_path = runtime / "state/experiment_state.json"
    marker_path = runtime / "AURORA_RUNTIME.json"
    if marker_path.exists():
        from .workflow import Ledger
        marker = json.loads(marker_path.read_text())
        if marker["runtime_wsl"] != str(runtime.resolve()):
            raise ValueError("CUDA runtime ownership mismatch")
        # Immutable event intent precedes a stale or missing cache file after
        # interrupted commits. Use the same canonical precedence for admission.
        state = Ledger(Path(marker["repo_wsl"]) / "config/experiments.json", state_path).read()
    else:
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if state.get("capabilities", {}).get("CURRENT_HEAVY_GPU_MONITOR_QUALIFIED") is False:
        raise RuntimeError("Current heavy CUDA admission held: under-load monitor qualification unavailable")
    path = runtime / "state/GPU_LEASE.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        stream.seek(0)
        stream.truncate()
        json.dump({"pid": os.getpid(), "started_at_unix": time.time()}, stream)
        stream.flush()
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def check_gpu_room(planned_gib: float, headroom_gib: float = 2) -> dict:
    value = telemetry()
    if planned_gib > 12 or value["total_mib"] - value["used_mib"] < (planned_gib + headroom_gib) * 1024:
        raise ValueError("Insufficient current VRAM or planned ceiling exceeded")
    processes = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"], text=True, capture_output=True, check=True).stdout
    if any(name in processes.lower() for name in ("python", "vllm", "ollama", "trainer", "xgboost")):
        raise ValueError("Another possible heavy CUDA owner is active")
    return value


def storage_admission(runtime: Path, root: Path, *, expected_growth_bytes: int, contract: dict) -> dict:
    """Conservative total owned footprint and both filesystem reserves.

    The original preparation marker has no trustworthy storage baseline, so
    the entire current owned footprint counts against the growth ceiling.
    No data, caches, old failures or unrelated applications are removed.
    """
    marker = json.loads((runtime / "AURORA_RUNTIME.json").read_text())
    if marker["runtime_wsl"] != str(runtime.resolve()) or marker["repo_wsl"] != str(root.resolve()) or expected_growth_bytes < 0:
        raise ValueError("Owned runtime, canonical source and bounded growth required")
    reserve = contract["backing_disk_min_free_gib"] * 1024**3
    ceiling = contract["storage_growth_ceiling_gib"] * 1024**3
    if not all(math.isfinite(value) and value >= 0 for value in (reserve, ceiling, expected_growth_bytes)):
        raise ValueError("Finite nonnegative storage contract required")
    footprint = int(subprocess.run(["du", "-sb", "--", str(runtime)], capture_output=True, text=True, check=True).stdout.split()[0])
    free_ext4, free_backing = shutil.disk_usage(runtime).free, shutil.disk_usage(root).free
    if footprint + expected_growth_bytes > ceiling or min(free_ext4, free_backing) < reserve + expected_growth_bytes:
        raise ValueError("Declared storage ceiling/reserve cannot admit expected growth; no silent expansion")
    return {"runtime_apparent_bytes": footprint, "expected_growth_bytes": expected_growth_bytes, "ceiling_bytes": ceiling, "reserve_bytes": reserve, "ext4_free_bytes": free_ext4, "backing_free_bytes": free_backing, "baseline_disposition": "Entire current footprint counted conservatively"}
