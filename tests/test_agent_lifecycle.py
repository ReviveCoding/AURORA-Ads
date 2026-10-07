from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_lifecycle import training_checkpoint_transition


class AgentLifecycleTests(unittest.TestCase):
    def test_later_failed_transfer_does_not_erase_actual_development_screen(self):
        previous = {"execution_status": "EXECUTED", "scientific_outcome": "UNDERPOWERED", "artifacts": [{"path": "abstract_screen.json", "sha256": "a" * 64}]}
        for passed in (True, False):
            result = training_checkpoint_transition(previous, passed=passed, artifact=Path("abstract_transfer.json"))
            self.assertEqual(result["status"], "EXECUTED")
            self.assertEqual(result["science"], "UNDERPOWERED")
            self.assertEqual(result["artifacts"], (Path("abstract_screen.json"), Path("abstract_transfer.json")))

    def test_optimizer_checkpoint_is_not_complete_development_comparison(self):
        previous = {"execution_status": "CHECKPOINTED", "scientific_outcome": "NOT_RUN", "artifacts": []}
        self.assertEqual(training_checkpoint_transition(previous, passed=True, artifact=Path("abstract.json"))["status"], "CHECKPOINTED")
        self.assertEqual(training_checkpoint_transition(previous, passed=False, artifact=Path("abstract.json"))["status"], "FAILED")
