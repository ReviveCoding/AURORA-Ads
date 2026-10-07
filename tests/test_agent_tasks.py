from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.agent_tasks import FAMILIES, FAMILY_GROUPS, TaskHost, gold_trace, task_for, assistant_call
from aurora.agent import parse_response, run_agent


class AgentTests(unittest.TestCase):
    def test_semantic_groups_are_split_owned_not_paraphrase_units(self):
        splits = {}
        for family, (split, _) in FAMILIES.items():
            group = FAMILY_GROUPS[family]
            splits.setdefault(group, set()).add(split)
        self.assertTrue(all(len(value) == 1 for value in splits.values()))
        self.assertEqual(sum(value == {"final"} for value in splits.values()), 9)

    def test_every_gold_workflow_executes_and_uses_at_most_eight_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            for family in FAMILIES:
                for number in range(5):
                    case = gold_trace(task_for(family, number), Path(directory), "gold", fixture=True)
                    self.assertFalse(any(record["response"].get("status") == "HOST_BLOCKED" for record in case["trace"]), (family, case))
                    self.assertLessEqual(len(case["trace"]), 8)
                    self.assertEqual(case["host_integrity"]["integrity"], "ok")

    def test_host_blocked_unsafe_proposal_is_not_a_wrong_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            task = task_for("proposal_execution_separation", 0)
            host = TaskHost(task, Path(directory), "bad", fixture=True)
            outputs = iter([assistant_call("commit_mock_action", {"campaign": "alpha", "snapshot_version": 0, "action": "NO_CHANGE", "prepared_id": "forged", "idempotency_key": "bad"}), '{"status":"completed","evidence_ids":[],"result":{}}'])
            report = run_agent(task, host, lambda task, trace, cap: (next(outputs), 10))
            self.assertEqual(report["unsafe_proposals"], 1)
            self.assertEqual(report["host_blocked_errors"], 1)
            self.assertEqual(report["wrong_committed_actions"], 0)

    def test_multiple_calls_and_extra_final_fields_are_rejected(self):
        for text in ('<tool_call>{"name":"x","arguments":{}}</tool_call><tool_call>{"name":"y","arguments":{}}</tool_call>', '{"status":"completed","evidence_ids":[],"result":{},"approval":true}'):
            with self.assertRaises(ValueError):
                parse_response(text)

    def test_expanded_gold_graphs_pass_distinct_executable_conditions(self):
        from copy import deepcopy
        import json
        from aurora.agent_taxonomy import NEW_WORKFLOWS
        with tempfile.TemporaryDirectory() as directory:
            for family in NEW_WORKFLOWS:
                for number in range(3):
                    task = task_for(family, number)
                    case = gold_trace(task, Path(directory), "teacher", fixture=True)
                    host = TaskHost(task, Path(directory), "replay", fixture=True)
                    def generate(task, trace, cap):
                        turn = len(trace)
                        if turn == len(case["trace"]):
                            status, result = host.final_expectation()
                            return json.dumps({"status": status, "result": result, "evidence_ids": [record["response"]["artifact_id"] for record in trace if "artifact_id" in record["response"]]}), 20
                        record = case["trace"][turn]
                        arguments = deepcopy(record["arguments"])
                        if record["name"] == "commit_mock_action":
                            arguments["prepared_id"] = next(prior["response"]["data"]["prepared_id"] for prior in reversed(trace) if prior["name"] == "prepare_action")
                        return assistant_call(record["name"], arguments), 20
                    result = run_agent(task, host, generate)
                    self.assertTrue(result["success"], (family, number, result))
                    self.assertEqual(result["unsafe_proposals"], 0, (family, result))
                    self.assertEqual(result["wrong_committed_actions"], 0)
