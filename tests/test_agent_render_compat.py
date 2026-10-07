from __future__ import annotations

import sys
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent import public_memory, encode_prefix
from aurora.agent_render_compat import compatible_trace, encode_prefix_compatible
from aurora.agent_tasks import task_for
from aurora.simulator import Snapshot


class AgentRenderCompatTests(unittest.TestCase):
    def test_actual_snapshot_names_alias_losslessly_without_mutating_host_trace(self):
        public = asdict(Snapshot(672, 0, 10000, 0, 0, 2., 3, 2., 0, initial_budget_units=10000))
        trace = [{"name": "get_campaign_snapshot", "arguments": {"campaign": "alpha"}, "response": {"status": "OK", "artifact_id": "a" * 64, "evidence_domain": "UNIT_FIXTURE_ONLY", "unit": "fixture", "horizon": "fixture", "permitted_use": "CPU format fixture; not model outcome", "snapshot_version": 0, "data": {"public_outcome_state": public}}}]
        with self.assertRaises(KeyError):
            public_memory(trace)  # Preserve evidence of the original formatting mismatch
        adapted = compatible_trace(trace)
        memory = public_memory(adapted)
        rendered = memory["latest_by_campaign_and_tool"]["alpha:get_campaign_snapshot"]["data"]["public_outcome_state"]
        self.assertEqual(rendered["matured_cohorts"], public["matured_cohort_count"])
        self.assertEqual(rendered["matured_value"], public["matured_exposure_value"])
        self.assertNotIn("matured_cohorts", trace[0]["response"]["data"]["public_outcome_state"])
        adapted[0]["response"]["data"]["public_outcome_state"]["matured_value"] = 999.
        with self.assertRaises(ValueError):
            compatible_trace(adapted)

    def test_existing_train_render_and_complete_tools_are_identical(self):
        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                return messages, kwargs
        task = task_for("metric_lookup", 0)  # TRAIN only
        tokenizer = Tokenizer()
        self.assertEqual(encode_prefix(tokenizer, task, []), encode_prefix_compatible(tokenizer, task, []))
