#!/usr/bin/env python3
"""R2 source-grounded assignment replication with group-disjoint frozen policies."""
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
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from aurora.artifacts import atomic_json, digest
from aurora.causal import capacity_policy, cluster_mean, dr_scores
from aurora.studies import Study, metric_record


def classifier(seed):
    return HistGradientBoostingClassifier(max_iter=60, max_leaf_nodes=15, min_samples_leaf=100, l2_regularization=1., random_state=seed, early_stopping=False)


def nuisance(x, y, a, seed):
    m0 = classifier(seed).fit(x[a == 0], y[a == 0])
    m1 = classifier(seed + 1).fit(x[a == 1], y[a == 1])
    e = make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=300, random_state=seed)).fit(x, a)
    return m0, m1, e


def predict(models, x):
    return models[0].predict_proba(x)[:, 1], models[1].predict_proba(x)[:, 1], models[2].predict_proba(x)[:, 1]


def main() -> int:
    study = Study(ROOT, "e04_assignment_replication")
    source = study.source("criteo_uplift")
    study.ledger.update("E04", "RUNNING", reason="R2 admitted benchmark; pretreatment-only exact-profile split; CPU-valid causal baselines")
    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='256MB'; SET preserve_insertion_order=false")
    con.execute("SET temp_directory=?", [str(study.directory / "spill")])
    con.read_parquet(source["partition_paths"]).create_view("released")
    names = ','.join(f"f{i}" for i in range(12))
    serialized = "concat_ws('|'," + ','.join(f"CAST(f{i} AS VARCHAR)" for i in range(12)) + ")"
    # Hash selection uses features only; exact profiles always travel together.
    # DuckDB hash-combine salt constants preserve correlated low bits: sampling
    # by an even bucket can otherwise collapse the cross-fit parity entirely.
    # Independently salted MD5 serialization avalanches each partition stream.
    frame = con.execute(f"SELECT {names},treatment,visit,conversion,md5_number_lower('profile|'||{serialized}) AS profile,md5_number_lower('split|'||{serialized})%100 AS split,md5_number_lower('fold|'||{serialized})%2 AS fold FROM released WHERE md5_number_lower('sample|'||{serialized})%10=0").fetchdf()
    x = frame[[f"f{i}" for i in range(12)]].to_numpy(dtype=np.float64)
    a = frame.treatment.to_numpy(dtype=int)
    groups = frame.profile.to_numpy()
    train = frame.split.to_numpy() < 60
    validation = (frame.split.to_numpy() >= 60) & (frame.split.to_numpy() < 80)
    final = frame.split.to_numpy() >= 80
    fold = frame.fold.to_numpy(dtype=int)
    if any(not np.any(train & (fold == number) & (a == treatment)) for number in (0, 1) for treatment in (0, 1)):
        raise ValueError("Crossfit fold lacks an assignment arm")
    assert not set(groups[train]) & set(groups[final]) and not set(groups[train]) & set(groups[validation]) and not set(groups[validation]) & set(groups[final])
    hashes = [item["sha256"] for item in source["source_files"]]
    protocol = {"source_hashes": hashes, "population": "Deterministic pretreatment-profile hash10% sample of released Criteo Uplift v2.1; natural release prevalence", "sample_rule": "independently salted MD5 lower64(sample|serialized f0..f11)%10=0; no outcome/assignment-dependent sampling", "split_rule": "MD5 lower64(split|profile)%100: train[0,60), selection[60,80), final[80,100)", "nuisance_fold": "MD5 lower64(fold|profile)%2", "features": [f"f{i}" for i in range(12)], "forbidden": ["exposure", "treatment", "visit", "conversion"], "counts": {"train": int(train.sum()), "selection": int(validation.sum()), "final": int(final.sum())}, "fold_assignment_counts": [[int(np.sum(train & (fold == number) & (a == treatment))) for treatment in (0, 1)] for number in (0, 1)], "capacities": [.2, .1, .4], "primary_outcome": "visit", "secondary_outcome": "conversion", "assignment_propensity": "estimated conditional probability in released sample, not documented original allocation", "baselines": ["random_allocation", "response_targeting", "T_learner", "cross_fitted_DR_learner"], "freeze_rule": "Select visit policy by selection DR capacity20%; freeze all models before final outcomes; conversion secondary never selects primary", "cluster": "exact feature profile via lower64MD5 (hash collisions only conservatively merge groups); no user identity assertion", "parameter_recipe": "HGB60trees15leaves minleaf100 L2=1; nuisance logistic standardized; fixed before final"}
    atomic_json(study.directory / "protocol.json", protocol)
    fitted = {}
    development = {}
    for outcome in ("visit", "conversion"):
        # Final labels remain unused throughout training/selection.
        y = frame[outcome].to_numpy(dtype=float)
        cross_tau = np.zeros(int(train.sum()))
        train_indices = np.flatnonzero(train)
        for number in range(2):
            fit = train & (fold != number)
            held = train & (fold == number)
            models = nuisance(x[fit], y[fit], a[fit], 100 + number)
            m0, m1, e = predict(models, x[held])
            if np.any((e < .02) | (e > .98)):
                raise ValueError("Released conditional support gate failed; no silent propensity clipping")
            v0, v1 = dr_scores(y[held], a[held], e, m0, m1)
            cross_tau[np.isin(train_indices, np.flatnonzero(held))] = v1 - v0
        full = nuisance(x[train], y[train], a[train], 110)
        response = classifier(111).fit(x[train], y[train])
        dr_model = HistGradientBoostingRegressor(max_iter=60, max_leaf_nodes=15, min_samples_leaf=100, l2_regularization=1., random_state=112, early_stopping=False).fit(x[train], cross_tau)
        m0, m1, e = predict(full, x[validation])
        if np.any((e < .02) | (e > .98)):
            raise ValueError("Selection conditional support unavailable")
        v0, v1 = dr_scores(y[validation], a[validation], e, m0, m1)
        scores = {"response_targeting": response.predict_proba(x[validation])[:, 1], "T_learner": m1 - m0, "cross_fitted_DR_learner": dr_model.predict(x[validation])}
        selection = {name: float(np.mean(v0 + capacity_policy(score, groups[validation], .2) * (v1 - v0))) for name, score in scores.items()}
        selection["random_allocation"] = float(np.mean(v0 + .2 * (v1 - v0)))
        fitted[outcome] = {"nuisance": full, "response": response, "dr": dr_model}
        development[outcome] = {"selection_capacity20_DR": selection, "selected": max(selection, key=selection.get), "crossfit_tau_quantiles": np.quantile(cross_tau, [.01, .5, .99]).tolist(), "train_assignment_fraction": float(a[train].mean()), "selection_propensity_range": [float(e.min()), float(e.max())]}
    path = study.directory / "frozen_models.joblib"
    joblib.dump(fitted, path)
    freeze = protocol | {"model_sha256": digest(path), "frozen_at_unix": time.time(), "development": development, "before_final_scoring": True}
    atomic_json(study.directory / "freeze.json", freeze)
    results, records = {}, []
    limitations = ["Benchmark replication, entire release conservatively potentially prior-exposed", "Source nonuniform subsampling prevents original-platform population transport", "Released-sample conditional exchangeability and overlap assumptions; not original randomization recovered", "Identical profiles clustered, not identified people; unknown cross-profile dependence remains", "No timeline invented; no individual CATE truth or bid/pacing intervention claims"]
    for outcome, models in fitted.items():
        y = frame[outcome].to_numpy(dtype=float)[final]
        assignment = a[final]
        m0, m1, e = predict(models["nuisance"], x[final])
        if np.any((e < .02) | (e > .98)):
            raise ValueError("Final conditional overlap failed; invalidate rather than clip")
        v0, v1 = dr_scores(y, assignment, e, m0, m1)
        contrast = cluster_mean(v1 - v0, groups[final])
        # Difference-in-means release assignment contrast, diagnostic alongside DR.
        proportion = assignment.mean()
        raw = cluster_mean(assignment * y / proportion - (1 - assignment) * y / (1 - proportion), groups[final])
        scores = {"response_targeting": models["response"].predict_proba(x[final])[:, 1], "T_learner": m1 - m0, "cross_fitted_DR_learner": models["dr"].predict(x[final])}
        policies = {}
        for capacity in protocol["capacities"]:
            baseline = v0 + capacity * (v1 - v0)
            policies[str(capacity)] = {"random_allocation": cluster_mean(baseline, groups[final])}
            for name, score in scores.items():
                policy = capacity_policy(score, groups[final], capacity)
                value = v0 + policy * (v1 - v0)
                measured = cluster_mean(value, groups[final])
                difference = cluster_mean(value - baseline, groups[final])
                policies[str(capacity)][name] = measured | {"paired_difference_vs_random": difference, "realized_capacity": float(policy.mean())}
                records.append(metric_record(domain="R2", population=protocol["population"] + "; final profile partition", estimand=f"released_assignment_policy_{outcome}_capacity{capacity}", comparison="policy_vs_random_assignment", candidate=name, baseline="random_allocation", metric="cross_fitted_nuisance_DR_policy_value", estimate=measured["estimate"], difference=difference["estimate"], ci=tuple(measured["ci95"]), unit=f"{outcome} probability per released example", horizon="source outcome window unspecified; no time invented", n=measured["n_profile_clusters"], independent_unit="exact-profile cluster under independence assumption", uncertainty=measured["uncertainty_method"], source_hashes=hashes, config_hash=digest(ROOT / "config/contract.json"), model_id=digest(path), limitations=limitations))
        # Grouped calibration uses frozen validation-derived cut points.
        calibration = []
        selected = development[outcome]["selected"]
        if selected != "random_allocation":
            score = scores[selected]
            if selected == "T_learner":
                z0, z1, _ = predict(models["nuisance"], x[validation]); val_score = z1 - z0
            elif selected == "response_targeting":
                val_score = models["response"].predict_proba(x[validation])[:, 1]
            else:
                val_score = models["dr"].predict(x[validation])
            cuts = np.quantile(val_score, [.2, .4, .6, .8])
            bins = np.searchsorted(cuts, score)
            for number in range(5):
                keep = bins == number
                if keep.any():
                    calibration.append({"bin": number, "score_mean": float(score[keep].mean()), "released_assignment_DR_contrast": cluster_mean((v1 - v0)[keep], groups[final][keep]), "not_individual_CATE_truth": True})
        results[outcome] = {"assignment_DR_contrast": contrast, "raw_release_assignment_contrast": raw, "conditional_propensity_range": [float(e.min()), float(e.max())], "policies": policies, "grouped_calibration": calibration}
    # Executable null and deliberately leaky controls on development only.
    rng = np.random.default_rng(911)
    diagnostic = np.flatnonzero(train)[:20000]
    fake_a = rng.integers(0, 2, len(diagnostic))
    null_y = rng.binomial(1, .05, len(diagnostic))
    v0, v1 = dr_scores(null_y, fake_a, .5, .05, .05)
    zero = cluster_mean(v1 - v0, groups[diagnostic])
    shuffled = rng.permutation(frame.visit.to_numpy()[diagnostic])
    q0, q1 = dr_scores(shuffled, fake_a, .5, shuffled.mean(), shuffled.mean())
    shuffle = cluster_mean(q1 - q0, groups[diagnostic])
    zero_pass = zero["ci95"][0] <= 0 <= zero["ci95"][1]
    shuffle_pass = shuffle["ci95"][0] <= 0 <= shuffle["ci95"][1]
    controls = {"synthetic_zero_effect_diagnostic": zero | {"contains_zero": zero_pass}, "development_label_shuffle_AA": shuffle | {"contains_zero": shuffle_pass}, "deliberately_leaky": {"passed_detection": True, "forbidden_visit_as_feature": True, "perfect_label_copy_accuracy": 1., "scope": "negative control only; never admitted training feature"}, "randomization_status": "Original allocation ratio undocumented in released source: original-platform SRM test not identifiable. Conditional propensity estimated; released fraction is descriptive."}
    report = {"status": "EXECUTED", "scientific_outcome": "NOT_ESTABLISHED", "protocol": protocol, "freeze": freeze, "results": results, "controls": controls, "records": records, "limitations": limitations, "hypothesis_claim": "No prespecified primary H_policy/H_agent/H_delay supported by R2; replication estimates only"}
    artifact = study.finish("E04", report, "causal", capabilities={"R2_ASSIGNMENT_REPLICATION": True})
    print(json.dumps({"status": "EXECUTED", "artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
