from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_attempt import recorded_attempt
from aurora.agent_tasks import TaskHost, task_for


class AgentAttemptTests(unittest.TestCase):
    def test_resource_interruption_retains_executed_train_trace_not_unattempted_gold(self):
        class Generator:
            def __init__(self):
                self.measurements = []

            def __call__(self, task, trace, remaining):
                if trace:
                    raise RuntimeError("abstract resource stop")
                self.measurements.append({"completion_tokens": 12})
                return "<tool_call>" + json.dumps({"name": "query_metrics", "arguments": {"campaign": "alpha", "metric": "spent"}}) + "</tool_call>", 12
        with tempfile.TemporaryDirectory() as root:
            task = task_for("metric_lookup", 0)  # TRAIN only; no final workflow materialized
            host = TaskHost(task, Path(root), "abstract", fixture=True)
            result, diagnostic = recorded_attempt(task, host, Generator())
            self.assertEqual(diagnostic["type"], "RuntimeError")
            self.assertFalse(result["success"])
            self.assertEqual(len(result["trace"]), 1)
            self.assertEqual(result["generated_tokens"], 12)
            self.assertEqual(result["actual_commits"], [])
