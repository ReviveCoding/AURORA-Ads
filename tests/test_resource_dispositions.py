import unittest

from aurora.resource_dispositions import blocked_track_plan


class ResourceDispositionTests(unittest.TestCase):
    def fixture(self):
        nodes = ("E03", "E15_R3_FREEZE", "E15_R3", "E10", "E13_AGENT", "E15_AGENT_FREEZE", "E15_AGENT", "E12", "E15_INTEGRATION")
        state = {"capabilities": {"CURRENT_HEAVY_GPU_MONITOR_QUALIFIED": False},
                 "nodes": {name: {"execution_status": "CHECKPOINTED"} for name in nodes}}
        exhausted = {"status": "ORIGINAL_SFT_INFERENCE_PROFILES_EXHAUSTED", "qualification_passed": False,
                     "no_final_semantic_outcomes_loaded": True, "attempts": [{"duty_pause_seconds": p} for p in (5., 10., 30.)]}
        return state, exhausted

    def test_resource_block_is_not_measured_semantic_failure(self):
        state, exhausted = self.fixture()
        plan = blocked_track_plan(state, exhausted)
        self.assertEqual(len(plan), 9)
        self.assertTrue(all(row["scientific_outcome"] == "BLOCKED_HARDWARE" for row in plan.values()))
        self.assertNotIn("E15_POLICY", plan)
        self.assertNotIn("E14", plan)

    def test_cannot_overwrite_completed_or_running_track(self):
        for status in ("EXECUTED", "RUNNING"):
            state, exhausted = self.fixture()
            state["nodes"]["E10"]["execution_status"] = status
            with self.assertRaises(ValueError):
                blocked_track_plan(state, exhausted)

    def test_requires_current_hold_and_exhausted_unscored_profiles(self):
        for key, value in (("qualification_passed", True), ("no_final_semantic_outcomes_loaded", False), ("attempts", [])):
            state, exhausted = self.fixture()
            exhausted[key] = value
            with self.assertRaises(ValueError):
                blocked_track_plan(state, exhausted)
        state, exhausted = self.fixture()
        state["capabilities"]["CURRENT_HEAVY_GPU_MONITOR_QUALIFIED"] = True
        with self.assertRaises(ValueError):
            blocked_track_plan(state, exhausted)


if __name__ == "__main__":
    unittest.main()
