#!/usr/bin/env python3
"""Terminal-only saved-result JSON handoff; no predictions, final rescoring or CSV authoring."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.completion import completion_matrix
from aurora.final_evidence import EVIDENCE_CLASSES, core_empirical_complete, final_reporting_gate, saved_record, unavailable_record
from aurora.studies import Study
from serving_study import active_project_compute

PUBLIC_INPUTS = {
    "R1": "reports/model/e15_r1_confirmation_1790881991684526040.json",
    "R2": "reports/causal/e04_assignment_replication_1790881140397659915.json",
    "R4": "reports/ope/e05_fixed_policy_ope_1790880719890434701.json",
}


def checked_pointer(relative: str) -> tuple[Path, dict, str]:
    pointer = json.loads((ROOT / relative).read_text())
    artifact = Path(pointer["artifact"])
    sha = digest(artifact)
    if sha != pointer["sha256"]:
        raise ValueError("Saved result pointer integrity failed: " + relative)
    return artifact, json.loads(artifact.read_text()), sha


def main() -> int:
    latest = ROOT / "reports/analysis/FINAL_EVIDENCE_BUNDLE.json"
    if latest.exists():
        raise ValueError("Existing final bundle must be verified/reused, not replaced")
    study = Study(ROOT, "terminal_saved_evidence_bundle")
    state = study.ledger.read()
    final_reporting_gate(state, active_owned_compute=active_project_compute())
    started = time.perf_counter()
    registry = json.loads((ROOT / "config/experiments.json").read_text())["nodes"]
    coverage = completion_matrix(registry, state)
    verified = {}
    for row in coverage["rows"]:
        for reference in row["artifacts"]:
            artifact = Path(reference["path"])
            resolved = artifact.resolve()
            if not resolved.is_relative_to(ROOT / "reports") and not resolved.is_relative_to(study.runtime / "runs"):
                raise ValueError("Reference outside owned evidence scope")
            if artifact.is_symlink() or not artifact.is_file() or digest(artifact) != reference["sha256"]:
                raise ValueError("Canonical artifact integrity failed")
            verified[str(artifact)] = reference["sha256"]
    records = []
    for domain, relative in PUBLIC_INPUTS.items():
        artifact = ROOT / relative
        sha = digest(artifact)
        if sha not in verified.values():
            raise ValueError("Public source report not bound by terminal ledger")
        report = json.loads(artifact.read_text())
        for index, original in enumerate(report["records"]):
            target = "UNAVAILABLE" if original["ci_lower"] is None else "estimate"
            row = saved_record(original, artifact=relative, sha256=sha, location=f"/records/{index}",
                evidence_class=EVIDENCE_CLASSES[domain], role="SECONDARY_FROZEN_BENCHMARK", interval_target=target)
            row.update(result_id=f"{domain}_record_{index}", compute="Historical run artifact; no current source hash attached retroactively")
            records.append(row)
    policy_path, policy, policy_sha = checked_pointer("reports/policy/POLICY_CONFIRMATION_RESULT.json")
    freeze_path, frozen, freeze_sha = checked_pointer("reports/policy/POLICY_CONFIRMATION_FREEZE.json")
    if policy["status"] != "FROZEN_POLICY_CONFIRMATION_EXECUTED" or policy["freeze_sha256"] != freeze_sha or policy["sample_size"] != len(frozen["worlds"]) or not policy["no_sequential_adaptation"]:
        raise ValueError("Full fixed-sample policy result must match its prospective freeze")
    if state["nodes"]["E15_POLICY"]["scientific_outcome"] != policy["scientific_outcome"]:
        raise ValueError("Policy scientific status differs from canonical ledger")
    if policy_sha not in verified.values() or freeze_sha not in verified.values():
        raise ValueError("Policy confirmation/freeze not bound by terminal ledger")
    interval = policy["analysis"]["primary_paired_complete_world"]
    policy_record = {"record_status": "MEASURED", "evidence_domain": "S1", "estimand_id": "paired_mean_completed_episode_normalized_net_value_difference",
        "comparison_id": "frozen_MSCP_vs_development_selected_conventional", "candidate": frozen["primary_candidate"]["id"],
        "baseline": frozen["primary_comparator"]["id"], "population": "Untouched fixed equal-family synthetic world mixture, frozen finite parameter catalog",
        "metric": "paired_completed_episode_utility_difference", "estimate": interval["mean"], "difference": interval["mean"],
        "unit": "normalized net utility per initial budget", "horizon": "14 decision days plus7-day maturation and declared receipt flush",
        "n_independent_units": policy["sample_size"], "independent_unit": "paired complete exogenous world; finite parameter blocks shared",
        "uncertainty_method": frozen["analysis"]["method"], "ci_lower": interval["lower"], "ci_upper": interval["upper"],
        "source_hashes": [policy["freeze_sha256"]], "config_hash": frozen["config_hashes"]["contract.json"],
        "model_calibrator_id": frozen["warmstart_pointer_sha256"] + "+" + frozen["support_pointer_sha256"],
        "scientific_outcome": policy["scientific_outcome"], "execution_status": "EXECUTED", "scope_limits": policy["limitations"],
        "missingness_handling": "Full mature episode; pending exposures checked by executed receipt validator"}
    records.append(saved_record(policy_record, artifact=str(policy_path.relative_to(ROOT)), sha256=policy_sha,
        location="/analysis/primary_paired_complete_world", evidence_class=EVIDENCE_CLASSES["S1"],
        role="PRIMARY_CONFIRMATION", interval_target="difference") | {"result_id": "S1_primary_confirmation",
        "practical_margin": frozen["analysis"]["practical_margin"], "compute_wall_seconds": policy["wall_seconds_this_invocation"],
        "planning_power": frozen["planning"]["planning_power"], "population_lift_claim": False})
    unavailable = [unavailable_record(row["node"], state["nodes"][row["node"]], evidence_class="UNAVAILABLE_" + row["evidence_domain"])
        for row in coverage["rows"] if row["node"] != "E16" and row["execution_status"] != "EXECUTED"]
    cpu_path, cpu, cpu_sha = checked_pointer("reports/serving/CPU_COMPONENT_MEASUREMENTS.json")
    if not cpu["passed"] or cpu["status"] != "CPU_COMPONENT_MEASURED_NOT_FULL_E14" or cpu["protocol"]["CUDA_execution"]:
        raise ValueError("Executed explicit CPU systems evidence required; no GPU relabeling")
    if cpu_sha not in verified.values():
        raise ValueError("CPU systems report not bound by terminal E14 disposition")
    bundle = {"status": "TERMINAL_SAVED_EVIDENCE_HANDOFF_NOT_E16_COMPLETION", "captured_generation": state["generation"],
        "captured_state": state, "coverage": coverage, "records": records, "unavailable_records": unavailable,
        "CPU_systems": {"artifact": str(cpu_path), "sha256": cpu_sha, "report": cpu},
        "verified_artifacts_sha256": verified, "policy_freeze": {"artifact": str(freeze_path), "sha256": freeze_sha},
        "completion_layers": {"CORE_TRACKS_CLOSED": True, "CORE_EMPIRICAL_COMPLETE": core_empirical_complete(registry, state),
            "production_deployment": False, "commercial_lift": False, "agent_semantic_outcomes": "UNSCORED"},
        "no_new_predictions_or_scoring": True, "final_csv_authored": False, "all_unfavorable_public_records_retained": True,
        "wall_seconds": time.perf_counter()-started, "argv": sys.argv,
        "code_sha256": {name: digest(ROOT / name) for name in ("tools/prepare_final_evidence.py", "src/aurora/final_evidence.py")},
        "limitations": ["Prepared aggregate handoff is not final-report completion or empirical qualification",
            "Historical record labels/compute metadata preserved; later source hashes are not retroactive provenance",
            "Blocked/invalid tracks forbid CORE_EMPIRICAL_COMPLETE regardless green engineering tests"]}
    artifact = ROOT / "reports/analysis" / (study.name + ".json")
    atomic_json(study.directory / "result.json", bundle)
    atomic_json(artifact, bundle)
    atomic_json(latest, {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"artifact": str(artifact), "records": len(records), "state_mutations": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
