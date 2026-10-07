#!/usr/bin/env python3
"""Development-only executable comparison; no primary final family is loaded."""
from __future__ import annotations

import gc
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.agent import run_agent
from aurora.agent_tasks import FAMILIES, FAMILY_GROUPS, Task, TaskHost
from aurora.agent_inference import LocalGenerator
from aurora.agent_safety import proposal_diagnostics, commit_multiplicity_diagnostics
from aurora.agent_qualification import pointer_path, verify_inference_identity
from aurora.artifacts import atomic_json, digest
from aurora.resources import cuda_lease, check_gpu_room
from aurora.studies import Study
from agent_study import agent_allocation_used_seconds, data_files, load_model, thermal_check


def main():
    study = Study(ROOT, "e10_1p7b_recipe_validation")
    corpus = data_files()
    tasks = json.loads(Path(corpus["files"]["validation_tasks"]["path"]).read_text())
    for item in tasks:
        if FAMILIES[item["task"]["family"]][0] != "validation" or item["semantic_group"] != FAMILY_GROUPS[item["task"]["family"]]:
            raise ValueError("Validation includes a held-out/train group or wrong identity")
    admission = json.loads((ROOT / "reports/agent/Qwen3-1.7B_ADMISSION.json").read_text())
    recipes = {"prompt_only": None}
    parents = {}
    for name in ("sft", "dpo", "ipo"):
        pointer = json.loads((ROOT / "reports/agent" / ("Qwen3-1.7B_" + name + "_seed41_LATEST.json")).read_text())
        if not pointer["passed"] or digest(Path(pointer["artifact"])) != pointer["sha256"]:
            raise ValueError("Failed/mismatched development training recipe cannot be scored as qualified")
        parent = json.loads(Path(pointer["artifact"]).read_text())
        if parent["corpus_sha256"] != corpus["sha256"] or parent["objective"] != name or parent["revision"] != admission["revision"] or parent["seed"] != 41:
            raise ValueError("Development recipe input mismatch")
        checkpoint = Path(pointer["checkpoint"])
        for filename, sha in parent["checkpoint_hashes"].items():
            if digest(checkpoint / filename) != sha:
                raise ValueError("Trained checkpoint changed")
        recipes[name] = checkpoint
        parents[name] = pointer
    report = {"status": "RUNNING", "model": admission["repo_id"], "revision": admission["revision"], "corpus_sha256": corpus["sha256"], "training_seed": 41, "decode": "greedy/nonthinking; same2048 context,8tools,2048generated tokens", "task_count_per_recipe": len(tasks), "validation_groups": sorted({item["semantic_group"] for item in tasks}), "final_agent_tasks_loaded": 0, "telemetry": [check_gpu_room(8)], "parents": parents, "recipe_results": {}, "qualified_finalist_recipes": []}
    target = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())["device_reported_target_c"]
    model = None
    started = time.perf_counter()
    used_seconds = agent_allocation_used_seconds()
    allocation_seconds = json.loads((ROOT / "config/resources.json").read_text())["gpu_hours_caps"]["agent"] * 3600
    report["allocation_accounting"] = {"prior_actual_wall_seconds_including_failures": used_seconds, "cap_seconds": allocation_seconds}
    # Pre-outcome engineering rule: use the slowest actual qualified decode
    # duty across ALL compared recipes, so physical pacing is matched.
    report["inference_duty_pause_seconds"] = None
    inference_admission = {}
    for name in recipes:
        pointer = json.loads(pointer_path(ROOT, "Qwen3-1.7B", name, 41).read_text())
        artifact = Path(pointer["artifact"])
        if not pointer["passed"] or digest(artifact) != pointer["sha256"]:
            raise ValueError("Actual recipe-specific inference duty qualification required before scoring")
        qualification = json.loads(artifact.read_text())
        expected_parent = None if name == "prompt_only" else parents[name]["sha256"]
        verify_inference_identity(qualification, model="Qwen3-1.7B", recipe=name, training_seed=41, revision=admission["revision"], corpus_sha256=corpus["sha256"], trained_parent_sha256=expected_parent, pointer_duty=pointer["duty_pause_seconds"])
        inference_admission[name] = pointer
    report["inference_duty_admission"] = inference_admission
    report["inference_duty_pause_seconds"] = max(pointer["duty_pause_seconds"] for pointer in inference_admission.values())
    report["inference_duty_rule"] = "common maximum of recipe-specific first-passing5/10/30-second TRAIN-prefix decode qualification; actual stopping monitor always active"
    def health_check():
        if used_seconds + time.perf_counter() - started >= allocation_seconds:
            raise RuntimeError("Agent allocation exhausted; preserve partial validation, no silent expansion")
        thermal_check(report["telemetry"], target)
    def generation_settle():
        health_check()
        time.sleep(report["inference_duty_pause_seconds"])
    try:
        import numpy as np
        from peft import LoraConfig
        with cuda_lease(study.runtime):
            model, tokenizer = load_model(admission, 8, 41)
            for name, checkpoint in recipes.items():
                if checkpoint is not None:
                    model.add_adapter(name, LoraConfig(r=8, lora_alpha=16, target_modules="all-linear", lora_dropout=0., task_type="CAUSAL_LM"))
                    for parameter_name, parameter in model.named_parameters():
                        if "." + name + "." in parameter_name:
                            parameter.data = parameter.data.float()
                    model.load_adapter(checkpoint, adapter_name=name, is_trainable=False, autocast_adapter_dtype=False)
                    model.set_adapter(name)
                else:
                    model.set_adapter("default")  # fresh B=0: pretrained baseline
                generator = LocalGenerator(model, tokenizer, records=study.directory / "generation_records" / name, before_generation=health_check, after_generation=generation_settle)
                results = []
                for item in tasks:
                    health_check()
                    task = Task(**item["task"])
                    host = TaskHost(task, study.runtime, study.name + "_" + name)
                    task_start = time.perf_counter()
                    result = run_agent(task, host, generator)
                    result["proposal_diagnostics"] = proposal_diagnostics(result)
                    result["commit_multiplicity_diagnostics"] = commit_multiplicity_diagnostics(result)
                    result["complete_task_wall_seconds"] = time.perf_counter() - task_start
                    results.append(result)
                    atomic_json(study.directory / (name + "_progress.json"), {"completed": len(results), "total": len(tasks), "last_result": result})
                    health_check()
                result_path = study.directory / (name + "_tasks.json")
                atomic_json(result_path, results)
                atomic_json(study.directory / (name + "_latencies.json"), generator.measurements)
                means = {group: float(np.mean([result["success"] for result in results if result["semantic_group"] == group])) for group in report["validation_groups"]}
                report["recipe_results"][name] = {"task_results_path": str(result_path), "sha256": digest(result_path), "family_means": means, "family_macro_success": float(np.mean(list(means.values()))), "unsafe_proposal_tasks": sum(result["unsafe_proposals"] > 0 for result in results), "host_blocked_tasks": sum(result["host_blocked_errors"] > 0 for result in results), "wrong_committed_action_tasks": sum(result["wrong_committed_actions"] > 0 for result in results), "task_failures": sum(result["failure"] is not None for result in results), "complete_task_wall_seconds": sum(result["complete_task_wall_seconds"] for result in results)}
                report["recipe_results"][name]["complementary_proposal_integrity_issue_tasks"] = sum(result["proposal_diagnostics"]["proposal_integrity_issue_observed"] for result in results)
                report["recipe_results"][name]["complementary_excess_applied_commit_tasks"] = sum(result["commit_multiplicity_diagnostics"]["excess_applied_commits"] > 0 for result in results)
                report["recipe_results"][name]["complementary_extra_expected_action_commits"] = sum(result["commit_multiplicity_diagnostics"]["extra_commits_of_expected_action"] for result in results)
                report["recipe_results"][name]["host_integrity_failed_tasks"] = sum(result["host_integrity"]["integrity"] != "ok" for result in results)
                report["recipe_results"][name]["complementary_proposal_diagnostic_call_counts"] = {key: sum(result["proposal_diagnostics"][key] for result in results) for key in ("budget_or_cooldown_ineligible_action_calls", "authorization_blocked_action_calls", "stale_state_action_calls", "schema_or_binding_blocked_action_calls", "unclassified_blocked_action_calls")}
                atomic_json(study.directory / "result_progress.json", report)
            # Qualified = actually trained and operationally scored with finite,
            # invariant-preserving outputs. Superiority is not a qualification gate.
            qualified = [name for name in ("sft", "dpo", "ipo") if report["recipe_results"][name]["wrong_committed_action_tasks"] == 0 and report["recipe_results"][name]["complementary_excess_applied_commit_tasks"] == 0 and report["recipe_results"][name]["host_integrity_failed_tasks"] == 0 and report["recipe_results"][name]["task_failures"] < len(tasks)]
            selected = max(qualified, key=lambda name: (report["recipe_results"][name]["family_macro_success"], -report["recipe_results"][name]["unsafe_proposal_tasks"], name)) if qualified else None
            # v2.1: retain one strongest qualified learned recipe. SFT parents
            # remain necessary for preference training, not extra comparison arms.
            finalists = [selected] if selected else []  # v2.1: one learned finalist, no extra SFT comparison
            report.update(status="DEVELOPMENT_RECIPE_SCREENING_EXECUTED", operationally_qualified_screened_recipes=qualified, qualified_finalist_recipes=finalists, selected_learned_recipe=selected, prompt_only_retained_as_system_candidate=selected is None or report["recipe_results"]["prompt_only"]["family_macro_success"] >= report["recipe_results"][selected]["family_macro_success"], frozen_before_final_scoring=True, passed=True, limitations=["Three development semantic groups do not establish generalization; selection only", "Final semantic groups remain unseen by this run", "No fine-tuning superiority requirement; unfavorable arms preserved", "One screening training seed; finalist confirmation must separately report three seeds", "Family/group convenience design and shared-host dependence persist", "v2.1 retains one learned finalist; optional4B transfer is separately qualified, not required"])
    except Exception as error:
        report.update(status="FAILED_RECIPE_SCREENING", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    finally:
        del model
        gc.collect()
    report["wall_seconds"] = time.perf_counter() - started
    export = ROOT / "reports/agent" / (study.name + ".json")
    if report["passed"]:
        # A complete actual four-arm development comparison closes E10;
        # a per-recipe optimizer checkpoint alone does not. Retain a valid
        # negative screening result even when no learned finalist qualifies.
        export = study.finish("E10", report, "agent", science="UNDERPOWERED", capabilities={"AGENT_DEVELOPMENT_SCREENED": True, "qualified_small_model": True, "qualified_agent_recipe": bool(report["qualified_finalist_recipes"]), "development_only": True})
        atomic_json(ROOT / "reports/agent/DEV_RECIPE_SELECTION.json", report | {"artifact": str(export), "sha256": digest(export)})
    else:
        atomic_json(export, report)
        atomic_json(study.directory / "result.json", report)
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
