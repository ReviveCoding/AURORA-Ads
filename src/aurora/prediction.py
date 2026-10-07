"""Matched natural-prevalence categorical prediction and proper-score metrics."""
from __future__ import annotations

import numpy as np
from scipy.special import logit
from sklearn.feature_extraction import FeatureHasher
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score


def hashed_features(codes):
    return FeatureHasher(n_features=2**16, input_type="string", alternate_sign=True).transform(([f"f{j}={value}" for j, value in enumerate(row)] for row in codes))


def probability(value):
    value = np.asarray(value, dtype=np.float64)
    if not np.isfinite(value).all() or np.any((value < 0) | (value > 1)):
        raise ValueError("Invalid predicted probability")
    return np.clip(value, 1e-7, 1 - 1e-7)


def proper_scores(y, p):
    y = np.asarray(y, dtype=np.float64)
    p = probability(p)
    if y.shape != p.shape or not np.all((y == 0) | (y == 1)):
        raise ValueError("Binary outcomes required")
    loss = -(y * np.log(p) + (1 - y) * np.log1p(-p))
    reliability = []
    edges = np.linspace(0, 1, 11)
    for lower, upper in zip(edges[:-1], edges[1:]):
        keep = (p >= lower) & (p < upper)
        if keep.any():
            reliability.append({"lower": float(lower), "upper": float(upper), "n": int(keep.sum()), "predicted": float(p[keep].mean()), "observed": float(y[keep].mean())})
    ece = sum(row["n"] * abs(row["predicted"] - row["observed"]) for row in reliability) / len(y)
    return {"logloss": float(loss.mean()), "brier": float(np.mean((y - p)**2)), "pr_auc": float(average_precision_score(y, p)), "auroc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None, "fixed_bin_ece": ece, "reliability": reliability, "prevalence": float(y.mean()), "n": len(y)}, loss


def fit_calibrator(y, p):
    model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=300)
    return model.fit(logit(probability(p)).reshape(-1, 1), y)


def calibrate(model, p):
    return model.predict_proba(logit(probability(p)).reshape(-1, 1))[:, 1] if model is not None else probability(p)


def categorical_frame(codes):
    import pandas as pd
    return pd.DataFrame({f"cat{i}": pd.Categorical(codes[:, i], categories=np.arange(1024)) for i in range(codes.shape[1])})


def neural_model(fields: int, embedding: int, width: int, cross: bool):
    import torch
    from torch import nn

    class CategoricalNetwork(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.ModuleList([nn.Embedding(1024, embedding) for _ in range(fields)])
            dimension = fields * embedding
            self.cross_layers = nn.ModuleList([nn.Linear(dimension, dimension) for _ in range(2)]) if cross else nn.ModuleList()
            self.deep = nn.Sequential(nn.Linear(dimension, width), nn.ReLU(), nn.Dropout(.1), nn.Linear(width, width), nn.ReLU())
            self.output = nn.Linear(width + (dimension if cross else 0), 1)

        def forward(self, codes):
            original = torch.cat([layer(codes[:, i]) for i, layer in enumerate(self.embedding)], dim=1)
            crossed = original
            for layer in self.cross_layers:
                crossed = original * layer(crossed) + crossed
            deep = self.deep(original)
            return self.output(torch.cat([deep, crossed], dim=1) if cross else deep).flatten()

    return CategoricalNetwork()


def neural_probability(model, codes, device="cuda"):
    import torch
    model.eval()
    output = []
    with torch.no_grad():
        for start in range(0, len(codes), 8192):
            tensor = torch.as_tensor(codes[start:start + 8192], dtype=torch.long, device=device)
            output.append(torch.sigmoid(model(tensor)).float().cpu().numpy())
    return np.concatenate(output)
