#!/usr/bin/env python3
"""Real admitted R3 CPU prior/logistic comparators, not GPU model substitution."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import joblib
import numpy as np
from sklearn.linear_model import SGDClassifier
from aurora.artifacts import atomic_json, digest
from aurora.prediction import calibrate, fit_calibrator, hashed_features, proper_scores
from aurora.r3_missingness import binary_score_bounds
from aurora.studies import Study


def training_target(data: dict, *, mature_only: bool) -> tuple[np.ndarray, np.ndarray]:
    valid = np.asarray(data["valid_delay"], dtype=bool)
    if mature_only:
        mask = valid & np.asarray(data["mature"], dtype=bool) & np.isfinite(data["within_horizon_label"])
        return mask, np.asarray(data["within_horizon_label"])[mask].astype(int)
    # D0 is explicitly the pending-negative diagnostic, not the principal
    # mature baseline. A missing conversion-delay label is never zero-filled.
    return valid, (np.asarray(data["event_bin"])[valid] >= 0).astype(int)


def main() -> int:
    study = Study(ROOT, "e03_r3_CPU_prior_logistic_development")
    started = time.perf_counter()
    pointer = json.loads((ROOT / "reports/data/R3_DEVELOPMENT_COHORTS.json").read_text())
    path = Path(pointer["artifact"])
    if digest(path) != pointer["sha256"]:
        raise ValueError("Development cohort identity changed")
    preparation = json.loads(path.read_text())
    if preparation["final_outcomes_scored"] or set(preparation["cohorts"]) != {"M41", "C54", "selection"}:
        raise ValueError("Only frozen development windows allowed")
    cohorts = {}
    for name, item in preparation["cohorts"].items():
        if digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Prepared cohort changed")
        with np.load(item["path"], allow_pickle=False) as loaded:
            cohorts[name] = {key: loaded[key].copy() for key in
                ("codes", "age_days", "event_bin", "mature", "valid_delay", "within_horizon_label")}
    protocol = {"source_cohort_sha256": pointer["sha256"], "model_calibrator_pair": "M41+C54",
                "cohort_identities": preparation["cohorts"], "final_outcomes_scored": 0,
                "CPU_baselines_declared": True, "not_GPU_fallback": True,
                "recipes": ["empirical_mature_prior", "D0_pending_negative_logistic_alpha1e-5",
                            "D1_mature_logistic_alpha1e-5", "D1_mature_logistic_alpha1e-4"],
                "logistic_epochs": 5, "loss": "log_loss", "seed": 41, "shuffle": True,
                "calibrators": ["identity", "Platt_C54"],
                "calibrator_selection": "selection-known-outcome proper logloss, deterministic recipe ID tie",
                "unknown_outcome_handling": "exclude from complete-case point scores; full-cohort identification bounds separately",
                "no_final_selection_yet": "D1 CUDA and D2/D3/D4/value development remain",
                "argv": sys.argv, "started_at_unix": time.time(),
                "code_hashes": {relative: digest(ROOT / relative) for relative in
                    ("tools/r3_cpu_baselines.py", "src/aurora/prediction.py", "src/aurora/r3_missingness.py")},
                "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json"),
                "config_hashes": {p.name: digest(p) for p in (ROOT / "config").glob("*.json")}}
    atomic_json(study.directory / "protocol_before_fits.json", protocol)
    matrix = {name: hashed_features(data["codes"]) for name, data in cohorts.items()}
    calibration_y = cohorts["C54"]["within_horizon_label"]
    selection_y = cohorts["selection"]["within_horizon_label"]
    calibration_known, selection_known = np.isfinite(calibration_y), np.isfinite(selection_y)
    recipes = []
    for name in protocol["recipes"]:
        began = time.perf_counter()
        mask, target = training_target(cohorts["M41"], mature_only=not name.startswith("D0"))
        if name == "empirical_mature_prior":
            model = float(target.mean())
            predict = lambda key: np.full(len(cohorts[key]["codes"]), model)
        else:
            alpha = 1e-4 if name.endswith("1e-4") else 1e-5
            model = SGDClassifier(loss="log_loss", alpha=alpha, max_iter=5, tol=None, random_state=41, shuffle=True)
            model.fit(matrix["M41"][mask], target)
            predict = lambda key: model.predict_proba(matrix[key])[:, 1]
        model_path = study.directory / (name + ".joblib")
        joblib.dump(model, model_path)
        calibration_p, selection_p = predict("C54"), predict("selection")
        fitted = fit_calibrator(calibration_y[calibration_known], calibration_p[calibration_known])
        variants = []
        for kind, calibrator in (("identity", None), ("Platt_C54", fitted)):
            predicted = calibrate(calibrator, selection_p)
            scores, _ = proper_scores(selection_y[selection_known], predicted[selection_known])
            bounds = binary_score_bounds(selection_y, predicted)
            calibration_path = study.directory / (name + "__" + kind + "_calibrator.joblib")
            joblib.dump(calibrator, calibration_path)
            variants.append({"id": name + "__" + kind, "calibration": kind, "scores": scores,
                             "full_cohort_bounds": bounds, "calibrator_path": str(calibration_path),
                             "calibrator_sha256": digest(calibration_path)})
        selected = min(variants, key=lambda item: (item["scores"]["logloss"], item["id"]))
        recipes.append({"id": name, "family": "empirical_prior" if isinstance(model, float) else "hashed_logistic",
                        "role": "biased diagnostic" if name.startswith("D0") else "mature-only baseline",
                        "model_path": str(model_path), "model_sha256": digest(model_path),
                        "training_rows": int(mask.sum()), "variants": variants, "selected_calibration": selected,
                        "wall_seconds": time.perf_counter() - began})
        atomic_json(study.directory / "progress.json", {"protocol": protocol, "completed_recipes": recipes,
                                                       "final_outcomes_scored": 0})
        print(json.dumps({"recipe": name, "training_rows": int(mask.sum()), "final_outcomes_scored": 0}), flush=True)
    report = {"status": "CPU_BASELINES_DEVELOPMENT_EXECUTED_NOT_FULL_LADDER", "protocol": protocol,
              "recipes": recipes, "wall_seconds": time.perf_counter() - started, "finished_at_unix": time.time(),
              "final_outcomes_scored": 0, "scientific_outcome": "NOT_RUN",
              "limitations": ["Development selection, not frozen R3 confirmation or H_delay support",
                "Complete-case proper scores do not identify every-click performance; bounds are not CIs",
                "Source sample/repeated key tuples are not independent people",
                "Actual CUDA mature-only and delay/value ladder remain required; no CPU substitution claim"]}
    artifact = ROOT / "reports/delay" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/delay/R3_CPU_BASELINES.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    study.ledger.update("E03", "CHECKPOINTED", artifacts=(artifact,), capabilities={"R3_CPU_BASELINES_READY": True},
                        reason="Real R3 CPU prior/D0/D1 development executed; remaining CUDA/delay/value ladder and freeze required")
    study.export_state()
    print(json.dumps({"artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
