"""Lossless host-field alias adapter; frozen oracle/tool/split code unchanged."""
from __future__ import annotations

from copy import deepcopy

from aurora.agent import encode_prefix

FIELD_ALIASES = {"matured_cohorts": "matured_cohort_count", "matured_value": "matured_exposure_value"}


def compatible_trace(trace: list[dict]) -> list[dict]:
    """Normalize names only in a rendering copy, never host records/quantities.

    Raw Snapshot fields are canonical; frozen public-memory presentation uses
    shorter names. Contradictory dual names fail rather than silently choosing.
    No missing numeric field is filled with zero, an estimate or model output.
    """
    copied = deepcopy(trace)
    for record in copied:
        data = record.get("response", {}).get("data", {})
        if "public_outcome_state" not in data:
            continue
        public = data["public_outcome_state"]
        if not isinstance(public, dict):
            raise ValueError("Actual public snapshot must be a typed object")
        for alias, canonical in FIELD_ALIASES.items():
            if canonical in public:
                if alias in public and public[alias] != public[canonical]:
                    raise ValueError("Public snapshot aliases contradict authoritative field")
                public[alias] = public[canonical]
            elif alias not in public:
                raise ValueError("Required actual public snapshot field absent; no invented fallback")
    return copied


def encode_prefix_compatible(tokenizer, task, trace):
    return encode_prefix(tokenizer, task, compatible_trace(trace))
