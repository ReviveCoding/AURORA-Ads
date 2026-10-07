#!/usr/bin/env python3
"""Descriptive locked E13 diagnostics; never selects or edits primary controllers."""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def paired_decomposition(candidate: dict, baseline: dict) -> dict:
    if candidate["world"] != baseline["world"] or not candidate["not_confirmation"] or not baseline["not_confirmation"]:
        raise ValueError("Same development/OOD world required; final outcomes forbidden")
    if candidate["world"]["stage"] not in {"validation", "ood"}:
        raise ValueError("Only locked development and separately labeled OOD diagnosis")
    a, b = candidate["evaluation"], baseline["evaluation"]
    if a["initial_budget"] <= 0 or a["initial_budget"] != b["initial_budget"] or a["final_pending_exposures"] or b["final_pending_exposures"]:
        raise ValueError("Matched budgets and completed maturation required")
    pieces = {key: (a[key] - b[key]) / a["initial_budget"] for key in
              ("unique_purchase_value", "no_ad_purchase_value", "spend", "operating_cost")}
    effect = a["utility"] - b["utility"]
    reconstructed = pieces["unique_purchase_value"] - pieces["no_ad_purchase_value"] - pieces["spend"] - pieces["operating_cost"]
    if not np.isclose(effect, reconstructed, rtol=1e-10, atol=1e-10):
        raise ValueError("Utility decomposition failed")
    return {"world_id": candidate["world"]["world_id"], "family": candidate["world"]["family"], "stage": candidate["world"]["stage"],
            "utility_difference": effect, "normalized_components": pieces}


def main() -> int:
    study = Study(ROOT, "e13_locked_policy_diagnostic_analysis")
    started = time.perf_counter()
    pointer = json.loads((ROOT / "reports/policy/E13_ABLATIONS_OOD.json").read_text())
    path = Path(pointer["artifact"])
    if digest(path) != pointer["sha256"]:
        raise ValueError("E13 result identity changed")
    parent = json.loads(path.read_text())
    if not parent["primary_selection_unchanged"] or parent["protocol"]["final_worlds_loaded"]:
        raise ValueError("Primary selection/final firewall violated")
    groups = defaultdict(dict)
    for item in parent["world_artifacts"]:
        path = Path(item["path"])
        if digest(path) != item["sha256"]:
            raise ValueError("E13 world bytes changed")
        row = json.loads(path.read_text())
        groups[row["recipe"]][row["world"]["world_id"]] = row
    contrasts, diagnostic_profiles = {}, {}
    for recipe, worlds in groups.items():
        paired = []
        for identity, row in worlds.items():
            reference = groups["static_bid0.25"].get(identity)
            if reference is not None and recipe != "static_bid0.25":
                paired.append(paired_decomposition(row, reference))
        contrasts[recipe] = {"per_world": paired, "mean_development_difference": float(np.mean([
            row["utility_difference"] for row in paired if row["stage"] == "validation"])) if any(
                row["stage"] == "validation" for row in paired) else None,
            "OOD_kept_separate": True}
        diagnostic_profiles[recipe] = [{"world_id": identity, "stage": row["world"]["stage"],
            "family": row["world"]["family"], "budget_per_campaign": row["world"]["budget_per_campaign"],
            "diagnostics": row["diagnostics"]} for identity, row in worlds.items()]
    report = {"source_artifact": pointer, "contrasts_vs_locked_conventional": contrasts,
        "per_world_diagnostic_profiles": diagnostic_profiles, "primary_selection_unchanged": True,
        "source_protocol_sha256": parent["protocol_sha256"], "final_outcomes_loaded": 0,
        "argv": sys.argv, "script_sha256": digest(Path(__file__)), "wall_seconds": time.perf_counter() - started,
        "evidence_class": "synthetic counterfactual development/secondary OOD diagnosis",
        "scientific_claim": "Descriptive development slices, not confirmatory component effects",
        "unavailable_slices": ["True losing-auction prices", "Production incidents", "Learned NO_BID usage in fixed-bid primary kernel"],
        "limitations": ["Small preselected development worlds; no outcome-driven primary reselection",
                        "Observed gross calibration is not incremental-value calibration",
                        "Support/uncertainty are heuristics, not calibrated confidence bounds"]}
    artifact = ROOT / "reports/policy" / (study.name + ".json")
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/policy/E13_DIAGNOSTIC_ANALYSIS.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
