from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_qualification import inference_pointer_name, verify_inference_identity


class AgentQualificationTests(unittest.TestCase):
    def fixture(self):
        decode = {"prefix_tokens": 1798, "generation_tokens": 250, "resource_stop_reason": None, "forced_decode_stress_not_task_answer": True, "wall_seconds_cuda_synchronized": 1.}
        return {"status": "BOUNDED_DECODE_DUTY_QUALIFIED", "passed": True, "model": "Qwen3-4B", "recipe": "dpo", "training_seed": 73, "revision": "pinned", "corpus_sha256": "corpus", "trained_parent_sha256": "checkpoint73", "context_tokens": 2048, "final_tasks_loaded": 0, "semantic_task_scoring": False, "duty_pause_seconds": 30., "decodes": [decode] * 8}

    def verify(self, report):
        verify_inference_identity(report, model="Qwen3-4B", recipe="dpo", training_seed=73, revision="pinned", corpus_sha256="corpus", trained_parent_sha256="checkpoint73", pointer_duty=30.)

    def test_actual_seed_parent_duty_and_complete_execution_required(self):
        self.verify(self.fixture())
        for change in ({"training_seed": 41}, {"trained_parent_sha256": "checkpoint41"}, {"duty_pause_seconds": 5.}, {"decodes": [{}] * 7}, {"final_tasks_loaded": 1}, {"semantic_task_scoring": True}, {"status": "RUNNING"}):
            with self.assertRaises(ValueError):
                self.verify(self.fixture() | change)
        for change in ({"generation_tokens": 249}, {"resource_stop_reason": "temperature"}, {"prefix_tokens": 2048}):
            report = self.fixture()
            report["decodes"] = [report["decodes"][0] | change] * 8
            with self.assertRaises(ValueError):
                self.verify(report)

    def test_seed_specific_paths_and_invalid_seed(self):
        self.assertNotEqual(inference_pointer_name("Qwen3-4B", "sft", 41), inference_pointer_name("Qwen3-4B", "sft", 73))
        with self.assertRaises(ValueError):
            inference_pointer_name("Qwen3-4B", "sft", True)
