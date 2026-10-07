"""Same-domain mature-outcome value comparators; no revenue-column invention."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler


def _admit(features: np.ndarray, value: np.ndarray, matured: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    features, value, matured = np.asarray(features, dtype=float), np.asarray(value, dtype=float), np.asarray(matured)
    if features.ndim != 2 or value.shape != (len(features),) or matured.shape != value.shape or matured.dtype != np.bool_ or len(value) == 0:
        raise ValueError("Explicit nonempty mature-cohort feature/value arrays required")
    if not matured.all() or not np.isfinite(features).all() or not np.isfinite(value).all() or np.any(value < 0):
        raise ValueError("Pending estimates cannot become observed value targets")
    return features, value


class DirectValue:
    """Squared-error ridge baseline, with prospectively fixed nonnegative output."""
    def __init__(self, alpha: float = 1.):
        self.scaler = StandardScaler()
        self.regression = Ridge(alpha=alpha)

    def fit(self, features: np.ndarray, value: np.ndarray, matured: np.ndarray) -> DirectValue:
        features, value = _admit(features, value, matured)
        self.regression.fit(self.scaler.fit_transform(features), value)
        return self

    def predict(self, features: np.ndarray) -> np.ndarray:
        return np.maximum(0., self.regression.predict(self.scaler.transform(features)))


class TwoPartValue:
    """Incidence × positive-value regression, fitted within one admitted domain.

    Positive log-value regression uses an independent, mature calibration set
    for Duan residual smearing. There is no silent in-sample smearing fallback.
    This alone does not establish joint calibration or incremental value.
    """
    def __init__(self, alpha: float = 1., seed: int = 41):
        self.scaler = StandardScaler()
        self.incidence = LogisticRegression(C=1., solver="lbfgs", max_iter=1000, random_state=seed)
        self.positive = Ridge(alpha=alpha)
        self.smearing: float | None = None

    def fit(self, features: np.ndarray, value: np.ndarray, matured: np.ndarray, *, origin_ids: list[str], calibration_origin_ids: list[str], calibration_features: np.ndarray, calibration_value: np.ndarray, calibration_matured: np.ndarray) -> TwoPartValue:
        features, value = _admit(features, value, matured)
        calibration_features, calibration_value = _admit(calibration_features, calibration_value, calibration_matured)
        if len(origin_ids) != len(value) or len(calibration_origin_ids) != len(calibration_value) or len(set(origin_ids)) != len(origin_ids) or len(set(calibration_origin_ids)) != len(calibration_origin_ids) or set(origin_ids) & set(calibration_origin_ids) or not all(isinstance(item, str) and item for item in origin_ids + calibration_origin_ids):
            raise ValueError("Unique disjoint admitted origin/cohort lineage required; these IDs do not imply people or cross-source joins")
        if features.shape[1] != calibration_features.shape[1] or not np.any(value == 0) or not np.any(value > 0) or not np.any(calibration_value > 0):
            raise ValueError("Two training incidence classes and independent positive calibration outcomes required")
        transformed = self.scaler.fit_transform(features)
        self.incidence.fit(transformed, value > 0)
        self.positive.fit(transformed[value > 0], np.log(value[value > 0]))
        mask = calibration_value > 0
        residual = np.log(calibration_value[mask]) - self.positive.predict(self.scaler.transform(calibration_features[mask]))
        self.smearing = float(np.mean(np.exp(residual)))
        if not np.isfinite(self.smearing) or self.smearing <= 0:
            raise FloatingPointError("Invalid positive-value smearing; do not clip into apparent success")
        return self

    def components(self, features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.smearing is None:
            raise ValueError("Independent value calibration not fitted")
        transformed = self.scaler.transform(features)
        probability = self.incidence.predict_proba(transformed)[:, 1]
        positive_value = np.exp(self.positive.predict(transformed)) * self.smearing
        if not np.isfinite(positive_value).all():
            raise FloatingPointError("Nonfinite value extrapolation; not calibrated evidence")
        return probability, positive_value

    def predict(self, features: np.ndarray) -> np.ndarray:
        probability, positive_value = self.components(features)
        return probability * positive_value
