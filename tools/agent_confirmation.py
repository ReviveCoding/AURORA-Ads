#!/usr/bin/env python3
"""Frozen matched-family final scoring; no selection, training or live actions."""
from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import shutil
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.agent_attempt import recorded_attempt
from aurora.agent import expected_commits
from aurora.agent_evaluation import AgentCase, matched_agent_comparison
from aurora.agent_evidence import owned_file, verified_pointer, verified_checkpoint
from aurora.agent_inference import LocalGenerator
from aurora.agent_ledger_admission import read_agent_ledger, snapshot_agent_ledger, reconcile_saved_actions
from aurora.agent_result_admission import admit_saved_result
from aurora.agent_safety import proposal_diagnostics, commit_multiplicity_diagnostics
from aurora.agent_tasks import TaskHost, task_for, FAMILIES, FAMILY_GROUPS
from aurora.artifacts import atomic_json, digest, immutable_json
from aurora.resources import check_gpu_room, cuda_lease, storage_admission
from aurora.studies import Study
from agent_study import agent_allocation_used_seconds, data_files, load_model, thermal_check


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-directory", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    study = Study(ROOT, "e15_agent_confirmation")
    allowed = (ROOT / "reports/agent", study.runtime / "runs")
    freeze, freeze_ref = verified_pointer(ROOT / "reports/agent/FINAL_AGENT_FREEZE.json", allowed)
    if freeze["status"] != "FINAL_AGENT_FROZEN_BEFORE_MODEL_SCORING" or freeze["scientific_status"] != "UNDERPOWERED":
        raise ValueError("Actual prospective final-agent freeze required")
    if study.ledger.read()["nodes"]["E15_AGENT_FREEZE"]["execution_status"] != "EXECUTED":
        raise ValueError("Frozen track dependency not executed")
    for relative, sha in {**freeze["code_sha256"], **freeze["config_sha256"]}.items():
        if digest(owned_file(ROOT / relative, (ROOT,))) != sha:
            raise ValueError("Frozen final evaluation source/config changed: " + relative)
    packages = sorted(f"{item.metadata['Name']}=={item.version}" for item in importlib.metadata.distributions())
    if freeze["environment"] != {"python": sys.version, "packages": packages}:
        raise ValueError("Exact frozen project-scoped Python/dependency environment changed")
    for absolute, sha in freeze["original_a1_provider_files_sha256"].items():
        if digest(owned_file(Path(absolute), (ROOT / "reports", study.runtime / "runs"))) != sha:
            raise ValueError("Original frozen A1 numerical provider changed")
    for absolute, sha in freeze["actual_pinned_model_files_sha256"].items():
        if digest(owned_file(Path(absolute), (study.runtime,))) != sha:
            raise ValueError("Pinned actual model/tokenizer/chat-template changed")
    corpus = data_files()
    if corpus["sha256"] != freeze["corpus_sha256"]:
        raise ValueError("Frozen training corpus identity changed")
    admission_path = Path(freeze["model_admission"]["artifact"])
    if digest(owned_file(admission_path, allowed)) != freeze["model_admission"]["sha256"]:
        raise ValueError("Pinned 4B model admission changed")
    admission = json.loads(admission_path.read_text())
    if admission["revision"] != freeze["revision"]:
        raise ValueError("Model revision mismatch")
    cases = tuple(AgentCase(**item) for item in freeze["cases"])
    mapping = freeze["workflow_groups"]
    for case in cases:
        if FAMILIES[case.workflow][0] != "final" or FAMILY_GROUPS[case.workflow] != case.semantic_group or mapping[case.workflow] != case.semantic_group:
            raise ValueError("Final roster differs from frozen executable semantic split")
    # Resolve only the frozen artifact paths, never a mutable LATEST checkpoint.
    checkpoints = {}
    for key, reference in freeze["training_reports"].items():
        path = owned_file(Path(reference["artifact"]), allowed)
        if digest(path) != reference["sha256"]:
            raise ValueError("Frozen actual training report changed")
        parent = json.loads(path.read_text())
        verified_checkpoint(parent, study.runtime)
        checkpoints[key] = parent["checkpoint"]
    for reference in freeze["inference_qualifications"].values():
        if digest(owned_file(Path(reference["artifact"]), allowed)) != reference["sha256"]:
            raise ValueError("Frozen inference qualification changed")
    evaluation_directory = study.directory
    if args.resume_directory:
        candidate = args.resume_directory
        if candidate.is_symlink() or not candidate.resolve().is_relative_to(study.runtime / "runs") or not candidate.name.startswith("e15_agent_confirmation_"):
            raise ValueError("Resume only an owned same-freeze evaluation directory")
        resume = json.loads(owned_file(candidate / "run_identity.json", (study.runtime / "runs",)).read_text())
        if resume["freeze_sha256"] != freeze_ref["sha256"]:
            raise ValueError("Do not mix independent freezes or move inspected finals into development")
        evaluation_directory = candidate
    identity = {"freeze_sha256": freeze_ref["sha256"], "freeze_artifact": freeze_ref["artifact"], "evaluation_directory": str(evaluation_directory)}
    if not (evaluation_directory / "run_identity.json").exists():
        atomic_json(evaluation_directory / "run_identity.json", identity)
    prior = agent_allocation_used_seconds()
    cap = json.loads((ROOT / "config/resources.json").read_text())["gpu_hours_caps"]["agent"] * 3600
    report = {"status": "RUNNING", "passed": False, "freeze": freeze_ref, "run_identity": identity,
        "model": admission["repo_id"], "revision": admission["revision"], "scientific_status": "UNDERPOWERED",
        "case_count_per_arm_seed": len(cases), "independent_family_count": len(set(mapping.values())),
        "training_seeds": freeze["training_seeds"], "arms": freeze["arms"], "completed": 0,
        "expected_case_seed_arm_records": len(cases) * len(freeze["training_seeds"]) * len(freeze["arms"]),
        "results": [], "comparisons": {}, "telemetry": [], "final_model_reselection": False,
        "allocation_accounting": {"prior_completed_full_wall_seconds": prior, "cap_seconds": cap},
        "tool_transport": "typed frozen in-process host; MCP transport qualification is separate, not claimed as per-task network execution"}
    device_qualification = freeze["device_qualification"]
    if digest(owned_file(Path(device_qualification["artifact"]), (ROOT / "reports/environment",))) != device_qualification["sha256"]:
        raise ValueError("Frozen device guidance/qualification changed; do not silently weaken target")
    target = device_qualification["device_reported_target_c"]
    resources = json.loads((ROOT / "config/resources.json").read_text())
    report["storage_admission"] = storage_admission(study.runtime, ROOT, expected_growth_bytes=freeze["expected_scoring_growth_bytes"], contract=resources)
    def health():
        if prior + time.perf_counter() - started >= cap:
            raise RuntimeError("Unchanged full-wall agent allocation exhausted; preserve partial final records")
        if min(shutil.disk_usage(ROOT).free, shutil.disk_usage(study.runtime).free) < resources["backing_disk_min_free_gib"] * 1024**3:
            raise RuntimeError("Declared filesystem reserve no longer maintained; stop without deleting unrelated data")
        thermal_check(report["telemetry"], target)
    def settle():
        health()
        time.sleep(freeze["common_duty_pause_seconds"])
    outcomes = {recipe: [] for recipe in freeze["arms"]}
    model = None
    try:
        allocation_gib = 8 if admission["repo_id"] == "Qwen/Qwen3-1.7B" else 10
        report["telemetry"].append(check_gpu_room(allocation_gib))
        study.ledger.update("E15_AGENT", "RUNNING", science="UNDERPOWERED", reason="Actual frozen final scoring; no selection")
        study.export_state()
        with cuda_lease(study.runtime):
            for recipe in freeze["arms"]:
                for seed in freeze["training_seeds"]:
                    health()
                    adapter = None if recipe == "prompt_only" else checkpoints[f"{recipe}_seed{seed}"]
                    model, tokenizer = load_model(admission, allocation_gib, seed, adapter)
                    generator = LocalGenerator(model, tokenizer, records=evaluation_directory / "raw_generations" / f"{recipe}_seed{seed}", before_generation=health, after_generation=settle)
                    for case in cases:
                        task = task_for(case.workflow, int(case.identity.rsplit("_", 1)[1]))
                        if task.task_id != case.identity:
                            raise ValueError("Final task identity differs from frozen roster")
                        path = evaluation_directory / "case_records" / f"{recipe}_seed{seed}__{case.identity}.json"
                        marker = path.with_suffix(".attempt.json")
                        interruption = None
                        if path.exists():
                            record, _ = verified_pointer(path, (study.runtime / "runs",))
                            if record["freeze_sha256"] != freeze_ref["sha256"] or record["recipe"] != recipe or record["training_seed"] != seed:
                                raise ValueError("Saved final record provenance mismatch")
                            result = record["result"]
                        else:
                            if marker.exists():
                                raise ValueError("Interrupted orphan attempt exists; preserve/reconcile actual trace and ledger, never silently replay or fabricate a result")
                            health()
                            namespace = evaluation_directory.name + f"_{recipe}_seed{seed}"
                            atomic_json(marker, {"case": asdict(case), "recipe": recipe, "seed": seed, "freeze_sha256": freeze_ref["sha256"], "host_namespace": namespace, "attempt_started_at_unix": time.time()})
                            begin = time.perf_counter()
                            host = TaskHost(task, study.runtime, namespace)
                            host_setup_seconds = time.perf_counter() - begin
                            generation_start = len(generator.measurements)
                            result, interruption = recorded_attempt(task, host, generator)
                            result["complete_task_wall_seconds"] = time.perf_counter() - begin
                            result["host_fixture_setup_wall_seconds_included"] = host_setup_seconds
                            result["proposal_diagnostics"] = proposal_diagnostics(result)
                            result["commit_multiplicity_diagnostics"] = commit_multiplicity_diagnostics(result)
                            snapshot = snapshot_agent_ledger(host.state.path, evaluation_directory / "ledger_snapshots" / f"{recipe}_seed{seed}__{case.identity}.sqlite", study.runtime)
                            record = {"freeze_sha256": freeze_ref["sha256"], "recipe": recipe, "training_seed": seed,
                                "result": result, "interruption": interruption,
                                "ledger_snapshot": snapshot, "host_tenant": host.tenant,
                                "generation_records": generator.measurements[generation_start:]}
                            blob = immutable_json(evaluation_directory / "case_blobs", record)
                            atomic_json(path, {"artifact": str(blob), "sha256": digest(blob)})
                        snapshot = record["ledger_snapshot"]
                        ledger_path = owned_file(Path(snapshot["path"]), (study.runtime / "runs",))
                        if digest(ledger_path) != snapshot["sha256"]:
                            raise ValueError("Saved actual ledger snapshot changed")
                        independent = read_agent_ledger(ledger_path, record["host_tenant"], study.runtime)
                        if record["host_tenant"] != evaluation_directory.name + f"_{recipe}_seed{seed}:" + task.task_id:
                            raise ValueError("Saved task tenant differs from fixed host namespace")
                        reconcile_saved_actions(result, independent, expected_commits(task))
                        outcome, multiplicity = admit_saved_result(result, case, asdict(task), seed)
                        outcomes[recipe].append(outcome)
                        report["results"].append({"recipe": recipe, "training_seed": seed, "case": asdict(case), "artifact": str(path), "sha256": digest(path), "success": outcome.success, "interruption": record["interruption"], "commit_multiplicity": multiplicity})
                        report["completed"] += 1
                        atomic_json(study.directory / "progress.json", report)
                        if interruption is not None:
                            raise RuntimeError("Resource/application interruption retained as an actual failed attempt; remaining cases unattempted")
                        health()
                    del model, tokenizer
                    model = None
                    gc.collect()
                    import torch
                    torch.cuda.empty_cache()
            # Prompt-only self-summary is explicitly an identity check, never
            # advertised as model improvement when no learned arm qualifies.
            report["prompt_only_summary"] = matched_agent_comparison(cases, freeze["training_seeds"], mapping, outcomes["prompt_only"], outcomes["prompt_only"], prospective_status="UNDERPOWERED", bootstrap_draws=freeze["bootstrap_draws"], bootstrap_seed=freeze["bootstrap_seed"])
            report["prompt_only_summary"]["comparison_scope"] = "prompt-only identity summary; not a superiority comparison"
            for recipe in freeze["arms"]:
                if recipe != "prompt_only":
                    report["comparisons"][recipe] = matched_agent_comparison(cases, freeze["training_seeds"], mapping, outcomes[recipe], outcomes["prompt_only"], prospective_status="UNDERPOWERED", bootstrap_draws=freeze["bootstrap_draws"], bootstrap_seed=freeze["bootstrap_seed"])
            report.update(status="FROZEN_AGENT_CONFIRMATION_EXECUTED", passed=True,
                limitations=["Nine convenience dependence groups; UNDERPOWERED regardless of favorable contrasts", "Seeds/templates do not add independent units", "Zero wrong commits does not establish zero unsafe proposals", "Synthetic local mock task outcomes are not production advertising impact", "All retained unsuccessful and host-blocked outcomes remain in matched roster"])
    except Exception as error:
        report.update(status="INCOMPLETE_FROZEN_AGENT_CONFIRMATION", diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    finally:
        del model
        gc.collect()
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/agent" / (study.name + ".json")
    if report["passed"]:
        artifact = study.finish("E15_AGENT", report, "agent", science="UNDERPOWERED", capabilities={"frozen_agent_roster_executed": True})
        atomic_json(ROOT / "reports/agent/FINAL_AGENT_RESULT.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    else:
        atomic_json(study.directory / "result.json", report)
        atomic_json(artifact, report)
        if study.ledger.read()["nodes"]["E15_AGENT"]["execution_status"] == "RUNNING":
            study.ledger.update("E15_AGENT", "CHECKPOINTED", science="UNDERPOWERED", artifacts=(artifact,), reason="Partial actual frozen scoring; missing cases are not fabricated/drop-filtered")
            study.export_state()
    print(json.dumps({"status": report["status"], "artifact": str(artifact), "completed": report["completed"], "expected": report["expected_case_seed_arm_records"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
