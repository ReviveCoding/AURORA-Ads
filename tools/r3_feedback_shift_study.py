#!/usr/bin/env python3
"""Prospective finite-H adaptation of FSIW; explicit CPU development only."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.linear_model import SGDClassifier
from aurora.artifacts import atomic_json, digest
from aurora.prediction import calibrate, fit_calibrator, hashed_features, proper_scores
from aurora.r3_feedback_shift import auxiliary_labels, feedback_weights
from aurora.r3_missingness import binary_score_bounds
from aurora.studies import Study


def main() -> int:
    latest = ROOT / "reports/delay/R3_FEEDBACK_SHIFT_DEVELOPMENT.json"
    if latest.exists():
        raise ValueError("Existing feedback-shift development must be reused, not retrained")
    study = Study(ROOT, "e03_r3_CPU_finite_H_feedback_shift")
    started = time.perf_counter()
    pointer = json.loads((ROOT / "reports/data/R3_DEVELOPMENT_COHORTS.json").read_text())
    if digest(Path(pointer["artifact"])) != pointer["sha256"]:
        raise ValueError("Cohort identity changed")
    preparation = json.loads(Path(pointer["artifact"]).read_text())
    if preparation["final_outcomes_scored"] or set(preparation["cohorts"]) != {"M41", "C54", "selection"}:
        raise ValueError("M41+C54 development-only inputs required")
    cohorts = {}
    for name, item in preparation["cohorts"].items():
        if digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Prepared snapshot changed")
        with np.load(item["path"], allow_pickle=False) as data:
            cohorts[name] = {key: data[key].copy() for key in (
                "codes", "origin_days", "age_days", "observed_delay_days", "valid_delay", "within_horizon_label")}
    protocol = {"frozen_before_fit": True, "model_calibrator_pair": "M41+C54", "horizon_days": 7,
        "source_cohort_sha256": pointer["sha256"], "final_outcomes_scored": 0,
        "method": "Finite-H adaptation of Yasui et al.2020 FSIW, not exact production replication",
        "method_source": "https://arxiv.org/abs/2002.02068",
        "auxiliary_cutoff": 34, "auxiliary_origins": "[0,34); labels mature at41",
        "auxiliary_heads": "P(observed_at34 | C_H=1,X,E), P(C_H=0 | not_observed_at34,X,E)",
        "auxiliary_age_feature": "min(E/7,1); primary prediction excludes age",
        "auxiliary_alpha": 1e-4, "primary_alphas": [1e-5, 1e-4],
        "epochs": 5, "tol": None, "seed": 41, "one_snapshot_per_origin": True,
        "weights": "positive1/eta1; negative eta0; fully mature identity; no clipping/renormalization",
        "selection": "known-outcome development proper logloss, deterministic ID tie",
        "calibrators": ["identity", "Platt_C54"], "device": "explicit CPU SGD; no GPU fallback",
        "assumptions": ["Earlier-cutoff conditional observation mechanism transports over time",
            "Recorded conversion occurrence assumed immediately reported; reporting lag unobserved",
            "Finite seven-day recorded target, not eventual conversion; unknown horizons excluded and bounded",
            "Nuisance models may be misspecified; importance weighting does not certify consistency"],
        "argv": sys.argv, "python": sys.version, "started_at_unix": time.time(),
        "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json"),
        "config_hashes": {p.name: digest(p) for p in (ROOT / "config").glob("*.json")},
        "code_hashes": {p: digest(ROOT / p) for p in ("tools/r3_feedback_shift_study.py",
            "src/aurora/r3_feedback_shift.py", "src/aurora/prediction.py", "src/aurora/r3_missingness.py")}}
    atomic_json(study.directory / "protocol_before_fit.json", protocol)
    matrices = {name: hashed_features(data["codes"]) for name, data in cohorts.items()}
    training = cohorts["M41"]
    auxiliary = auxiliary_labels(training["origin_days"], training["within_horizon_label"], training["observed_delay_days"])
    aux_matrix = hstack((matrices["M41"], csr_matrix(np.clip(auxiliary["age"]/7, 0, 1)[:, None])), format="csr")
    nuisance = {}
    diagnostics = {}
    for name in ("positive_aux", "negative_aux"):
        mask, target = auxiliary[name], auxiliary[name + "_target"]
        if set(np.unique(target)) != {0, 1}:
            raise ValueError("Auxiliary conditional classification lacks both classes; no invented labels")
        model = SGDClassifier(loss="log_loss", alpha=1e-4, max_iter=5, tol=None, random_state=41)
        model.fit(aux_matrix[mask], target)
        nuisance[name] = model
        model_path = study.directory / (name + ".joblib")
        joblib.dump(model, model_path)
        diagnostics[name] = {"rows": int(mask.sum()), "positive_fraction": float(target.mean()),
            "model_path": str(model_path), "model_sha256": digest(model_path)}
    valid = training["valid_delay"].astype(bool)
    age = training["age_days"][valid]
    y = (training["observed_delay_days"][valid] >= 0).astype(int)
    main_matrix = matrices["M41"][valid]
    pending = age < 7
    if np.any(training["origin_days"][valid][pending] < auxiliary["cutoff"]):
        raise ValueError("Nuisance weight origins overlap auxiliary-label training")
    pending_matrix = hstack((main_matrix[pending], csr_matrix((age[pending]/7)[:, None])), format="csr")
    tp, tn = np.ones(len(y)), np.ones(len(y))
    tp[pending] = nuisance["positive_aux"].predict_proba(pending_matrix)[:, 1]
    tn[pending] = nuisance["negative_aux"].predict_proba(pending_matrix)[:, 1]
    weights = feedback_weights(y, age, tp, tn)
    def weight_summary(mask):
        values = weights[mask]
        return {"rows": len(values), "sum": float(values.sum()),
            "ess": float(values.sum()**2 / np.square(values).sum()) if np.square(values).sum() > 0 else 0.,
            "quantiles_0_50_90_99_100": np.quantile(values, [0, .5, .9, .99, 1]).tolist() if len(values) else []}
    diagnostics["weights"] = {name: weight_summary(mask) for name, mask in (
        ("all", np.ones(len(y), dtype=bool)), ("positive", y == 1), ("negative", y == 0), ("pending", pending))}
    diagnostics["mature_weights_identity"] = bool(np.all(weights[~pending] == 1))
    recipes = []
    calibration_y, selection_y = cohorts["C54"]["within_horizon_label"], cohorts["selection"]["within_horizon_label"]
    calibration_known, selection_known = np.isfinite(calibration_y), np.isfinite(selection_y)
    for alpha in protocol["primary_alphas"]:
        began = time.perf_counter()
        name = f"D2_finite_H_FSIW_alpha{alpha}"
        model = SGDClassifier(loss="log_loss", alpha=alpha, max_iter=5, tol=None, random_state=41)
        model.fit(main_matrix, y, sample_weight=weights)
        path = study.directory / (name + ".joblib")
        joblib.dump(model, path)
        raw_calibration = model.predict_proba(matrices["C54"])[:, 1]
        raw_selection = model.predict_proba(matrices["selection"])[:, 1]
        if not np.isfinite(raw_calibration).all() or not np.isfinite(raw_selection).all():
            raise ValueError("Nonfinite weighted prediction")
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
        recipes.append({"id": name, "model_path": str(path), "model_sha256": digest(path),
            "training_rows": int(valid.sum()), "fixed_epoch_completion": int(model.n_iter_),
            "not_a_convergence_claim": True, "variants": variants,
            "selected_calibration": min(variants, key=lambda item: (item["scores"]["logloss"], item["id"])),
            "wall_seconds": time.perf_counter() - began})
    report = {"status": "CPU_FINITE_H_FEEDBACK_SHIFT_DEVELOPMENT_ONLY", "protocol": protocol,
        "diagnostics": diagnostics, "recipes": recipes, "final_outcomes_scored": 0,
        "finished_at_unix": time.time(), "wall_seconds": time.perf_counter() - started}
    artifact = ROOT / "reports/delay" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(latest, {"artifact": str(artifact), "sha256": digest(artifact)})
    previous = tuple(Path(item["path"]) for item in study.ledger.read()["nodes"]["E03"]["artifacts"])
    study.ledger.update("E03", "CHECKPOINTED", artifacts=previous + (artifact,),
        reason="Finite-H feedback-shift CPU comparator executed; GPU ladder/freeze unfinished",
        capabilities={"R3_CPU_FEEDBACK_SHIFT_READY": True})
    study.export_state()
    print(json.dumps({"artifact": str(artifact), "wall_seconds": report["wall_seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
