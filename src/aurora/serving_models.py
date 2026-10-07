"""A hash-verified observed-only head for matched CPU/GPU serving measurements."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .artifacts import digest
from .policies import LinearPosterior


class FrozenNeuralLinearMean(nn.Module):
    """Frozen mean, not Thompson exploration or an adaptive budget controller.

    Targets already subtract spend and operating cost exactly once. Scores are
    observed exposed net-value forecasts, NOT incremental simulator truth.
    Input preprocessing is outside ``forward`` for inference-only timing.
    """
    def __init__(self, embedding, coefficients: np.ndarray, mean: np.ndarray, scale: np.ndarray):
        super().__init__()
        if coefficients.shape != (17, 6) or np.asarray(mean).shape != (24,) or np.asarray(scale).shape != (24,) or np.any(np.asarray(scale) <= 0) or not all(np.isfinite(value).all() for value in (coefficients, mean, scale)):
            raise ValueError("Qualified public feature/head shapes required")
        self.embedding = embedding
        self.register_buffer("coefficients", torch.as_tensor(coefficients, dtype=torch.float32))
        self.register_buffer("mean", torch.as_tensor(mean, dtype=torch.float32))
        self.register_buffer("scale", torch.as_tensor(scale, dtype=torch.float32))

    def encode(self, values: np.ndarray) -> torch.Tensor:
        values = np.asarray(values, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != 24 or not len(values) or not np.isfinite(values).all():
            raise ValueError("Finite nonempty24-feature public batch required")
        raw = torch.as_tensor(values, device=self.mean.device)
        return (raw - self.mean) / self.scale

    def forward(self, standardized: torch.Tensor) -> torch.Tensor:
        latent = self.embedding(standardized)
        design = torch.cat([torch.ones_like(latent[:, :1]), latent], dim=1)
        return (design @ self.coefficients) * 100.


def load_frozen_mean(root: Path) -> tuple[FrozenNeuralLinearMean, dict, np.ndarray]:
    path = root / "reports/policy/WARMSTART_LATEST.json"
    raw_report = path.read_bytes()
    report = json.loads(raw_report)
    neural = report["model_fits"]["neural_representation"]
    training = report["cohort_artifacts"]["train"]
    if digest(Path(neural["embedding_path"])) != neural["embedding_sha256"] or digest(Path(training["path"])) != training["sha256"]:
        raise ValueError("Frozen observed-only serving artifacts changed")
    with np.load(training["path"], allow_pickle=False) as stored:
        values = {name: stored[name].copy() for name in ("x", "action", "gross", "spend", "operating", "available_day", "origin_interval", "cohort_id")}
    if len(np.unique(values["cohort_id"])) != len(values["x"]) or np.any(values["available_day"] < (values["origin_interval"] + 1) / 96 + 7):
        raise ValueError("Duplicate or nonmatured training origin")
    torch.set_num_threads(2)
    scripted = torch.jit.load(neural["embedding_path"], map_location="cpu").eval()
    # An eager equivalent permits a fully captured compile benchmark rather
    # than silently timing a TorchScript graph-break fallback as compiled.
    embedding = nn.Sequential(nn.Linear(24, 32), nn.ReLU(), nn.Linear(32, 16), nn.Tanh()).float().eval()
    embedding.load_state_dict(scripted.state_dict(), strict=True)
    mean, scale = np.asarray(report["scaler_mean"]), np.asarray(report["scaler_scale"])
    standardized = ((values["x"] - mean) / scale).astype(np.float32)
    with torch.inference_mode():
        fixture = torch.from_numpy(standardized[:512])
        torch.testing.assert_close(embedding(fixture), scripted(fixture), rtol=0, atol=0)
        latent = np.concatenate([embedding(torch.from_numpy(standardized[begin:begin + 4096])).numpy() for begin in range(0, len(standardized), 4096)])
    posterior = LinearPosterior(17)
    posterior.batch_fit(np.column_stack([np.ones(len(latent)), latent]), values["action"], (values["gross"] - values["spend"] - values["operating"]) / 100)
    coefficients = np.einsum("aij,aj->ai", posterior.inverse, posterior.b).T
    identity = {"embedding_sha256": neural["embedding_sha256"], "training_cohorts_sha256": training["sha256"], "warm_report_sha256": hashlib.sha256(raw_report).hexdigest(), "coefficient_fp32_sha256": hashlib.sha256(np.ascontiguousarray(coefficients.astype(np.float32)).tobytes()).hexdigest(), "definition": "Frozen observed-only neural-linear posterior mean; ridge10; net gross-spend-operating exactly once; not adaptive TS/MSCP", "dtype": "float32 on both CPU/GPU", "feature_count": 24, "candidate_count": 6, "evidence_domain": "S1_OBSERVED_MATURED_SYNTHETIC_SURROGATE", "horizon": "one origin interval, fully matured7day recorded exposed value plus declared reporting maturity", "loader_sha256": digest(Path(__file__))}
    identity["model_sha256"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return FrozenNeuralLinearMean(embedding, coefficients, mean, scale).eval(), identity, values["x"][:512].astype(np.float32)
