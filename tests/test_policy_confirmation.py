import unittest
import tempfile
from pathlib import Path

import numpy as np

from aurora.artifacts import atomic_json, digest
from aurora.policy_confirmation import PILOT_INPUT_BINDINGS, paired_analysis, verified_episode_record, verified_pilot_record, verify_pilot_inputs, world_roster


class PolicyConfirmationTest(unittest.TestCase):
    def test_pilot_freeze_model_environment_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root, protocol = Path(directory), {}
            for key, relative in PILOT_INPUT_BINDINGS.items():
                path = root / relative
                atomic_json(path, {"identity": key})
                protocol[key] = digest(path)
            verify_pilot_inputs(root, protocol)
            atomic_json(root / PILOT_INPUT_BINDINGS["incident_detector_pointer_sha256"], {"identity": "changed"})
            with self.assertRaises(ValueError):
                verify_pilot_inputs(root, protocol)

    def test_resume_receipt_and_episode_integrity(self):
        world = world_roster("pilot", 20)[0]
        record = {"world": world, "arm": "locked_MSCP", "protocol_sha256": "abc",
                  "excluded_from_confirmation": True, "evaluation": {
                      "world_id": world["world_id"], "family": world["family"], "stage": "pilot",
                      "final_pending_exposures": 0, "snapshot_reward_updates_before_day7": 0, "utility": -.5}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "world.json"
            atomic_json(path, record)
            with self.assertRaises(ValueError):
                verified_pilot_record(path, world, "locked_MSCP", "abc")
            atomic_json(path.with_suffix(".receipt.json"), {"sha256": digest(path)})
            self.assertEqual(verified_pilot_record(path, world, "locked_MSCP", "abc"), record)
            with self.assertRaises(ValueError):
                verified_episode_record(path, world, "locked_MSCP", "abc", stage="final")
            with self.assertRaises(ValueError):
                verified_pilot_record(path, world, "static_bid0.25", "abc")
            record["evaluation"]["final_pending_exposures"] = 1
            atomic_json(path, record)
            atomic_json(path.with_suffix(".receipt.json"), {"sha256": digest(path)})
            with self.assertRaises(ValueError):
                verified_pilot_record(path, world, "locked_MSCP", "abc")

    def test_disjoint_balanced_rosters(self):
        pilot, final = world_roster("pilot", 20), world_roster("final", 40)
        self.assertEqual(len({row["world_id"] for row in pilot + final}), 60)
        self.assertEqual(final, world_roster("final", 40))
        self.assertTrue({row["budget_per_campaign"] for row in pilot + final} <= {4000, 10000, 20000})
        self.assertTrue(set(row["parameter_index"] for row in pilot).isdisjoint(
            row["parameter_index"] for row in final))
        self.assertEqual([sum(row["family"] == family for row in final)
                          for family in {row["family"] for row in final}], [10] * 4)
        for stage, count in (("pilot", 24), ("final", 39), ("final", 204), ("validation", 20), ("pilot", 20.0)):
            with self.assertRaises(ValueError):
                world_roster(stage, count)

    def test_block_sensitivity_does_not_inflate_catalog(self):
        roster = world_roster("final", 40)
        baseline = np.zeros(40)
        candidate = np.arange(40) / 1000
        result = paired_analysis(roster, candidate, baseline, bootstrap_draws=200)
        self.assertEqual(result["primary_paired_complete_world"]["units"], 40)
        self.assertEqual(result["parameter_block_cluster_sensitivity"]["units"], 16)
        with self.assertRaises(ValueError):
            paired_analysis(roster, candidate[:-1], baseline)


if __name__ == "__main__":
    unittest.main()
