from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.resources import cuda_lease, storage_admission
from aurora.artifacts import atomic_json
from aurora.workflow import Ledger


class ResourceTests(unittest.TestCase):
    def test_cuda_hold_uses_committed_event_not_stale_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            runtime = root / "owned"
            registry = root / "config/experiments.json"
            atomic_json(registry, {"nodes": [{"id": "x", "requires": []}]})
            atomic_json(runtime / "AURORA_RUNTIME.json", {"runtime_wsl": str(runtime), "repo_wsl": str(root)})
            ledger = Ledger(registry, runtime / "state/experiment_state.json")
            initial = ledger.read()
            ledger.update("x", "CHECKPOINTED", capabilities={"CURRENT_HEAVY_GPU_MONITOR_QUALIFIED": False})
            atomic_json(ledger.state, initial)
            with self.assertRaisesRegex(RuntimeError, "admission held"):
                with cuda_lease(runtime):
                    self.fail("Stale cache must not override committed monitor hold")
            self.assertFalse((runtime / "state/GPU_LEASE.lock").exists())
            ledger.state.unlink()  # disposable fixture cache only, events retained
            with self.assertRaisesRegex(RuntimeError, "admission held"):
                with cuda_lease(runtime):
                    self.fail("Missing cache must not override committed monitor hold")

    def test_latched_monitor_hold_precedes_cuda_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            (runtime / "state").mkdir()
            state = runtime / "state/experiment_state.json"
            state.write_text(json.dumps({"capabilities": {"GPU_QUALIFIED": True,
                "CURRENT_HEAVY_GPU_MONITOR_QUALIFIED": False}}))
            with self.assertRaisesRegex(RuntimeError, "admission held"):
                with cuda_lease(runtime):
                    self.fail("Historical PASS must not permit a currently held lease")
            self.assertFalse((runtime / "state/GPU_LEASE.lock").exists())
            state.write_text(json.dumps({"capabilities": {"CURRENT_HEAVY_GPU_MONITOR_QUALIFIED": True}}))
            with cuda_lease(runtime):
                self.assertTrue((runtime / "state/GPU_LEASE.lock").exists())

    def test_storage_ownership_footprint_and_reserve_are_admitted_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            runtime = root / "owned"
            runtime.mkdir()
            marker = runtime / "AURORA_RUNTIME.json"
            marker.write_text(json.dumps({"runtime_wsl": str(runtime), "repo_wsl": str(root)}))
            contract = {"backing_disk_min_free_gib": 0, "storage_growth_ceiling_gib": 1}
            result = storage_admission(runtime, root, expected_growth_bytes=1024, contract=contract)
            self.assertGreater(result["runtime_apparent_bytes"], 0)
            self.assertEqual(result["expected_growth_bytes"], 1024)
            with self.assertRaisesRegex(ValueError, "ceiling/reserve"):
                storage_admission(runtime, root, expected_growth_bytes=2 * 1024**3, contract=contract)
            with self.assertRaisesRegex(ValueError, "ceiling/reserve"):
                storage_admission(runtime, root, expected_growth_bytes=1, contract=contract | {"backing_disk_min_free_gib": 10**9})
            with self.assertRaisesRegex(ValueError, "Owned runtime"):
                storage_admission(runtime, runtime, expected_growth_bytes=0, contract=contract)
