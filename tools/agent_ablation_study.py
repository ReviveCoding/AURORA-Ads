#!/usr/bin/env python3
"""Actual development input-component ablations; final families never loaded."""
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
from aurora.agent_ablation import INPUT_VARIANTS, ablation_prefix_encoder, development_ablation_subset
from aurora.agent_inference import LocalGenerator
from aurora.agent_qualification import pointer_path, verify_inference_identity
from aurora.agent_safety import proposal_diagnostics, commit_multiplicity_diagnostics
from aurora.agent_tasks import Task, TaskHost, FAMILIES, FAMILY_GROUPS
from aurora.artifacts import atomic_json, digest
from aurora.resources import check_gpu_room, cuda_lease
from aurora.studies import Study
from agent_study import agent_allocation_used_seconds, data_files, load_model, thermal_check


def main():
    study = Study(ROOT, "e13_agent_development_input_ablation")
    started = time.perf_counter()
    report = {"status": "RUNNING", "final_tasks_loaded": 0, "input_variants": INPUT_VARIANTS, "results": {}, "telemetry": [], "not_model_reselection": True}
    model = None
    try:
        import numpy as np
        from peft import LoraConfig
        selection = json.loads((ROOT / "reports/agent/DEV_RECIPE_SELECTION.json").read_text())
        if not selection["passed"] or digest(Path(selection["artifact"])) != selection["sha256"]:
            raise ValueError("Actual hash-bound complete development selection required")
        if study.ledger.read()["nodes"]["E10"]["execution_status"] != "EXECUTED":
            raise ValueError("E10 actual four-arm screening must be complete")
        corpus = data_files()
        if selection["corpus_sha256"] != corpus["sha256"] or selection["final_agent_tasks_loaded"] != 0:
            raise ValueError("Development/corpus/final-exposure identity mismatch")
        items = development_ablation_subset(json.loads(Path(corpus["files"]["validation_tasks"]["path"]).read_text()))
        for item in items:
            family = item["task"]["family"]
            if FAMILIES[family][0] != "validation" or FAMILY_GROUPS[family] != item["semantic_group"]:
                raise ValueError("Ablation subset differs from frozen development mapping")
        model_name = "Qwen3-1.7B"
        admission = json.loads((ROOT / "reports/agent" / (model_name + "_ADMISSION.json")).read_text())
        selected = selection["selected_learned_recipe"]
        recipes = {"prompt_only": None}
        parents = {}
        if selected is not None:
            if selected not in selection["qualified_finalist_recipes"]:
                raise ValueError("Only actually qualified selected learned recipe can be ablated")
            pointer = json.loads((ROOT / "reports/agent" / f"{model_name}_{selected}_seed41_LATEST.json").read_text())
            if pointer["sha256"] != selection["parents"][selected]["sha256"] or not pointer["passed"] or digest(Path(pointer["artifact"])) != pointer["sha256"]:
                raise ValueError("Selected development checkpoint changed")
            parent = json.loads(Path(pointer["artifact"]).read_text())
            if parent["seed"] != 41 or parent["corpus_sha256"] != corpus["sha256"] or parent["revision"] != admission["revision"] or parent["objective"] != selected:
                raise ValueError("Selected trained model identity mismatch")
            for filename, sha in parent["checkpoint_hashes"].items():
                if digest(Path(pointer["checkpoint"]) / filename) != sha:
                    raise ValueError("Actual selected adapter changed")
            recipes[selected] = Path(pointer["checkpoint"])
            parents[selected] = pointer
        # Retain the SAME common duty used by all four actual screening arms,
        # not a faster ablation-specific cadence chosen after success outcomes.
        duty = selection["inference_duty_pause_seconds"]
        for recipe in recipes:
            pointer = json.loads(pointer_path(ROOT, model_name, recipe, 41).read_text())
            if not pointer["passed"] or digest(Path(pointer["artifact"])) != pointer["sha256"]:
                raise ValueError("Actual recipe-specific decode qualification required")
            qualification = json.loads(Path(pointer["artifact"]).read_text())
            verify_inference_identity(qualification, model=model_name, recipe=recipe, training_seed=41, revision=admission["revision"], corpus_sha256=corpus["sha256"], trained_parent_sha256=None if recipe == "prompt_only" else parents[recipe]["sha256"], pointer_duty=pointer["duty_pause_seconds"])
            if duty < qualification["duty_pause_seconds"]:
                raise ValueError("Ablation cannot weaken matched actual decode duty")
        groups = sorted({item["semantic_group"] for item in items})
        report.update(model=admission["repo_id"], revision=admission["revision"], corpus_sha256=corpus["sha256"], development_selection_sha256=selection["sha256"], trained_parents=parents, tasks_per_arm=len(items), semantic_groups=groups, independent_groups=len(groups), common_inference_duty_seconds=duty, tasks_path=str(corpus["files"]["validation_tasks"]["path"]), tasks_sha256=corpus["files"]["validation_tasks"]["sha256"], subset_rule="first three numeric indices per entire validation workflow; modulo3 branches all retained")
        prior = agent_allocation_used_seconds()
        cap = json.loads((ROOT / "config/resources.json").read_text())["gpu_hours_caps"]["agent"] * 3600
        report["allocation_accounting"] = {"prior_full_wall_seconds": prior, "cap_seconds": cap}
        target = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())["device_reported_target_c"]
        def health():
            if prior + time.perf_counter() - started >= cap:
                raise RuntimeError("Agent allocation exhausted; preserve partial ablation")
            thermal_check(report["telemetry"], target)
        def settle():
            health()
            time.sleep(duty)
        report["telemetry"].append(check_gpu_room(8))
        study.ledger.update("E13_AGENT", "RUNNING")
        with cuda_lease(study.runtime):
            model, tokenizer = load_model(admission, 8, 41)
            for recipe, checkpoint in recipes.items():
                if checkpoint is not None:
                    model.add_adapter(recipe, LoraConfig(r=8, lora_alpha=16, target_modules="all-linear", lora_dropout=0., task_type="CAUSAL_LM"))
                    for name, parameter in model.named_parameters():
                        if "." + recipe + "." in name:
                            parameter.data = parameter.data.float()
                    model.load_adapter(checkpoint, adapter_name=recipe, is_trainable=False, autocast_adapter_dtype=False)
                    model.set_adapter(recipe)
                else:
                    model.set_adapter("default")
                for variant in INPUT_VARIANTS:
                    arm = recipe + "__" + variant
                    results = []
                    generator = LocalGenerator(model, tokenizer, records=study.directory / "generation_records" / arm, before_generation=health, after_generation=settle, prefix_encoder=ablation_prefix_encoder(variant), input_variant=variant)
                    for item in items:
                        health()
                        task = Task(**item["task"])
                        host = TaskHost(task, study.runtime, study.name + "_" + arm)
                        begin = time.perf_counter()
                        result = run_agent(task, host, generator)
                        result["complete_task_wall_seconds"] = time.perf_counter() - begin
                        result["proposal_diagnostics"] = proposal_diagnostics(result)
                        result["commit_multiplicity_diagnostics"] = commit_multiplicity_diagnostics(result)
                        results.append(result)
                        atomic_json(study.directory / (arm + "_progress.json"), {"completed": len(results), "total": len(items), "last_result": result})
                    path = study.directory / (arm + "_tasks.json")
                    atomic_json(path, results)
                    latency_path = study.directory / (arm + "_latencies.json")
                    atomic_json(latency_path, generator.measurements)
                    means = {group: float(np.mean([result["success"] for result in results if result["semantic_group"] == group])) for group in groups}
                    report["results"][arm] = {"tasks_path": str(path), "tasks_sha256": digest(path), "latencies_path": str(latency_path), "latencies_sha256": digest(latency_path), "family_means": means, "family_macro_success": float(np.mean(list(means.values()))), "unsafe_proposal_tasks": sum(result["unsafe_proposals"] > 0 for result in results), "host_blocked_tasks": sum(result["host_blocked_errors"] > 0 for result in results), "wrong_commit_tasks": sum(result["wrong_committed_actions"] > 0 for result in results), "excess_applied_commit_tasks": sum(result["commit_multiplicity_diagnostics"]["excess_applied_commits"] > 0 for result in results), "host_integrity_failed_tasks": sum(result["host_integrity"]["integrity"] != "ok" for result in results), "task_failures": sum(result["failure"] is not None for result in results), "complete_task_wall_seconds": sum(result["complete_task_wall_seconds"] for result in results)}
                    atomic_json(study.directory / "result_progress.json", report)
                    health()
        report.update(status="DEVELOPMENT_INPUT_ABLATIONS_EXECUTED", passed=True, limitations=["Nine development cases/three dependence groups, not independent final-agent evidence", "One development training seed; templates and repeated context arms do not add units", "Ablations deliberately remove input guidance/evidence, never host authorization/budget/schema checks", "Not a final recipe/context reselection; frozen primary full-context representation remains unchanged", "Qualified TRAIN-prefix resource fixture does not guarantee every longer decode; stops/partial failures retained", "If no learned recipe qualified, learned ablation arm is unavailable, not fabricated"])
    except Exception as error:
        report.update(status="FAILED_DEVELOPMENT_INPUT_ABLATIONS", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    finally:
        del model
        gc.collect()
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/agent" / (study.name + ".json")
    if report["passed"]:
        artifact = study.finish("E13_AGENT", report, "agent", science="UNDERPOWERED", capabilities={"AGENT_DEVELOPMENT_ABLATIONS_EXECUTED": True})
        atomic_json(ROOT / "reports/agent/DEVELOPMENT_ABLATIONS.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    else:
        atomic_json(study.directory / "result.json", report)
        atomic_json(artifact, report)
        if study.ledger.read()["nodes"]["E13_AGENT"]["execution_status"] == "RUNNING":
            study.ledger.update("E13_AGENT", "FAILED", artifacts=(artifact,), reason="Actual development ablation command failed; preserve diagnostics before repair")
            study.export_state()
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
