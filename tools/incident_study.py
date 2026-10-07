#!/usr/bin/env python3
"""E08 public-channel rules/XGBoost/temporal challenger; world-cluster diagnostics."""
from __future__ import annotations

import gc
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import joblib
import numpy as np
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, roc_auc_score

from aurora.artifacts import atomic_json, digest
from aurora.causal import cluster_mean
from aurora.incidents import FEATURE_NAMES, features, rule_scores, temporal_model, temporal_sequences
from aurora.prediction import calibrate, fit_calibrator
from aurora.resources import check_gpu_room, cuda_lease, telemetry
from aurora.simulator import FAMILIES, StaticController, WorldSpec, run_world
from aurora.studies import Study


def generate(argument):
    phase, number = argument
    stage = {"train": "train", "calibration": "calibration", "selection": "validation", "evaluation": "calibration"}[phase]
    index = {"train": 0, "calibration": 32, "selection": 16, "evaluation": 36}[phase] + number
    world_id = f"incident-{phase}-{number}"
    family = FAMILIES[number % 4]

    class Collector:
        def __init__(self):
            self.rows = []

        def choose(self, snapshot):
            self.rows.append((features(snapshot), snapshot.campaign, snapshot.interval))
            return StaticController().choose(snapshot)

    collector = Collector()
    result = run_world(WorldSpec(world_id, family, stage=stage, parameter_index=index), collector)
    x = np.stack([row[0] for row in collector.rows])
    campaigns = np.array([row[1] for row in collector.rows])
    intervals = np.array([row[2] for row in collector.rows])
    # Truth labels are evaluator-only. None enter snapshots or feature extraction.
    labels = np.zeros(len(x), dtype=int)
    if family == "reporting_competition_shift":
        labels[intervals >= 7 * 96] = 1
        labels[(intervals >= 7 * 96) & (intervals < 9 * 96)] = 2
    return {"x": x, "sequence": temporal_sequences(x, campaigns, intervals), "y": labels, "world": np.repeat(world_id, len(x)), "public_features": FEATURE_NAMES, "truth_metadata": {"family": family, "parameter_index": index, "stage": stage, "endpoint_utility": result.utility}}


def evaluate(probability, labels, worlds, threshold, cost):
    predicted = probability >= threshold
    actual = labels > 0
    output = {"confusion": confusion_matrix(actual, predicted, labels=[False, True]).tolist(), "any_incident_pr_auc": float(average_precision_score(actual, probability)), "any_incident_auroc": float(roc_auc_score(actual, probability)), "alarm_threshold": threshold, "worlds": {}}
    per_world_cost = []
    for world in np.unique(worlds):
        keep = worlds == world
        fn = int(np.sum(actual[keep] & ~predicted[keep]))
        fp = int(np.sum(~actual[keep] & predicted[keep]))
        loss = (cost["missed_incident_interval"] * fn + cost["unnecessary_alarm_interval"] * fp) / keep.sum()
        per_world_cost.append(loss)
        output["worlds"][str(world)] = {"missed_incident_intervals": fn, "unnecessary_alarm_intervals": fp, "declared_decision_loss_per_interval": loss}
    output["world_macro_decision_loss"] = cluster_mean(per_world_cost, np.arange(len(per_world_cost)))
    output["cost_interpretation"] = cost["unit"]
    output["scientific_outcome"] = "UNDERPOWERED"
    return output


