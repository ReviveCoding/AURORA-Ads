#!/usr/bin/env python3
"""Freeze admitted selected-model finalist evidence before final scoring."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.agent_confirmation_plan import confirmation_manifest, TRAINING_SEEDS
from aurora.agent_evidence import verified_pointer, verified_checkpoint, owned_file, verified_model_files
from aurora.agent_qualification import pointer_path
from aurora.agent_tasks import FAMILIES, FAMILY_GROUPS
from aurora.artifacts import atomic_json, digest, immutable_json
from aurora.resources import storage_admission
from aurora.studies import Study
from agent_study import data_files, agent_allocation_used_seconds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-per-group", type=int, required=True)
    parser.add_argument("--index-start", type=int, default=10000)
    parser.add_argument("--model", choices=["Qwen3-1.7B", "Qwen3-4B"], default="Qwen3-1.7B")
    args = parser.parse_args()
    started = time.perf_counter()
    study = Study(ROOT, "e15_agent_confirmation_freeze")
    state = study.ledger.read()
    for node in ("E10", "E13_AGENT"):
        if state["nodes"][node]["execution_status"] != "EXECUTED":
            raise ValueError("Actual complete dependency required: " + node)
    if state["nodes"]["E15_AGENT"]["execution_status"] != "PENDING" or state["nodes"]["E15_AGENT"]["artifacts"]:
        raise ValueError("Final scoring has started; never refreeze from its outcomes")
    destination = ROOT / "reports/agent/FINAL_AGENT_FREEZE.json"
    if destination.exists() or state["nodes"]["E15_AGENT_FREEZE"]["execution_status"] == "EXECUTED":
        raise ValueError("Final agent freeze already exists; resume it, never overwrite/reselect")
    allowed = (ROOT / "reports/agent", study.runtime / "runs")
    corpus = data_files()
    selection, selection_ref = verified_pointer(ROOT / "reports/agent/DEV_RECIPE_SELECTION.json", allowed)
    ablation, ablation_ref = verified_pointer(ROOT / "reports/agent/DEVELOPMENT_ABLATIONS.json", allowed)
    if ablation.get("status") != "DEVELOPMENT_INPUT_ABLATIONS_EXECUTED" or ablation.get("passed") is not True or ablation.get("final_tasks_loaded") != 0 or ablation.get("corpus_sha256") != corpus["sha256"] or ablation.get("development_selection_sha256") != selection_ref["sha256"]:
        raise ValueError("Actual same-corpus development ablations required")
    taxonomy, taxonomy_ref = verified_pointer(ROOT / "reports/agent/TAXONOMY_V2_FREEZE.json", allowed)
    mapping = {workflow: FAMILY_GROUPS[workflow] for workflow, item in FAMILIES.items() if item[0] == "final"}
    frozen_mapping = {workflow: item["dependence_group"] for workflow, item in taxonomy["family_split"].items() if item["split"] == "final"}
    if mapping != frozen_mapping:
        raise ValueError("Final executable workflow/split identity changed")
    config_taxonomy = json.loads((ROOT / "config/agent_taxonomy_v2.json").read_text())
    admission_path = ROOT / "reports/agent" / (args.model + "_ADMISSION.json")
    admission = json.loads(admission_path.read_text())
    model_files = verified_model_files(admission, study.runtime)
    device_qualification_path = ROOT / "reports/environment/GPU_QUALIFICATION.json"
    device_target = json.loads(device_qualification_path.read_text())["device_reported_target_c"]
    finalists = selection["qualified_finalist_recipes"]
    training_recipes = set(finalists) | ({"sft"} if any(recipe in {"dpo", "ipo"} for recipe in finalists) else set())
    trained, qualifications = {}, {}
    training_refs, qualification_refs = {}, {}
    for recipe in sorted(training_recipes):
        for seed in TRAINING_SEEDS:
            parent, reference = verified_pointer(ROOT / "reports/agent" / f"{args.model}_{recipe}_seed{seed}_LATEST.json", allowed)
            checkpoint = verified_checkpoint(parent, study.runtime)
            trained[recipe, seed] = {"report": parent, "sha256": reference["sha256"]}
            training_refs[f"{recipe}_seed{seed}"] = {**reference, **checkpoint}
    for recipe in ("prompt_only", *sorted(finalists)):
        for seed in TRAINING_SEEDS:
            qualification, reference = verified_pointer(pointer_path(ROOT, args.model, recipe, seed), allowed)
            qualifications[recipe, seed] = {"report": qualification, "sha256": reference["sha256"], "duty_pause_seconds": qualification["duty_pause_seconds"]}
            qualification_refs[f"{recipe}_seed{seed}"] = reference
    manifest = confirmation_manifest(selection=selection, workflow_groups=mapping,
        expected_groups=tuple(config_taxonomy["effective_dependence_groups"]["final"]),
        revision=admission["revision"], corpus_sha256=corpus["sha256"],
        taxonomy_sha256=taxonomy_ref["sha256"], trained=trained,
        device_target_c=device_target,
        qualifications=qualifications, cases_per_group=args.cases_per_group, index_start=args.index_start,
        evaluation_model=args.model)
    rates = [decode["wall_seconds_cuda_synchronized"] / decode["generation_tokens"] for item in qualifications.values() for decode in item["report"]["decodes"]]
    # A conservative engineering forecast, not a measured final-task latency or
    # universal performance bound. Actual full-wall cap is checked while scoring.
    if not rates or any(not math.isfinite(value) or value <= 0 for value in rates):
        raise ValueError("Positive actual TRAIN decode cost information required")
    per_case_forecast = 2048 * max(rates) + 9 * manifest["common_duty_pause_seconds"]
    reload_forecast = sum(item["report"]["wall_seconds"] for item in qualifications.values())
    forecast = len(manifest["cases"]) * len(manifest["arms"]) * len(TRAINING_SEEDS) * per_case_forecast + reload_forecast
    resources = json.loads((ROOT / "config/resources.json").read_text())
    prior = agent_allocation_used_seconds()
    cap = resources["gpu_hours_caps"]["agent"] * 3600
    manifest["allocation_admission"] = {"prior_completed_full_wall_seconds": prior,
        "cap_seconds": cap, "current_freeze_elapsed_seconds": time.perf_counter() - started,
        "prospective_full_roster_seconds": forecast, "per_case_forecast_seconds": per_case_forecast,
        "forecast_method": "max actual TRAIN forced-decode seconds/token ×2048 +9 common duty pauses; add all actual decode qualification wall as conservative reload allowance",
        "forecast_is_not_measured_final_latency_or_guaranteed_bound": True}
    if prior + forecast + time.perf_counter() - started >= cap:
        atomic_json(study.directory / "resource_admission_refusal.json", manifest)
        raise ValueError("Prospective roster does not fit unchanged agent cap; preserve this refusal and choose only a pre-outcome resource profile, never inspect finals")
    record_count = len(manifest["cases"]) * len(manifest["arms"]) * len(TRAINING_SEEDS)
    manifest["expected_scoring_growth_bytes"] = record_count * 1024**2 + 256 * 1024**2
    manifest["storage_forecast_method"] = "1MiB per case/arm/seed incl raw generations and trace evidence +256MiB metadata; engineering forecast, actual reserve checked during execution"
    manifest["storage_admission"] = storage_admission(study.runtime, ROOT, expected_growth_bytes=manifest["expected_scoring_growth_bytes"], contract=resources)
    code_names = ["src/aurora/" + name + ".py" for name in (
        "agent", "agent_tasks", "agent_taxonomy", "tools", "state", "agent_inference",
        "agent_safety", "agent_evaluation", "agent_result_admission", "agent_case_roster",
        "agent_confirmation_plan", "agent_evidence", "agent_attempt", "agent_ledger_admission", "agent_render_compat", "agent_qualification", "inference",
        "inference_monitor", "resources", "artifacts", "studies", "workflow")]
    code_names += ["src/aurora/" + name + ".py" for name in ("simulator", "policies", "policy_registry", "prediction", "incidents")]
    code_names += ["tools/agent_confirmation.py", "tools/freeze_agent_confirmation.py", "tools/agent_study.py"]
    # The frozen A1 host uses the original registered S1 provider, not a future
    # repaired/numerical policy pointer. Bind all its actual numerical inputs.
    provider_paths = (ROOT / "reports/policy/WARMSTART_LATEST.json", ROOT / "reports/incidents/DETECTOR_FREEZE.json")
    provider_hashes = {str(path): digest(path) for path in provider_paths}
    warm = json.loads(provider_paths[0].read_text())
    detector = json.loads(provider_paths[1].read_text())
    detector_recipe = next(item for item in detector["candidates"] if item["id"] == detector["selected"])
    provider_items = [(warm["support_path"], warm["support_sha256"])]
    provider_items += [(warm["model_fits"][target]["path"], warm["model_fits"][target]["sha256"]) for target in ("gross", "spend")]
    neural = warm["model_fits"]["neural_representation"]
    cohort = warm["cohort_artifacts"]["train"]
    provider_items += [(neural["embedding_path"], neural["embedding_sha256"]), (cohort["path"], cohort["sha256"]), (detector_recipe["path"], detector_recipe["sha256"]), (detector_recipe["calibrator_path"], detector_recipe["calibrator_sha256"])]
    for path_string, sha in provider_items:
        path = owned_file(Path(path_string), (study.runtime / "runs",))
        if digest(path) != sha:
            raise ValueError("Original frozen A1 numerical provider changed")
        provider_hashes[str(path)] = sha
    manifest.update(status="FINAL_AGENT_FROZEN_BEFORE_MODEL_SCORING", study_id=study.name,
        selection=selection_ref, development_ablations=ablation_ref,
        taxonomy=taxonomy_ref, training_reports=training_refs,
        inference_qualifications=qualification_refs, model_admission={"artifact": str(admission_path), "sha256": digest(admission_path)},
        original_a1_provider_files_sha256=provider_hashes,
        actual_pinned_model_files_sha256=model_files,
        device_qualification={"artifact": str(device_qualification_path), "sha256": digest(device_qualification_path), "device_reported_target_c": device_target},
        environment={"python": sys.version, "packages": sorted(f"{item.metadata['Name']}=={item.version}" for item in importlib.metadata.distributions())},
        code_sha256={name: digest(ROOT / name) for name in code_names},
        config_sha256={str(path.relative_to(ROOT)): digest(path) for path in (ROOT / "config").glob("*.json")},
        final_tasks_target=400, actual_count_is_not_more_semantic_independence=True,
        limitations=["Nine dependence groups; UNDERPOWERED regardless of favorable outcomes", "Shared generator sensitivity remains one unit", "Any smaller-than-target resource profile reduces coverage, never improves power", "Complete final-task cost/health remains measured during scoring, not guaranteed by this forecast"])
    artifact = immutable_json(ROOT / "reports/agent/confirmation_freezes", manifest)
    # Immutable freeze + ledger precede the public pointer. If interrupted before
    # pointer export, reconcile its content-addressed artifact; never refreeze.
    study.ledger.update("E15_AGENT_FREEZE", "EXECUTED", science="UNDERPOWERED", artifacts=(artifact,), capabilities={"agent_final_roster_frozen_before_scoring": True})
    study.export_state()
    atomic_json(destination, {"artifact": str(artifact), "sha256": digest(artifact)})
    atomic_json(study.directory / "result.json", {"artifact": str(artifact), "sha256": digest(artifact), "status": manifest["status"], "wall_seconds": time.perf_counter() - started})
    print(json.dumps({"status": manifest["status"], "artifact": str(artifact), "case_count_per_arm_seed": len(manifest["cases"]), "effective_independent_families": len(set(mapping.values()))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
