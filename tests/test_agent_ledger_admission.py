from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_ledger_admission import read_agent_ledger, snapshot_agent_ledger, reconcile_saved_actions
from aurora.agent_tasks import TaskHost, task_for, gold_trace


class AgentLedgerAdmissionTests(unittest.TestCase):
    def test_json_tuple_normalization_cannot_hide_extra_commits_or_changed_gold(self):
        integrity = {"integrity": "ok", "audit_head": "a" * 64, "audit_events": 4}
        independent = {**integrity, "actual_application_commits": [["alpha", "NO_CHANGE"]]}
        result = {"host_integrity": integrity, "actual_commits": [("alpha", "NO_CHANGE")], "expected_commits": [["alpha", "NO_CHANGE"]]}
        reconcile_saved_actions(result, independent, [("alpha", "NO_CHANGE")])
        for key in ("actual_commits", "expected_commits"):
            corrupted = result | {key: [["alpha", "NO_CHANGE"], ["alpha", "NO_CHANGE"]]}
            with self.assertRaises(ValueError):
                reconcile_saved_actions(corrupted, independent, [("alpha", "NO_CHANGE")])

    def test_train_ledger_online_snapshot_has_exact_application_commit_pairs(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task = task_for("direct_authorized_workflow", 2)  # TRAIN oracle, not model/final evidence
            trace = gold_trace(task, root, "abstract", fixture=True)
            source = root / "state/agent_cases/abstract" / (task.task_id + ".sqlite")
            before = read_agent_ledger(source, "abstract:" + task.task_id, root)
            result = snapshot_agent_ledger(source, root / "evidence.sqlite", root)
            after = read_agent_ledger(Path(result["path"]), "abstract:" + task.task_id, root)
            self.assertEqual(before, after)
            self.assertEqual(before["actual_application_commits"], [["alpha", "NO_CHANGE"]])
            self.assertEqual(after["audit_head"], trace["host_integrity"]["audit_head"])

    def test_tampered_budget_not_admitted_as_zero_risk(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task = task_for("metric_lookup", 0)
            host = TaskHost(task, root, "abstract", fixture=True)
            read_agent_ledger(host.state.path, host.tenant, root)
            with sqlite3.connect(host.state.path) as connection:
                connection.execute("UPDATE campaign SET budget=budget+100,spent=1 WHERE tenant=? AND id='alpha'", (host.tenant,))
            with self.assertRaises(ValueError):
                read_agent_ledger(host.state.path, host.tenant, root)
