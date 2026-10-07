from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.state import StateHost
from aurora.tools import CATALOG, HostContext, ToolHost


class ToolTests(unittest.TestCase):
    def test_registered_model_requires_fresh_version_and_budget_bound_public_state(self):
        from dataclasses import asdict
        from aurora.simulator import Snapshot
        import numpy as np
        class Model:
            def estimates(self, snapshot):
                return np.array([1, 2, 3, 4, 5, 6.]), np.zeros(6), np.ones(6), np.full(6, 4), np.zeros(25)

        import tempfile
        from aurora.state import StateHost, Conflict
        from aurora.tools import ToolHost, HostContext
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = StateHost(root / "state.sqlite", fixture=True)
            state.create_campaign("tenant", "campaign", 0)
            host = ToolHost(state, HostContext("tenant", "caller"), root / "artifacts", models=Model(), model_artifact="fixture-not-empirical")
            self.assertEqual(host.call("recommend_action", {"campaign": "campaign"}).status, "MODEL_STATE_UNAVAILABLE")
            observation = Snapshot(0, 0, 0, 0, 0, 0, 0, 0, 0, initial_budget_units=0)
            state.publish_observation("tenant", "campaign", 0, asdict(observation))
            result = host.call("recommend_action", {"campaign": "campaign"})
            self.assertEqual(result.data["action"], "NO_CHANGE")
            self.assertEqual(result.evidence_domain, "S1_OBSERVED_MATURED")
            with self.assertRaises(Conflict):
                state.publish_observation("tenant", "campaign", 1, asdict(observation))
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        directory = Path(self.temp.name)
        self.state = StateHost(directory / "state.sqlite", fixture=True)
        self.state.create_campaign("tenant", "campaign", 1000)
        self.tools = ToolHost(self.state, HostContext("tenant", "caller", True), directory / "evidence")

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_commit_report_replay(self):
        args = {"campaign": "campaign", "snapshot_version": 0, "action": "PACE_DOWN"}
        prepared = self.tools.call("prepare_action", args)
        commit = args | {"prepared_id": prepared.data["prepared_id"], "idempotency_key": "key"}
        self.tools.call("commit_mock_action", commit)
        self.tools.call("commit_mock_action", commit)
        result = self.tools.call("query_metrics", {"campaign": "campaign", "metric": "spent"})
        self.assertEqual(result.data["value_units_1e4"], 100)
        self.assertEqual(result.evidence_domain, "S1_MOCK")
        self.assertEqual(self.tools.call("build_measurement_report", {"campaign": "campaign"}).data["integrity"]["integrity"], "ok")

    def test_forged_approval_tenant_sql_and_unavailable_models(self):
        for extra in ({"approved": True}, {"tenant": "other"}, {"sql": "DROP TABLE campaign"}, {"max_spend_units": 10000}):
            with self.assertRaises(ValidationError):
                self.tools.call("prepare_action", {"campaign": "campaign", "snapshot_version": 0, "action": "NO_CHANGE"} | extra)
        self.assertEqual(len(CATALOG), 9)
        for name in ("estimate_outcomes", "simulate_policy", "recommend_action"):
            result = self.tools.call(name, {"campaign": "campaign"})
            self.assertEqual(result.status, "MODEL_NOT_QUALIFIED")
            self.assertIsNone(result.data["estimate"])

    def test_no_host_grant_no_commit(self):
        unapproved = ToolHost(self.state, HostContext("tenant", "caller", False), Path(self.temp.name) / "evidence")
        args = {"campaign": "campaign", "snapshot_version": 0, "action": "NO_CHANGE"}
        prepared = unapproved.call("prepare_action", args)
        with self.assertRaises(ValueError):
            unapproved.call("commit_mock_action", args | {"prepared_id": prepared.data["prepared_id"], "idempotency_key": "key"})
