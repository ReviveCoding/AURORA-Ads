from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_confirmation_plan import confirmation_manifest, TRAINING_SEEDS


class ConfirmationPlanTests(unittest.TestCase):
    def inputs(self):
        selection = {"status": "DEVELOPMENT_RECIPE_SCREENING_EXECUTED", "passed": True, "final_agent_tasks_loaded": 0, "corpus_sha256": "c" * 64, "qualified_finalist_recipes": [], "operationally_qualified_screened_recipes": [], "selected_learned_recipe": None}
        qualifications = {}
        for seed in TRAINING_SEEDS:
            qualifications["prompt_only", seed] = {
                "sha256": "a" * 64, "duty_pause_seconds": 10.,
                "report": {"passed": True, "model": "Qwen3-4B", "recipe": "prompt_only", "training_seed": seed, "revision": "resolved", "corpus_sha256": "c" * 64, "context_tokens": 2048, "final_tasks_loaded": 0, "semantic_task_scoring": False, "trained_parent_sha256": None, "duty_pause_seconds": 10., "status": "BOUNDED_DECODE_DUTY_QUALIFIED", "decodes": [{"prefix_tokens": 1500, "generation_tokens": 512, "wall_seconds_cuda_synchronized": 1., "resource_stop_reason": None, "forced_decode_stress_not_task_answer": True} for _ in range(8)]},
            }
        return {"selection": selection, "workflow_groups": {"abstract_a": "g1", "abstract_b": "g2", "abstract_c": "g2"}, "expected_groups": ("g1", "g2"), "revision": "resolved", "corpus_sha256": "c" * 64, "taxonomy_sha256": "t" * 64, "device_target_c": 87., "trained": {}, "qualifications": qualifications, "cases_per_group": 6, "index_start": 2000}

    def test_prompt_only_negative_screen_is_valid_without_extra_units(self):
        result = confirmation_manifest(**self.inputs())
        self.assertEqual(result["arms"], ["prompt_only"])
        self.assertEqual(result["case_count_per_arm_seed"], 12)
        self.assertEqual(result["effective_independent_family_count"], 2)
        self.assertEqual(result["scientific_status"], "UNDERPOWERED")
        self.assertFalse(result["seed_template_replication_adds_independence"])

    def test_partial_seed_or_recipe_reselection_refused(self):
        args = self.inputs()
        del args["qualifications"]["prompt_only", 101]
        with self.assertRaises(ValueError):
            confirmation_manifest(**args)

    def learned_inputs(self):
        import copy
        args = self.inputs()
        args["selection"].update(qualified_finalist_recipes=["dpo"], operationally_qualified_screened_recipes=["dpo"], selected_learned_recipe="dpo")
        for seed in TRAINING_SEEDS:
            for recipe in ("sft", "dpo"):
                report = {"stage": "train", "status": "POSTTRAINING_EXECUTED", "passed": True, "objective": recipe, "model": "Qwen/Qwen3-4B", "revision": "resolved", "tokenizer_revision": "resolved", "seed": seed, "corpus_sha256": "c" * 64, "checkpoint": f"abstract_{recipe}_{seed}", "optimizer_updates": 2}
                report["resource_monitoring"] = "latched_background_device_samples_nominal2s_query_timeout3s_plus_phase_boundaries_v1"
                report["background_resource_monitor"] = {"latched_failure": None, "reserve_mib": 2048, "device_reported_target_c": 87., "samples": [{"temperature_c": 80., "total_mib": 16376., "used_mib": 10000.}]}
                if recipe == "dpo":
                    report["same_sft_parent"] = {"checkpoint": f"abstract_sft_{seed}"}
                args["trained"][recipe, seed] = {"report": report, "sha256": "b" * 64}
            qual = copy.deepcopy(args["qualifications"]["prompt_only", seed])
            qual["report"].update(recipe="dpo", trained_parent_sha256="b" * 64)
            args["qualifications"]["dpo", seed] = qual
        return args

    def test_unqualified_sft_can_be_parent_without_new_comparison_arm(self):
        result = confirmation_manifest(**self.learned_inputs())
        self.assertEqual(result["arms"], ["prompt_only", "dpo"])
        self.assertEqual(len(result["evidence"]), 6)

    def test_v21_qualified_sft_is_not_an_extra_finalist(self):
        args = self.learned_inputs()
        args["selection"]["operationally_qualified_screened_recipes"] = ["sft", "dpo", "ipo"]
        self.assertEqual(confirmation_manifest(**args)["arms"], ["prompt_only", "dpo"])
        args["selection"]["qualified_finalist_recipes"] = ["sft", "dpo"]
        with self.assertRaises(ValueError):
            confirmation_manifest(**args)

    def test_v21_1p7b_boundary_evidence_not_relabelled_sustained_4b(self):
        args = self.learned_inputs()
        args["evaluation_model"] = "Qwen3-1.7B"
        for item in args["trained"].values():
            item["report"]["model"] = "Qwen/Qwen3-1.7B"
            item["report"].pop("resource_monitoring")
            item["report"].pop("background_resource_monitor")
            item["report"]["telemetry"] = [{"temperature_c": 86, "total_mib": 16376, "used_mib": 10400}]
        for item in args["qualifications"].values():
            item["report"]["model"] = "Qwen3-1.7B"
        result = confirmation_manifest(**args)
        self.assertEqual(result["model"], "Qwen/Qwen3-1.7B")
        self.assertEqual(result["scientific_status"], "UNDERPOWERED")
        args["trained"]["sft", 41]["report"]["telemetry"][0]["temperature_c"] = 87
        with self.assertRaises(ValueError):
            confirmation_manifest(**args)

    def test_bounded_qualifier_small_model_or_wrong_parent_cannot_be_final_training(self):
        for field, value in (("stage", "qualify"), ("model", "Qwen/Qwen3-1.7B"), ("seed", 73)):
            args = self.learned_inputs()
            args["trained"]["sft", 41]["report"][field] = value
            with self.assertRaises(ValueError):
                confirmation_manifest(**args)
        args = self.learned_inputs()
        args["trained"]["dpo", 41]["report"]["same_sft_parent"]["checkpoint"] = "another_parent"
        with self.assertRaises(ValueError):
            confirmation_manifest(**args)

    def test_old_boundary_only_or_latched_failed_monitor_not_sustained_admission(self):
        args = self.learned_inputs()
        args["trained"]["sft", 41]["report"].pop("resource_monitoring")
        with self.assertRaises(ValueError):
            confirmation_manifest(**args)
        args = self.learned_inputs()
        args["trained"]["dpo", 41]["report"]["background_resource_monitor"]["latched_failure"] = "abstract hot sample followed by cooldown"
        with self.assertRaises(ValueError):
            confirmation_manifest(**args)
        args = self.inputs()
        args["selection"]["qualified_finalist_recipes"] = ["dpo"]
        with self.assertRaises(ValueError):
            confirmation_manifest(**args)
