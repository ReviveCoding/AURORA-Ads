#!/usr/bin/env python3
"""Fixed-sample untouched paired complete-world confirmation, with verified resume."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from aurora.artifacts import atomic_json, digest
from aurora.policies import BanditController, PolicyParameters
from aurora.policy_confirmation import paired_analysis, verified_episode_record
from aurora.policy_support_bundle import load_weighted_bundle
from aurora.simulator import StaticController, WorldSpec, run_world
from aurora.studies import Study


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    if (ROOT / "reports/policy/POLICY_CONFIRMATION_RESULT.json").exists():
        raise ValueError("Completed confirmation must not be rerun")
    pointer = json.loads((ROOT / "reports/policy/POLICY_CONFIRMATION_FREEZE.json").read_text())
    frozen = Path(pointer["artifact"])
    if digest(frozen) != pointer["sha256"]:
        raise ValueError("Final freeze integrity failed")
    manifest = json.loads(frozen.read_text())
    if not manifest["frozen"] or manifest["final_outcomes_loaded"]:
        raise ValueError("Prospective freeze required")
    for relative, sha in manifest["source_hashes"].items() | manifest["tool_hashes"].items():
        if digest(ROOT / relative) != sha:
            raise ValueError("Frozen code changed: " + relative)
    for name, sha in manifest["config_hashes"].items():
        if digest(ROOT / "config" / name) != sha:
            raise ValueError("Frozen configuration changed")
    for relative, key in (("reports/environment/ENVIRONMENT_LOCK.json", "environment_lock_sha256"),
                          ("reports/policy/WARMSTART_LATEST.json", "warmstart_pointer_sha256"),
                          ("reports/policy/SUPPORT_V2_QUALIFICATION.json", "support_pointer_sha256"),
                          ("reports/incidents/DETECTOR_FREEZE.json", "incident_detector_pointer_sha256")):
        if digest(ROOT / relative) != manifest[key]:
            raise ValueError("Frozen environment/model/support identity changed")
    study = Study(ROOT, "e15_locked_policy_confirmation")
    state = study.ledger.read()
    if state["nodes"]["E15_POLICY_FREEZE"]["execution_status"] != "EXECUTED":
        raise ValueError("Canonical policy freeze not committed")
    if args.resume:
        directory = args.resume.resolve()
        if directory.parent != (study.runtime / "runs").resolve() or not directory.name.startswith("e15_locked_policy_confirmation_"):
            raise ValueError("Only owned final confirmation directory may resume")
        admission = json.loads((directory / "run_admission.json").read_text())
        if admission["freeze_sha256"] != pointer["sha256"]:
            raise ValueError("Resume freeze differs")
        study.directory, study.name = directory, directory.name
    else:
        reserve = json.loads((ROOT / "config/resources.json").read_text())["backing_disk_min_free_gib"] * 2**30
        free = {"WSL": shutil.disk_usage(study.runtime).free, "Windows_backing": shutil.disk_usage(ROOT).free}
        if min(free.values()) < reserve + 2**30:
            raise ValueError("Insufficient fixed confirmation artifact headroom")
        atomic_json(study.directory / "run_admission.json", {"freeze_sha256": pointer["sha256"],
            "started_at_unix": time.time(), "argv": sys.argv, "free_bytes": free,
            "cpu_load": list(__import__("os").getloadavg()), "memory": Path("/proc/meminfo").read_text(),
            "workers": 1, "explicit_CPU_inference": True, "not_GPU_training_fallback": True})
    study.ledger.update("E15_POLICY", "RUNNING", artifacts=(frozen,), reason="Fixed untouched final worlds; no tuning or sequential sample-size adaptation")
    study.export_state()
    started = time.perf_counter()
    bundle, training, _ = load_weighted_bundle(ROOT)
    pairs, artifacts = [], []
    for number, frozen_world in enumerate(manifest["worlds"]):
        world = frozen_world | {"final_manifest": str(frozen)}
        pair = {}
        for arm in ("static_bid0.25", "locked_MSCP"):
            path = study.directory / "worlds" / f"{number}__{arm}.json"
            if path.exists():
                record = verified_episode_record(path, world, arm, pointer["sha256"], stage="final")
            else:
                controller = StaticController() if arm == "static_bid0.25" else BanditController(bundle,
                    PolicyParameters(**manifest["primary_candidate"]["parameters"]), training["x"], training["action"],
                    training["gross"], training["spend"] + training["operating"])
                result = run_world(WorldSpec(**world), controller, base_bid=.25 if arm == "static_bid0.25" else 1.)
                record = {"arm": arm, "world": world, "evaluation": asdict(result) | {"utility": result.utility},
                          "excluded_from_confirmation": False, "protocol_sha256": pointer["sha256"]}
                atomic_json(path, record)
                atomic_json(path.with_suffix(".receipt.json"), {"sha256": digest(path)})
                verified_episode_record(path, world, arm, pointer["sha256"], stage="final")
            artifacts.append({"path": str(path), "sha256": digest(path)})
            pair[arm] = record["evaluation"]["utility"]
        pairs.append(pair)
        atomic_json(ROOT / "reports/policy/CONFIRMATION_PROGRESS.json", {"completed_pairs": len(pairs),
            "fixed_total_pairs": len(manifest["worlds"]), "run_directory": str(study.directory),
            "freeze_sha256": pointer["sha256"], "interim_scores_not_for_decisions": True})
    candidate = np.array([pair["locked_MSCP"] for pair in pairs])
    baseline = np.array([pair["static_bid0.25"] for pair in pairs])
    analysis = paired_analysis(manifest["worlds"], candidate, baseline,
                               bootstrap_draws=manifest["analysis"]["draws"])
    interval = analysis["primary_paired_complete_world"]
    outcome = "UNDERPOWERED" if manifest["planning"]["scientific_status"] == "UNDERPOWERED" else (
        "SUPPORTED" if interval["lower"] > manifest["analysis"]["practical_margin"] else "NOT_ESTABLISHED")
    report = {"status": "FROZEN_POLICY_CONFIRMATION_EXECUTED", "freeze_sha256": pointer["sha256"],
        "pairs": pairs, "world_artifacts": artifacts, "analysis": analysis, "scientific_outcome": outcome,
        "candidate_mean": float(candidate.mean()), "baseline_mean": float(baseline.mean()),
        "negative_direction": interval["upper"] < 0, "relative_effect": None,
        "relative_effect_reason": "Near-zero comparator; absolute normalized utility remains primary",
        "sample_size": len(pairs), "no_sequential_adaptation": True, "wall_seconds_this_invocation": time.perf_counter() - started,
        "finished_at_unix": time.time(), "evidence_class": "synthetic counterfactual policy result",
        "limitations": ["Frozen finite synthetic parameter catalog, not live advertiser lift",
                        "Controller optimization seed fixed; repeated shocks do not create new mechanisms"]}
    artifact = study.finish("E15_POLICY", report, "policy", science=outcome)
    atomic_json(ROOT / "reports/policy/POLICY_CONFIRMATION_RESULT.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"artifact": str(artifact), "scientific_outcome": outcome}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
