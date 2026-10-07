from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_evaluation import AgentCase
from aurora.agent_result_admission import admit_saved_result


class AgentResultAdmissionTests(unittest.TestCase):
    def fixture(self):
        case = AgentCase("final_abstract_2000", "abstract", "abstract_group")
        task = {"task_id": case.identity, "family": case.workflow, "split": "final", "state": "abstract_unit_fixture_not_a_final_prompt"}
        record = {"task": dict(task), "semantic_group": case.semantic_group, "trace": [], "tool_rounds": 0, "generated_tokens": 10, "success": False, "failure": "parse error retained", "answer_ok": False, "evidence_ok": False, "workflow_ok": False, "host_integrity": {"integrity": "ok"}, "expected_commits": [], "actual_commits": [], "unsafe_proposals": 0, "host_blocked_errors": 0, "wrong_committed_actions": 0}
        return record, case, task

    def test_failed_task_preserved_and_counter_identity_refusals(self):
        record, case, task = self.fixture()
        outcome, _ = admit_saved_result(record, case, task, 41)
        self.assertFalse(outcome.success)
        for change in ({"task": task | {"state": "changed"}}, {"semantic_group": "wrong_group"}, {"host_blocked_errors": 1}, {"generated_tokens": 2049}, {"tool_rounds": 1}, {"wrong_committed_actions": 1}, {"success": True}):
            with self.assertRaises(ValueError):
                admit_saved_result(record | change, case, task, 41)

    def test_extra_expected_commits_visible_without_changing_frozen_counter(self):
        record, case, task = self.fixture()
        record.update(expected_commits=[["alpha", "NO_CHANGE"]], actual_commits=[["alpha", "NO_CHANGE"], ["alpha", "NO_CHANGE"]])
        outcome, diagnostic = admit_saved_result(record, case, task, 41)
        self.assertEqual(outcome.wrong_committed_actions, 0)
        self.assertEqual(diagnostic["excess_applied_commits"], 1)
        self.assertFalse(outcome.success)
