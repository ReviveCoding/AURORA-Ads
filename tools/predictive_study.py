#!/usr/bin/env python3
"""R1 real CUDA model ladder; separate frozen confirmation, no R3 coupling."""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb
import joblib
import numpy as np
import torch
import xgboost as xgb
from sklearn.linear_model import SGDClassifier

from aurora.artifacts import atomic_json, digest
from aurora.causal import cluster_mean
from aurora.prediction import calibrate, categorical_frame, fit_calibrator, hashed_features, neural_model, neural_probability, proper_scores
from aurora.resources import check_gpu_room, cuda_lease, telemetry
from aurora.studies import Study, metric_record


def data(study, source):
    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='256MB'; SET preserve_insertion_order=false")
    con.execute("SET temp_directory=?", [str(study.directory / "spill")])
    con.read_parquet(source["partition_paths"]).create_view("events")
    lo, hi = con.execute("SELECT MIN(timestamp),MAX(timestamp) FROM events").fetchone()
    columns = ["campaign", *[f"cat{i}" for i in range(1, 10)]]
    fields = ','.join(f'hash("{name}")%1024 AS "{name}"' for name in columns)
    frame = con.execute(f"SELECT {fields},click,CAST(uid AS VARCHAR) AS uid,timestamp FROM events WHERE hash(uid,timestamp,campaign,{','.join(columns[1:])})%10=0").fetchdf()
    normalized = (frame.timestamp.to_numpy() - lo) / (hi - lo)
    masks = {"train": normalized < .6, "calibration": (normalized >= .6) & (normalized < .7), "selection": (normalized >= .7) & (normalized < .8), "final": normalized >= .8}
    # Bound the declared developer cohort without selecting on outcomes.
    indices = np.flatnonzero(masks["train"])
    if len(indices) > 2_000_000:
        masks["train"][indices[2_000_000:]] = False
    if masks["train"].sum() < 500000:
        raise ValueError("Declared developer cohort minimum500k unavailable")
    blocks = np.minimum(19, np.maximum(0, np.floor((normalized - .8) / .2 * 20))).astype(int)
    return frame[columns].to_numpy(dtype=np.int64), frame.click.to_numpy(dtype=np.float32), frame.uid.to_numpy(), masks, blocks, {"native_time_min": lo, "native_time_max": hi, "native_time_units": "publisher-native ordered clock; no calendar-unit assertion", "cut_fractions": [.6, .7, .8], "feature_columns": columns, "sampling": "outcome-blind hash(uid,timestamp,campaign,cat1..9)%10=0; natural selected-cohort prevalence", "counts": {name: int(mask.sum()) for name, mask in masks.items()}, "categorical_encoding": "stateless per-field source-category hashmod1024 shared across all models; collisions retained", "feature_eligibility": "campaign+cat1..9 only; all post-impression fields, uid, realized cost and unverified histories excluded"}


