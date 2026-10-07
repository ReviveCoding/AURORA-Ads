#!/usr/bin/env python3
"""Exact pinned tokenizer/chat-template compatibility; no model/task scoring."""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study
from agent_study import data_files


def main():
    study = Study(ROOT, "qwen_tokenizer_corpus_transfer_integrity")
    started = time.perf_counter()
    report = {"status": "RUNNING", "final_tasks_loaded": 0, "CUDA_models_loaded": 0, "not_training_or_inference_qualification": True}
    try:
        corpus = data_files()
        admitted = {name: json.loads((ROOT / "reports/agent" / (name + "_ADMISSION.json")).read_text()) for name in ("Qwen3-1.7B", "Qwen3-4B")}
        hashes, vocabulary_limits = {}, {}
        for name, admission in admitted.items():
            directory = Path(admission["model_directory"])
            hashes[name] = {}
            for filename in ("tokenizer.json", "tokenizer_config.json"):
                actual = digest(directory / filename)
                if actual != admission["file_hashes"][filename]:
                    raise ValueError("Pinned tokenizer bytes changed")
                hashes[name][filename] = actual
            configuration = json.loads((directory / "config.json").read_text())
            vocabulary_limits[name] = configuration["vocab_size"]
        if hashes["Qwen3-1.7B"] != hashes["Qwen3-4B"]:
            raise ValueError("Pretokenized corpus requires explicit retokenization/qualification; model sizes alone do not prove token compatibility")
        maximum_id, tokens_checked, maximum_sequence = -1, 0, 0
        for kind in ("sft", "preferences"):
            rows = json.loads(Path(corpus["files"][kind]["path"]).read_text())
            for row in rows:
                fields = ("prefix_ids", "completion_ids") if kind == "sft" else ("prefix_ids", "chosen_ids", "rejected_ids")
                for field in fields:
                    ids = row[field]
                    if not ids or any(not isinstance(value, int) or value < 0 for value in ids):
                        raise ValueError("Invalid pretokenized training IDs")
                    maximum_id = max(maximum_id, max(ids))
                    tokens_checked += len(ids)
                maximum_sequence = max(maximum_sequence, len(row["prefix_ids"]) + max(len(row[field]) for field in fields[1:]))
        if maximum_id >= min(vocabulary_limits.values()) or maximum_sequence > 2048:
            raise ValueError("Corpus exceeds a finalist vocabulary/context admission")
        report.update(status="EXACT_TOKENIZER_CORPUS_TRANSFER_PASSED", passed=True, corpus_sha256=corpus["sha256"], byte_hashes=hashes, resolved_revisions={name: {key: value[key] for key in ("revision", "tokenizer_revision", "chat_template_revision")} for name, value in admitted.items()}, vocabulary_limits=vocabulary_limits, maximum_token_id=maximum_id, training_token_positions_checked=tokens_checked, maximum_training_sequence_tokens=maximum_sequence, exact_tokenizer_and_template_bytes=True, limitations=["Tokenizer compatibility only; does not qualify4B sustained training, shorter inference duty or task performance", "Training token positions are not independent semantic families"])
    except Exception as error:
        report.update(status="TOKENIZER_CORPUS_TRANSFER_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    if report["passed"]:
        atomic_json(ROOT / "reports/agent/TOKENIZER_TRANSFER_QUALIFICATION.json", {"artifact": str(artifact), "sha256": digest(artifact), "passed": True, "corpus_sha256": corpus["sha256"]})
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
