#!/usr/bin/env python3
"""Same-source mature attributed-value development; no unique purchase/lift claim."""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb
import joblib
import numpy as np
from sklearn.linear_model import Ridge, TweedieRegressor
from aurora.artifacts import atomic_json, digest
from aurora.data import SCHEMAS
from aurora.prediction import calibrate, hashed_features
from aurora.studies import Study


def value_bounds(known_values, known_prediction, unknown_prediction, unknown_amount) -> dict:
    values, prediction, pending_prediction, amount = [np.asarray(item, dtype=float) for item in
        (known_values, known_prediction, unknown_prediction, unknown_amount)]
    if values.shape != prediction.shape or pending_prediction.shape != amount.shape or not len(values):
        raise ValueError("Aligned known and unknown source values required")
    if not np.isfinite(values).all() or not np.isfinite(prediction).all() or not np.isfinite(pending_prediction).all() or np.any(values < 0) or np.any(prediction < 0) or np.any(pending_prediction < 0):
        raise ValueError("Finite nonnegative mature value and predictions required")
    supported = np.isfinite(amount) & (amount >= 0)
    n = len(values) + len(amount)
    error = prediction - values
    zero_error, conversion_error = pending_prediction[supported], pending_prediction[supported] - amount[supported]
    square = float(np.sum(error**2))
    absolute = float(np.sum(np.abs(error)))
    lower_square = (square + np.minimum(zero_error**2, conversion_error**2).sum()) / n
    upper_square = (square + np.maximum(zero_error**2, conversion_error**2).sum()) / n if supported.all() else None
    lower_absolute = (absolute + np.minimum(np.abs(zero_error), np.abs(conversion_error)).sum()) / n
    upper_absolute = (absolute + np.maximum(np.abs(zero_error), np.abs(conversion_error)).sum()) / n if supported.all() else None
    return {"known_mature_rows": len(values), "unknown_horizon_rows": len(amount), "full_cohort_rows": n,
            "complete_case_MSE": square / len(values), "complete_case_MAE": absolute / len(values),
            "full_cohort_MSE_identification_bounds": [float(lower_square), float(upper_square) if upper_square is not None else None],
            "full_cohort_MAE_identification_bounds": [float(lower_absolute), float(upper_absolute) if upper_absolute is not None else None],
            "unknown_amount_rows": int((~supported).sum()), "not_confidence_intervals": True,
            "unit": "source attributed amount in publisher-labeled Euro units; not incremental advertiser value"}


def checked_pointer(relative):
    pointer = json.loads((ROOT / relative).read_text())
    path = Path(pointer["artifact"])
    if digest(path) != pointer["sha256"]:
        raise ValueError("Input pointer identity mismatch")
    return pointer, json.loads(path.read_text())