def main():
    study = Study(ROOT, "e08_incident_development")
    study.ledger.update("E08", "RUNNING", reason="Qualified S1; public-signal detector roster, world-disjoint development and diagnostic evaluation")
    contract = json.loads((ROOT / "config/incidents.json").read_text())
    phases = ("train", "calibration", "selection", "evaluation")
    # Two bounded CPU workers; no CUDA imports/contexts in child workers.
    with ProcessPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(generate, [(phase, number) for phase in phases for number in range(4)]))
    data = {}
    for i, phase in enumerate(phases):
        values = outputs[i * 4:(i + 1) * 4]
        data[phase] = {key: np.concatenate([item[key] for item in values]) for key in ("x", "sequence", "y", "world")}
        path = study.directory / (phase + "_dataset.npz")
        np.savez_compressed(path, **data[phase])
    source_hashes = {phase: digest(study.directory / (phase + "_dataset.npz")) for phase in phases}
    protocol = {"contract": contract, "dataset_hashes": source_hashes, "public_feature_catalog": FEATURE_NAMES, "evaluator_only_truth": [item["truth_metadata"] for item in outputs], "no_final_policy_worlds_generated": True, "cross_world_splits": True, "evaluation_worlds": 4}
    atomic_json(study.directory / "protocol.json", protocol)
    candidates = []
    predictions = {}
    for name, position in (("impression_only_rule", 0), ("multi_signal_rule", 1)):
        predictions[name] = {phase: rule_scores(data[phase]["x"])[position] for phase in phases}
        candidates.append({"id": name, "family": "rule", "rule_position": position})
    check_gpu_room(8)
    import torch
    import xgboost as xgb
    torch.set_num_threads(2)
    with cuda_lease(study.runtime):
        for depth in (3, 5):
            name = f"XGBoost_CUDA_depth{depth}"
            started = time.perf_counter()
            model = xgb.XGBClassifier(n_estimators=128, max_depth=depth, learning_rate=.05, tree_method="hist", device="cuda", n_jobs=2, random_state=43).fit(data["train"]["x"], data["train"]["y"])
            predictions[name] = {phase: 1 - model.predict_proba(data[phase]["x"])[:, 0] for phase in ("calibration", "selection")}
            path = study.directory / (name + ".json")
            model.save_model(path)
            candidates.append({"id": name, "family": "XGBoost_CUDA", "path": str(path), "sha256": digest(path), "training_wall_seconds": time.perf_counter() - started})
            del model
        for hidden in (8, 16):
            name = f"temporal_GRU_hidden{hidden}"
            started = time.perf_counter()
            torch.manual_seed(43)
            model = temporal_model(hidden).cuda()
            optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
            generator = np.random.default_rng(43)
            for epoch in range(3):
                model.train()
                order = generator.permutation(len(data["train"]["y"]))
                for begin in range(0, len(order), 512):
                    index = order[begin:begin + 512]
                    sequence = torch.as_tensor(data["train"]["sequence"][index], device="cuda")
                    label = torch.as_tensor(data["train"]["y"][index], device="cuda")
                    optimizer.zero_grad(set_to_none=True)
                    loss = torch.nn.functional.cross_entropy(model(sequence), label)
                    loss.backward()
                    assert torch.isfinite(loss)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
                    optimizer.step()
            model.eval()
            predictions[name] = {}
            with torch.no_grad():
                for phase in ("calibration", "selection"):
                    predictions[name][phase] = np.concatenate([(1 - torch.softmax(model(torch.as_tensor(data[phase]["sequence"][begin:begin + 2048], device="cuda")), dim=1)[:, 0]).cpu().numpy() for begin in range(0, len(data[phase]["y"]), 2048)])
            path = study.directory / (name + ".pt")
            torch.save(model.state_dict(), path)
            candidates.append({"id": name, "family": "temporal_GRU", "hidden": hidden, "path": str(path), "sha256": digest(path), "epochs": 3, "training_wall_seconds": time.perf_counter() - started})
            del model, optimizer
            gc.collect(); torch.cuda.empty_cache()
        selection = {}
        for recipe in candidates:
            name = recipe["id"]
            cal = fit_calibrator(data["calibration"]["y"] > 0, predictions[name]["calibration"])
            cal_path = study.directory / (name + "_calibrator.joblib")
            joblib.dump(cal, cal_path)
            recipe.update(calibrator_path=str(cal_path), calibrator_sha256=digest(cal_path))
            scores = calibrate(cal, predictions[name]["selection"])
            evaluated = [evaluate(scores, data["selection"]["y"], data["selection"]["world"], threshold, contract["selection_cost"]) for threshold in contract["alarm_threshold_grid"]]
            best = min(evaluated, key=lambda result: result["world_macro_decision_loss"]["estimate"])
            recipe["threshold"] = best["alarm_threshold"]
            selection[name] = best
        selected = min(selection, key=lambda name: selection[name]["world_macro_decision_loss"]["estimate"])
        freeze = protocol | {"candidates": candidates, "selected": selected, "selection": selection, "frozen_at_unix": time.time(), "before_evaluation_scoring": True, "telemetry": telemetry()}
        atomic_json(study.directory / "freeze.json", freeze)
        atomic_json(ROOT / "reports/incidents/DETECTOR_FREEZE.json", freeze)
        final = {}
        for recipe in candidates:
            name = recipe["id"]
            if recipe["family"] == "rule":
                raw = predictions[name]["evaluation"]
            elif recipe["family"] == "XGBoost_CUDA":
                model = xgb.XGBClassifier(); model.load_model(recipe["path"])
                raw = 1 - model.predict_proba(data["evaluation"]["x"])[:, 0]
                final_multiclass = model.predict(data["evaluation"]["x"])
                recipe["diagnostic_joint_state_macro_F1"] = float(f1_score(data["evaluation"]["y"], final_multiclass, average="macro"))
                del model
            else:
                model = temporal_model(recipe["hidden"]).cuda()
                model.load_state_dict(torch.load(recipe["path"], map_location="cuda", weights_only=True)); model.eval()
                with torch.no_grad():
                    raw = np.concatenate([(1 - torch.softmax(model(torch.as_tensor(data["evaluation"]["sequence"][begin:begin + 2048], device="cuda")), dim=1)[:, 0]).cpu().numpy() for begin in range(0, len(data["evaluation"]["y"]), 2048)])
                del model; torch.cuda.empty_cache()
            score = calibrate(joblib.load(recipe["calibrator_path"]), raw)
            final[name] = evaluate(score, data["evaluation"]["y"], data["evaluation"]["world"], recipe["threshold"], contract["selection_cost"])
            np.savez_compressed(study.directory / (name + "_immutable_predictions.npz"), score=score, label=data["evaluation"]["y"], world=data["evaluation"]["world"])
    report = {"status": "EXECUTED", "scientific_outcome": "UNDERPOWERED", "freeze": freeze, "results": final, "selected_on_development": selected, "no_reselection": True, "immutable_prediction_hashes": {path.name: digest(path) for path in study.directory.glob("*_immutable_predictions.npz")}, "limitations": ["Only4 independent diagnostic worlds, not43400 independent interval replicates", "Joint competition/reporting states may be observationally ambiguous; predictions do not identify causal root cause", "Declared missed-incident/false-alarm loss is synthetic and not measured economic impact", "Complete policy utility and OOD mechanism qualification remain separate", "Fixed change times can induce shortcuts; whole-mechanism OOD evaluated separately", "No held-out fault labels or family identifiers supplied to detector input"]}
    artifact = study.finish("E08", report, "incidents", science="UNDERPOWERED", capabilities={"detector_roster_qualified": True})
    print(json.dumps({"status": "EXECUTED", "artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
