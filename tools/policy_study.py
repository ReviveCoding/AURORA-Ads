#!/usr/bin/env python3
"""Resumable policy stages, beginning with observed-only randomized S1 warmstart."""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import joblib
import numpy as np
from sklearn.neighbors import KDTree

from aurora.artifacts import atomic_json, digest
from aurora.incidents import FEATURE_NAMES, features
from aurora.resources import check_gpu_room, cuda_lease, telemetry
from aurora.simulator import FAMILIES, WorldSpec, run_world
from aurora.state import Action
from aurora.studies import Study
from aurora.policies import BanditController, PolicyParameters
from aurora.policy_registry import load_bundle
from aurora.simulator import StaticController


def generate(argument):
    stage, number = argument
    family = FAMILIES[number % 4]
    block = (0 if stage == "train" else 32) + number
    identity = f"warmstart-{stage}-{number}"

    class Collector:
        policy_seed = 735

        def __init__(self):
            self.rows = []

        def probabilities(self, snapshot):
            p = np.full(6, .1 / 6)
            p[0] += .9
            return p

        def observe(self, observation):
            self.rows.append(observation)

    collector = Collector()
    # Budget is chosen ex ante, not from realized traffic/spend.
    budget = (4000, 10000, 20000)[number % 3]
    result = run_world(WorldSpec(identity, family, budget_per_campaign=budget, stage=stage, parameter_index=block), collector)
    rows = collector.rows
    assert len(rows) == 8 * 1344 and len({row.cohort_id for row in rows}) == len(rows)
    return {"x": np.stack([features(row.origin_snapshot) for row in rows]), "action": np.array([tuple(Action).index(row.executed_action) for row in rows]), "propensity": np.array([row.executed_probability for row in rows]), "gross": np.array([row.observed_gross_value for row in rows]), "spend": np.array([row.actual_spend for row in rows]), "operating": np.array([row.operational_cost for row in rows]), "exposures": np.array([row.exposures for row in rows]), "purchase_count": np.array([row.observed_purchase_count for row in rows]), "delay_counts": np.array([row.observed_delay_counts for row in rows]), "cohort_id": np.array([row.cohort_id for row in rows]), "available_day": np.array([row.observed_at_day for row in rows]), "origin_interval": np.array([row.origin_interval for row in rows]), "world": np.repeat(identity, len(rows)), "evaluator_metadata": {"family": family, "block": block, "budget": budget, "completed_utility": result.utility, "not_learner_target": True}}


