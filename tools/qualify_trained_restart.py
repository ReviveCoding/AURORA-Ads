#!/usr/bin/env python3
"""Two serialized disposable AdamW replay probes from an actual SFT boundary."""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.posttraining import assistant_labels
from aurora.resources import check_gpu_room, cuda_lease
from aurora.studies import Study
from agent_study import agent_allocation_used_seconds, data_files, load_model, sequence, thermal_check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["Qwen3-1.7B", "Qwen3-4B"], default="Qwen3-1.7B")
    parser.add_argument("--seed", type=int, choices=[41, 73, 101], default=41)
    args = parser.parse_args()
    study = Study(ROOT, "actual_sft_cuda_restart_probe")
    started = time.perf_counter()
    report = {"status": "RUNNING", "model": args.model, "seed": args.seed, "final_tasks_scored": 0, "disposable_probe_not_substantive_continuation": True, "telemetry": [], "replays": []}
    try:
        import torch
        corpus = data_files()
        pointer = json.loads((ROOT / "reports/agent" / (args.model + "_sft_seed" + str(args.seed) + "_LATEST.json")).read_text())
        source_path = Path(pointer["artifact"]).resolve()
        if not source_path.is_relative_to(ROOT / "reports/agent") or digest(source_path) != pointer["sha256"] or not pointer["passed"]:
            raise ValueError("Successful owned actual SFT result required")
        source = json.loads(source_path.read_text())
        admission = json.loads((ROOT / "reports/agent" / (args.model + "_ADMISSION.json")).read_text())
        checkpoint = Path(source["checkpoint"]).resolve()
        if source["stage"] != "train" or source["objective"] != "sft" or source["seed"] != args.seed or source["revision"] != admission["revision"] or source["corpus_sha256"] != corpus["sha256"] or not checkpoint.is_relative_to(study.runtime / "runs") or digest(checkpoint.parent / "result.json") != pointer["sha256"]:
            raise ValueError("Actual same-source trained boundary mismatch")
        for name, sha in source["checkpoint_hashes"].items():
            if digest(checkpoint / name) != sha:
                raise ValueError("Trained checkpoint identity changed")
        state = torch.load(source["optimizer_state"]["path"], map_location="cpu", weights_only=True)
        if state["next_position"] != source["examples"] or source["examples"] != source["parameters"]["sft_examples_cap"] or state["corpus_sha256"] != corpus["sha256"]:
            raise ValueError("Complete actual optimizer/sampler boundary required")
        records = json.loads(Path(corpus["files"]["sft"]["path"]).read_text())
        fixture = records[int(state["order"][0])]
        report["source"] = {"result_sha256": pointer["sha256"], "checkpoint": str(checkpoint), "adapter_sha256": source["checkpoint_hashes"]["adapter_model.safetensors"], "optimizer_state_sha256": source["optimizer_state"]["sha256"], "corpus_sha256": corpus["sha256"], "fixture_train_index": int(state["order"][0])}
        allocation = source["parameters"]["allocation_gib"]
        target = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())["device_reported_target_c"]
        prior = agent_allocation_used_seconds()
        cap = json.loads((ROOT / "config/resources.json").read_text())["gpu_hours_caps"]["agent"] * 3600
        def health():
            if prior + time.perf_counter() - started >= cap:
                raise RuntimeError("Agent allocation exhausted; no silent expansion")
            thermal_check(report["telemetry"], target)
        report["telemetry"].append(check_gpu_room(allocation))
        first_weights = None
        first_loss = None
        with cuda_lease(study.runtime):
            for replay in range(2):
                health()
                # AdamW's noncapturable CPU step tensors may alias a supplied
                # state_dict. Reload immutable bytes for EACH independent replay;
                # never reuse an in-memory dictionary advanced by the first step.
                state = torch.load(source["optimizer_state"]["path"], map_location="cpu", weights_only=True)
                model, tokenizer = load_model(admission, allocation, args.seed, str(checkpoint))
                trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
                if any(parameter.dtype != torch.float32 for parameter in trainable):
                    raise ValueError("FP32 adapter required for restart")
                optimizer = torch.optim.AdamW(trainable, lr=source["parameters"]["sft_lr"])
                optimizer.load_state_dict(state["optimizer"])
                before_steps = {int(value["step"]) for value in optimizer.state.values()}
                if before_steps != {source["optimizer_updates"]}:
                    raise ValueError("Actual AdamW moments/steps were not restored")
                torch.set_rng_state(state["cpu_rng"])
                torch.cuda.set_rng_state(state["cuda_rng"])
                ids, prefix = sequence(fixture, "completion_ids")
                model.train()
                health()
                output = model(input_ids=ids, labels=assistant_labels(ids, prefix))
                loss = output.loss
                (loss / 16).backward()  # bounded diagnostic, not next training batch
                if not torch.isfinite(loss) or any(parameter.grad is not None and not torch.isfinite(parameter.grad).all() for parameter in trainable):
                    raise FloatingPointError("Restart probe loss/gradient is nonfinite")
                torch.nn.utils.clip_grad_norm_(trainable, 1.)
                optimizer.step()
                torch.cuda.synchronize()
                values = {name: parameter.detach().cpu().clone() for name, parameter in model.named_parameters() if parameter.requires_grad}
                actual_loss = float(loss.detach())
                steps = {int(value["step"]) for value in optimizer.state.values()}
                if steps != {source["optimizer_updates"] + 1}:
                    raise ValueError("AdamW diagnostic restart did not advance exactly once")
                if replay == 0:
                    first_weights, first_loss = values, actual_loss
                else:
                    torch.testing.assert_close(torch.tensor(actual_loss), torch.tensor(first_loss), rtol=1e-5, atol=1e-4)
                    if values.keys() != first_weights.keys():
                        raise ValueError("Replay parameter identities changed")
                    for name in values:
                        torch.testing.assert_close(values[name], first_weights[name], rtol=1e-5, atol=1e-7)
                report["replays"].append({"index": replay, "restored_step": source["optimizer_updates"], "diagnostic_step": source["optimizer_updates"] + 1, "train_fixture_loss": actual_loss, "trainable_tensors": len(values)})
                health()
                del output, loss, optimizer, trainable, ids, values, model, tokenizer
                gc.collect()
                torch.cuda.empty_cache()
                time.sleep(30.)
            for name, sha in source["checkpoint_hashes"].items():
                if digest(checkpoint / name) != sha:
                    raise ValueError("Original trained boundary was modified by diagnostic")
        report.update(status="ACTUAL_TRAINED_CUDA_RESTART_QUALIFIED", passed=True, original_adapter_optimizer_unchanged=True, replay_loss_tolerance={"rtol": 1e-5, "atol": 1e-4}, replay_adapter_tolerance={"rtol": 1e-5, "atol": 1e-7}, limitations=["Two bounded serialized diagnostic steps, not sustained-training qualification", "One existing train fixture; no semantic task or final outcome evaluation"])
    except Exception as error:
        report.update(status="ACTUAL_TRAINED_CUDA_RESTART_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    if report["passed"]:
        atomic_json(ROOT / "reports/agent" / (args.model + "_SFT_RESTART_QUALIFICATION.json"), {"artifact": str(artifact), "sha256": digest(artifact), "passed": True, "source": report["source"]})
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
