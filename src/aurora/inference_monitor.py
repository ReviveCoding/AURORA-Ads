"""Sampled resource stop during token generation; never a continuous peak claim."""
from __future__ import annotations

import time
import math
import subprocess
from collections.abc import Callable


class DecodeResourceMonitor:
    def __init__(self, health: Callable[[], None], *, cadence_seconds: float = 2., clock=time.perf_counter):
        if not math.isfinite(cadence_seconds) or cadence_seconds <= 0:
            raise ValueError("Positive monitoring cadence required")
        self.health = health
        self.cadence = cadence_seconds
        self.clock = clock
        self.last: float | None = None
        self.failure: str | None = None

    def __call__(self, input_ids=None, scores=None, **kwargs) -> bool:
        if self.failure is not None:
            return True
        current = self.clock()
        if self.last is None or current - self.last >= self.cadence:
            self.last = current
            try:
                self.health()
            except RuntimeError as error:
                self.failure = str(error)
                return True
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
                self.failure = f"Resource instrumentation failed: {type(error).__name__}: {str(error)}"
                return True
        return False
