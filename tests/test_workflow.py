from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.workflow import Ledger
sys.path.insert(0, str(ROOT / "tools"))
from acquire_data import resolve_landing_html


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.registry = self.directory / "registry.json"
        self.registry.write_bytes((ROOT / "config/experiments.json").read_bytes())
        self.ledger = Ledger(self.registry, self.directory / "state.json")
        self.evidence = self.directory / "evidence.json"
        atomic_json(self.evidence, {"measured": "test fixture"})

    def tearDown(self):
        self.temp.cleanup()

    def test_dependencies_and_independent_tracks(self):
        self.assertEqual(self.ledger.ready(), ["E00"])
        with self.assertRaises(ValueError):
            self.ledger.update("E10", "RUNNING")
        self.ledger.update("E00", "EXECUTED", artifacts=(self.evidence,))
        self.ledger.update("E01", "BLOCKED_SOURCE", reason="Fixture: metadata unavailable")
        self.assertIn("E07", self.ledger.ready())
        self.assertNotIn("E16", self.ledger.ready())

    def test_immutable_evidence_and_hashes(self):
        first = self.ledger.update("E00", "EXECUTED", artifacts=(self.evidence,))
        event = Path(first["last_event"])
        original = digest(event)
        self.ledger.update("E00", "FAILED", reason="qualification invalidation fixture")
        self.assertEqual(digest(event), original)
        self.assertEqual(first["nodes"]["E00"]["artifacts"][0]["sha256"], digest(self.evidence))

    def test_interrupted_state_export_replays_immutable_intent(self):
        first = self.ledger.update("E00", "EXECUTED", artifacts=(self.evidence,))
        self.ledger.state.unlink()
        recovered = self.ledger.read()
        self.assertEqual(recovered, first)
        self.ledger.update("E01", "RUNNING")
        self.assertEqual(self.ledger.read()["generation"], 2)

    def test_lock_and_contract_change_fail_closed(self):
        self.ledger.update("E00", "RUNNING")
        lock = self.directory / "state.lock"
        lock.touch()
        with self.assertRaises(FileExistsError):
            self.ledger.update("E00", "FAILED")
        lock.unlink()
        self.registry.write_text("{}")
        with self.assertRaises(ValueError):
            self.ledger.read()

    def test_no_evidence_no_success(self):
        with self.assertRaises(ValueError):
            self.ledger.update("E00", "EXECUTED")
        with self.assertRaises(ValueError):
            self.ledger.update("E00", "BLOCKED_HARDWARE")
        with self.assertRaises(ValueError):
            self.ledger.update("E00", "PENDING", science="SUPPORTED")
        self.assertFalse(self.ledger.state.exists())

    def test_publisher_legacy_http_is_upgraded_only_to_same_host(self):
        spec = {"source_page": "https://ailab.criteo.com/", "landing_link_host": "go.criteo.net", "landing_link_text": "click here"}
        self.assertEqual(resolve_landing_html('<a href="http://go.criteo.net/data.tar.gz">click here</a>', spec), "https://go.criteo.net/data.tar.gz")
        with self.assertRaises(ValueError):
            resolve_landing_html('<a href="http://evil.example/data.tar.gz">click here</a>', spec)


if __name__ == "__main__":
    unittest.main()
