#!/usr/bin/env python3
"""Freeze locked primary policies and fixed final world identities, without scoring."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest, immutable_json
from aurora.policy_confirmation import verify_pilot_inputs, world_roster
from aurora.policy_support_bundle import load_weighted_bundle
from aurora.studies import Study
from policy_pilot_study import checked_pointer


def main() -> int:
    if (ROOT / "reports/policy/POLICY_CONFIRMATION_FREEZE.json").exists():
        raise ValueError("Existing final freeze must be reused, not replaced")
    study = Study(ROOT, "e15_locked_policy_confirmation_freeze")
    state = study.ledger.read()
    if any(state["nodes"][node]["execution_status"] != "EXECUTED" for node in ("E09", "E13_POLICY")):
        raise ValueError("Required primary development and ablations incomplete")
    pilot_pointer, pilot = checked_pointer("reports/policy/PILOT_SAMPLE_SIZE.json")
    selection_pointer, selection = checked_pointer("reports/policy/CORRECTED_DEVELOPMENT_SELECTION.json")
    ablation_pointer, ablations = checked_pointer("reports/policy/E13_ABLATIONS_OOD.json")
    if pilot["final_worlds_loaded"] or not pilot["primary_selection_unchanged"] or not ablations["primary_selection_unchanged"]:
        raise ValueError("Pilot/selection firewall violated")
    if pilot["protocol"]["corrected_selection_sha256"] != selection_pointer["sha256"] or pilot["protocol"]["completed_ablation_sha256"] != ablation_pointer["sha256"]:
        raise ValueError("Pilot did not bind current primary evidence")
    verify_pilot_inputs(ROOT, pilot["protocol"])
    candidate, comparator = selection["selected_MSCP"], selection["selected_conventional"]
    if candidate["id"] != "MSCP_v2_eta0.01_max5.0_beta1.0" or comparator["id"] != "static_bid0.25":
        raise ValueError("No outcome-driven primary reselection")
    for relative, sha in pilot["protocol"]["source_hashes"].items():
        if digest(ROOT / relative) != sha:
            raise ValueError("Code changed after pilot: " + relative)
    for name, sha in pilot["protocol"]["config_hashes"].items():
        if digest(ROOT / "config" / name) != sha:
            raise ValueError("Configuration changed after pilot")
    physics = ROOT / "reports/simulator/full_horizon_bidder_physics_qualification_1790934777168734343.json"
    physics_report = json.loads(physics.read_text())
    if physics_report["status"] != "FULL_HORIZON_PHYSICS_COMPATIBILITY_PASSED" or physics_report["current_simulator_sha256"] != digest(ROOT / "src/aurora/simulator.py"):
        raise ValueError("Current physics compatibility not established")
    _, _, warm = load_weighted_bundle(ROOT)  # actual model/support/checkpoint hash validation
    manifest = {"frozen": True, "frozen_at_unix": time.time(), "argv": sys.argv,
        "primary_candidate": candidate, "primary_comparator": comparator,
        "corrected_development_sha256": selection_pointer["sha256"],
        "ablations_sha256": ablation_pointer["sha256"], "pilot_sha256": pilot_pointer["sha256"],
        "planning": pilot["planning"], "worlds": world_roster("final", pilot["planning"]["selected_worlds"]),
        "simulator_sha256": digest(ROOT / "src/aurora/simulator.py"),
        "current_physics": {"path": str(physics), "sha256": digest(physics)},
        "source_hashes": pilot["protocol"]["source_hashes"], "config_hashes": pilot["protocol"]["config_hashes"],
        "tool_hashes": {relative: digest(ROOT / relative) for relative in (
            "tools/freeze_policy_confirmation.py", "tools/policy_pilot_study.py", "tools/policy_confirmation_study.py")},
        "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json"),
        "warmstart_pointer_sha256": digest(ROOT / "reports/policy/WARMSTART_LATEST.json"),
        "support_pointer_sha256": digest(ROOT / "reports/policy/SUPPORT_V2_QUALIFICATION.json"),
        "warmstart_model_identities": warm["model_fits"], "training_cohort_identity": warm["cohort_artifacts"]["train"],
        "incident_detector_pointer_sha256": digest(ROOT / "reports/incidents/DETECTOR_FREEZE.json"),
        "analysis": {"method": "equal-family paired complete-world bootstrap", "draws": 10000,
            "bootstrap_seed": 514, "confidence": .95, "practical_margin": .01,
            "parameter_block_sensitivity": "equal block-weight within family, separately labeled",
            "underpowered_rule": "Retain prospective UNDERPOWERED if planning power below0.8 at cap"},
        "controller_seeds": {"candidate": candidate["parameters"]["seed"], "comparator": "deterministic"},
        "bidder_mode": "fixed bid, MSCP1.0 versus validation-selected static0.25",
        "mechanics": json.loads((ROOT / "config/contract.json").read_text())["policy"],
        "numerical_state": "existing24-field public state; no25-field bidder extension",
        "final_outcomes_loaded": 0, "evidence_class": "synthetic counterfactual policy result"}
    frozen = immutable_json(study.directory / "freeze", manifest)
    export = ROOT / "reports/policy" / (study.name + ".json")
    atomic_json(export, manifest)
    atomic_json(ROOT / "reports/policy/POLICY_CONFIRMATION_FREEZE.json", {"artifact": str(frozen), "sha256": digest(frozen), "export": str(export)})
    study.ledger.update("E15_POLICY_FREEZE", "EXECUTED", artifacts=(frozen, export),
                        capabilities={"POLICY_FINAL_FROZEN": True}, reason="No final outcomes scored; fixed sample and locked recipes")
    study.export_state()
    print(json.dumps({"freeze": str(frozen), "worlds": len(manifest["worlds"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
