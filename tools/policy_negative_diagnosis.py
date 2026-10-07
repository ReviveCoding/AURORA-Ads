#!/usr/bin/env python3
"""Diagnose locked negative DEVELOPMENT evidence; no tuning or final-world access."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study

BASELINE = "static_bid0.25"
CANDIDATE = "MSCP_v2_eta0.01_max5.0_beta1.0"


def decompose(candidate: dict, baseline: dict) -> dict[str, float]:
    if candidate["initial_budget"] != baseline["initial_budget"] or candidate["initial_budget"] <= 0:
        raise ValueError("Paired equal positive initial budgets required")
    budget = candidate["initial_budget"]
    purchase = (candidate["unique_purchase_value"] - baseline["unique_purchase_value"]) / budget
    no_ad = (candidate["no_ad_purchase_value"] - baseline["no_ad_purchase_value"]) / budget
    spend = (candidate["spend"] - baseline["spend"]) / budget
    operating = (candidate["operating_cost"] - baseline["operating_cost"]) / budget
    difference = purchase - no_ad - spend - operating
    if abs(difference - (candidate["utility"] - baseline["utility"])) > 1e-12:
        raise ValueError("Stored utility differs from independent cost/purchase decomposition")
    return {"purchase_value_difference_normalized": purchase,
            "no_ad_value_difference_normalized": no_ad, "ordinary_spend_difference_normalized": spend,
            "operating_cost_difference_normalized": operating, "utility_difference": difference}


def main() -> int:
    study = Study(ROOT, "e13_policy_locked_negative_development_diagnosis")
    start = time.perf_counter()
    correction_path = ROOT / "reports/policy/CORRECTED_DEVELOPMENT_SELECTION.json"
    correction = json.loads(correction_path.read_text())
    if digest(Path(correction["artifact"])) != correction["sha256"]:
        raise ValueError("Corrected primary development artifact identity failed")
    if correction["selected_conventional"]["id"] != BASELINE or correction["selected_MSCP"]["id"] != CANDIDATE:
        raise ValueError("v2.1 locks primary candidates; no outcome-driven reselection")
    original_pointer = correction["original_result"]
    if digest(Path(original_pointer["artifact"])) != original_pointer["sha256"]:
        raise ValueError("Original archived development identity failed")
    original = json.loads(Path(original_pointer["artifact"]).read_text())
    manifests = {BASELINE: original["world_artifact_manifest"], CANDIDATE: correction["world_artifact_manifest"]}
    rows, identities = {}, []
    for recipe, manifest in manifests.items():
        selected = [item for item in manifest if Path(item["path"]).name.startswith(recipe + "__world")]
        if len(selected) != 12:
            raise ValueError("Exactly twelve recorded development worlds per locked recipe required")
        rows[recipe] = {}
        for item in selected:
            path = Path(item["path"])
            if digest(path) != item["sha256"]:
                raise ValueError("Immutable development world changed")
            row = json.loads(path.read_text())
            if row["stage"] != "validation" or row["recipe"]["id"] != recipe:
                raise ValueError("No pilot/final data admitted to development diagnosis")
            number = row["world_number"]
            if number in rows[recipe]:
                raise ValueError("Duplicate development world")
            rows[recipe][number] = row
            identities.append(item)
        if set(rows[recipe]) != set(range(12)):
            raise ValueError("Missing development identity")
    pairs = []
    for number in range(12):
        candidate, baseline = rows[CANDIDATE][number]["evaluation"], rows[BASELINE][number]["evaluation"]
        if candidate["world_id"] != baseline["world_id"] or candidate["family"] != baseline["family"]:
            raise ValueError("Unpaired world mechanism")
        pairs.append({"world_number": number, "world_id": candidate["world_id"],
                      "family": candidate["family"], "initial_account_budget": candidate["initial_budget"],
                      "candidate_utility": candidate["utility"], "baseline_utility": baseline["utility"],
                      **decompose(candidate, baseline)})
    components = list(decompose(rows[CANDIDATE][0]["evaluation"], rows[BASELINE][0]["evaluation"]))
    average = lambda selected: {key: sum(row[key] for row in selected) / len(selected) for key in components}
    report = {"status": "LOCKED_NEGATIVE_DEVELOPMENT_DECOMPOSITION", "primary_selection_unchanged": True,
              "evidence_class": "synthetic counterfactual policy DEVELOPMENT diagnosis",
              "not_confirmation": True, "final_worlds_loaded": 0, "candidate": CANDIDATE, "comparator": BASELINE,
              "independent_worlds": 12, "unit": "normalized synthetic cost units",
              "horizon": "14 decision days plus7-day maturation and declared receipt flush",
              "paired_decomposition": pairs, "mean_decomposition": average(pairs),
              "per_family": {family: average([row for row in pairs if row["family"] == family])
                             for family in sorted({row["family"] for row in pairs})},
              "per_budget": {str(budget): average([row for row in pairs if row["initial_account_budget"] == budget])
                             for budget in sorted({row["initial_account_budget"] for row in pairs})},
              "artifact_inputs": identities, "corrected_result_sha256": correction["sha256"],
              "original_result_sha256": original_pointer["sha256"],
              "analysis_code_sha256": digest(Path(__file__)), "wall_seconds": time.perf_counter() - start,
              "limitations": ["Post-development descriptive diagnosis, not confirmatory inference or policy selection",
                "Purchase/spend decomposition does not identify a causal learned-component effect",
                "Historical world files do not record action frequencies, support activation, ESS or dual trajectories",
                "Required predeclared instrumented component ablations and OOD studies remain unexecuted",
                "No nowcast, reward, bidder, budget, support or nuisance-model definition changed"]}
    artifact = ROOT / "reports/policy" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    text = ("# Locked negative policy development diagnosis\n\n"
            f"{CANDIDATE} versus {BASELINE}; twelve paired DEVELOPMENT worlds, not confirmation.\n\n"
            "Completed utility difference is purchase value difference minus ordinary spend and operational costs; "
            "the paired no-ad term is checked explicitly. This does not reselect either policy.\n\n"
            + "\n".join(f"- Mean {key}: {value:.12g}" for key, value in report["mean_decomposition"].items())
            + "\n\nHistorical files lack action/support/dual traces; these are unavailable, not reconstructed from guesses. "
            "Instrumented permitted ablations and OOD remain required. Synthetic units are not realized advertiser lift.\n\n"
            f"Evidence: {artifact.name}; source24 world file hashes and family/budget slices in JSON.\n")
    (ROOT / "reports/policy" / (study.name + ".md")).write_text(text)
    atomic_json(ROOT / "reports/policy/NEGATIVE_DEVELOPMENT_DIAGNOSIS.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    study.ledger.update("E13_POLICY", "CHECKPOINTED", artifacts=(artifact,),
                        reason="Locked existing negative development decomposed; required component ablations/OOD still pending, no primary reselection")
    study.export_state()
    print(json.dumps({"artifact": str(artifact), "mean_decomposition": report["mean_decomposition"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
