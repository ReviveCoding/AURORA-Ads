"""Host-owned hash-verified S1 model registry; inference cannot access evaluator truth."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from .artifacts import digest
from .policies import PolicyBundle
from .prediction import calibrate


def load_bundle(root: Path, warm_path: Path | None = None):
    import torch
    import xgboost as xgb
    report_path = warm_path or root / "reports/policy/WARMSTART_LATEST.json"
    report = json.loads(report_path.read_text())
    models = {}
    for target in ("gross", "spend"):
        identity = report["model_fits"][target]
        if digest(Path(identity["path"])) != identity["sha256"]:
            raise ValueError("S1 model hash mismatch")
        model = xgb.XGBRegressor()
        model.load_model(identity["path"])
        model.set_params(device="cpu", n_jobs=2)
        models[target] = model
    if digest(Path(report["support_path"])) != report["support_sha256"]:
        raise ValueError("Support artifact changed")
    support = joblib.load(report["support_path"])
    neural_identity = report["model_fits"]["neural_representation"]
    if digest(Path(neural_identity["embedding_path"])) != neural_identity["embedding_sha256"]:
        raise ValueError("Neural representation hash mismatch")
    torch.set_num_threads(2)
    neural = torch.jit.load(neural_identity["embedding_path"], map_location="cpu").eval()

    def transform(values):
        with torch.no_grad():
            return neural(torch.as_tensor(values, dtype=torch.float32)).numpy()

    detector_freeze = json.loads((root / "reports/incidents/DETECTOR_FREEZE.json").read_text())
    recipe = next(item for item in detector_freeze["candidates"] if item["id"] == detector_freeze["selected"])
    if recipe["family"] != "XGBoost_CUDA":
        raise ValueError("Registered detector family needs an explicit compatible loader")
    if digest(Path(recipe["path"])) != recipe["sha256"] or digest(Path(recipe["calibrator_path"])) != recipe["calibrator_sha256"]:
        raise ValueError("Detector artifact changed")
    classifier = xgb.XGBClassifier()
    classifier.load_model(recipe["path"])
    classifier.set_params(device="cpu", n_jobs=2)
    calibrator = joblib.load(recipe["calibrator_path"])

    def detector(values):
        raw = 1 - classifier.predict_proba(np.asarray(values, dtype=np.float32)[None])[:, 0]
        return float(calibrate(calibrator, raw)[0])

    training_identity = report["cohort_artifacts"]["train"]
    if digest(Path(training_identity["path"])) != training_identity["sha256"]:
        raise ValueError("Observed training cohorts changed")
    with np.load(training_identity["path"], allow_pickle=False) as data:
        training = {name: data[name].copy() for name in ("x", "action", "gross", "spend", "operating")}
    bundle = PolicyBundle(models["gross"], models["spend"], report["scaler_mean"], report["scaler_scale"], support["tree"], support["actions"], report["action_residual_scale"], report["observed_receipt_delay_cdf"], neural_transform=transform, detector=detector)
    return bundle, training, report
