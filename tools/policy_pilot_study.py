#!/usr/bin/env python3
"""Excluded20-world variance pilot; never opens final worlds or reselects policy."""
from __future__ import annotations

import json
import argparse
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from aurora.artifacts import atomic_json, digest
from aurora.inference import pilot_sample_size
from aurora.policies import BanditController, PolicyParameters
from aurora.policy_confirmation import paired_analysis, verified_pilot_record, world_roster
from aurora.policy_support_bundle import load_weighted_bundle
from aurora.simulator import StaticController, WorldSpec, run_world
from aurora.studies import Study


def checked_pointer(relative: str) -> tuple[dict, dict]:
    pointer = json.loads((ROOT / relative).read_text())
    path = Path(pointer["artifact"])
    if digest(path) != pointer["sha256"]:
        raise ValueError("Pilot input pointer changed")
    return pointer, json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", type=Path, help="Owned interrupted pilot directory; never rerun verified complete worlds")
    args = parser.parse_args()
    if (ROOT / "reports/policy/PILOT_SAMPLE_SIZE.json").exists():
        raise ValueError("Existing pilot result must be verified/reused, not rerun")
    study = Study(ROOT, "e15_policy_excluded_variance_pilot")
    state = study.ledger.read()
    if state["nodes"]["E13_POLICY"]["execution_status"] != "EXECUTED":
        raise ValueError("Finish required policy ablations before pilot planning")
    if not state["capabilities"].get("OPTIONAL_BIDDER_CURRENT_PHYSICS_QUALIFIED"):
        raise ValueError("Current physics qualification required")
    selection_pointer, selection = checked_pointer("reports/policy/CORRECTED_DEVELOPMENT_SELECTION.json")
    ablation_pointer, ablations = checked_pointer("reports/policy/E13_ABLATIONS_OOD.json")
    if not ablations["primary_selection_unchanged"]:
        raise ValueError("Primary recipe integrity failed")
    for relative in ("src/aurora/policies.py", "src/aurora/simulator.py", "src/aurora/state.py",
                     "src/aurora/measurement.py", "src/aurora/incidents.py", "src/aurora/support.py",
                     "src/aurora/policy_score_units.py", "src/aurora/policy_registry.py",
                     "src/aurora/policy_support_bundle.py", "src/aurora/prediction.py"):
        if digest(ROOT / relative) != ablations["protocol"]["code_hashes"][relative]:
            raise ValueError("Primary kernel changed after required E13 work: " + relative)
    candidate = selection["selected_MSCP"]
    if candidate["id"] != "MSCP_v2_eta0.01_max5.0_beta1.0" or selection["selected_conventional"]["id"] != "static_bid0.25":
        raise ValueError("Primary locked recipes only")
    roster = world_roster("pilot", 20)
    contract = json.loads((ROOT / "config/contract.json").read_text())["policy"]
    protocol = {"frozen_before_pilot_outcomes": True, "worlds": roster,
        "candidate": candidate, "comparator": selection["selected_conventional"],
        "corrected_selection_sha256": selection_pointer["sha256"],
        "completed_ablation_sha256": ablation_pointer["sha256"], "contract": contract,
        "source_hashes": {str(path.relative_to(ROOT)): digest(path) for path in sorted((ROOT / "src").rglob("*.py"))},
        "config_hashes": {path.name: digest(path) for path in (ROOT / "config").glob("*.json")},
        "script_sha256": digest(Path(__file__)), "argv": sys.argv, "python": sys.version,
        "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json"),
        "warmstart_pointer_sha256": digest(ROOT / "reports/policy/WARMSTART_LATEST.json"),
        "support_pointer_sha256": digest(ROOT / "reports/policy/SUPPORT_V2_QUALIFICATION.json"),
        "incident_detector_pointer_sha256": digest(ROOT / "reports/incidents/DETECTOR_FREEZE.json"),
        "started_at_unix": time.time(), "final_worlds_loaded": 0, "workers": 1,
        "scope": "Variance-only sample-size planning, no policy reselection"}
    if args.resume:
        resumed = args.resume.resolve()
        if resumed.parent != (study.runtime / "runs").resolve() or not resumed.name.startswith("e15_policy_excluded_variance_pilot_"):
            raise ValueError("Only owned pilot directories may resume")
        previous = json.loads((resumed / "protocol_before_outcomes.json").read_text())
        for key in ("worlds", "candidate", "comparator", "corrected_selection_sha256",
                    "completed_ablation_sha256", "contract", "source_hashes", "config_hashes",
                    "script_sha256", "environment_lock_sha256", "warmstart_pointer_sha256", "support_pointer_sha256",
                    "incident_detector_pointer_sha256"):
            if previous[key] != protocol[key]:
                raise ValueError("Interrupted pilot scientific/runtime identity changed: " + key)
        study.directory, study.name, protocol = resumed, resumed.name, previous
    protocol_path = study.directory / "protocol_before_outcomes.json"
    if not args.resume:
        atomic_json(protocol_path, protocol)
    started = time.perf_counter()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    bundle, training, _ = load_weighted_bundle(ROOT)
    pairs, artifacts = [], []
    for number, world in enumerate(roster):
        pair = {}
        for arm in ("static_bid0.25", "locked_MSCP"):
            path = study.directory / "worlds" / f"{number}__{arm}.json"
            receipt = path.with_suffix(".receipt.json")
            if path.exists():
                record = verified_pilot_record(path, world, arm, digest(protocol_path))
                artifacts.append({"path": str(path), "sha256": digest(path)})
                pair[arm] = record["evaluation"]["utility"]
                continue
            controller = StaticController() if arm == "static_bid0.25" else BanditController(
                bundle, PolicyParameters(**candidate["parameters"]), training["x"], training["action"],
                training["gross"], training["spend"] + training["operating"])
            result = run_world(WorldSpec(**world), controller, base_bid=.25 if arm == "static_bid0.25" else 1.)
            record = {"arm": arm, "world": world, "evaluation": asdict(result) | {"utility": result.utility},
                      "excluded_from_confirmation": True, "protocol_sha256": digest(protocol_path)}
            atomic_json(path, record)
            atomic_json(receipt, {"sha256": digest(path)})
            verified_pilot_record(path, world, arm, digest(protocol_path))
            artifacts.append({"path": str(path), "sha256": digest(path)})
            pair[arm] = result.utility
        pairs.append(pair)
        atomic_json(ROOT / "reports/policy/PILOT_PROGRESS.json", {"completed_pairs": len(pairs),
            "total_pairs": 20, "directory": str(study.directory), "protocol_sha256": digest(protocol_path)})
    candidate_values = np.array([pair["locked_MSCP"] for pair in pairs])
    baseline_values = np.array([pair["static_bid0.25"] for pair in pairs])
    planning = pilot_sample_size(candidate_values - baseline_values,
        minimum=contract["final_worlds_min"], maximum=contract["final_worlds_max"],
        alternative=contract["planning_alternative_normalized"], null_boundary=contract["practical_margin_normalized"])
    report = {"status": "EXCLUDED_PILOT_COMPLETE_NOT_POLICY_FREEZE", "protocol": protocol,
        "protocol_sha256": digest(protocol_path), "pairs": pairs, "world_artifacts": artifacts,
        "planning": planning, "pilot_diagnostics": paired_analysis(roster, candidate_values, baseline_values),
        "wall_seconds": time.perf_counter() - started, "finished_at_unix": time.time(),
        "final_worlds_loaded": 0, "primary_selection_unchanged": True}
    artifact = ROOT / "reports/policy" / f"{study.name}.json"
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/policy/PILOT_SAMPLE_SIZE.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    previous = state["nodes"]["E15_POLICY_FREEZE"]
    retained = tuple(Path(item["path"]) for item in previous["artifacts"])
    study.ledger.update("E15_POLICY_FREEZE", "CHECKPOINTED", artifacts=retained + (artifact,),
        reason="Excluded pilot fixed sample size; complete manifest freeze still required",
        capabilities={"POLICY_PILOT_COMPLETE": True})
    study.export_state()
    print(json.dumps({"artifact": str(artifact), "planning": planning}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
