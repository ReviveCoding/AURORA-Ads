"""Latched sampled resource monitor; no CUDA work or device-setting mutation."""
from __future__ import annotations

import math
import subprocess
import threading
import time
from typing import Callable


def bounded_gpu_sample() -> dict:
    """Read device telemetry with a bounded query, no settings or CUDA work."""
    result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw,pstate", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True, timeout=3.)
    lines = result.stdout.strip().splitlines()
    if len(lines) != 1:
        raise ValueError("Exactly one declared local device must be observed")
    fields = [value.strip() for value in lines[0].split(",")]
    if len(fields) != 7:
        raise ValueError("Complete bounded GPU telemetry required")
    return {"at_unix": time.time(), "name": fields[0], "total_mib": float(fields[1]), "used_mib": float(fields[2]), "utilization_pct": float(fields[3]), "temperature_c": float(fields[4]), "power_w": float(fields[5]), "pstate": fields[6]}


class SampledResourceMonitor:
    """Background measurement within one heavy job, not another CUDA owner.

    A detected breach stays latched after cooling. The executing job checks the
    latch at every phase boundary and stops/checkpoints there; this cannot abort
    an already submitted CUDA kernel or prove continuous physical maxima.
    """
    def __init__(self, sampler: Callable[[], dict], *, device_target_c: float, reserve_mib: float = 2048., interval_seconds: float = 2.):
        if not all(math.isfinite(value) and value > 0 for value in (device_target_c, reserve_mib, interval_seconds)) or interval_seconds > 2 or reserve_mib < 2048:
            raise ValueError("Device-derived target, unchanged reserve and bounded cadence required")
        self.sampler = sampler
        self.target = device_target_c
        self.reserve = reserve_mib
        self.interval = interval_seconds
        self.samples: list[dict] = []
        self.failure: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def sample_now(self) -> None:
        try:
            sample = self.sampler()
            fields = ("temperature_c", "total_mib", "used_mib", "power_w", "at_unix")
            if any(not isinstance(sample.get(name), (int, float)) or not math.isfinite(sample[name]) for name in fields):
                raise ValueError("Nonfinite/incomplete resource telemetry")
            if sample["total_mib"] <= 0 or sample["used_mib"] < 0 or sample["power_w"] < 0:
                raise ValueError("Invalid resource telemetry")
            reason = None
            if sample["temperature_c"] >= self.target:
                reason = "Sampled device operating target reached; stop/checkpoint at next phase boundary"
            elif sample["total_mib"] - sample["used_mib"] < self.reserve:
                reason = "Sampled device VRAM reserve violated; no other applications/settings changed"
            with self._lock:
                self.samples.append(dict(sample))
                if reason is not None and self.failure is None:
                    self.failure = reason
        except Exception as error:
            with self._lock:
                if self.failure is None:
                    self.failure = f"Resource instrumentation failed: {type(error).__name__}: {str(error)[:200]}"

    def check(self) -> None:
        with self._lock:
            failure = self.failure
        if failure is not None:
            raise RuntimeError(failure)

    def snapshot(self) -> dict:
        with self._lock:
            return {"interval_seconds": self.interval, "device_reported_target_c": self.target, "reserve_mib": self.reserve, "latched_failure": self.failure, "samples": [dict(sample) for sample in self.samples], "interpretation": "Sampled peaks only; stops at phase boundaries, not an emergency kernel abort or universal temperature guarantee"}

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self.sample_now()

    def __enter__(self):
        if self._thread is not None:
            raise RuntimeError("Monitor cannot be restarted or clear a latched failure")
        self.sample_now()
        self.check()
        self._thread = threading.Thread(target=self._loop, name="aurora-owned-resource-sampling", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=6.)
            if self._thread.is_alive():
                with self._lock:
                    if self.failure is None:
                        self.failure = "Resource sampler did not stop within bounded6second join"
        if exc_type is None:
            self.check()
        return False
