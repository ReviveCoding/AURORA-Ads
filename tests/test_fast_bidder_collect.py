from __future__ import annotations

import sys
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from fast_bidder_collect import observed_archive_payload, collect_world


class FastBidderCollectTests(unittest.TestCase):
    def test_evaluator_fields_never_enter_learner_payload(self):
        row = SimpleNamespace(context=np.zeros((1, 7)), submitted_bid=np.array([.25]), eligible=np.array([True]), won=np.array([False]), payment=np.array([0.]), observed_gross=np.array([0.]), executed_bid_probability=np.array([.125]), origin_ids=("fixture_only",), market=np.array([99.]), organic_value=np.array([200.]), utility=99.)
        data = observed_archive_payload(row)
        self.assertEqual(set(data), {"context", "submitted_bid", "eligible", "won", "payment", "observed_gross", "executed_bid_probability", "origin_id"})
        self.assertEqual(data["origin_id"].tolist(), ["fixture_only"])
        self.assertNotIn("utility", data)

    def test_no_fabricated_logging_probability(self):
        row = SimpleNamespace(context=np.zeros((0, 7)), submitted_bid=np.empty(0), eligible=np.empty(0, dtype=bool), won=np.empty(0, dtype=bool), payment=np.empty(0), observed_gross=np.empty(0), executed_bid_probability=None, origin_ids=())
        self.assertIsNone(observed_archive_payload(row)["executed_bid_probability"])

    def test_partial_world_is_not_overwritten_on_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "train_0"
            destination.mkdir()
            evidence = destination / "observed_arrays.npz"
            evidence.write_bytes(b"partial fixture evidence")
            with self.assertRaisesRegex(ValueError, "orphan overwrite"):
                collect_world((0, "train", "second_price", temporary, "a" * 64))
            self.assertEqual(evidence.read_bytes(), b"partial fixture evidence")

    def test_symlink_world_rejected_before_any_collection(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "train_0"
            target = Path(temporary) / "other_fixture"
            target.mkdir()
            destination.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                collect_world((0, "train", "second_price", temporary, "a" * 64))
            self.assertEqual(list(target.iterdir()), [])
