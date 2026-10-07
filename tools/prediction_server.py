#!/usr/bin/env python3
"""Loopback-only read-only CPU surrogate service; no campaign mutation APIs."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.serving import BackendEnvelopeLost, BackendResourceExhausted, BoundedPredictor, create_app
from aurora.serving_models import load_frozen_mean
from aurora.resources import check_gpu_room, cuda_lease, telemetry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--queue-capacity", type=int, default=16)
    parser.add_argument("--fixture-backend-delay-seconds", type=float, default=0.)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--lease-owner-pid", type=int)
    parser.add_argument("--fixture-gpu-oom-once", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not 1 <= args.queue_capacity <= 64 or not 0 <= args.fixture_backend_delay_seconds <= .1:
        raise ValueError("Bounded local-only serving profile required")
    import numpy as np
    import torch
    import uvicorn
    if args.fixture_gpu_oom_once and args.device != "cuda":
        raise ValueError("GPU allocation OOM fixture cannot be relabeled CPU execution")
    runtime = Path.home() / ".local/share/aurora-ads"
    guidance = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())
    with ExitStack() as stack:
        if args.device == "cuda":
            if args.lease_owner_pid is None:
                check_gpu_room(4)
                stack.enter_context(cuda_lease(runtime))
            else:
                import fcntl
                lease_path = runtime / "state/GPU_LEASE.lock"
                owner = json.loads(lease_path.read_text())
                if owner["pid"] != args.lease_owner_pid:
                    raise ValueError("Server is not a child of the current benchmark lease owner")
                os.kill(args.lease_owner_pid, 0)
                # The PID record alone is insufficient: prove the parent's
                # serialization lock is actually held. Never bypass an idle lock.
                with lease_path.open("r+") as lock:
                    try:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        pass
                    else:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
                        raise ValueError("Benchmark owner is not holding the CUDA lease")
            torch.cuda.set_per_process_memory_fraction(4 * 1024**3 / torch.cuda.get_device_properties(0).total_memory)
        model, identity, _ = load_frozen_mean(ROOT)
        model.to(args.device)
        health_at = 0.
        health_failure = None
        first = True
        def infer(values):
            nonlocal health_at, health_failure, first
            if health_failure is not None:
                raise BackendEnvelopeLost(health_failure)
            if time.perf_counter() - health_at >= 2:
                current = telemetry()  # identical observation cadence on CPU/GPU
                health_at = time.perf_counter()
                if args.device == "cuda" and (current["temperature_c"] >= guidance["device_reported_target_c"] or current["total_mib"] - current["used_mib"] < 2048):
                    health_failure = "GPU resource envelope unavailable; no driver/power/application changes"
                    print(json.dumps({"status": "RESOURCE_ENVELOPE_LOST", "telemetry": current}), file=sys.stderr, flush=True)
                    raise BackendEnvelopeLost(health_failure)
            try:
                if first and args.fixture_gpu_oom_once:
                    first = False
                    # Allocator-limited OOM:64MiB allowance,128MiB request.
                    # This does not attempt to fill physical device VRAM.
                    torch.cuda.set_per_process_memory_fraction(64 * 1024**2 / torch.cuda.get_device_properties(0).total_memory)
                    try:
                        torch.empty(128 * 1024**2 // 4, device="cuda", dtype=torch.float32)
                        raise AssertionError("Expected allocator OOM did not occur")
                    finally:
                        torch.cuda.set_per_process_memory_fraction(4 * 1024**3 / torch.cuda.get_device_properties(0).total_memory)
                        torch.cuda.empty_cache()
                with torch.inference_mode():
                    return model(model.encode(np.asarray(values)[None])).squeeze(0).tolist()
            except torch.cuda.OutOfMemoryError as error:
                raise BackendResourceExhausted("Actual allocator-limited CUDA OOM; not full-device exhaustion") from error
        async def backend(values):
            if args.fixture_backend_delay_seconds:
                await asyncio.sleep(args.fixture_backend_delay_seconds)
            return await asyncio.to_thread(infer, values)
        service = BoundedPredictor(identity["model_sha256"], backend, capacity=args.queue_capacity)
        uvicorn.run(create_app(service), host="127.0.0.1", port=args.port, log_level="warning", access_log=False, workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
