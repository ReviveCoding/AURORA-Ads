"""Saved-result presentation gates; never fit, rescore, or promote evidence."""
from __future__ import annotations

import math
from copy import deepcopy
from numbers import Real

from .completion import TERMINAL_DISPOSITIONS
from .workflow import EXECUTION, SCIENCE

EVIDENCE_CLASSES = {
    "R1": "PUBLIC_TEMPORAL_BENCHMARK_REPLICATION",
    "R2": "RANDOMIZED_ASSIGNMENT_BENCHMARK_REPLICATION",
    "R3": "PUBLIC_TEMPORAL_DELAY_VALUE_REPLICATION",
    "R4": "LOGGED_BANDIT_OPE",
    "S1": "SYNTHETIC_COUNTERFACTUAL_POLICY_RESULT",
    "A1": "EXECUTABLE_LOCAL_AGENT_BENCHMARK",
    "LOCAL_SYSTEMS": "LOCAL_SYSTEMS_SERVING_RESULT",
    "FIXTURE": "SYNTHETIC_FIXTURE_NOT_RESEARCH",
}


def final_reporting_gate(state: dict, *, active_owned_compute: list[int]) -> None:
    if active_owned_compute:
        raise ValueError("Final reporting requires no active owned empirical process")
    unfinished = [node for node, row in state["nodes"].items()
                  if node != "E16" and row["execution_status"] not in TERMINAL_DISPOSITIONS]
    if unfinished:
        raise ValueError("Nonterminal tracks prevent E16: " + ",".join(unfinished))


def finite_or_missing(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError("Finite recorded number or explicit unavailable value required")
    return value


def saved_record(row: dict, *, artifact: str, sha256: str, location: str, evidence_class: str,
                 role: str, interval_target: str) -> dict:
    required = ("record_status", "evidence_domain", "estimand_id", "comparison_id", "candidate",
                "baseline", "population", "metric", "estimate", "difference", "unit", "horizon",
                "n_independent_units", "independent_unit", "uncertainty_method", "ci_lower", "ci_upper",
                "source_hashes", "config_hash", "model_calibrator_id", "scientific_outcome", "execution_status", "scope_limits")
    if any(name not in row for name in required):
        raise ValueError("Saved result lacks required meaning/provenance fields")
    if EVIDENCE_CLASSES.get(row["evidence_domain"]) != evidence_class:
        raise ValueError("Recorded evidence domain cannot be relabeled as another evidence class")
    if role not in {"PRIMARY_CONFIRMATION", "SECONDARY_FROZEN_BENCHMARK", "DEVELOPMENT_ONLY", "SECONDARY_EXPLORATORY", "FIXTURE"}:
        raise ValueError("Explicit primary/secondary/development/exploratory role required")
    if row["record_status"] != "MEASURED" or row["execution_status"] != "EXECUTED" or row["scientific_outcome"] not in SCIENCE:
        raise ValueError("Unexecuted/planned result cannot be exported as measured")
    estimate = finite_or_missing(row["estimate"])
    finite_or_missing(row["difference"])
    lower, upper = (finite_or_missing(row[name]) for name in ("ci_lower", "ci_upper"))
    if estimate is None or (lower is None) != (upper is None) or lower is not None and lower > upper:
        raise ValueError("Measured point and complete ordered-or-unavailable interval required")
    if lower is None and interval_target != "UNAVAILABLE" or lower is not None and interval_target not in {"estimate", "difference"}:
        raise ValueError("Explicit absolute/contrast interval meaning required")
    if interval_target == "difference" and row["difference"] is None:
        raise ValueError("A contrast interval cannot decorate a missing contrast")
    count = row["n_independent_units"]
    if count is None and lower is not None:
        raise ValueError("Inferential interval requires its recorded independent-unit count")
    if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 1):
        raise ValueError("Recorded positive independent-unit count required; do not substitute rows/seeds")
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise ValueError("Exact artifact SHA required")
    output = deepcopy(row)
    output.update(artifact=artifact, artifact_sha256=sha256, artifact_location=location,
                  evidence_class=evidence_class, role=role, interval_target=interval_target)
    return output


def unavailable_record(node: str, state_record: dict, *, evidence_class: str) -> dict:
    execution, science = state_record["execution_status"], state_record["scientific_outcome"]
    if execution not in EXECUTION or science not in SCIENCE or execution not in TERMINAL_DISPOSITIONS or execution == "EXECUTED":
        raise ValueError("Terminal unexecuted disposition required for unavailable record")
    if not state_record.get("reason") or not state_record["artifacts"]:
        raise ValueError("Unavailable evidence requires a reason and inspected artifact provenance")
    return {"node": node, "record_status": "UNAVAILABLE_NOT_MEASURED", "execution_status": execution,
        "scientific_outcome": science, "evidence_class": evidence_class, "estimate": None, "difference": None,
        "ci_lower": None, "ci_upper": None, "n_independent_units": None,
        "reason": state_record["reason"], "artifacts": deepcopy(state_record["artifacts"])}


def core_empirical_complete(registry_nodes: list[dict], state: dict) -> bool:
    core = [node for node in registry_nodes if node["scope"] == "core" and node["id"] != "E16"]
    return bool(core) and all(state["nodes"][node["id"]]["execution_status"] == "EXECUTED"
                              and state["nodes"][node["id"]]["scientific_outcome"] != "INVALID" for node in core)
