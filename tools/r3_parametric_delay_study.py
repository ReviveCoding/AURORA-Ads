#!/usr/bin/env python3
"""Explicit sparse CPU D3 development; no CUDA/neural-model substitution."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import joblib
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from aurora.artifacts import atomic_json, digest
from aurora.prediction import calibrate, fit_calibrator, hashed_features, proper_scores
from aurora.r3_missingness import binary_score_bounds
from aurora.r3_sparse_exponential import sparse_objective
from aurora.studies import Study


def main() -> int:
    if (ROOT / "reports/delay/R3_PARAMETRIC_DELAY_DEVELOPMENT.json").exists():
        raise ValueError("Existing D3 development must be verified/reused, not retrained")
    study = Study(ROOT, "e03_r3_sparse_CPU_conditional_exponential")
    started = time.perf_counter()
    pointer = json.loads((ROOT / "reports/data/R3_DEVELOPMENT_COHORTS.json").read_text())
    path = Path(pointer["artifact"])
    if digest(path) != pointer["sha256"]:
        raise ValueError("Development cohort identity changed")
    preparation = json.loads(path.read_text())
    if preparation["final_outcomes_scored"] or set(preparation["cohorts"]) != {"M41", "C54", "selection"}:
        raise ValueError("M41+C54 development-only inputs required")
    cohorts = {}
    for name, item in preparation["cohorts"].items():
        if digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Prepared snapshot changed")
        with np.load(item["path"], allow_pickle=False) as data:
            cohorts[name] = {key: data[key].copy() for key in
                ("codes", "age_days", "observed_delay_days", "valid_delay", "within_horizon_label")}
    training = cohorts["M41"]
    valid = training["valid_delay"].astype(bool)
    observed = training["observed_delay_days"][valid]
    if np.any(observed == 0):
        raise ValueError("Immediate TRAIN events require the separately qualified atom model")
    protocol = {"frozen_before_fit": True, "source_cohort_sha256": pointer["sha256"],
        "model_calibrator_pair": "M41+C54", "horizon_days": 7, "final_outcomes_scored": 0,
        "family": "D3 linear logistic incidence plus conditional-on-H exponential delay",
        "device": "explicit CPU sparse SciPy L-BFGS; not neural/GPU fallback",
        "alphas": [1e-5, 1e-4], "max_iterations": 100, "ftol": 1e-7, "gtol": 1e-5,
        "rate_parameterization": "softplus(linear rate logit), no hidden tower",
        "zero_atom": "not used: no observed immediate TRAIN conversions; not chosen from final",
        "initializer": "zero feature weights, mature M41 prior incidence, rate0.5/day",
        "observation_assumption": "recorded occurrence assumed immediately reported; unknown delay labels excluded and bounded",
        "one_snapshot_per_origin": True, "natural_prevalence_hash_sample": "same outcome-blind1/8 cohort",
        "calibrators": ["identity", "Platt_C54"], "selection": "known-outcome development logloss, ID tie",
        "argv": sys.argv, "python": sys.version, "seed": "deterministic optimizer, no stochastic sampling",
        "started_at_unix": time.time(), "code_hashes": {relative: digest(ROOT / relative) for relative in (
            "tools/r3_parametric_delay_study.py", "src/aurora/r3_sparse_exponential.py", "src/aurora/prediction.py")},
        "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json"),
        "config_hashes": {item.name: digest(item) for item in (ROOT / "config").glob("*.json")}}
    atomic_json(study.directory / "protocol_before_fit.json", protocol)
    matrices = {name: hashed_features(data["codes"]) for name, data in cohorts.items()}
    matrix = matrices["M41"][valid]
    age = training["age_days"][valid]
    mature_labels = training["within_horizon_label"]
    prior = float(mature_labels[np.isfinite(mature_labels)].mean())
    dimension = matrix.shape[1]
    recipes = []
    for alpha in protocol["alphas"]:
        began = time.perf_counter()
        initial = np.zeros((2, dimension+1))
        initial[0, -1] = np.log(prior/(1-prior))
        initial[1, -1] = np.log(np.expm1(.5))
        name = f"D3_sparse_exponential_alpha{alpha}"
        result = minimize(sparse_objective, initial.ravel(), args=(matrix, age, observed, alpha),
                          jac=True, method="L-BFGS-B", options={"maxiter": 100, "ftol": 1e-7, "gtol": 1e-5})
        if not np.isfinite(result.x).all() or not np.isfinite(result.fun):
            raise ValueError("Nonfinite D3 optimizer result")
        heads = result.x.reshape(2, dimension+1)
        model_path = study.directory / (name + ".joblib")
        joblib.dump({"heads": heads, "horizon_days": 7, "rate": "softplus", "zero_atom": False}, model_path)
        def incidence(cohort):
            return expit(np.asarray(matrices[cohort] @ heads[0, :-1]) + heads[0, -1])
        raw_calibration, raw_selection = incidence("C54"), incidence("selection")
        calibration_y, selection_y = cohorts["C54"]["within_horizon_label"], cohorts["selection"]["within_horizon_label"]
        calibration_known, selection_known = np.isfinite(calibration_y), np.isfinite(selection_y)
        platt = fit_calibrator(calibration_y[calibration_known], raw_calibration[calibration_known])
        variants = []
        for kind, calibrator in (("identity", None), ("Platt_C54", platt)):
            predicted = calibrate(calibrator, raw_selection)
            scores, _ = proper_scores(selection_y[selection_known], predicted[selection_known])
            calibrator_path = study.directory / (name + "__" + kind + ".joblib")
            joblib.dump(calibrator, calibrator_path)
            variants.append({"id": name + "__" + kind, "scores": scores,
                "full_cohort_bounds": binary_score_bounds(selection_y, predicted),
                "calibrator_path": str(calibrator_path), "calibrator_sha256": digest(calibrator_path)})
        recipes.append({"id": name, "model_path": str(model_path), "model_sha256": digest(model_path),
            "training_rows": int(valid.sum()), "optimizer_success": bool(result.success), "optimizer_status": int(result.status),
            "optimizer_message": str(result.message), "iterations": int(result.nit), "function_evaluations": int(result.nfev),
            "objective": float(result.fun), "variants": variants,
            "selected_calibration": min(variants, key=lambda item: (item["scores"]["logloss"], item["id"])),
            "qualified_for_final_selection": bool(result.success), "wall_seconds": time.perf_counter() - began})
        atomic_json(study.directory / "progress.json", {"protocol": protocol, "recipes": recipes, "final_outcomes_scored": 0})
        print(json.dumps({"recipe": name, "optimizer_success": bool(result.success), "iterations": int(result.nit)}), flush=True)
    report = {"status": "PARAMETRIC_CPU_D3_DEVELOPMENT_ONLY", "protocol": protocol, "recipes": recipes,
        "wall_seconds": time.perf_counter() - started, "finished_at_unix": time.time(), "final_outcomes_scored": 0,
        "limitations": ["Explicit sparse CPU parametric baseline, not actual GPU/neural ladder evidence",
                        "Optimizer nonconvergence is retained and cannot qualify a finalist",
                        "Unknown horizons require separate bounds; no missing-as-negative correction",
                        "Development selection is not H_delay confirmation; reporting clock remains assumed"]}
    artifact = ROOT / "reports/delay" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/delay/R3_PARAMETRIC_DELAY_DEVELOPMENT.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    previous = tuple(Path(item["path"]) for item in study.ledger.read()["nodes"]["E03"]["artifacts"])
    study.ledger.update("E03", "CHECKPOINTED", artifacts=previous + (artifact,),
        reason="Declared CPU parametric D3 development executed; GPU ladder/freeze unfinished",
        capabilities={"R3_CPU_PARAMETRIC_DELAY_READY": any(item["qualified_for_final_selection"] for item in recipes)})
    study.export_state()
    print(json.dumps({"artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
