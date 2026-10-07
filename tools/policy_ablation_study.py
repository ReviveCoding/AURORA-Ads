#!/usr/bin/env python3
"""Locked-primary development ablations and prospective mechanism OOD diagnosis."""
from __future__ import annotations

import json
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.policies import BanditController, PolicyParameters
from aurora.policy_diagnostics import DiagnosticController
from aurora.policy_support_bundle import load_weighted_bundle
from aurora.simulator import FAMILIES, OOD_MECHANISMS, StaticController, WorldSpec, run_world
from aurora.studies import Study

_BUNDLE = _TRAINING = None


def variants(parameters: dict) -> dict:
    result = {"locked_MSCP": dict(parameters)}
    for component in ("delay", "support", "uncertainty", "dual", "reliability"):
        result["remove_" + component] = parameters | {"remove_" + component: True}
    result["remove_delay_and_reliability"] = parameters | {"remove_delay": True, "remove_reliability": True}
    return result


def initialize():
    global _BUNDLE, _TRAINING
    _BUNDLE, _TRAINING, _ = load_weighted_bundle(ROOT)


def evaluate(task: dict) -> str:
    started = time.perf_counter()
    parameters = task["parameters"]
    if parameters is None:
        controller = StaticController()
    else:
        controller = DiagnosticController(_BUNDLE, PolicyParameters(**parameters), _TRAINING["x"],
            _TRAINING["action"], _TRAINING["gross"], _TRAINING["spend"] + _TRAINING["operating"])
    specification = WorldSpec(**task["world"])
    result = run_world(specification, controller, base_bid=.25 if parameters is None else 1.)
    record = {"recipe": task["recipe"], "world": task["world"],
              "evaluation": asdict(result) | {"utility": result.utility},
              "diagnostics": controller.diagnostics() if parameters is not None else None,
              "wall_seconds": time.perf_counter() - started, "not_confirmation": True,
              "no_primary_reselection": True, "evidence_class": "synthetic counterfactual development diagnosis"}
    path = Path(task["destination"])
    atomic_json(path, record)
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--qualify-only", action="store_true")
    args = parser.parse_args()
    study = Study(ROOT, "e13_policy_locked_ablations_ood")
    started = time.perf_counter()
    pointer = json.loads((ROOT / "reports/policy/CORRECTED_DEVELOPMENT_SELECTION.json").read_text())
    result_path = Path(pointer["artifact"])
    if digest(result_path) != pointer["sha256"]:
        raise ValueError("Corrected primary selection identity changed")
    selection = json.loads(result_path.read_text())
    candidate, baseline = selection["selected_MSCP"], selection["selected_conventional"]
    if candidate["id"] != "MSCP_v2_eta0.01_max5.0_beta1.0" or baseline["id"] != "static_bid0.25":
        raise ValueError("Primary recipes must remain locked")
    trace_hashes = {relative: digest(ROOT / relative) for relative in (
        "src/aurora/policy_diagnostics.py", "src/aurora/policies.py", "src/aurora/simulator.py",
        "src/aurora/policy_registry.py", "src/aurora/policy_support_bundle.py",
        "reports/policy/WARMSTART_LATEST.json", "reports/policy/SUPPORT_V2_QUALIFICATION.json")}
    if args.qualify_only:
        initialize()
        results = []
        for family in FAMILIES:
            warm = (_TRAINING["x"], _TRAINING["action"], _TRAINING["gross"], _TRAINING["spend"] + _TRAINING["operating"])
            parameters = PolicyParameters(**candidate["parameters"])
            plain = BanditController(_BUNDLE, parameters, *warm)
            traced = DiagnosticController(_BUNDLE, parameters, *warm)
            world = WorldSpec("trace-real-model-reference-" + family, family, campaigns=1, intervals=16,
                              nominal_arrivals=4, stage="smoke")
            expected, actual = run_world(world, plain), run_world(world, traced)
            if expected != actual or traced.diagnostics()["pending_predictions"]:
                raise ValueError("Real-model full-flush trace parity failed")
            results.append({"family": family, "exact_evaluation_match": True,
                            "matured_observation_count": traced.received_observation_count})
        artifact = ROOT / "reports/policy" / (study.name + "_qualification.json")
        report = {"passed": True, "code_hashes": trace_hashes, "candidate": candidate,
                  "fixtures": results, "not_scientific_efficacy": True,
                  "wall_seconds": time.perf_counter() - started, "argv": sys.argv}
        atomic_json(artifact, report)
        atomic_json(ROOT / "reports/policy/E13_TRACE_QUALIFICATION.json", {"artifact": str(artifact), "sha256": digest(artifact)})
        print(json.dumps({"artifact": str(artifact), "passed": True}))
        return 0
    trace_pointer = json.loads((ROOT / "reports/policy/E13_TRACE_QUALIFICATION.json").read_text())
    trace_path = Path(trace_pointer["artifact"])
    if digest(trace_path) != trace_pointer["sha256"]:
        raise ValueError("Trace qualification identity changed")
    trace_report = json.loads(trace_path.read_text())
    if not trace_report["passed"] or trace_report["code_hashes"] != trace_hashes or trace_report["candidate"] != candidate:
        raise ValueError("Current locked-controller tracing qualification required")
    roster = variants(candidate["parameters"])
    tasks = []
    for recipe, parameters in {**roster, "static_bid0.25": None}.items():
        for number in range(12):
            world = {"world_id": f"policy-validation-world{number}", "family": FAMILIES[number % 4],
                     "budget_per_campaign": (4000, 10000, 20000)[(number // 4) % 3],
                     "stage": "validation", "parameter_index": 16 + number}
            tasks.append({"recipe": recipe, "parameters": parameters, "world": world,
                          "destination": str(study.directory / "worlds" / f"{recipe}__development{number}.json")})
    # All five pre-existing disjoint mechanisms are fixed before any OOD result;
    # these are secondary diagnostics, never mixed into primary confirmation.
    for mechanism in sorted(OOD_MECHANISMS):
        for family in FAMILIES:
            for recipe, parameters in (("locked_MSCP", candidate["parameters"]), ("static_bid0.25", None)):
                world = {"world_id": f"e13-locked-ood-{mechanism}-{family}", "family": family,
                         "budget_per_campaign": 10000, "stage": "ood", "ood_mechanism": mechanism}
                tasks.append({"recipe": recipe, "parameters": parameters, "world": world,
                    "destination": str(study.directory / "worlds" / f"{recipe}__{mechanism}__{family}.json")})
    protocol = {"frozen_before_new_outcomes": True, "corrected_selection_sha256": pointer["sha256"],
                "candidate": candidate, "comparator": baseline, "tasks": tasks,
                "argv": sys.argv, "python": sys.version, "started_at_unix": time.time(),
                "code_hashes": {str(path.relative_to(ROOT)): digest(path)
                                for path in sorted((ROOT / "src").rglob("*.py"))},
                "script_sha256": digest(Path(__file__)),
                "config_hashes": {path.name: digest(path) for path in (ROOT / "config").glob("*.json")},
                "warmstart_pointer_sha256": digest(ROOT / "reports/policy/WARMSTART_LATEST.json"),
                "support_pointer_sha256": digest(ROOT / "reports/policy/SUPPORT_V2_QUALIFICATION.json"),
                "trace_qualification_sha256": trace_pointer["sha256"],
                "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json"),
                "workers": args.workers, "final_worlds_loaded": 0, "primary_selection_immutable": True,
                "delay_reliability_2x2": ["locked_MSCP", "remove_delay", "remove_reliability", "remove_delay_and_reliability"],
                "OOD_role": "prospectively specified secondary development diagnosis, not primary endpoint"}
    protocol_path = study.directory / "protocol_before_outcomes.json"
    atomic_json(protocol_path, protocol)
    completed = []
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=get_context("spawn"), initializer=initialize) as pool:
        for path in pool.map(evaluate, tasks):
            completed.append(path)
            progress = {"completed": len(completed), "total": len(tasks), "status": "RUNNING",
                        "runtime_directory": str(study.directory), "protocol_sha256": digest(protocol_path),
                        "last_artifact": path, "not_confirmation": True}
            atomic_json(ROOT / "reports/policy/E13_PROGRESS.json", progress)
            print(json.dumps(progress), flush=True)
    summaries = {}
    for path in completed:
        row = json.loads(Path(path).read_text())
        key = row["recipe"] + ("__" + row["world"]["ood_mechanism"] if row["world"].get("ood_mechanism") else "__development")
        summaries.setdefault(key, []).append({"world_id": row["world"]["world_id"], "family": row["world"]["family"],
                                             "utility": row["evaluation"]["utility"]})
    report = {"protocol": protocol, "protocol_sha256": digest(protocol_path), "status": "DEVELOPMENT_ABLATIONS_OOD_EXECUTED",
              "summaries": summaries, "world_artifacts": [{"path": path, "sha256": digest(Path(path))} for path in completed],
              "wall_seconds": time.perf_counter() - started, "finished_at_unix": time.time(),
              "not_confirmation": True, "primary_selection_unchanged": True,
              "limitations": ["Small development-world counts; no significance or production lift claim",
                  "Observed calibration is not incremental evaluator value calibration",
                  "Fixed bidder; no invented losing-auction market prices",
                  "OOD mechanism results are separate secondary diagnostics, not primary confirmation"]}
    artifact = study.finish("E13_POLICY", report, "policy", science="NOT_ESTABLISHED")
    atomic_json(ROOT / "reports/policy/E13_ABLATIONS_OOD.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"artifact": str(artifact), "completed": len(completed)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
