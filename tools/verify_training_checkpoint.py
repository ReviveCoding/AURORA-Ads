#!/usr/bin/env python3
"""CPU integrity of an actual training boundary, not CUDA functional reload."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--progress", type=Path, required=True)
    args = parser.parse_args()
    study = Study(ROOT, "actual_training_boundary_cpu_integrity")
    source_path = args.progress.resolve()
    if not source_path.is_relative_to(study.runtime / "runs") or args.progress.is_symlink():
        raise ValueError("Owned actual training progress required")
    payload = source_path.read_bytes()  # atomic progress may advance: hash THESE bytes
    source = json.loads(payload)
    if source["stage"] != "train" or not source["checkpoint"]:
        raise ValueError("Disposable qualification/no-boundary report is not trained-checkpoint evidence")
    checkpoint = Path(source["checkpoint"]).resolve()
    state_path = Path(source["optimizer_state"]["path"]).resolve()
    if checkpoint.parent != source_path.parent or checkpoint.is_symlink() or state_path.parent != checkpoint or state_path.is_symlink() or digest(state_path) != source["optimizer_state"]["sha256"]:
        raise ValueError("Checkpoint/optimizer identity mismatch")
    import torch
    from safetensors.torch import load_file
    state = torch.load(state_path, map_location="cpu", weights_only=True)
    weights = load_file(str(checkpoint / "adapter_model.safetensors"), device="cpu")
    ids = [identity for group in state["optimizer"]["param_groups"] for identity in group["params"]]
    if state["objective"] != source["objective"] or state["seed"] != source["seed"] or state["corpus_sha256"] != source["corpus_sha256"] or len(ids) != len(set(ids)) or len(weights) != len(ids) or set(ids) != set(state["optimizer"]["state"]):
        raise ValueError("Training/sampler/parameter identity mismatch")
    next_position = state["next_position"]
    if next_position > source["examples"] or next_position > len(state["order"]) or next_position % 16 and next_position != len(state["order"]) or sorted(state["order"]) != list(range(len(state["order"]))):
        raise ValueError("Not a coherent complete optimizer boundary")
    if any(value.dtype != torch.float32 or not torch.isfinite(value).all() for value in weights.values()):
        raise ValueError("Nonfinite or non-FP32 actual adapter")
    steps = []
    for parameter in state["optimizer"]["state"].values():
        if not all(torch.isfinite(parameter[key]).all() for key in ("step", "exp_avg", "exp_avg_sq")):
            raise ValueError("Nonfinite actual optimizer state")
        steps.append(int(parameter["step"]))
    expected_updates = (next_position + 15) // 16
    if set(steps) != {expected_updates} or state["cpu_rng"].dtype != torch.uint8 or state["cuda_rng"].dtype != torch.uint8:
        raise ValueError("Optimizer step/RNG boundary mismatch")
    report = {"status": "ACTUAL_TRAINING_BOUNDARY_CPU_INTEGRITY_PASSED", "source_progress_path": str(source_path), "captured_progress_sha256": hashlib.sha256(payload).hexdigest(), "checkpoint": str(checkpoint), "checkpoint_files_sha256": {path.name: digest(path) for path in checkpoint.iterdir() if path.is_file()}, "optimizer_updates": expected_updates, "committed_examples": next_position, "observed_progress_examples": source["examples"], "uncommitted_microbatches_to_replay_if_stopped": source["examples"] - next_position, "adapter_tensors": len(weights), "adapter_parameters": sum(value.numel() for value in weights.values()), "nonzero_lora_B_tensors": sum(torch.count_nonzero(value).item() > 0 for name, value in weights.items() if "lora_B" in name), "finite_fp32_weights_optimizer_rng_sampler": True, "model_performance_or_final_outcomes_loaded": 0, "limitations": ["CPU serialization/state coherence only; no concurrent CUDA model load", "Functional trained-adapter CPU/GPU inference parity and actual optimizer restart remain separate qualification", "Captured progress is a point-in-time observation, not a promise of continued execution"]}
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(export, report)
    print(json.dumps({"status": report["status"], "artifact": str(export), "checkpoint": str(checkpoint)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
