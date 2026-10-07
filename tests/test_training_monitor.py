from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.training_monitor import SampledResourceMonitor


class TrainingMonitorTests(unittest.TestCase):
    def sample(self, **changes):
        return {"temperature_c": 78., "total_mib": 16376., "used_mib": 6000., "power_w": 20., "at_unix": 1000.} | changes

    def test_cooldown_cannot_erase_detected_breach(self):
        samples = iter([self.sample(), self.sample(temperature_c=87.), self.sample()])
        monitor = SampledResourceMonitor(lambda: next(samples), device_target_c=87.)
        monitor.sample_now()
        monitor.check()
        monitor.sample_now()
        monitor.sample_now()
        with self.assertRaises(RuntimeError):
            monitor.check()
        self.assertEqual(len(monitor.snapshot()["samples"]), 3)
        self.assertIsNotNone(monitor.snapshot()["latched_failure"])

    def test_reserve_and_instrumentation_failures_not_silently_qualified(self):
        for sample in (self.sample(used_mib=15000.), self.sample(power_w=float("nan")), {}):
            monitor = SampledResourceMonitor(lambda: sample, device_target_c=87.)
            monitor.sample_now()
            with self.assertRaises(RuntimeError):
                monitor.check()
        for kwargs in ({"reserve_mib": 1024.}, {"interval_seconds": 5.}, {"device_target_c": float("nan")}):
            with self.assertRaises(ValueError):
                SampledResourceMonitor(self.sample, **({"device_target_c": 87.} | kwargs))

    def test_context_stops_its_owned_thread_without_device_writes(self):
        monitor = SampledResourceMonitor(self.sample, device_target_c=87.)
        with monitor:
            monitor.check()
        self.assertFalse(monitor._thread.is_alive())
        self.assertEqual(len(monitor.snapshot()["samples"]), 1)
