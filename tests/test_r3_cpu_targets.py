import importlib.util
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r3_CPU_fixture", ROOT / "tools/r3_cpu_baselines.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class R3CPUTargetTests(unittest.TestCase):
    def test_pending_diagnostic_distinct_from_mature_baseline_and_unknown(self):
        data = {"valid_delay": np.array([True, True, True, False]),
                "mature": np.array([True, False, True, False]),
                "within_horizon_label": np.array([1., np.nan, 0., np.nan]),
                "event_bin": np.array([5, -1, -1, -1])}
        mask, target = MODULE.training_target(data, mature_only=True)
        np.testing.assert_array_equal(mask, [True, False, True, False])
        np.testing.assert_array_equal(target, [1, 0])
        mask, target = MODULE.training_target(data, mature_only=False)
        np.testing.assert_array_equal(mask, [True, True, True, False])
        np.testing.assert_array_equal(target, [1, 0, 0])
