#!/usr/bin/env python3
"""Executable, split-owned agent corpus with explicit context admission."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.agent import encode_prefix, phase_tools, SYSTEM
from aurora.agent_tasks import FAMILIES, FAMILY_GROUPS, TaskHost, assistant_call, gold_trace, task_for
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study
from aurora.tools import CATALOG


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sft-cap", type=int, default=512)
    parser.add_argument("--pairs-cap", type=int, default=256)
    parser.add_argument("--model", choices=["Qwen3-1.7B", "Qwen3-4B"], default="Qwen3-1.7B")
    args = parser.parse_args()
    contract = json.loads((ROOT / "config/contract.json").read_text())["agent"]
    if not 1 <= args.sft_cap <= contract["sft_examples_cap"] or not 1 <= args.pairs_cap <= contract["preference_pairs_cap"]:
        raise ValueError("Declared corpus caps exceeded")
    study = Study(ROOT, "e10_executable_agent_corpus")
    freeze_pointer = json.loads((ROOT / "reports/agent/TAXONOMY_V2_FREEZE.json").read_text())
    freeze_path = Path(freeze_pointer["artifact"])
    if digest(freeze_path) != freeze_pointer["sha256"]:
        raise ValueError("Prospective taxonomy freeze identity mismatch")
    freeze = json.loads(freeze_path.read_text())
    for relative, sha in freeze["code_sha256"].items():
        if digest(ROOT / relative) != sha:
            raise ValueError("Frozen workflow/predicate source changed; explicit repair record required")
    study.ledger.update("E10_TOOLS", "RUNNING")
    from transformers import AutoTokenizer
    admission = json.loads((ROOT / "reports/agent" / (args.model + "_ADMISSION.json")).read_text())
    tokenizer = AutoTokenizer.from_pretrained(admission["model_directory"], local_files_only=True, trust_remote_code=False)
    complete_tools = [{"type": "function", "function": {"name": name, "description": "Source-tagged local mock; host authorization required for mutation; no live advertising.", "parameters": schema.model_json_schema()}} for name, schema in CATALOG.items()]
    contract_tokens = len(tokenizer.apply_chat_template([{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Inspect alpha; do not mutate."}], tools=complete_tools, tokenize=True, add_generation_prompt=True, enable_thinking=False))
    if contract_tokens + 256 > 2048:
        raise ValueError("Full system and nine-tool contract plus reserve fails effective context")
    groups = {split: sorted({FAMILY_GROUPS[family] for family, value in FAMILIES.items() if value[0] == split}) for split in ("train", "validation", "final")}
    if any(set(groups[a]) & set(groups[b]) for a, b in (("train", "validation"), ("train", "final"), ("validation", "final"))):
        raise ValueError("Semantic family split overlap")
    examples, pairs, validation, cases = [], [], [], []
    rejected = []
    max_prefix = 0
    # Round-robin across complete train families prevents a cap silently dropping
    # the latter workflows. Final prompts/golds are never materialized here.
    train_families = [name for name, value in FAMILIES.items() if value[0] == "train"]
    for number in range(64):
        for family in train_families:
            if len(examples) >= args.sft_cap and len(pairs) >= args.pairs_cap:
                break
            task = task_for(family, number)
            # Numeric variants create distinct executable states, NOT new families.
            if number >= 5 and task.budget_units >= 10000:
                task = replace(task, budget_units=task.budget_units + number * 137)
            case = gold_trace(task, study.runtime, study.name + "_teacher")
            cases.append(case)
            prior = []
            targets = [assistant_call(record["name"], record["arguments"]) for record in case["trace"]] + [json.dumps(case["final"], separators=(",", ":"))]
            for turn, target in enumerate(targets):
                prefix = encode_prefix(tokenizer, task, prior)
                completion = tokenizer.encode(target + tokenizer.eos_token, add_special_tokens=False)
                max_prefix = max(max_prefix, len(prefix))
                if len(prefix) + len(completion) > 2048 or len(prefix) + 256 > 2048:
                    rejected.append({"task_id": task.task_id, "turn": turn, "prefix_tokens": len(prefix), "completion_tokens": len(completion), "reason": "CONTEXT_ADMISSION_FAILED; no truncation"})
                elif len(examples) < args.sft_cap:
                    examples.append({"task_id": task.task_id, "semantic_group": FAMILY_GROUPS[family], "prefix_ids": prefix, "completion_ids": completion, "turn": turn, "supervision": "assistant and tool-argument tokens only"})
                if turn < len(case["trace"]):
                    prior.append(case["trace"][turn])
            if len(pairs) < args.pairs_cap:
                prefix = encode_prefix(tokenizer, task, [])
                chosen = targets[0]
                if case["trace"]:
                    first = case["trace"][0]
                    bad_args = first["arguments"] | {"tenant": "forged_other_tenant"}
                    rejected_text = assistant_call(first["name"], bad_args)
                    judge_host = TaskHost(task, study.runtime, study.name + "_pair_judge")
                    response = judge_host.call(first["name"], bad_args)
                    if response["status"] != "HOST_BLOCKED" or judge_host.committed():
                        raise ValueError("Executable preference rejection failed")
                    judgement = {"rule": "host-forbidden identity injection outranks efficiency and answer fluency", "rejected_status": response["status"], "rejected_commits": 0}
                else:
                    rejected_text = '{"status":"completed","evidence_ids":[],"result":{"production_incremental_lift":1.0}}'
                    judgement = {"rule": "unsupported invented economic quantity rejected by deterministic answer/state contract", "expected_status": case["final"]["status"], "invented_quantity": True}
                good_ids = tokenizer.encode(chosen + tokenizer.eos_token, add_special_tokens=False)
                bad_ids = tokenizer.encode(rejected_text + tokenizer.eos_token, add_special_tokens=False)
                if len(prefix) + max(len(good_ids), len(bad_ids)) <= 2048 and len(prefix) + 256 <= 2048:
                    pairs.append({"task_id": task.task_id, "semantic_group": FAMILY_GROUPS[family], "prefix_ids": prefix, "chosen_ids": good_ids, "rejected_ids": bad_ids, "judgement": judgement})
        if len(examples) >= args.sft_cap and len(pairs) >= args.pairs_cap:
            break
    for family, (split, _) in FAMILIES.items():
        if split == "validation":
            for number in range(16):
                task = task_for(family, number + 1000)
                validation.append({"task": task.__dict__, "semantic_group": FAMILY_GROUPS[family]})
    paths = {}
    for name, data in (("sft", examples), ("preferences", pairs), ("validation_tasks", validation), ("teacher_traces", cases), ("context_rejections", rejected)):
        path = study.directory / (name + ".json")
        atomic_json(path, data)
        paths[name] = {"path": str(path), "sha256": digest(path), "count": len(data)}
    report = {"status": "EXECUTABLE_SPLIT_OWNED_CORPUS", "taxonomy_freeze": {"artifact": str(freeze_path), "sha256": freeze_pointer["sha256"]}, "historical_audit": freeze["historical_audit"], "model_id": admission["repo_id"], "revision": admission["revision"], "tokenizer_revision": admission["tokenizer_revision"], "files": paths, "semantic_groups": groups, "final_tasks_materialized": 0, "context": {"effective_tokens": 2048, "full_nine_tool_system_tokens": contract_tokens, "max_phase_prefix_tokens": max_prefix, "context_rejections": len(rejected), "truncated_contracts": 0, "supervised_system_tool_tokens": 0, "history_representation": "fixed public-memory semantic projection; no LLM summary; complete turn-specific phase schemas"}, "requested_caps": vars(args), "preference_ties_retained": 0, "preference_scope": "basic identity-injection/refusal preferences, not a broad learned policy optimality signal", "tool_schemas": {name: schema.model_json_schema() for name, schema in CATALOG.items()}, "phase_schemas": {name: phase_tools(task_for(name, 0)) for name in FAMILIES}, "limitations": [f"Actual final dependence units={len(groups['final'])}, nominal target80; prospective freeze power/single-generator sensitivity remains UNDERPOWERED, independent of prompt/seed count", "Small developer/core corpus is below starting caps; actual counts are reported", "Synthetic mock workflows and host documentation, not production behavior or structural-oracle optimal actions", "State/wording/clock variants are not independent semantic families"]}
    export = study.finish("E10_TOOLS", report, "agent", science="UNDERPOWERED", capabilities={"AGENT_TASKS_READY": True, "verified_reward_code": True})
    atomic_json(ROOT / "reports/agent/CORPUS_LATEST.json", {"artifact": str(export), "sha256": digest(export), "files": paths})
    print(json.dumps({"status": report["status"], "artifact": str(export), "sft": len(examples), "preferences": len(pairs), "context_rejections": len(rejected)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
