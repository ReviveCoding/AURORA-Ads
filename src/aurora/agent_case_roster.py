"""Prospective whole-workflow case identities; no prompts/golds or model scores."""
from __future__ import annotations

from math import lcm
from typing import Mapping

from aurora.agent_evaluation import AgentCase


def balanced_case_roster(workflow_groups: Mapping[str, str], *, cases_per_group: int, index_start: int) -> tuple[AgentCase, ...]:
    """Give every group equal cases and each member workflow equal variants.

    Three consecutive state indices cover the frozen expanded fixture's modulo3
    branches. This does not assert every possible numeric state was sampled or
    create additional semantic units. Caller freezes actual resource/count choice
    before model scoring; this function makes no outcome-dependent selection.
    """
    if not workflow_groups or any(not isinstance(key, str) or not key or not isinstance(value, str) or not value for key, value in workflow_groups.items()):
        raise ValueError("Explicit frozen workflow/group mapping required")
    if type(cases_per_group) is not int or type(index_start) is not int or index_start < 0:
        raise ValueError("Integer prospective case count and nonnegative index required")
    groups = sorted(set(workflow_groups.values()))
    members = {group: sorted(workflow for workflow, assigned in workflow_groups.items() if assigned == group) for group in groups}
    count_multiple = lcm(*(3 * len(names) for names in members.values()))
    if cases_per_group < count_multiple or cases_per_group % count_multiple:
        raise ValueError("Count must preserve equal group/workflow weights and all three fixture branches")
    result = []
    for group, names in members.items():
        for workflow in names:
            for offset in range(cases_per_group // len(names)):
                number = index_start + offset
                result.append(AgentCase(f"final_{workflow}_{number}", workflow, group))
    return tuple(result)
