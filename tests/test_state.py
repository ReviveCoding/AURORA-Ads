from __future__ import annotations

import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.state import Action, ActionRequest, Conflict, StateHost, reserve_units


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.time = 1000.
        self.path = Path(self.temp.name) / "state.sqlite"
        self.host = StateHost(self.path, clock=lambda: self.time, fixture=True)
        self.host.create_campaign("tenant", "campaign", 100)
        self.request = ActionRequest("tenant", "campaign", "caller", 0, Action.NO_CHANGE, 80, "a" * 64)

    def tearDown(self):
        self.temp.cleanup()

    def approved(self, request=None):
        request = request or self.request
        prepared = self.host.prepare(request)
        token = self.host.issue_mock_authorization(prepared, request.tenant, request.caller)
        return prepared, token

    def test_concurrent_retry_and_restart_do_not_double_spend(self):
        prepared, token = self.approved()
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(lambda _: self.host.commit(prepared, self.request, "retry", token), range(8)))
        self.assertTrue(all(row == rows[0] for row in rows))
        self.assertEqual(self.host.snapshot("tenant", "campaign")["reserved"], 80)
        restarted = StateHost(self.path, clock=lambda: self.time, fixture=True)
        self.assertEqual(restarted.commit(prepared, self.request, "retry", token), rows[0])
        restarted.settle("tenant", "caller", "retry", 51)
        restarted.settle("tenant", "caller", "retry", 51)
        snapshot = restarted.snapshot("tenant", "campaign")
        self.assertEqual((snapshot["spent"], snapshot["reserved"]), (51, 0))
        self.assertEqual(restarted.verify()["integrity"], "ok")
        with self.assertRaises(Conflict):
            restarted.settle("tenant", "caller", "retry", 52)

    def test_forged_approval_payload_and_tenant_fail(self):
        prepared, token = self.approved()
        with self.assertRaises(Conflict):
            self.host.commit(prepared, self.request, "key", "approved=true")
        with self.assertRaises(Conflict):
            self.host.commit(prepared, replace(self.request, max_spend_units=79), "key", token)
        with self.assertRaises(ValueError):
            self.host.prepare(replace(self.request, tenant="other"))
        self.host.verify()

    def test_stale_two_prepares_and_insufficient_budget(self):
        first, first_token = self.approved()
        second, second_token = self.approved()
        self.host.commit(first, self.request, "first", first_token)
        with self.assertRaises(Conflict):
            self.host.commit(second, self.request, "second", second_token)
        with self.assertRaises(Conflict):
            self.host.prepare(replace(self.request, version=1, max_spend_units=21))

    def test_expiry_does_not_release_unreconciled_spend(self):
        prepared, token = self.approved()
        self.host.commit(prepared, self.request, "key", token)
        self.time += 1000
        self.assertEqual(self.host.snapshot("tenant", "campaign")["reserved"], 80)
        self.host.settle("tenant", "caller", "key", 70)
        self.assertEqual(self.host.snapshot("tenant", "campaign")["spent"], 70)
        self.host.verify()

    def test_expired_prepare_and_duplicate_changed_payload(self):
        prepared, token = self.approved()
        self.time += 901
        with self.assertRaises(Conflict):
            self.host.commit(prepared, self.request, "key", token)
        self.time = 1000
        self.host.commit(prepared, self.request, "key", token)
        with self.assertRaises(Conflict):
            self.host.commit(prepared, replace(self.request, action=Action.PACE_DOWN), "key", token)

    def test_conservative_quantization_and_invalid_types(self):
        self.assertEqual(reserve_units(.00001), 1)
        self.assertEqual(reserve_units(.00011), 2)
        for value in (-1., float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                reserve_units(value)
        with self.assertRaises(ValueError):
            replace(self.request, max_spend_units=True)
