#!/usr/bin/env python3
"""R4 men position-one, frozen fixed-policy OPE; never adaptive certification."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

from aurora.artifacts import atomic_json, digest
from aurora.ope import all_rewards, epsilon_target, estimate_with_clusters, reward_features
from aurora.studies import Study, metric_record


def main() -> int:
    study = Study(ROOT, "e05_fixed_policy_ope")
    study.ledger.update("E05", "RUNNING", reason="Admitted R4; pinned raw position1; independent temporal partitions")
    source = study.source("obd_men")
    paths = [path for path in source["partition_paths"] if "/random_men_men.csv/" in path]
    if not paths:
        raise ValueError("Explicit random logger lineage missing")
    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='256MB'; SET TimeZone='UTC'")
    con.read_parquet(paths).create_view("random_events")
    # No item-affinity or reward-dependent columns admitted as context here.
    frame = con.execute("SELECT CAST(timestamp AS TIMESTAMP) AS clock,item_id,click,propensity_score,user_feature_0,user_feature_1,user_feature_2,user_feature_3 FROM random_events WHERE position=1 ORDER BY clock,C0").fetchdf()
    days = frame.clock.dt.strftime("%Y-%m-%d").to_numpy()
    dates = sorted(set(days))
    if len(dates) != 7:
        raise ValueError(f"Expected documented seven-day source; observed {dates}")
    actions = frame.item_id.to_numpy(dtype=int)
    reward = frame.click.to_numpy(dtype=float)
    propensity = frame.propensity_score.to_numpy(dtype=float)
    context = frame[[f"user_feature_{i}" for i in range(4)]].to_numpy(dtype=str)
    assert set(actions) == set(range(34))
    np.testing.assert_allclose(propensity, 1 / 34, rtol=0, atol=1e-14)
    masks = {"target_training": np.isin(days, dates[:2]), "reward_fold0": days == dates[2], "reward_fold1": days == dates[3], "selection": days == dates[4], "final": np.isin(days, dates[5:])}
    hashes = [item["sha256"] for item in source["source_files"]]
    protocol = {"position": 1, "eligible_item_mapping": list(range(34)), "feature_columns": [f"user_feature_{i}" for i in range(4)], "source_hashes": hashes, "dates": dates, "partition_dates": {key: sorted(set(days[mask])) for key, mask in masks.items()}, "counts": {key: int(mask.sum()) for key, mask in masks.items()}, "hyperparameter_grid": [.1, 1.], "target_epsilon": .1, "clipping_sensitivity": 10, "primary_cluster": "UTC calendar day", "restriction": "benchmark replication; fixed position-conditional one-step value, not slate or adaptive budget"}
    atomic_json(study.directory / "protocol.json", protocol)
    target_candidates = []
    target_mask, validation = masks["target_training"], masks["selection"]
    for strength in protocol["hyperparameter_grid"]:
        model = LogisticRegression(C=strength, solver="liblinear", max_iter=1000, random_state=37).fit(reward_features(context[target_mask], actions[target_mask]), reward[target_mask])
        loss = log_loss(reward[validation], model.predict_proba(reward_features(context[validation], actions[validation]))[:, 1], labels=[0, 1])
        target_candidates.append((loss, strength, model))
    _, selected_c, target_model = min(target_candidates, key=lambda row: row[0])
    reward_models = []
    crossfit = []
    for fold in range(2):
        fit = masks[f"reward_fold{fold}"]
        opposite = masks[f"reward_fold{1-fold}"]
        model = LogisticRegression(C=selected_c, solver="liblinear", max_iter=1000, random_state=38 + fold).fit(reward_features(context[fit], actions[fit]), reward[fit])
        crossfit.append({"fit_dates": sorted(set(days[fit])), "out_of_fold_dates": sorted(set(days[opposite])), "out_of_fold_logloss": log_loss(reward[opposite], model.predict_proba(reward_features(context[opposite], actions[opposite]))[:, 1], labels=[0, 1])})
        reward_models.append(model)
    model_path = study.directory / "frozen_models.joblib"
    joblib.dump({"target": target_model, "reward_crossfit": reward_models}, model_path)
    freeze = protocol | {"selected_C": selected_c, "selection_losses": [{"C": row[1], "logloss": row[0]} for row in target_candidates], "model_sha256": digest(model_path), "frozen_at_unix": time.time(), "before_final_outcome_scoring": True}
    atomic_json(study.directory / "freeze.json", freeze)
    final = masks["final"]
    predictions = np.mean([all_rewards(model, context[final]) for model in reward_models], axis=0)
    target = epsilon_target(all_rewards(target_model, context[final]))
    uniform = np.full(predictions.shape, 1 / 34)
    estimates = {}
    for name, probabilities in (("uniform", uniform), ("frozen_contextual_epsilon", target)):
        estimates[name] = {"unclipped": estimate_with_clusters(actions[final], reward[final], propensity[final], probabilities, predictions, days[final]), "clipped_10_sensitivity": estimate_with_clusters(actions[final], reward[final], propensity[final], probabilities, predictions, days[final], clip=10)}
    observed = float(reward[final].mean())
    for name in ("ips", "snips"):
        assert abs(estimates["uniform"]["unclipped"]["estimates"][name] - observed) < 1e-14
    assert estimates["uniform"]["unclipped"]["estimates"]["ess"] == int(final.sum())
    assert estimates["frozen_contextual_epsilon"]["unclipped"]["estimates"]["max_weight"] <= 34
    limits = ["Entire release conservatively potentially prior-exposed; replication only", "Only two final calendar-day clusters; intervals are unstable/underpowered and temporal independence is not established", "Raw position1 marginal action-probability semantics; not whole-slate value", "No independent user IDs; no row-level significance claim", "BTS is not reconstructed and cannot be arbitrary-policy ground truth"]
    records = []
    for candidate, values in estimates.items():
        primary = values["unclipped"]
        for estimator in ("dm", "ips", "snips", "dr"):
            ci = primary["intervals"].get(estimator, {}).get("ci95")
            records.append(metric_record(domain="R4", population=f"OBD men random logger raw position1; {dates[5:]} UTC", estimand="fixed_position_conditional_click_value", comparison="uniform_vs_frozen_contextual_target", candidate=candidate, baseline="uniform", metric=estimator, estimate=primary["estimates"][estimator], unit="click probability per logged position1 impression", horizon="one decision", n=2, independent_unit="calendar-day clusters; independence not proven", uncertainty="small-cluster t sandwich diagnostic" if ci else "no valid small-cluster ratio interval claimed", ci=tuple(ci) if ci else None, source_hashes=hashes, config_hash=digest(ROOT / "config/contract.json"), model_id=digest(model_path), outcome="UNDERPOWERED", limitations=limits))
    report = {"status": "EXECUTED", "scientific_outcome": "UNDERPOWERED", "protocol": protocol, "freeze": freeze, "crossfit_reward_diagnostics": crossfit, "identity_control": {"passed": True, "observed_final_random_mean": observed, "uniform_IPS_SNIPS_equal_mean": True}, "estimates": estimates, "records": records, "limitations": limits, "BTS_comparison": "Not used as ground truth; arbitrary target not documented BTS", "host_memory_profile": "DuckDB256MB; two threads; all-action reward prediction in1024-row chunks"}
    artifact = study.finish("E05", report, "ope", science="UNDERPOWERED", capabilities={"R4_FIXED_POLICY_OPE": True})
    print(json.dumps({"artifact": str(artifact), "status": "EXECUTED_UNDERPOWERED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
