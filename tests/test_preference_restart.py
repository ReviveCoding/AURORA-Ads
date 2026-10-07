from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from qualify_preference_restart import validate_replay_boundary


class PreferenceRestartTests(unittest.TestCase):
    def fixture(self, objective="dpo"):
        source = {"passed": True, "stage": "train", "objective": objective, "seed": 41, "examples": 2, "corpus_sha256": "corpus", "completion_projection": "full_attended_context_suffix_L_plus_1_v1", "parameters": {"preference_pairs_cap": 2, "accumulation": 16, "beta": .1}, "same_sft_parent": {"weights_sha256": "sft", "checkpoint": "sft_checkpoint"}}
        state = {"objective": objective, "seed": 41, "corpus_sha256": "corpus", "next_position": 2, "order": [1, 0]}
        reference = {"objective": objective, "normalization": "completion mean" if objective == "ipo" else "completion sum", "preference_sha256": "preferences", "adapter_sha256": "sft", "same_sft_checkpoint": "sft_checkpoint", "values": [[-1., -2.], [-3., -4.]]}
        return source, state, reference

    def test_same_actual_parent_objective_sampler_and_reference(self):
        for objective in ("dpo", "ipo"):
            self.assertEqual(validate_replay_boundary(*self.fixture(objective), "corpus", "preferences"), 1)
        for change in ({"passed": False}, {"stage": "qualify"}, {"examples": 1}, {"completion_projection": "unknown"}):
            source, state, reference = self.fixture()
            with self.assertRaises(ValueError):
                validate_replay_boundary(source | change, state, reference, "corpus", "preferences")

    def test_wrong_normalization_missing_reference_or_advanced_state_refused(self):
        for change in ({"normalization": "completion mean"}, {"adapter_sha256": "different_sft"}, {"values": [[-1., -2.]]}, {"values": [[float("nan"), -2.], [-3., -4.]]}):
            source, state, reference = self.fixture()
            with self.assertRaises(ValueError):
                validate_replay_boundary(source, state, reference | change, "corpus", "preferences")
        source, state, reference = self.fixture()
        with self.assertRaises(ValueError):
            validate_replay_boundary(source, state | {"next_position": 3}, reference, "corpus", "preferences")
