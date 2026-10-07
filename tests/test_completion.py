from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.completion import completion_matrix


class CompletionTests(unittest.TestCase):
    def fixture(self):
        nodes = [{"id": key, "name": key, "evidence_domain": "fixture", "requires": [], "capabilities": []} for key in ("A", "E16")]
        state = {"generation": 1, "capabilities": {}, "nodes": {key: {"execution_status": "PENDING", "scientific_outcome": "NOT_RUN", "artifacts": [], "reason": ""} for key in ("A", "E16")}}
        return nodes, state

    def test_negative_valid_result_and_final_reporting_required(self):
        nodes, state = self.fixture()
        state["nodes"]["A"].update(execution_status="EXECUTED", scientific_outcome="NOT_ESTABLISHED", artifacts=[{"path": "fixture", "sha256": "fixture"}])
        self.assertFalse(completion_matrix(nodes, state)["overall_project_complete"])
        state["nodes"]["E16"].update(execution_status="EXECUTED", artifacts=[{"path": "report", "sha256": "fixture"}])
        result = completion_matrix(nodes, state)
        self.assertTrue(result["overall_project_complete"])
        self.assertEqual(result["supported_scientific_nodes"], [])

    def test_failure_is_not_genuine_terminal_blocker(self):
        nodes, state = self.fixture()
        state["nodes"]["A"]["execution_status"] = "FAILED"
        self.assertEqual(completion_matrix(nodes, state)["unfinished_or_repair_required"], ["A"])
        state["nodes"]["A"].update(execution_status="BLOCKED_SOURCE", scientific_outcome="BLOCKED_SOURCE", reason="Official source exceeds unchanged cap; new authorization needed")
        self.assertEqual(completion_matrix(nodes, state)["unfinished_or_repair_required"], [])

    def test_executed_requires_evidence_and_unexecuted_cannot_support(self):
        nodes, state = self.fixture()
        state["nodes"]["A"]["execution_status"] = "EXECUTED"
        with self.assertRaises(ValueError):
            completion_matrix(nodes, state)
        state["nodes"]["A"].update(execution_status="PENDING", scientific_outcome="SUPPORTED")
        with self.assertRaises(ValueError):
            completion_matrix(nodes, state)
