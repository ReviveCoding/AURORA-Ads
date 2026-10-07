from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_budget import completed_agent_wall_seconds


class AgentBudgetTests(unittest.TestCase):
    def write_fixture(self, root, name, wall, exit_code):
        path = root / ("execution_" + name + "_unit") / "execution.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"command": ["python", name + ".py"], "wall_seconds": wall, "status": "FAILED" if exit_code else "EXECUTED", "exit_code": exit_code}))
        return path

    def test_failed_references_and_preference_restart_are_charged_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_fixture(root, "agent_study", 1000., 2)
            self.write_fixture(root, "qualify_preference_restart", 414., 0)
            self.write_fixture(root, "agent_validation", 600., 0)
            self.write_fixture(root, "completion_audit", 1., 0)
            result = completed_agent_wall_seconds(root)
            self.assertEqual(result["completed_full_wall_seconds"], 2014.)
            self.assertEqual(result["command_count"], 3)

    def test_incomplete_or_mismatched_exports_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_fixture(root, "qualify_preference_restart", 10., 0)
            original = json.loads(path.read_text())
            for changes in ({"status": "RUNNING"}, {"wall_seconds": float("nan")}, {"command": ["python", "other.py"]}, {"exit_code": 2}):
                path.write_text(json.dumps(original | changes))
                with self.assertRaises(ValueError):
                    completed_agent_wall_seconds(root)