def warmstart(study):
    study.ledger.update("E09", "RUNNING", reason="Observed-cohort S1 warmstart; exact post-mask epsilon probabilities; no final-world data")
    study.export_state()
    with ProcessPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(generate, [("train", number) for number in range(8)] + [("calibration", number) for number in range(4)]))
    columns = [key for key in outputs[0] if key != "evaluator_metadata"]
    data = {stage: {column: np.concatenate([item[column] for item in outputs[indices]]) for column in columns} for stage, indices in (("train", slice(0, 8)), ("calibration", slice(8, 12)))}
    for stage in data:
        assert np.all((data[stage]["propensity"] > 0) & (data[stage]["propensity"] <= 1))
        assert np.all(data[stage]["available_day"] >= (data[stage]["origin_interval"] + 1) / 96 + 7)
        np.savez_compressed(study.directory / (stage + "_observed_cohorts.npz"), **data[stage])
    mean = data["train"]["x"].mean(0)
    scale = data["train"]["x"].std(0)
    scale = np.maximum(scale, .1)
    design = {stage: np.column_stack([(values["x"] - mean) / scale, np.eye(6)[values["action"]]]) for stage, values in data.items()}
    check_gpu_room(8)
    import torch
    import xgboost as xgb
    torch.set_num_threads(2)
    fits = {}
    with cuda_lease(study.runtime):
        for target in ("gross", "spend"):
            started = time.perf_counter()
            model = xgb.XGBRegressor(n_estimators=192, max_depth=4, learning_rate=.05, reg_lambda=10., tree_method="hist", device="cuda", random_state=47, n_jobs=2).fit(design["train"], data["train"][target])
            prediction = np.maximum(0, model.predict(design["calibration"]))
            path = study.directory / (target + "_xgb.json")
            model.save_model(path)
            fits[target] = {"path": str(path), "sha256": digest(path), "actual_cuda_fit": True, "fit_wall_seconds": time.perf_counter() - started, "calibration_mse": float(np.mean((prediction - data["calibration"][target])**2)), "calibration_prediction_mean": float(prediction.mean()), "calibration_observed_mean": float(data["calibration"][target].mean())}
            if target == "gross":
                residual = prediction - data["calibration"][target]
                residual_scale = np.array([max(1., np.sqrt(np.mean(residual[data["calibration"]["action"] == action]**2))) for action in range(6)])
            del model
        # Serious neural-linear TS representation, fitted to observed gross/spend
        # only, not a random network falsely called a trained neural baseline.
        torch.manual_seed(47)
        network = torch.nn.Sequential(torch.nn.Linear(len(FEATURE_NAMES), 32), torch.nn.ReLU(), torch.nn.Linear(32, 16), torch.nn.Tanh(), torch.nn.Linear(16, 2)).cuda()
        optimizer = torch.optim.AdamW(network.parameters(), lr=.001)
        generator = np.random.default_rng(47)
        x = ((data["train"]["x"] - mean) / scale).astype(np.float32)
        y = np.column_stack([data["train"]["gross"], data["train"]["spend"]]).astype(np.float32) / 100
        losses = []
        for epoch in range(5):
            order = generator.permutation(len(x))
            summed = 0.
            for begin in range(0, len(order), 1024):
                index = order[begin:begin + 1024]
                optimizer.zero_grad(set_to_none=True)
                prediction = network(torch.as_tensor(x[index], device="cuda"))
                loss = torch.nn.functional.mse_loss(prediction, torch.as_tensor(y[index], device="cuda"))
                loss.backward()
                assert torch.isfinite(loss)
                torch.nn.utils.clip_grad_norm_(network.parameters(), 5.)
                optimizer.step()
                summed += float(loss.detach()) * len(index)
            losses.append(summed / len(x))
        network.eval().cpu()
        neural_path = study.directory / "neural_value_representation.pt"
        torch.save(network.state_dict(), neural_path)
        # Freeze an inference-only representation that has no fault/truth inputs.
        scripted = torch.jit.trace(network[:-1], torch.zeros(1, len(FEATURE_NAMES)))
        script_path = study.directory / "neural_embedding.torchscript"
        scripted.save(str(script_path))
        fits["neural_representation"] = {"path": str(neural_path), "sha256": digest(neural_path), "embedding_path": str(script_path), "embedding_sha256": digest(script_path), "epoch_mse": losses, "actual_cuda_training": True, "target": "fully observed matured synthetic gross/spend only"}
        observed = telemetry()
        guidance = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())
        if observed["temperature_c"] >= guidance["device_reported_target_c"]:
            raise ValueError("Current device operating target reached")
    standardized = (data["train"]["x"] - mean) / scale
    support_path = study.directory / "public_support.joblib"
    joblib.dump({"tree": KDTree(standardized), "actions": data["train"]["action"]}, support_path)
    delay_counts = data["train"]["delay_counts"].sum(0)
    # Public receipt-delay CDF estimated from mature observed events; temporary
    # reporting lag is not silently called conversion occurrence delay.
    cdf = np.cumsum(delay_counts) / max(1, delay_counts.sum())
    report = {"status": "WARMSTART_FITTED_NOT_POLICY_DEVELOPMENT_COMPLETE", "source_domain": "S1_OBSERVED_MATURED", "study_id": study.name, "runtime_directory": str(study.directory), "model_fits": fits, "feature_names": FEATURE_NAMES, "scaler_mean": mean.tolist(), "scaler_scale": scale.tolist(), "action_residual_scale": residual_scale.tolist(), "support_path": str(support_path), "support_sha256": digest(support_path), "observed_receipt_delay_cdf": cdf.tolist(), "observed_delay_counts": delay_counts.tolist(), "cohort_artifacts": {stage: {"path": str(study.directory / (stage + "_observed_cohorts.npz")), "sha256": digest(study.directory / (stage + "_observed_cohorts.npz")), "cohorts": len(data[stage]["action"]), "worlds": len(np.unique(data[stage]["world"])), "action_counts": np.bincount(data[stage]["action"], minlength=6).tolist()} for stage in data}, "evaluator_only_metadata": [item["evaluator_metadata"] for item in outputs], "simulator_sha256": digest(ROOT / "src/aurora/simulator.py"), "blocks_sha256": digest(ROOT / "config/simulator_blocks.json"), "telemetry": observed, "limitations": ["Gross exposed purchase value is recorded observed reward, not evaluator incremental effect", "Not real R3 delay evidence or cross-domain calibration", "Receipt-delay empirical CDF includes declared reporting lag and view-through observed purchases", "Small independent warmstart world count does not certify whole-policy value", "Prospective full-world baseline selection, ablations, pilot and frozen confirmation remain"]}
    atomic_json(study.directory / "warmstart.json", report)
    artifact = ROOT / "reports/policy" / (study.name + "_warmstart.json")
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/policy/WARMSTART_LATEST.json", report | {"artifact": str(artifact), "sha256": digest(artifact)})
    study.ledger.update("E09", "CHECKPOINTED", artifacts=(artifact,), reason="Observed-cohort randomized warmstart/model fitting complete; full prospective development comparisons next", capabilities={"S1_OBSERVED_VALUE_MODELS": True, "S1_NEURAL_LINEAR_FEATURES": True})
    study.export_state()
    return artifact


