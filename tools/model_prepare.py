#!/usr/bin/env python3
"""Anonymous official model identity/license/revision/tokenizer-context admission."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study
from aurora.tools import CATALOG


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["Qwen/Qwen3-1.7B", "Qwen/Qwen3-4B"], default="Qwen/Qwen3-1.7B")
    parser.add_argument("--weights", action="store_true")
    args = parser.parse_args()
    study = Study(ROOT, "model_identity_context_admission")
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HOME"] = str(study.runtime / "cache/huggingface")
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"
    from huggingface_hub import HfApi, snapshot_download
    from transformers import AutoTokenizer
    api = HfApi(token=False)
    previous_path = ROOT / "reports/agent" / (args.model.split("/")[-1] + "_ADMISSION.json")
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
    info = api.model_info(args.model, revision=previous["revision"] if previous else None, files_metadata=True, token=False)
    revision = info.sha
    if not revision or len(revision) != 40 or info.gated or info.private:
        raise ValueError("Public ungated exact model identity required")
    license_id = info.card_data.get("license") if info.card_data else None
    if license_id != "apache-2.0":
        raise ValueError("Configured Qwen publisher Apache2.0 license not verified; no new terms automatically accepted")
    files = [{"name": entry.rfilename, "bytes": entry.size} for entry in info.siblings]
    expected = sum(entry["bytes"] or 0 for entry in files if entry["name"].endswith(".safetensors")) if args.weights else 1024**3
    if args.weights and expected <= 0:
        raise ValueError("Expected weights growth unresolved")
    # Download and cache can temporarily coexist; retain reserve on both volumes.
    free = {"backing": shutil.disk_usage(ROOT).free, "runtime": shutil.disk_usage(study.runtime).free}
    if min(free.values()) < 20 * 1024**3 + expected * 2 + 1024**3:
        raise ValueError("Model cache growth plus20GiB storage reserve unavailable")
    atomic_json(study.directory / "publisher_identity.json", {"repo_id": args.model, "resolved_revision": revision, "license": license_id, "files": files, "expected_growth_bytes": expected, "storage_before": free, "anonymous": True})
    folder = study.runtime / "models" / args.model.replace("/", "__") / revision
    folder.mkdir(parents=True, exist_ok=True)
    patterns = ["*.json", "*.jinja", "tokenizer*", "merges.txt", "vocab*", "README.md", "LICENSE*"]
    if args.weights:
        patterns.append("*.safetensors")
    snapshot_download(repo_id=args.model, revision=revision, local_dir=folder, allow_patterns=patterns, max_workers=2, token=False)
    tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True, trust_remote_code=False)
    model_config = json.loads((folder / "config.json").read_text())
    tools = [{"type": "function", "function": {"name": name, "description": f"Source-tagged local mock {name}; deterministic authorization and no live advertising.", "parameters": schema.model_json_schema()}} for name, schema in CATALOG.items()]
    system = "You are one bounded AURORA control-plane agent. Use only exposed tools, preserve source domains and units, never invent economic quantities or approval. Local mock changes require prepare then host-authorized commit. No live advertising, SQL, production-impact or unsupported causal claims. Return compact JSON tool calls or an evidence-referenced final response."
    partitions = {"all_nine": list(CATALOG), "analysis": ["get_campaign_snapshot", "query_metrics", "build_measurement_report"], "action": ["get_campaign_snapshot", "validate_action", "prepare_action", "commit_mock_action"], "policy": ["get_campaign_snapshot", "estimate_outcomes", "simulate_policy", "recommend_action"], "recovery": ["get_campaign_snapshot", "prepare_action", "commit_mock_action", "build_measurement_report"]}
    audit = {}
    for phase, names in partitions.items():
        token_ids = tokenizer.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": "Inspect the current campaign and execute only the authorized local task using its versioned evidence."}], tools=[entry for entry in tools if entry["function"]["name"] in names], tokenize=True, add_generation_prompt=True, enable_thinking=False)
        audit[phase] = {"complete_contract_tokens": len(token_ids), "minimum_generation_reserve": 256, "fits1024": len(token_ids) + 256 <= 1024, "fits2048": len(token_ids) + 256 <= 2048, "tool_names": names, "truncated_tokens": 0}
    if any(not value["fits2048"] for key, value in audit.items() if key != "all_nine"):
        raise ValueError("Complete phase-specific contract exceeds declared2048 context; no silent truncation")
    chosen = 1024 if all(value["fits1024"] for key, value in audit.items() if key != "all_nine") else 2048
    report = {"status": "PINNED_WEIGHTS_CONTEXT_ADMITTED_PENDING_DEVICE_UPDATE" if args.weights else "PINNED_TOKENIZER_CONTEXT_ADMITTED", "repo_id": args.model, "revision": revision, "tokenizer_revision": revision, "chat_template_revision": revision, "license": license_id, "model_directory": str(folder), "weights_downloaded": args.weights, "weights_expected_bytes": expected if args.weights else None, "file_hashes": {str(path.relative_to(folder)): digest(path) for path in sorted(folder.rglob("*")) if path.is_file() and ".cache" not in path.parts}, "tool_payload_audit": audit, "effective_model_context": model_config["max_position_embeddings"], "proposed_training_context": chosen, "training_context_device_qualified": False, "nonthinking": True, "fixed_phase_exposure": partitions, "system_instruction": system, "restrictions": "Complete contracts must also fit actual example +256 generation reserve; reject overflow, never silently truncate. Same phase exposure and context for every recipe.", "storage_after": {"backing": shutil.disk_usage(ROOT).free, "runtime": shutil.disk_usage(study.runtime).free}}
    export = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(study.directory / "admission.json", report)
    atomic_json(export, report)
    atomic_json(ROOT / "reports/agent" / (args.model.split("/")[-1] + "_ADMISSION.json"), report | {"artifact": str(export), "sha256": digest(export)})
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
