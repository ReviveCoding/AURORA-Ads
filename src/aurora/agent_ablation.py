"""Development input ablations, never weakening deterministic host guards."""
from __future__ import annotations

import json
from typing import Any

from aurora.agent import SYSTEM, messages, phase_tools
from aurora.agent_render_compat import compatible_trace

INPUT_VARIANTS = ("frozen_full_context", "remove_public_memory", "remove_operating_guidance")
PROTOCOL_ONLY = ("You are one AURORA local-mock tool agent, never a live advertiser. "
                 "Return one <tool_call>{\"name\":...,\"arguments\":...}</tool_call> "
                 "or a final JSON object with status completed/unsupported, evidence_ids and result.")


def ablated_messages(task, trace: list[dict], variant: str) -> list[dict[str, Any]]:
    if variant not in INPUT_VARIANTS:
        raise ValueError("Predeclared input ablation required")
    trace = compatible_trace(trace)
    if variant == "frozen_full_context":
        return messages(task, trace)
    if variant == "remove_public_memory":
        # Explicit absent evidence, not a silently truncated contract/history.
        return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task.prompt + "\nPublic memory: " + json.dumps({"rounds_used": len(trace), "evidence_payload_removed_by_development_ablation": True}, separators=(",", ":"))}]
    result = messages(task, trace)
    result[0] = {"role": "system", "content": PROTOCOL_ONLY}
    return result


def ablation_prefix_encoder(variant: str):
    if variant not in INPUT_VARIANTS:
        raise ValueError("No adaptive/new input recipe may enter this ablation")
    def encode(tokenizer, task, trace):
        return tokenizer.apply_chat_template(ablated_messages(task, trace, variant), tools=phase_tools(task, trace), tokenize=True, add_generation_prompt=True, enable_thinking=False)
    return encode


def development_ablation_subset(items: list[dict]) -> list[dict]:
    """First three cases of EVERY validation workflow, never final outcomes.

    Three variants cover the frozen modulo3 execution branches; still only three
    dependence groups in current V2. This is a bounded diagnostic, not a new
    training/reselection set or a final-family power expansion.
    """
    by_workflow = {}
    for item in items:
        task = item["task"]
        if task["split"] != "validation":
            raise ValueError("Final/train task cannot enter development ablation")
        by_workflow.setdefault(task["family"], []).append(item)
    if not by_workflow:
        raise ValueError("Nonempty development roster required")
    selected = []
    for workflow, members in sorted(by_workflow.items()):
        ordered = sorted(members, key=lambda item: int(item["task"]["task_id"].rsplit("_", 1)[1]))
        if len(ordered) < 3 or len({item["task"]["task_id"] for item in members}) != len(members) or len({item["semantic_group"] for item in members}) != 1:
            raise ValueError("Complete distinct cases in one frozen workflow group required")
        chosen = ordered[:3]
        if {int(item["task"]["task_id"].rsplit("_", 1)[1]) % 3 for item in chosen} != {0, 1, 2}:
            raise ValueError("Subset must preserve all three fixed fixture branches")
        selected.extend(chosen)
    return selected