_BUNDLE = None
_TRAINING = None


def initialize_worker(warm_path):
    global _BUNDLE, _TRAINING
    _BUNDLE, _TRAINING, _ = load_bundle(ROOT, Path(warm_path))


def evaluate_world(argument):
    recipe, number, stage, result_directory = argument
    started = time.perf_counter()
    family = FAMILIES[number % 4]
    bounds = {"validation": 16, "pilot": 64, "ood": 16}
    block = bounds[stage] + number % 16
    budget = (4000, 10000, 20000)[(number // 4) % 3]
    identity = f"policy-{stage}-world{number}"
    specification = WorldSpec(identity, family, budget_per_campaign=budget, stage=stage, parameter_index=block)
    if recipe["family"] == "static":
        controller = StaticController()
    else:
        parameters = PolicyParameters(**recipe["parameters"])
        controller = BanditController(_BUNDLE, parameters, _TRAINING["x"], _TRAINING["action"], _TRAINING["gross"], _TRAINING["spend"] + _TRAINING["operating"])
    result = run_world(specification, controller, base_bid=recipe.get("base_bid", 1.), no_ad=recipe.get("no_ad", False))
    record = {"recipe": recipe, "world_number": number, "stage": stage, "evaluation": asdict(result) | {"utility": result.utility}, "wall_seconds": time.perf_counter() - started, "observed_reward_updates": getattr(controller, "received_observation_count", 0), "controller_seed": recipe.get("parameters", {}).get("seed"), "unit": "completed independent synthetic world", "not_one_step_OPE": True}
    path = Path(result_directory) / f"{recipe['id']}__world{number}.json"
    atomic_json(path, record)
    return str(path)


def development(study):
    study.ledger.update("E09", "RUNNING", reason="Complete prospective development comparison; all arms common guards; no final-world outcomes")
    study.export_state()
    warm_path = ROOT / "reports/policy/WARMSTART_LATEST.json"
    warm = json.loads(warm_path.read_text())
    if warm["simulator_sha256"] != digest(ROOT / "src/aurora/simulator.py"):
        raise ValueError("Warmstart simulator differs; inspect scientific compatibility before proceeding")
    recipes = [{"id": "no_ad", "family": "static", "base_bid": 0., "no_ad": True}, {"id": "no_change", "family": "static", "base_bid": 1.}]
    recipes += [{"id": f"static_bid{bid}", "family": "static", "base_bid": bid} for bid in (0., .25, .5, .75, 1., 1.5, 2., 3.)]
    for name in ("rule_PID", "epsilon_greedy", "LinUCB", "neural_linear_TS", "MPC_pacing"):
        recipes.append({"id": name, "family": "bandit", "parameters": asdict(PolicyParameters(name))})
    for name in ("delay_TS_primal_dual", "support_gated_delay_TS", "MSCP_v2"):
        for eta in (.01, .05, .1):
            for maximum in (2., 5.):
                for beta in ((0., .5, 1.) if name == "MSCP_v2" else (.5,)):
                    identifier = f"{name}_eta{eta}_max{maximum}_beta{beta}"
                    recipes.append({"id": identifier, "family": "bandit", "parameters": asdict(PolicyParameters(name, eta=eta, lambda_max=maximum, beta=beta))})
    protocol = {"stage": "development", "recipes": recipes, "worlds": 12, "independent_units": "12 worlds; campaigns/events not independent", "family_weights": [.25] * 4, "budgets": [4000, 10000, 20000], "budget_selection": "ex-ante balanced family×budget validation design; no realized traffic adaptation", "world_parameter_blocks": list(range(16, 28)), "primary_recipe_selection": "highest equal-world completed utility mean; deterministic id tie-break; no final-world access", "warmstart_sha256": digest(warm_path), "simulator_sha256": digest(ROOT / "src/aurora/simulator.py"), "controller_sha256": digest(ROOT / "src/aurora/policies.py"), "registry_sha256": digest(ROOT / "src/aurora/policy_registry.py"), "script_sha256": digest(Path(__file__)), "common_guards": "Same atomic conservative settlement, budget, fallback, cooldown,15min duration, no budget increase; identical operating overhead", "controller_seeds": [41], "no_regret_or_adaptive_OPE_certificate": True}
    atomic_json(study.directory / "development_protocol.json", protocol)
    result_directory = study.directory / "world_results"
    result_directory.mkdir()
    completed = []
    tasks = [(recipe, number, "validation", str(result_directory)) for recipe in recipes for number in range(12)]
    with ProcessPoolExecutor(max_workers=2, initializer=initialize_worker, initargs=(str(warm_path),)) as pool:
        for path in pool.map(evaluate_world, tasks):
            completed.append(path)
            progress = {"status": "RUNNING", "study_id": study.name, "runtime_directory": str(study.directory), "completed": len(completed), "total": len(tasks), "protocol_sha256": digest(study.directory / "development_protocol.json"), "last_artifact": path, "not_final_outcomes": True}
            atomic_json(ROOT / "reports/policy/DEVELOPMENT_PROGRESS.json", progress)
            print(json.dumps(progress), flush=True)
    summaries = {}
    for recipe in recipes:
        records = [json.loads((result_directory / f"{recipe['id']}__world{number}.json").read_text()) for number in range(12)]
        utilities = np.array([row["evaluation"]["utility"] for row in records])
        summaries[recipe["id"]] = {"mean_completed_utility": float(utilities.mean()), "per_world": utilities.tolist(), "per_family": {family: float(utilities[np.arange(12) % 4 == index].mean()) for index, family in enumerate(FAMILIES)}, "per_budget": {str(budget): float(utilities[(np.arange(12) // 4) % 3 == index].mean()) for index, budget in enumerate((4000, 10000, 20000))}}
    conventional = [recipe for recipe in recipes if recipe.get("parameters", {}).get("name") != "MSCP_v2"]
    proposed = [recipe for recipe in recipes if recipe.get("parameters", {}).get("name") == "MSCP_v2"]
    key = lambda recipe: (-summaries[recipe["id"]]["mean_completed_utility"], recipe["id"])
    selected_baseline = sorted(conventional, key=key)[0]
    selected_candidate = sorted(proposed, key=key)[0]
    # Reference arms are selected within method on development only, not final.
    references = []
    for name in ("static", "rule_PID", "epsilon_greedy", "LinUCB", "neural_linear_TS", "delay_TS_primal_dual", "support_gated_delay_TS", "MPC_pacing"):
        group = [recipe for recipe in recipes if (recipe["family"] == "static" and recipe["id"].startswith("static_")) if name == "static"] if name == "static" else [recipe for recipe in recipes if recipe.get("parameters", {}).get("name") == name]
        references.append(sorted(group, key=key)[0])
    report = {"status": "POLICY_DEVELOPMENT_EXECUTED_NOT_CONFIRMATION", "scientific_outcome": "NOT_ESTABLISHED", "protocol": protocol, "summaries": summaries, "selected_conventional": selected_baseline, "selected_MSCP": selected_candidate, "reference_arms": recipes[:2] + references, "world_artifact_manifest": [{"path": path, "sha256": digest(Path(path))} for path in completed], "runtime_directory": str(study.directory), "no_hypothesis_claim": True, "limitations": ["Only12 development worlds; no final significance claim", "One preregistered controller RNG seed; seed sensitivity separate", "Observed purchase-value surrogate can credit organic exposed purchases; evaluator utility uses unique incremental potential-outcome difference and ordinary spend", "Support/uncertainty are heuristic controller inputs, not an adaptive causal confidence certificate", "Pilot, component-fixed ablations, freeze and independent final worlds remain"]}
    artifact = study.finish("E09", report, "policy", capabilities={"S1_POLICY_DEVELOPED": True})
    atomic_json(ROOT / "reports/policy/DEVELOPMENT_SELECTION.json", report | {"artifact": str(artifact), "sha256": digest(artifact)})
    return artifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["warmstart", "development"], default="warmstart")
    args = parser.parse_args()
    study = Study(ROOT, "e09_policy_" + args.stage)
    artifact = warmstart(study) if args.stage == "warmstart" else development(study)
    print(json.dumps({"status": "EXECUTED_STAGE", "artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
