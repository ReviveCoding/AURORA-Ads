"""Shared evidence/time interfaces; these are NOT invented native source columns."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol

EvidenceDomain = Literal["R1", "R2", "R3", "R4", "R5", "S1", "A1", "LOCAL_ENGINEERING"]
EvidenceKind = Literal["RECORDED", "RANDOMIZED_REPLICATION", "LOGGED_BANDIT_OPE", "DESCRIPTIVE_ATTRIBUTION", "SYNTHETIC_COUNTERFACTUAL", "LOCAL_MEASUREMENT", "AGENT_BENCHMARK"]


@dataclass(frozen=True)
class ForecastIdentity:
    domain: EvidenceDomain
    population: str
    feature_schema_sha256: str
    horizon: str
    asof: float
    model_sha256: str
    calibration_status: Literal["CALIBRATED_ON_SEPARATE_DEVELOPMENT", "UNCALIBRATED"]

    def __post_init__(self) -> None:
        if self.domain not in {"R1", "R2", "R3", "R4", "R5", "S1", "A1", "LOCAL_ENGINEERING"} or self.calibration_status not in {"CALIBRATED_ON_SEPARATE_DEVELOPMENT", "UNCALIBRATED"}:
            raise ValueError("Declared evidence domain and calibration disposition required")
        if not self.population or not self.horizon or not math.isfinite(self.asof):
            raise ValueError("Explicit population/horizon/asof required")
        for value in (self.feature_schema_sha256, self.model_sha256):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError("Qualified schema/model SHA256 required")


@dataclass(frozen=True)
class FiniteHorizonForecast:
    identity: ForecastIdentity
    probability: float
    conditional_positive_value: float | None = None
    unit: str = "probability"

    def __post_init__(self) -> None:
        if not math.isfinite(self.probability) or not 0 <= self.probability <= 1:
            raise ValueError("Finite probability required")
        if self.conditional_positive_value is not None and (not math.isfinite(self.conditional_positive_value) or self.conditional_positive_value < 0 or self.unit == "probability"):
            raise ValueError("Nonnegative value and explicit monetary/synthetic unit required")


def compose_expected_value(probability: FiniteHorizonForecast, value: FiniteHorizonForecast) -> tuple[float, str]:
    """Same-domain/population clocks are necessary, not proof of calibration."""
    a, b = probability.identity, value.identity
    if (a.domain, a.population, a.feature_schema_sha256, a.horizon, a.asof) != (b.domain, b.population, b.feature_schema_sha256, b.horizon, b.asof):
        raise ValueError("Cross-source/population/clock multiplication prohibited; use a separately labeled synthetic coupling study")
    if value.conditional_positive_value is None:
        raise ValueError("Conditional positive-value estimator required")
    return probability.probability * value.conditional_positive_value, "UNCALIBRATED_COMPOSITION_REQUIRES_JOINT_QUALIFICATION"


class ForecastProvider(Protocol):
    def forecast(self, campaign: str, version: int) -> FiniteHorizonForecast: ...


@dataclass(frozen=True)
class OriginClock:
    """Normalized interface with separate occurrence/receipt, not a source schema."""
    origin: float
    horizon: float
    occurrence: float | None
    receipt: float | None
    receipt_assumption: Literal["MEASURED", "OCCURRENCE_EQUALS_RECEIPT_ASSUMED", "UNKNOWN"]

    def __post_init__(self) -> None:
        if self.receipt_assumption not in {"MEASURED", "OCCURRENCE_EQUALS_RECEIPT_ASSUMED", "UNKNOWN"}:
            raise ValueError("Explicit measured/assumed/unknown reporting clock required")
        if not math.isfinite(self.origin) or not math.isfinite(self.horizon) or self.horizon <= 0:
            raise ValueError("Finite origin and positive horizon required")
        if self.occurrence is not None and (not math.isfinite(self.occurrence) or self.occurrence < self.origin):
            raise ValueError("Event precedes origin")
        if self.receipt is not None and (self.occurrence is None or not math.isfinite(self.receipt) or self.receipt < self.occurrence):
            raise ValueError("Receipt precedes occurrence")
        if self.receipt_assumption == "MEASURED" and self.occurrence is not None and self.receipt is None:
            raise ValueError("Measured receipt cannot be invented")
        if self.receipt_assumption == "OCCURRENCE_EQUALS_RECEIPT_ASSUMED" and self.receipt not in {None, self.occurrence}:
            raise ValueError("Declared reporting assumption and supplied receipt disagree")

    def event_available(self, asof: float) -> bool:
        if not math.isfinite(asof):
            raise ValueError("Finite as-of clock required")
        if self.occurrence is None or self.occurrence - self.origin > self.horizon:
            return False
        if self.receipt_assumption == "UNKNOWN":
            raise ValueError("Unknown reporting availability must not become an observed label")
        available = self.receipt if self.receipt is not None else self.occurrence
        return available <= asof