def predict(recipe, codes):
    model = joblib.load(recipe["model_path"]) if recipe["family"] in {"prior", "hashed_logistic"} else None
    if recipe["family"] == "prior":
        return np.full(len(codes), model)
    if recipe["family"] == "hashed_logistic":
        outputs = [model.predict_proba(hashed_features(codes[start:start + 65536]))[:, 1] for start in range(0, len(codes), 65536)]
        return np.concatenate(outputs)
    if recipe["family"] == "xgboost_cuda":
        model = xgb.XGBClassifier()
        model.load_model(recipe["model_path"])
        return model.predict_proba(categorical_frame(codes))[:, 1]
    model = neural_model(codes.shape[1], recipe["embedding"], recipe["width"], recipe["family"] == "DCNv2").cuda()
    model.load_state_dict(torch.load(recipe["model_path"], map_location="cuda", weights_only=True))
    result = neural_probability(model, codes)
    del model
    torch.cuda.empty_cache()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    study = Study(ROOT, "e15_r1_confirmation" if args.confirm else "e02_prediction_development")
    if args.confirm and study.ledger.read()["nodes"]["E15_R1"]["execution_status"] == "EXECUTED":
        raise ValueError("Frozen final already executed; do not rescore/reselect. Read its immutable artifact.")
    source = study.source("criteo_attribution")
    gpu = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())
    if not gpu["GPU_QUALIFIED"]:
        raise ValueError("Actual GPU qualification required; no silent CPU training fallback")
    check_gpu_room(8)
    codes, y, groups, masks, time_blocks, protocol = data(study, source)
    source_hashes = [value["sha256"] for value in source["source_files"]]
    protocol.update(source_hashes=source_hashes, numerical_probability_clip=[1e-7, 1 - 1e-7], selection_metric="proper logloss", calibration="Independent temporal calibration partition Platt vs identity, selected on selection partition", fixed_reliability_bins=list(np.arange(0, 1.01, .1)), source_scope="benchmark replication only; not production incremental value")
    atomic_json(study.directory / "protocol.json", protocol)
    candidates, telemetry_log = [], []
    with cuda_lease(study.runtime):
        if not args.confirm:
            study.ledger.update("E02", "RUNNING", reason="Admitted R1 natural-prevalence cohort; matched CPU logistic + actual CUDA XGB/MLP/DCNv2 ladder")
            train = masks["train"]
            xtrain, ytrain = codes[train], y[train]

            def register(recipe, started, update_count):
                calibration_p = predict(recipe, codes[masks["calibration"]])
                platt = fit_calibrator(y[masks["calibration"]], calibration_p)
                cal_path = study.directory / (recipe["id"] + "_calibrator.joblib")
                joblib.dump(platt, cal_path)
                raw = predict(recipe, codes[masks["selection"]])
                measurements = {}
                for name, cal in (("identity", None), ("Platt", platt)):
                    score, _ = proper_scores(y[masks["selection"]], calibrate(cal, raw))
                    measurements[name] = score
                selected = min(measurements, key=lambda name: measurements[name]["logloss"])
                recipe.update(calibrator_path=str(cal_path), calibrator_sha256=digest(cal_path), calibration_choice=selected, model_sha256=digest(Path(recipe["model_path"])), selection=measurements, selected_logloss=measurements[selected]["logloss"], fit_and_selection_wall_seconds=time.perf_counter() - started, updates=update_count, training_rows=int(train.sum()))
                candidates.append(recipe)
                atomic_json(study.directory / "candidate_progress.json", {"candidates": candidates})
                observed = telemetry()
                telemetry_log.append(observed)
                if observed["temperature_c"] >= gpu["device_reported_target_c"]:
                    raise ValueError("Device-reported operating target reached; sustained stability unclear")

            start = time.perf_counter()
            path = study.directory / "prior.joblib"
            joblib.dump(float(ytrain.mean()), path)
            register({"id": "P0_prior", "family": "prior", "model_path": str(path)}, start, 0)
            for alpha in (1e-5, 1e-4):
                start = time.perf_counter()
                model = SGDClassifier(loss="log_loss", alpha=alpha, learning_rate="optimal", random_state=41, average=True)
                generator = np.random.default_rng(41)
                for epoch in range(3):
                    order = generator.permutation(len(xtrain))
                    for begin in range(0, len(order), 65536):
                        chunk = order[begin:begin + 65536]
                        model.partial_fit(hashed_features(xtrain[chunk]), ytrain[chunk], classes=[0, 1])
                path = study.directory / f"logistic_{alpha}.joblib"
                joblib.dump(model, path)
                register({"id": f"P1_alpha{alpha}", "family": "hashed_logistic", "alpha": alpha, "epochs": 3, "model_path": str(path)}, start, 3 * int(np.ceil(len(xtrain) / 65536)))
                del model
            for depth in (4, 6):
                start = time.perf_counter()
                model = xgb.XGBClassifier(n_estimators=128, max_depth=depth, learning_rate=.1, subsample=1., colsample_bytree=1., reg_lambda=1., tree_method="hist", device="cuda", enable_categorical=True, max_cat_to_onehot=4, random_state=41, n_jobs=2)
                model.fit(categorical_frame(xtrain), ytrain)
                path = study.directory / f"xgb_depth{depth}.json"
                model.save_model(path)
                del model
                register({"id": f"P2_depth{depth}", "family": "xgboost_cuda", "depth": depth, "trees": 128, "model_path": str(path)}, start, 128)
            torch.set_num_threads(2)
            for family in ("embedding_MLP", "DCNv2"):
                for embedding, width, epochs in ((8, 64, 3), (16, 128, 4)):
                    start = time.perf_counter()
                    torch.manual_seed(41)
                    model = neural_model(10, embedding, width, family == "DCNv2").cuda()
                    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=1e-4)
                    generator = np.random.default_rng(41)
                    epoch_losses = []
                    for epoch in range(epochs):
                        model.train()
                        order = generator.permutation(len(xtrain))
                        summed = 0.
                        for begin in range(0, len(order), 4096):
                            chunk = order[begin:begin + 4096]
                            xx = torch.as_tensor(xtrain[chunk], dtype=torch.long, device="cuda")
                            yy = torch.as_tensor(ytrain[chunk], dtype=torch.float32, device="cuda")
                            optimizer.zero_grad(set_to_none=True)
                            loss = torch.nn.functional.binary_cross_entropy_with_logits(model(xx), yy)
                            loss.backward()
                            if not torch.isfinite(loss) or not all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()):
                                raise ValueError("Neural nonfinite gradient")
                            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
                            optimizer.step()
                            summed += float(loss.detach()) * len(chunk)
                        epoch_losses.append(summed / len(xtrain))
                        observed = telemetry()
                        telemetry_log.append(observed)
                        if observed["temperature_c"] >= gpu["device_reported_target_c"]:
                            raise ValueError("Device-reported thermal target reached")
                    path = study.directory / f"{family}_emb{embedding}.pt"
                    torch.save(model.state_dict(), path)
                    del model, optimizer
                    gc.collect(); torch.cuda.empty_cache()
                    register({"id": f"{family}_emb{embedding}", "family": family, "embedding": embedding, "width": width, "epochs": epochs, "epoch_training_logloss": epoch_losses, "model_path": str(path)}, start, epochs * int(np.ceil(len(xtrain) / 4096)))
            selected = min(candidates, key=lambda row: row["selected_logloss"])
            freeze = {"protocol": protocol, "candidates": candidates, "selected": selected["id"], "frozen_at_unix": time.time(), "final_outcomes_scored": False, "telemetry": telemetry_log, "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(), "scope": "all methods share fields, sample/prevalence, temporal partitions and calibration choices; optimization exposures separately disclosed"}
            freeze_path = ROOT / "reports/model/R1_FREEZE.json"
            atomic_json(study.directory / "freeze.json", freeze)
            atomic_json(freeze_path, freeze)
            artifact = study.finish("E02", freeze, "model", capabilities={"R1_MODELS_DEVELOPED": True})
            study.ledger.update("E15_R1_FREEZE", "EXECUTED", artifacts=(freeze_path,), reason="Selected by temporal development logloss; model+calibrator hashes bound before final scoring", capabilities={"R1_FROZEN": True})
            study.export_state()
        else:
            freeze_path = ROOT / "reports/model/R1_FREEZE.json"
            freeze = json.loads(freeze_path.read_text())
            if freeze["protocol"] != protocol:
                raise ValueError("Confirmation population/protocol differs from freeze")
            study.ledger.update("E15_R1", "RUNNING", reason="Independent frozen R1 confirmation; no model or calibrator refit")
            final = masks["final"]
            results, losses, prediction_artifacts = {}, {}, {}
            for recipe in freeze["candidates"]:
                if digest(Path(recipe["model_path"])) != recipe["model_sha256"] or digest(Path(recipe["calibrator_path"])) != recipe["calibrator_sha256"]:
                    raise ValueError("Frozen model/calibrator identity mismatch")
                cal = joblib.load(recipe["calibrator_path"]) if recipe["calibration_choice"] == "Platt" else None
                p = calibrate(cal, predict(recipe, codes[final]))
                prediction_path = study.directory / (recipe["id"] + "_immutable_final_predictions.npz")
                np.savez_compressed(prediction_path, prediction=p, observed=y[final], uid=groups[final].astype(str), time_block=time_blocks[final])
                prediction_artifacts[recipe["id"]] = {"path": str(prediction_path), "sha256": digest(prediction_path)}
                results[recipe["id"]], losses[recipe["id"]] = proper_scores(y[final], p)
            baseline = "P0_prior"
            records = []
            comparisons = {}
            conventional = min([recipe for recipe in freeze["candidates"] if recipe["family"] in {"prior", "hashed_logistic", "xgboost_cuda"}], key=lambda recipe: recipe["selected_logloss"])["id"]
            for recipe in freeze["candidates"]:
                identifier = recipe["id"]
                comparison = cluster_mean(losses[identifier] - losses[baseline], groups[final])
                comparisons[identifier] = comparison | {"native_time20block_sensitivity": cluster_mean(losses[identifier] - losses[baseline], time_blocks[final]), "paired_vs_development_selected_conventional": cluster_mean(losses[identifier] - losses[conventional], groups[final]), "conventional_time_block_sensitivity": cluster_mean(losses[identifier] - losses[conventional], time_blocks[final])}
                records.append(metric_record(domain="R1", population="Admitted Criteo attribution; native-time final[80%,100%] selected impressions; natural prevalence", estimand="recorded_impression_click_prediction", comparison="frozen_candidate_vs_prior", candidate=identifier, baseline=baseline, metric="logloss", estimate=results[identifier]["logloss"], difference=comparison["estimate"], unit="nats per impression", horizon="recorded impression click; source reporting availability unspecified", n=comparison["n_profile_clusters"], independent_unit="uid cluster; unknown cross-user campaign dependence", uncertainty=comparison["uncertainty_method"].replace("exact-profile", "source uid"), source_hashes=source_hashes, config_hash=digest(ROOT / "config/contract.json"), model_id=recipe["model_sha256"] + "+" + recipe["calibrator_sha256"], limitations=["Benchmark replication only; no virgin external confirmation", "No production or incremental value interpretation", "Shared campaign/time dependence beyond uid clustering may widen uncertainty", "Finite unequal optimization exposure disclosed", "No R1×R3 calibrated-probability product"]))
            report = {"status": "EXECUTED", "scientific_outcome": "NOT_ESTABLISHED", "freeze_sha256": digest(freeze_path), "selected_on_development": freeze["selected"], "development_selected_conventional": conventional, "final_results": results, "paired_logloss_vs_prior": comparisons, "immutable_predictions": prediction_artifacts, "records": records, "no_reselection": True, "final_scope": "Frozen internal temporal benchmark replication; not external unseen-data claim", "secondary_reliability_implementation_fix": "Use contiguous linspace edges, replacing floating-point lower+.1 overlaps; development-selected proper logloss and calibration unaffected; before final scoring", "telemetry_end": telemetry()}
            artifact = study.finish("E15_R1", report, "model", capabilities={"R1_FROZEN_CONFIRMATION": True})
    print(json.dumps({"status": "EXECUTED", "artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
