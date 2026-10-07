#!/usr/bin/env python3
"""Two disposable replay updates from an actual completed DPO/IPO boundary."""
from __future__ import annotations

import argparse
import gc
import json
import math
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.posttraining import preference_loss, suffix_completion_logp
from aurora.resources import check_gpu_room, cuda_lease, storage_admission
from aurora.studies import Study
from agent_study import agent_allocation_used_seconds, data_files, load_model, sequence, thermal_check


def validate_replay_boundary(source, persisted, reference, corpus_sha, preference_sha):
    """Admit completed actual training; qualification/progress is not a parent."""
    objective = source["objective"]
    count = source["parameters"]["preference_pairs_cap"]
    if not source.get("passed") or source["stage"] != "train" or objective not in {"dpo", "ipo"} or source["corpus_sha256"] != corpus_sha:
        raise ValueError("Completed actual same-corpus preference training required")
    if type(count) is not int or count < 1 or source.get("completion_projection") != "full_attended_context_suffix_L_plus_1_v1" or source["parameters"]["accumulation"] != 16 or source["parameters"]["beta"] != .1:
        raise ValueError("Matched qualified projection/accumulation/beta required")
    if source["examples"] != count or persisted["next_position"] != count or sorted(persisted["order"]) != list(range(count)) or persisted["objective"] != objective or persisted["seed"] != source["seed"] or persisted["corpus_sha256"] != corpus_sha:
        raise ValueError("Actual complete optimizer/sampler boundary required")
    if reference["objective"] != objective or reference["normalization"] != ("completion mean" if objective == "ipo" else "completion sum") or reference["preference_sha256"] != preference_sha or len(reference["values"]) != count or reference["adapter_sha256"] != source["same_sft_parent"]["weights_sha256"] or reference["same_sft_checkpoint"] != source["same_sft_parent"]["checkpoint"]:
        raise ValueError("Frozen same-SFT objective/reference identity mismatch")
    if any(not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in pair) for pair in reference["values"]):
        raise ValueError("Finite matched reference scalars required")
    return int(persisted["order"][0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["Qwen3-1.7B", "Qwen3-4B"], default="Qwen3-1.7B")
    parser.add_argument("--objective", choices=["dpo", "ipo"], required=True)
    parser.add_argument("--seed", type=int, choices=[41, 73, 101], default=41)
    args = parser.parse_args()
    study = Study(ROOT, "actual_preference_cuda_restart_probe")
    started = time.perf_counter()
    report = {"status": "RUNNING", "model": args.model, "objective": args.objective, "seed": args.seed, "telemetry": [], "replays": [], "final_tasks_scored": 0, "disposable_probe_not_substantive_continuation": True}
    try:
        import torch
        resource_contract = json.loads((ROOT / "config/resources.json").read_text())
        report["storage_admission"] = storage_admission(study.runtime, ROOT, expected_growth_bytes=1024**3, contract=resource_contract)
        corpus = data_files()
        pointer = json.loads((ROOT / "reports/agent" / f"{args.model}_{args.objective}_seed{args.seed}_LATEST.json").read_text())
        artifact = Path(pointer["artifact"]).resolve()
        if not artifact.is_relative_to(ROOT / "reports/agent") or not pointer["passed"] or digest(artifact) != pointer["sha256"]:
            raise ValueError("Successful owned actual trained preference result required")
        source = json.loads(artifact.read_text())
        admission = json.loads((ROOT / "reports/agent" / (args.model + "_ADMISSION.json")).read_text())
        checkpoint = Path(source["checkpoint"]).resolve()
        if source["objective"] != args.objective or source["seed"] != args.seed or source["revision"] != admission["revision"] or not checkpoint.is_relative_to(study.runtime / "runs") or digest(checkpoint.parent / "result.json") != pointer["sha256"]:
            raise ValueError("Actual model/seed/trained-checkpoint identity mismatch")
        for name, sha in source["checkpoint_hashes"].items():
            if digest(checkpoint / name) != sha:
                raise ValueError("Actual trained checkpoint changed")
        optimizer_path = Path(source["optimizer_state"]["path"]).resolve()
        reference_path = Path(source["reference_logps"]["path"]).resolve()
        if optimizer_path.parent != checkpoint or reference_path.parent != checkpoint.parent or digest(optimizer_path) != source["optimizer_state"]["sha256"] or digest(reference_path) != source["reference_logps"]["sha256"]:
            raise ValueError("Owned optimizer/reference identity required")
        state = torch.load(optimizer_path, map_location="cpu", weights_only=True)
        reference = json.loads(reference_path.read_text())
        fixture_index = validate_replay_boundary(source, state, reference, corpus["sha256"], corpus["files"]["preferences"]["sha256"])
        records = json.loads(Path(corpus["files"]["preferences"]["path"]).read_text())[:source["parameters"]["preference_pairs_cap"]]
        fixture = records[fixture_index]
        report["source"] = {"result_sha256": pointer["sha256"], "checkpoint": str(checkpoint), "optimizer_state_sha256": source["optimizer_state"]["sha256"], "reference_sha256": source["reference_logps"]["sha256"], "fixture_train_index": fixture_index, "corpus_sha256": corpus["sha256"]}
        allocation = source["parameters"]["allocation_gib"]
        duty = source["parameters"]["duty_pause_seconds"]
        target = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())["device_reported_target_c"]
        prior = agent_allocation_used_seconds()
        cap = resource_contract["gpu_hours_caps"]["agent"] * 3600
        def health():
            if prior + time.perf_counter() - started >= cap:
                raise RuntimeError("Agent allocation exhausted; no expansion")
            thermal_check(report["telemetry"], target)
        def settle():
            health()
            time.sleep(duty)
        report["telemetry"].append(check_gpu_room(allocation))
        first_weights = first_loss = None
        with cuda_lease(study.runtime):
            for replay in range(2):
                # A fresh dictionary avoids aliasing AdamW's CPU step tensor.
                state = torch.load(optimizer_path, map_location="cpu", weights_only=True)
                health()
                model, tokenizer = load_model(admission, allocation, args.seed, str(checkpoint))
                parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
                if any(parameter.dtype != torch.float32 for parameter in parameters):
                    raise ValueError("Qualified FP32 adapters required")
                optimizer = torch.optim.AdamW(parameters, lr=source["parameters"]["preference_lr"])
                optimizer.load_state_dict(state["optimizer"])
                if {int(item["step"]) for item in optimizer.state.values()} != {source["optimizer_updates"]}:
                    raise ValueError("Actual optimizer steps not restored")
                torch.set_rng_state(state["cpu_rng"])
                torch.cuda.set_rng_state(state["cuda_rng"])
                model.train()
                values = []
                with torch.no_grad():
                    for key in ("chosen_ids", "rejected_ids"):
                        health()
                        ids, prefix = sequence(fixture, key)
                        values.append(float(suffix_completion_logp(model, ids, prefix, average=args.objective == "ipo")))
                        settle()
                chosen, rejected = [torch.tensor(value, device="cuda", requires_grad=True) for value in values]
                ref_chosen, ref_rejected = [torch.tensor(value, device="cuda") for value in reference["values"][fixture_index]]
                loss = preference_loss(chosen, rejected, ref_chosen, ref_rejected, objective=args.objective)
                derivatives = torch.autograd.grad(loss, (chosen, rejected))
                for index, (key, derivative) in enumerate(zip(("chosen_ids", "rejected_ids"), derivatives)):
                    health()
                    ids, prefix = sequence(fixture, key)
                    logp = suffix_completion_logp(model, ids, prefix, average=args.objective == "ipo")
                    torch.testing.assert_close(logp.detach(), torch.tensor(values[index], device="cuda"), rtol=1e-5, atol=1e-4)
                    (derivative.detach() * logp / 16).backward()
                    settle()
                if not torch.isfinite(loss) or any(parameter.grad is not None and not torch.isfinite(parameter.grad).all() for parameter in parameters):
                    raise FloatingPointError("Nonfinite actual preference replay loss/gradient")
                torch.nn.utils.clip_grad_norm_(parameters, 1.)
                optimizer.step()
                torch.cuda.synchronize()
                weights = {name: parameter.detach().cpu().clone() for name, parameter in model.named_parameters() if parameter.requires_grad}
                value = float(loss.detach())
                if {int(item["step"]) for item in optimizer.state.values()} != {source["optimizer_updates"] + 1}:
                    raise ValueError("Diagnostic optimizer did not advance exactly once")
                if replay == 0:
                    first_weights, first_loss = weights, value
                else:
                    torch.testing.assert_close(torch.tensor(value), torch.tensor(first_loss), rtol=1e-5, atol=1e-4)
                    if weights.keys() != first_weights.keys():
                        raise ValueError("Replay adapter parameter identity changed")
                    for name in weights:
                        torch.testing.assert_close(weights[name], first_weights[name], rtol=1e-5, atol=1e-7)
                report["replays"].append({"index": replay, "restored_step": source["optimizer_updates"], "diagnostic_step": source["optimizer_updates"] + 1, "loss": value, "adapter_tensors": len(weights)})
                health()
                del model, tokenizer, optimizer, parameters, weights, loss, logp, ids, derivatives, chosen, rejected
                gc.collect()
                torch.cuda.empty_cache()
                time.sleep(duty)
            for name, sha in source["checkpoint_hashes"].items():
                if digest(checkpoint / name) != sha:
                    raise ValueError("Original adapter/optimizer modified by diagnostic")
        report.update(status="ACTUAL_PREFERENCE_CUDA_RESTART_QUALIFIED", passed=True, original_checkpoint_unchanged=True, limitations=["Two single-pair disposable partial-batch steps; not a real next-batch resume or sustained qualification", "Existing TRAIN fixture, no final tasks or semantic model performance", "Sampled resource boundaries/subpasses, not continuous maxima"])
    except Exception as error:
        report.update(status="ACTUAL_PREFERENCE_CUDA_RESTART_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    if report["passed"]:
        atomic_json(ROOT / "reports/agent" / f"{args.model}_{args.objective}_seed{args.seed}_RESTART_QUALIFICATION.json", {"artifact": str(artifact), "sha256": digest(artifact), "passed": True, "source": report["source"]})
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
