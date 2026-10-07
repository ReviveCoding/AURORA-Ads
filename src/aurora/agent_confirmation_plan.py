"""Pre-score final-agent manifest admission; no prompts, golds or inference."""
from __future__ import annotations

from dataclasses import asdict
from typing import Mapping

from aurora.agent_case_roster import balanced_case_roster
from aurora.agent_qualification import verify_inference_identity

TRAINING_SEEDS = (41, 73, 101)


def confirmation_manifest(
    *,
    selection: Mapping,
    workflow_groups: Mapping[str, str],
    expected_groups: tuple[str, ...],
    revision: str,
    corpus_sha256: str,
    taxonomy_sha256: str,
    device_target_c: float,
    trained: Mapping[tuple[str, int], Mapping],
    qualifications: Mapping[tuple[str, int], Mapping],
    cases_per_group: int,
    index_start: int,
    evaluation_model: str = "Qwen3-4B",
) -> dict:
    """Caller SHA-verifies every supplied artifact before this semantic gate.

    Counts/profile must be selected from resource information before outcomes.
    This never opens task prompts or promotes the prospective UNDERPOWERED audit.
    An incomplete finalist roster cannot be silently turned into fewer seeds.
    """
    if selection.get("status") != "DEVELOPMENT_RECIPE_SCREENING_EXECUTED" or selection.get("passed") is not True or selection.get("final_agent_tasks_loaded") != 0 or selection.get("corpus_sha256") != corpus_sha256:
        raise ValueError("Complete same-corpus development-only recipe screening required")
    finalists = selection.get("qualified_finalist_recipes")
    qualified = selection.get("operationally_qualified_screened_recipes")
    selected = selection.get("selected_learned_recipe")
    if not isinstance(finalists, list) or not isinstance(qualified, list) or any(recipe not in {"sft", "dpo", "ipo"} for recipe in qualified) or len(set(qualified)) != len(qualified):
        raise ValueError("Explicit actually screened recipe roster required")
    if evaluation_model not in {"Qwen3-1.7B", "Qwen3-4B"}:
        raise ValueError("Explicit qualified pinned Qwen evaluation model required")
    expected_finalists = {selected} if selected is not None else set()
    if selected is not None and selected not in qualified or set(finalists) != expected_finalists or len(set(finalists)) != len(finalists):
        raise ValueError("At most one selected learned finalist; SFT parent is not an extra comparison arm")
    if set(workflow_groups.values()) != set(expected_groups) or not expected_groups or len(set(expected_groups)) != len(expected_groups):
        raise ValueError("Complete frozen final dependence-group mapping required")
    if not revision or len(corpus_sha256) != 64 or len(taxonomy_sha256) != 64:
        raise ValueError("Resolved model and corpus/taxonomy identities required")
    arms = ["prompt_only", *sorted(finalists)]
    training_recipes = set(finalists) | ({"sft"} if any(recipe in {"dpo", "ipo"} for recipe in finalists) else set())
    expected_training = {(recipe, seed) for recipe in training_recipes for seed in TRAINING_SEEDS}
    expected_qualification = {(recipe, seed) for recipe in arms for seed in TRAINING_SEEDS}
    if set(trained) != expected_training or set(qualifications) != expected_qualification:
        raise ValueError("All retained arms and three declared seeds required; missing evidence is not a zero outcome")
    for recipe, seed in sorted(expected_training):
        report = trained[recipe, seed]["report"]
        expected = {"stage": "train", "status": "POSTTRAINING_EXECUTED", "passed": True, "objective": recipe, "model": "Qwen/" + evaluation_model, "revision": revision, "tokenizer_revision": revision, "seed": seed, "corpus_sha256": corpus_sha256}
        if any(report.get(key) != value for key, value in expected.items()) or not report.get("checkpoint") or type(report.get("optimizer_updates")) is not int or report["optimizer_updates"] < 1 or len(trained[recipe, seed]["sha256"]) != 64:
            raise ValueError("Actual same-revision/model trained checkpoint required; disposable qualifiers are not finalists")
        monitor = report.get("background_resource_monitor", {})
        if evaluation_model == "Qwen3-4B" and (report.get("resource_monitoring") != "latched_background_device_samples_nominal2s_query_timeout3s_plus_phase_boundaries_v1" or monitor.get("latched_failure") is not None or monitor.get("reserve_mib") != 2048 or monitor.get("device_reported_target_c") != device_target_c or not monitor.get("samples")):
            raise ValueError("Actual sustained 4B job must retain its matched latched resource-monitor evidence")
        samples = monitor.get("samples") or report.get("telemetry", [])
        if not samples or monitor.get("latched_failure") is not None or any(sample["temperature_c"] >= device_target_c or sample["total_mib"] - sample["used_mib"] < 2048 for sample in samples):
            raise ValueError("Saved sustained-job samples do not maintain the unchanged target/reserve")
    evidence = []
    for recipe, seed in sorted(expected_qualification):
        parent_sha = None
        if recipe != "prompt_only":
            item = trained[recipe, seed]
            report = item["report"]
            if recipe in {"dpo", "ipo"}:
                sft = trained.get(("sft", seed))
                if sft is None or report.get("same_sft_parent", {}).get("checkpoint") != sft["report"]["checkpoint"]:
                    raise ValueError("Final preference recipe must share its actual same-seed/model SFT parent")
            parent_sha = item["sha256"]
        qualification = qualifications[recipe, seed]
        verify_inference_identity(qualification["report"], model=evaluation_model, recipe=recipe, training_seed=seed, revision=revision, corpus_sha256=corpus_sha256, trained_parent_sha256=parent_sha, pointer_duty=qualification["duty_pause_seconds"])
        evidence.append({"recipe": recipe, "training_seed": seed, "training_report_sha256": parent_sha, "qualification_sha256": qualification["sha256"], "qualified_duty_pause_seconds": qualification["duty_pause_seconds"]})
    cases = balanced_case_roster(workflow_groups, cases_per_group=cases_per_group, index_start=index_start)
    return {
        "status": "PRE_SCORE_CONFIRMATION_MANIFEST_ADMITTED_NOT_EXECUTED",
        "model": "Qwen/" + evaluation_model, "revision": revision,
        "corpus_sha256": corpus_sha256, "taxonomy_sha256": taxonomy_sha256,
        "arms": arms, "training_seeds": list(TRAINING_SEEDS), "evidence": evidence,
        "workflow_groups": dict(workflow_groups), "cases": [asdict(case) for case in cases],
        "case_count_per_arm_seed": len(cases), "effective_independent_family_count": len(expected_groups),
        "scientific_status": "UNDERPOWERED", "seed_template_replication_adds_independence": False,
        "final_model_outcomes_inspected_by_this_builder": 0,
        "common_duty_pause_seconds": max(item["qualified_duty_pause_seconds"] for item in evidence),
        "input_variant": "frozen_full_context", "maximum_tool_rounds": 8,
        "context_tokens": 2048, "generated_token_budget": 2048, "thinking": False,
        "decode": "greedy", "bootstrap_draws": 10000, "bootstrap_seed": 514,
        "dependence_sensitivity": "one shared executable-generator unit; no population CI",
        "resource_admission": "Caller must freeze cost/storage admission and run-time resource stops separately",
    }
