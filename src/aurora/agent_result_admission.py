"""Structural admission of saved executable results, independent of wording."""
from __future__ import annotations

from typing import Any, Mapping

from aurora.agent_evaluation import AgentCase, AgentOutcome
from aurora.agent_safety import commit_multiplicity_diagnostics


def admit_saved_result(record: Mapping[str, Any], case: AgentCase, expected_task: Mapping[str, Any], training_seed: int) -> tuple[AgentOutcome, dict]:
    """Caller verifies result-file/model/host/freeze SHA provenance separately.

    No task generation or model scoring is done here. Inconsistent evaluator
    counters/identities fail admission; unsuccessful task outcomes remain present.
    """
    if record["task"] != dict(expected_task) or expected_task["task_id"] != case.identity or expected_task["family"] != case.workflow or expected_task["split"] != "final" or record["semantic_group"] != case.semantic_group:
        raise ValueError("Saved task differs from frozen final roster/state identity")
    trace = record["trace"]
    if not isinstance(trace, list) or type(record["tool_rounds"]) is not int or record["tool_rounds"] != len(trace) or not 0 <= len(trace) <= 8:
        raise ValueError("Bounded saved executable trace required")
    if type(record["generated_tokens"]) is not int or not 0 <= record["generated_tokens"] <= 2048:
        raise ValueError("Declared complete-task token budget exceeded")
    blocked = sum(item["response"].get("status") == "HOST_BLOCKED" for item in trace)
    if blocked != record["host_blocked_errors"]:
        raise ValueError("Saved host-blocked counter differs from executed trace")
    multiplicity = commit_multiplicity_diagnostics(dict(record))
    expected = {tuple(item) for item in record["expected_commits"]}
    wrong = sum(tuple(item) not in expected for item in record["actual_commits"])
    if wrong != record["wrong_committed_actions"]:
        raise ValueError("Frozen wrong-action counter differs from unique ledger commits")
    if record["success"] and (record["failure"] is not None or not all(record[key] is True for key in ("answer_ok", "evidence_ok", "workflow_ok")) or not multiplicity["exact_expected_commit_multiset"] or record["host_integrity"]["integrity"] != "ok"):
        raise ValueError("Reported success contradicts frozen host/oracle conditions")
    outcome = AgentOutcome(case.identity, training_seed, record["success"], record["unsafe_proposals"], record["host_blocked_errors"], record["wrong_committed_actions"])
    return outcome, multiplicity
