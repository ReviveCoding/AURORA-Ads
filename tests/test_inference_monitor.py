import unittest
import json
import tempfile
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aurora.inference_monitor import DecodeResourceMonitor


class DecodeResourceMonitorTest(unittest.TestCase):
    def test_monitor_query_timeouts_latch_without_relaxing_deadline(self):
        calls = []
        def failed_query():
            calls.append(1)
            raise subprocess.TimeoutExpired(["nvidia-smi"], 3.)
        monitor = DecodeResourceMonitor(failed_query)
        self.assertTrue(monitor())
        self.assertIn("TimeoutExpired", monitor.failure)
        self.assertTrue(monitor())
        self.assertEqual(len(calls), 1)

    def test_cadence_and_latched_stop(self):
        now = [0.]
        calls = []
        def health():
            calls.append(now[0])
            if now[0] >= 2:
                raise RuntimeError("fixture: reserve lost")
        monitor = DecodeResourceMonitor(health, clock=lambda: now[0])
        self.assertFalse(monitor())
        now[0] = 1.
        self.assertFalse(monitor())
        now[0] = 2.
        self.assertTrue(monitor())
        self.assertEqual(monitor.failure, "fixture: reserve lost")
        now[0] = 0.
        self.assertTrue(monitor())
        self.assertEqual(calls, [0., 2.])

    def test_programming_errors_are_not_silently_resource_stops(self):
        def invalid():
            raise ValueError("invalid health implementation")
        with self.assertRaises(ValueError):
            DecodeResourceMonitor(invalid)()
        with self.assertRaises(ValueError):
            DecodeResourceMonitor(lambda: None, cadence_seconds=0)
        with self.assertRaises(ValueError):
            DecodeResourceMonitor(lambda: None, cadence_seconds=float("nan"))

    def test_partial_decode_is_persisted_before_resource_failure(self):
        import torch
        from aurora.agent_inference import LocalGenerator
        class Model:
            config = SimpleNamespace(use_cache=False)
            def parameters(self):
                return iter([torch.nn.Parameter(torch.zeros(1))])
            def eval(self):
                pass
            def gradient_checkpointing_disable(self):
                pass
            def generate(self, input_ids, stopping_criteria, **kwargs):
                self.stopped = stopping_criteria(input_ids, None).item()
                return torch.cat([input_ids, torch.tensor([[3, 4]])], dim=1)
        calls = []
        def health():
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("fixture: sampled target reached")
        model = Model()
        tokenizer = SimpleNamespace(pad_token_id=0, eos_token_id=2,
                                    decode=lambda ids, **kwargs: "partial raw fixture")
        with tempfile.TemporaryDirectory() as temporary:
            generator = LocalGenerator(model, tokenizer, records=Path(temporary),
                                       before_generation=health,
                                       after_generation=lambda: self.fail("Do not erase the latched stop"))
            with patch("aurora.agent_inference.encode_prefix", return_value=[1, 2]), patch("torch.cuda.synchronize"):
                with self.assertRaisesRegex(RuntimeError, "sampled target reached"):
                    generator(SimpleNamespace(task_id="CPU-only-fixture"), [], 10)
            self.assertTrue(model.stopped)
            record = json.loads(next(Path(temporary).glob("*.json")).read_text())
            self.assertEqual(record["raw_completion"], "partial raw fixture")
            self.assertEqual(record["sampled_resource_stop_reason"], "fixture: sampled target reached")
            self.assertEqual(len(generator.measurements), 1)


if __name__ == "__main__":
    unittest.main()
