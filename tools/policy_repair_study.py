#!/usr/bin/env python3
"""Preserve original E09; prospective same-world cost/support correction supplement."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from multiprocessing import get_context
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from aurora.artifacts import atomic_json, digest
from aurora.policies import BanditController, PolicyParameters
from aurora.policy_registry import load_bundle
from aurora.policy_support_bundle import load_weighted_bundle
from aurora.simulator import FAMILIES, Snapshot, WorldSpec, run_world
from aurora.state import SCALE
from aurora.studies import Study

ORIGINAL_PROTOCOL_SHA = "c1a5cde6c47e7942e67e4ccb192d8dc0a49ab3b8de1bbf28a9b6cd7a0c80cddf"
COST_METHODS = {"epsilon_greedy", "LinUCB", "neural_linear_TS", "delay_TS_primal_dual", "support_gated_delay_TS"}
SUPPORT_METHODS = {"support_gated_delay_TS", "MSCP_v2"}
_BUNDLE = _TRAINING = None


def original_result():
    pointer = json.loads((ROOT / "reports/policy/DEVELOPMENT_SELECTION.json").read_text())
    artifact = Path(pointer["artifact"])
    if digest(artifact) != pointer["sha256"]:
        raise ValueError("Original development result changed")
    report = json.loads(artifact.read_text())
    directory = Path(report["runtime_directory"])
    protocol = directory / "development_protocol.json"
    if digest(protocol) != ORIGINAL_PROTOCOL_SHA or len(report["world_artifact_manifest"]) != 540:
        raise ValueError("Not the completed original540-world sweep")
    for item in report["world_artifact_manifest"]:
        if digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Original world artifact changed")
    # Discover the wrapper by its child argv and result-directory identity,
    # never assume a timestamp guessed by this script is the executed wrapper.
    terminals = []
    for path in (ROOT / "reports/execution").glob("execution_policy_study_*/execution.json"):
        item = json.loads(path.read_text())
        if item.get("exit_code") == 0 and item.get("status") == "EXECUTED" and item.get("inputs_sha256", {}).get("src/aurora/policies.py") == report["protocol"]["controller_sha256"] and "development" in item["command"]:
            terminals.append(path)
    if len(terminals) != 1:
        raise ValueError("One actual successful original terminal wrapper required")
    terminal = terminals[0]
    return pointer, report, terminal


def archive(study):
    pointer, original, terminal = original_result()
    expected = {"src/aurora/policies.py": "controller_sha256", "src/aurora/simulator.py": "simulator_sha256", "src/aurora/policy_registry.py": "registry_sha256", "tools/policy_study.py": "script_sha256", "reports/policy/WARMSTART_LATEST.json": "warmstart_sha256"}
    records = {}
    for relative, key in expected.items():
        source = ROOT / relative
        if digest(source) != original["protocol"][key]:
            raise ValueError(f"Original source changed before archive: {relative}")
        destination = study.directory / "original_evidence" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o444)
        records[relative] = {"path": str(destination), "sha256": digest(destination)}
    report = {"status": "ORIGINAL_E09_TERMINAL_SOURCE_PRESERVED", "passed": True, "original_result": pointer, "original_terminal": {"path": str(terminal), "sha256": digest(terminal)}, "original_protocol_sha256": ORIGINAL_PROTOCOL_SHA, "original_source_evidence": records, "original_world_count": 540, "not_retroactive_full_launch_archive": True, "not_policy_confirmation": True, "wall_seconds": time.perf_counter() - study._archive_started}
    artifact = ROOT / "reports/policy" / (study.name + ".json")
    atomic_json(artifact, report)
    atomic_json(study.directory / "result.json", report)
    atomic_json(ROOT / "reports/policy/ORIGINAL_DEVELOPMENT_ARCHIVE.json", report | {"artifact": str(artifact), "sha256": digest(artifact)})
    return artifact


def verify_archive():
    pointer = json.loads((ROOT / "reports/policy/ORIGINAL_DEVELOPMENT_ARCHIVE.json").read_text())
    if not pointer["passed"] or digest(Path(pointer["artifact"])) != pointer["sha256"]:
        raise ValueError("Original archive report identity failed")
    for item in pointer["original_source_evidence"].values():
        if digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Original archived bytes changed")
    return pointer


def unaffected_compatibility(archived):
    path = Path(archived["original_source_evidence"]["src/aurora/policies.py"]["path"])
    specification = importlib.util.spec_from_file_location("aurora._original_policy_evidence", path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    original_bundle, _, _ = load_bundle(ROOT)
    repaired_bundle, _, _ = load_weighted_bundle(ROOT)
    outputs = []
    for method in ("rule_PID", "MPC_pacing"):
        old = module.BanditController(original_bundle, module.PolicyParameters(method))
        new = BanditController(repaired_bundle, PolicyParameters(method))
        for number in range(100):
            budget = (4000, 10000, 20000)[number % 3]
            charged = budget * SCALE * (number % 10) // 10
            snapshot = Snapshot(13 * number, number % 8, budget * SCALE - charged, charged, number, number * 20., number, number * 10., 40, initial_budget_units=budget * SCALE, last_spend_units=(number % 8) * SCALE, last_supply=32, last_wins=16, last_auction_losses=16, pending_age_counts=(5,) * 8)
            if old.choose(snapshot) != new.choose(snapshot):
                raise ValueError("An allegedly unaffected PID/MPC action differs")
        outputs.append({"method": method, "matched_public_fixtures": 100})
    return {"static_physics_sha256_unchanged": True, "PID_MPC_action_fixtures": outputs, "not_new_world_outcomes": True}


def initialize_worker():
    global _BUNDLE, _TRAINING
    _BUNDLE, _TRAINING, _ = load_weighted_bundle(ROOT)


def evaluate(argument):
    recipe, number, directory = argument
    started = time.perf_counter()
    controller = BanditController(_BUNDLE, PolicyParameters(**recipe["parameters"]), _TRAINING["x"], _TRAINING["action"], _TRAINING["gross"], _TRAINING["spend"] + _TRAINING["operating"])
    specification = WorldSpec(f"policy-validation-world{number}", FAMILIES[number % 4], budget_per_campaign=(4000, 10000, 20000)[(number // 4) % 3], stage="validation", parameter_index=16 + number)
    result = run_world(specification, controller)
    record = {"recipe": recipe, "world_number": number, "stage": "validation", "evaluation": asdict(result) | {"utility": result.utility}, "wall_seconds": time.perf_counter() - started, "observed_reward_updates": controller.received_observation_count, "unit": "completed independent synthetic world", "controller_seed": recipe["parameters"]["seed"], "not_one_step_OPE": True, "correction_supplement": True}
    path = Path(directory) / f"{recipe['id']}__world{number}.json"
    atomic_json(path, record)
    return str(path)


def development(study):
    archived = verify_archive()
    pointer, original, _ = original_result()
    protocol = original["protocol"]
    for relative, key in (("src/aurora/simulator.py", "simulator_sha256"), ("src/aurora/policy_registry.py", "registry_sha256"), ("reports/policy/WARMSTART_LATEST.json", "warmstart_sha256")):
        if digest(ROOT / relative) != protocol[key]:
            raise ValueError("Same-world supplement requires unchanged physics and original warmstart")
    if digest(ROOT / "src/aurora/policies.py") == protocol["controller_sha256"]:
        raise ValueError("Cost correction has not been integrated")
    compatibility = unaffected_compatibility(archived)
    affected = [r for r in protocol["recipes"] if r.get("parameters", {}).get("name") in COST_METHODS | SUPPORT_METHODS]
    if len(affected) != 33:
        raise ValueError("Unexpected correction roster")
    supplement = {"frozen_before_supplement_outcomes": True, "original_protocol_sha256": ORIGINAL_PROTOCOL_SHA, "original_result_sha256": pointer["sha256"], "recipes": affected, "worlds": 12, "world_ids_and_shocks": "same original policy-validation-world0..11, unchanged physics/blocks/budgets", "controller_sha256": digest(ROOT / "src/aurora/policies.py"), "support_sha256": digest(ROOT / "reports/policy/SUPPORT_V2_QUALIFICATION.json"), "supplement_script_sha256": digest(Path(__file__)), "correction_selection": "same equal-world utility/deterministic ID tie rule, all corrected and unaffected candidates; no final access", "unaffected_reuse": compatibility, "common_mechanics": protocol["common_guards"], "not_fast_bidder_qualification": True}
    atomic_json(study.directory / "supplement_protocol.json", supplement)
    study.ledger.update("E09", "RUNNING", capabilities={"POLICY_SCORE_UNITS_QUALIFIED": False, "POLICY_SUPPORT_QUALIFIED": False}, reason="Original sweep preserved; same-world33-recipe cost/support development supplement, no final outcomes")
    study.export_state()
    directory = study.directory / "world_results"
    directory.mkdir()
    completed = []
    tasks = [(recipe, number, str(directory)) for recipe in affected for number in range(12)]
    # Parent compatibility fixtures initialize native OpenMP/Torch pools;
    # fresh spawn avoids inheriting their locks into forked workers.
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn"), initializer=initialize_worker) as pool:
        for path in pool.map(evaluate, tasks):
            completed.append(path)
            atomic_json(ROOT / "reports/policy/REPAIR_PROGRESS.json", {"status": "RUNNING", "runtime_directory": str(study.directory), "completed": len(completed), "total": len(tasks), "protocol_sha256": digest(study.directory / "supplement_protocol.json"), "last_artifact": path, "not_final_outcomes": True})
    summaries = dict(original["summaries"])
    for recipe in affected:
        rows = [json.loads((directory / f"{recipe['id']}__world{n}.json").read_text()) for n in range(12)]
        utilities = np.array([row["evaluation"]["utility"] for row in rows])
        summaries[recipe["id"]] = {"mean_completed_utility": float(utilities.mean()), "per_world": utilities.tolist(), "per_family": {f: float(utilities[np.arange(12) % 4 == i].mean()) for i, f in enumerate(FAMILIES)}, "per_budget": {str(b): float(utilities[(np.arange(12) // 4) % 3 == i].mean()) for i, b in enumerate((4000, 10000, 20000))}, "correction_supplement": True}
    recipes = protocol["recipes"]
    key = lambda r: (-summaries[r["id"]]["mean_completed_utility"], r["id"])
    baseline = min([r for r in recipes if r.get("parameters", {}).get("name") != "MSCP_v2"], key=key)
    candidate = min([r for r in recipes if r.get("parameters", {}).get("name") == "MSCP_v2"], key=key)
    report = {"status": "CORRECTED_POLICY_DEVELOPMENT_NOT_CONFIRMATION", "protocol": supplement, "summaries": summaries, "selected_conventional": baseline, "selected_MSCP": candidate, "original_result": pointer, "world_artifact_manifest": [{"path": p, "sha256": digest(Path(p))} for p in completed], "reused_unaffected_recipe_ids": [r["id"] for r in recipes if r not in affected], "not_final_worlds": True, "limitations": ["Only12 development worlds, no scientific confirmation", "Original agent provider/warmstart unchanged; support adapter is numerical-policy only", "Fixed-bid kernel only; learned-bidder nuisance applicability still unqualified", "Residual-scale support uncertainty is heuristic, not calibrated causal confidence"]}
    artifact = study.finish("E09", report, "policy", capabilities={"POLICY_SCORE_UNITS_QUALIFIED": True, "POLICY_SUPPORT_QUALIFIED": True})
    atomic_json(ROOT / "reports/policy/CORRECTED_DEVELOPMENT_SELECTION.json", report | {"artifact": str(artifact), "sha256": digest(artifact)})
    atomic_json(ROOT / "reports/policy/REPAIR_PROGRESS.json", {"status": "EXECUTED", "completed": len(completed), "total": len(tasks), "artifact": str(artifact), "not_final_outcomes": True})
    return artifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["archive", "development"], required=True)
    args = parser.parse_args()
    study = Study(ROOT, "e09_policy_repair_" + args.stage)
    study._archive_started = time.perf_counter()
    artifact = archive(study) if args.stage == "archive" else development(study)
    print(json.dumps({"artifact": str(artifact), "stage": args.stage}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
