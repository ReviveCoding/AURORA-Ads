#!/usr/bin/env python3
"""Actual pinned-tokenizer identity on existing TRAIN traces; no final cases."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.agent import encode_prefix
from aurora.agent_render_compat import encode_prefix_compatible
from aurora.agent_tasks import Task
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study
from agent_study import data_files


def main():
    from transformers import AutoTokenizer
    study = Study(ROOT, "agent_render_train_tokenizer_identity")
    started = time.perf_counter()
    corpus = data_files()
    admission = json.loads((ROOT / "reports/agent/Qwen3-1.7B_ADMISSION.json").read_text())
    tokenizer = AutoTokenizer.from_pretrained(admission["model_directory"], local_files_only=True, trust_remote_code=False)
    cases = json.loads(Path(corpus["files"]["teacher_traces"]["path"]).read_text())
    existing = json.loads(Path(corpus["files"]["sft"]["path"]).read_text())
    stored = {(item["task_id"], item["turn"]): item["prefix_ids"] for item in existing}
    checked = recorded = maximum = 0
    for case in cases:
        task = Task(**case["task"])
        if task.split != "train":
            raise ValueError("TRAIN traces only; no held-out model outcomes or prompts")
        for turn in range(len(case["trace"]) + 1):
            trace = case["trace"][:turn]
            original = encode_prefix(tokenizer, task, trace)
            adapted = encode_prefix_compatible(tokenizer, task, trace)
            if original != adapted:
                raise ValueError("Existing TRAIN token IDs changed by rendering compatibility adapter")
            if (task.task_id, turn) in stored:
                if original != stored[(task.task_id, turn)]:
                    raise ValueError("Existing frozen SFT prefix differs from pinned tokenizer")
                recorded += 1
            maximum = max(maximum, len(original))
            checked += 1
    if recorded != len(existing):
        raise ValueError("Every frozen SFT prefix must be accounted for")
    report = {"status": "TRAIN_TOKENIZER_RENDER_IDENTITY_PASSED", "corpus_sha256": corpus["sha256"], "revision": admission["revision"], "tokenizer_revision": admission["tokenizer_revision"], "train_cases": len(cases), "prefixes_checked": checked, "frozen_sft_prefixes_checked": recorded, "max_prefix_tokens": maximum, "final_cases_materialized": 0, "model_outcomes_scored": 0, "code_sha256": {relative: digest(ROOT / relative) for relative in ("src/aurora/agent_render_compat.py", "src/aurora/agent.py", "tools/qualify_agent_render.py")}, "wall_seconds": time.perf_counter() - started, "scope": "Lossless rendering identity on existing TRAIN traces; typed public-snapshot alias fixture is separate, not semantic model efficacy"}
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(export, report)
    atomic_json(ROOT / "reports/agent/RENDER_COMPATIBILITY_QUALIFICATION.json", {"artifact": str(export), "sha256": digest(export)})
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
