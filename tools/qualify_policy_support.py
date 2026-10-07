#!/usr/bin/env python3
"""Bounded label-free support artifact from existing development-only snapshots."""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import joblib
import numpy as np
from aurora.artifacts import atomic_json, digest
from aurora.support import neighborhood_support, validation_distance_threshold
from aurora.studies import Study


def main():
    study = Study(ROOT, "policy_support_v2_label_free_qualification")
    started = time.perf_counter()
    report = {"status": "RUNNING", "outcomes_or_final_features_loaded": 0, "original_E09_restarted_or_edited": False}
    try:
        warm_path = ROOT / "reports/policy/WARMSTART_LATEST.json"
        warm = json.loads(warm_path.read_text())
        training_path = Path(warm["cohort_artifacts"]["train"]["path"])
        support_path = Path(warm["support_path"])
        if digest(training_path) != warm["cohort_artifacts"]["train"]["sha256"] or digest(support_path) != warm["support_sha256"]:
            raise ValueError("Warmstart public training/support identity changed")
        with np.load(training_path, allow_pickle=False) as stored:
            train_x, train_actions, propensities = stored["x"].copy(), stored["action"].copy(), stored["propensity"].copy()
        support = joblib.load(support_path)
        if not np.array_equal(train_actions, support["actions"]):
            raise ValueError("Support tree actions/propensities are not aligned")
        mean, scale = np.asarray(warm["scaler_mean"]), np.asarray(warm["scaler_scale"])
        # The original builder normalized in the source feature dtype before
        # JSON serialization; do not mistake float32 promotion for changed IDs.
        np.testing.assert_allclose(np.asarray(support["tree"].data), (train_x - mean.astype(train_x.dtype)) / scale.astype(train_x.dtype), rtol=0, atol=0)
        freeze_path = ROOT / "reports/incidents/DETECTOR_FREEZE.json"
        freeze = json.loads(freeze_path.read_text())
        candidate = next(item for item in freeze["candidates"] if item["id"] == freeze["selected"])
        validation_path = Path(candidate["path"]).parent / "selection_dataset.npz"
        if digest(validation_path) != freeze["dataset_hashes"]["selection"]:
            raise ValueError("Existing validation-only public snapshot identity changed")
        with np.load(validation_path, allow_pickle=False) as stored:
            raw, worlds = stored["x"].copy(), stored["world"].copy()
        if set(np.unique(worlds)) != {"incident-selection-" + str(number) for number in range(4)}:
            raise ValueError("Not the declared four validation block16..19 worlds")
        selected = np.concatenate([np.flatnonzero(worlds == world)[np.linspace(0, np.sum(worlds == world) - 1, 1024, dtype=int)] for world in sorted(np.unique(worlds))])
        z = (raw[selected] - mean) / scale
        maxima = []
        equal_count_cases, unequal_count_cases = 0, 0
        for begin in range(0, len(z), 128):
            distances, neighbors = support["tree"].query(z[begin:begin + 128], k=64)
            maxima.extend(distances.max(axis=1).tolist())
            for d, indexes in zip(distances, neighbors):
                local = neighborhood_support(train_actions[indexes], propensities[indexes], d, maximum_distance=float(d.max()))
                populated = local.action_rows > 0
                equal_count_cases += int(np.sum(np.isclose(local.action_ess[populated], local.action_rows[populated], rtol=1e-12, atol=1e-12)))
                unequal_count_cases += int(np.sum(~np.isclose(local.action_ess[populated], local.action_rows[populated], rtol=1e-12, atol=1e-12)))
        threshold = validation_distance_threshold(maxima, quantile=.95)
        artifact = study.directory / "support_v2.joblib"
        joblib.dump(support | {"propensities": propensities, "maximum_distance": threshold, "neighborhood_size": 64, "ess_definition": "inverse exact executed-action propensity ESS; no clipping"}, artifact)
        report.update(status="LABEL_FREE_SUPPORT_ARTIFACT_QUALIFIED_NOT_CONTROLLER_INTEGRATION", passed=True, support_artifact={"path": str(artifact), "sha256": digest(artifact)}, warm_report_sha256=digest(warm_path), training_cohorts_sha256=digest(training_path), validation_snapshots_sha256=digest(validation_path), validation_public_columns_loaded=["x", "world"], validation_blocks=list(range(16, 20)), validation_rows=len(raw), deterministic_subsample="1024 uniformly spaced source rows per validation world; fixed before distance computation", validation_rows_used=len(selected), independent_validation_worlds=4, fixed_quantile=.95, quantile_method="higher", maximum_distance=threshold, neighbor_size=64, validation_distance_quantiles={str(q): float(np.quantile(maxima, q)) for q in (0., .5, .95, 1.)}, action_neighborhood_cases_equal_ESS_count=equal_count_cases, action_neighborhood_cases_unequal_ESS_count=unequal_count_cases, propensity_range=[float(propensities.min()), float(propensities.max())], limitations=["Four reference validation worlds at10k campaign budget; not broad OOD calibration", "Empirical action support only, not positivity/overlap-probability or calibrated policy-value certificate", "No reward/fault labels loaded; threshold never tuned for candidate advantage", "Original sweep still uses its recorded older support definition; supplemental controller integration/comparison required"])
    except Exception as error:
        report.update(status="LABEL_FREE_SUPPORT_QUALIFICATION_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    export = ROOT / "reports/policy" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(export, report)
    if report["passed"]:
        atomic_json(ROOT / "reports/policy/SUPPORT_V2_QUALIFICATION.json", {"artifact": str(export), "sha256": digest(export), "support_artifact": report["support_artifact"], "passed": True})
        study.ledger.update("E15_POLICY_FREEZE", "CHECKPOINTED", artifacts=(export,), capabilities={"POLICY_SUPPORT_ARTIFACT_READY": True, "POLICY_SUPPORT_QUALIFIED": False}, reason="Label-free ESS/distance artifact ready; actual supplemental controller comparison remains required")
        study.export_state()
    print(json.dumps({"artifact": str(export), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