def main() -> int:
    study = Study(ROOT, "e03_r3_mature_attributed_value_development")
    started = time.perf_counter()
    cohort_pointer, preparation = checked_pointer("reports/data/R3_DEVELOPMENT_COHORTS.json")
    baseline_pointer, baselines = checked_pointer("reports/delay/R3_CPU_BASELINES.json")
    admission_pointer, source = checked_pointer("reports/data/R3_ANALYSIS_ADMISSION.json")
    if baselines["protocol"]["source_cohort_sha256"] != cohort_pointer["sha256"] or preparation["protocol"]["source_admission_sha256"] != admission_pointer["sha256"]:
        raise ValueError("Same-source cohort/incidence/admission lineage required")
    for partition in source["partition_manifest"]:
        if digest(Path(partition["path"])) != partition["sha256"]:
            raise ValueError("Source partition changed before supplemental unknown-amount query")
    qualified = [recipe for recipe in baselines["recipes"] if recipe["id"].startswith("D1_mature")]
    q_recipe = min(qualified, key=lambda item: (item["selected_calibration"]["scores"]["logloss"], item["id"]))
    q_calibration = q_recipe["selected_calibration"]
    for path, sha in ((q_recipe["model_path"], q_recipe["model_sha256"]), (q_calibration["calibrator_path"], q_calibration["calibrator_sha256"])):
        if digest(Path(path)) != sha:
            raise ValueError("CPU incidence model/calibrator changed")
    q_model, q_calibrator = joblib.load(q_recipe["model_path"]), joblib.load(q_calibration["calibrator_path"])
    cohorts = {}
    for name, item in preparation["cohorts"].items():
        if name not in {"M41", "C54", "selection"} or digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Development windows only, exact immutable cohort files")
        if item["missing_mature_value_rows"]:
            raise ValueError("Known-horizon missing revenue requires an explicit additional bound, not silent complete-case deletion")
        with np.load(item["path"], allow_pickle=False) as loaded:
            cohorts[name] = {key: loaded[key].copy() for key in ("codes", "mature", "valid_delay", "within_horizon_label", "available_value")}
    protocol = {"model_calibrator_pair": "M41+C54", "final_outcomes_scored": 0,
                "cohort_sha256": cohort_pointer["sha256"], "CPU_incidence_sha256": baseline_pointer["sha256"],
                "selected_CPU_incidence": q_recipe["id"], "q_model_sha256": q_recipe["model_sha256"],
                "q_calibrator_sha256": q_calibration["calibrator_sha256"],
                "recipes": {"empirical_mature_value_mean": {}, "two_part_log1p_Ridge_Duan_C54": {"alpha": 100., "max_iter": 100, "tol": 1e-5},
                            "direct_Tweedie": {"power": 1.5, "alpha": 1., "max_iter": 100, "tol": 1e-5, "link": "log"}},
                "primary_value_training": "only finite fully mature M41 values; no pending positives as full-cohort rewards",
                "two_part_positive_target": "amount conditional on within7-day conversion, including zero amounts",
                "smearing": "independent mature C54 residual exp mean for log1p(amount); predict exp(mean)*smear-1",
                "nonnegative_prediction_projection": "max(0, retransformed conditional mean); targets/tails never clipped",
                "no_source_coupling": "q and amount are same R3 population; no R1/S1 probability multiplication",
                "primary_raw_tail": True, "no_primary_clipping": True,
                "argv": sys.argv, "started_at_unix": time.time(),
                "code_hashes": {relative: digest(ROOT / relative) for relative in ("tools/r3_value_study.py", "src/aurora/prediction.py")},
                "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json")}
    atomic_json(study.directory / "protocol_before_fits.json", protocol)
    masks = {name: data["mature"] & np.isfinite(data["available_value"]) for name, data in cohorts.items()}
    matrix = {name: hashed_features(data["codes"]) for name, data in cohorts.items()}
    training_y = cohorts["M41"]["available_value"][masks["M41"]]
    # Recover ONLY development unknown-horizon monetary amounts/features, which
    # are not mature labels. No final SQL or fabricated order identity.
    fields = SCHEMAS["criteo_search"].features
    codes = ",".join(f'CASE WHEN "{name}" IS NULL OR "{name}" IN (\'-1\',\'-1.0\') THEN 0 ELSE 1+hash("{name}")%1023 END AS "{name}"' for name in fields)
    connection = duckdb.connect()
    connection.execute("SET threads=1")
    connection.execute("SET memory_limit='256MB'")
    connection.read_parquet(source["partition_paths"]).create_view("events")
    zero, factor = source["day_zero_native"], source["clock"]["seconds_per_native_unit"]
    frame = connection.execute(f"SELECT {codes},SalesAmountInEuro FROM events WHERE click_timestamp>=? AND click_timestamp<? AND hash(user_id,click_timestamp,product_id,partner_id,41)%8=0 AND Sale=1 AND time_delay_for_conversion=-1", [zero + 54 * 86400 / factor, zero + 60 * 86400 / factor]).fetchdf()
    expected_unknown = int((~cohorts["selection"]["valid_delay"]).sum())
    if len(frame) != expected_unknown:
        raise ValueError("Unknown value/cohort sampling identity mismatch")
    unknown_matrix = hashed_features(frame[list(fields)].to_numpy(dtype=np.int64))
    unknown_amount = frame.SalesAmountInEuro.to_numpy(dtype=float)
    connection.close()
    models = {}
    fit_warnings = []
    models["empirical_mature_value_mean"] = float(training_y.mean())
    positive_train = masks["M41"] & (cohorts["M41"]["within_horizon_label"] == 1)
    positive_calibration = masks["C54"] & (cohorts["C54"]["within_horizon_label"] == 1)
    regression = Ridge(alpha=100., solver="lsqr", max_iter=100, tol=1e-5)
    regression.fit(matrix["M41"][positive_train], np.log1p(cohorts["M41"]["available_value"][positive_train]))
    residual = np.log1p(cohorts["C54"]["available_value"][positive_calibration]) - regression.predict(matrix["C54"][positive_calibration])
    smear = float(np.exp(residual).mean())
    if not np.isfinite(smear) or smear <= 0:
        raise FloatingPointError("Invalid independent retransformation correction; do not clip into apparent success")
    models["two_part_log1p_Ridge_Duan_C54"] = {"positive_model": regression, "smearing": smear}
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        direct = TweedieRegressor(power=1.5, alpha=1., link="log", max_iter=100, tol=1e-5)
        direct.fit(matrix["M41"][masks["M41"]], training_y)
        fit_warnings.extend({"type": item.category.__name__, "message": str(item.message)} for item in captured)
    models["direct_Tweedie"] = direct
    def predict(name, values):
        model = models[name]
        if isinstance(model, float):
            result = np.full(values.shape[0], model)
        elif isinstance(model, dict):
            q = calibrate(q_calibrator, q_model.predict_proba(values)[:, 1])
            result = q * np.maximum(0., np.exp(model["positive_model"].predict(values)) * model["smearing"] - 1)
        else:
            result = model.predict(values)
        if not np.isfinite(result).all() or np.any(result < 0):
            raise FloatingPointError("Nonfinite/negative attributed-value prediction; retain failure, no hidden repair")
        return result
    results = []
    for name, model in models.items():
        predicted = predict(name, matrix["selection"])
        unknown_prediction = predict(name, unknown_matrix)
        scores = value_bounds(cohorts["selection"]["available_value"][masks["selection"]], predicted[masks["selection"]], unknown_prediction, unknown_amount)
        path = study.directory / (name + ".joblib")
        joblib.dump(model, path)
        results.append({"id": name, "model_path": str(path), "model_sha256": digest(path), "scores": scores,
                        "known_mature_predicted_mean": float(predicted[masks["selection"]].mean()),
                        "known_mature_observed_mean": float(cohorts["selection"]["available_value"][masks["selection"]].mean())})
    report = {"status": "ATTRIBUTED_VALUE_DEVELOPMENT_ONLY", "protocol": protocol, "results": results,
              "smearing_C54": smear, "fit_warnings": fit_warnings, "direct_iterations": int(direct.n_iter_),
              "raw_training_value_quantiles": np.quantile(training_y, [0, .5, .9, .99, .999, 1]).tolist(),
              "wall_seconds": time.perf_counter() - started, "final_outcomes_scored": 0,
              "limitations": ["Recorded source-attributed click value, not unique purchases or incremental advertiser value",
                "Development-only model comparisons; no primary H_delay or monetary superiority confirmation",
                "Full-cohort identification bounds are not confidence intervals",
                "No clipped tail substituted for raw primary targets; convergence warnings retained"]}
    artifact = ROOT / "reports/delay" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/delay/R3_VALUE_DEVELOPMENT.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    study.ledger.update("E03", "CHECKPOINTED", artifacts=(artifact,), capabilities={"R3_VALUE_DEVELOPMENT_READY": True},
                        reason="Same-source mature attributed-value baselines executed; remaining delay/CUDA and independent freeze still required")
    study.export_state()
    print(json.dumps({"artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
