#!/usr/bin/env python3
"""Single Qwen3 post-training, bounded duty qualification and real task inference."""
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
from aurora.agent_lifecycle import training_checkpoint_transition
from aurora.resources import check_gpu_room, cuda_lease, storage_admission
from aurora.training_monitor import SampledResourceMonitor, bounded_gpu_sample
from aurora.studies import Study


def data_files():
    pointer = json.loads((ROOT / "reports/agent/CORPUS_LATEST.json").read_text())
    if digest(Path(pointer["artifact"])) != pointer["sha256"]:
        raise ValueError("Corpus identity mismatch")
    corpus = json.loads(Path(pointer["artifact"]).read_text())
    freeze_pointer = json.loads((ROOT / "reports/agent/TAXONOMY_V2_FREEZE.json").read_text())
    if corpus.get("taxonomy_freeze", {}).get("sha256") != freeze_pointer["sha256"]:
        raise ValueError("Historical V1 corpus cannot enter substantive training after prospective V2 correction")
    freeze = json.loads(Path(freeze_pointer["artifact"]).read_text())
    if digest(Path(freeze_pointer["artifact"])) != freeze_pointer["sha256"]:
        raise ValueError("Frozen taxonomy changed")
    for relative, sha in freeze["code_sha256"].items():
        if digest(ROOT / relative) != sha:
            raise ValueError("Frozen executable oracle source changed")
    for item in pointer["files"].values():
        if digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Split-owned corpus file changed")
    return pointer


def load_model(admission, allocation, seed, adapter=None):
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    torch.manual_seed(seed)
    torch.cuda.set_per_process_memory_fraction(allocation * 1024**3 / torch.cuda.get_device_properties(0).total_memory)
    model = AutoModelForCausalLM.from_pretrained(admission["model_directory"], local_files_only=True, trust_remote_code=False, torch_dtype=torch.bfloat16, device_map={"": 0}, quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16), attn_implementation="sdpa")
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False})
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, target_modules="all-linear", lora_dropout=0., task_type="CAUSAL_LM"))
    if adapter:
        model.load_adapter(adapter, adapter_name="default", is_trainable=True, autocast_adapter_dtype=False)
    tokenizer = AutoTokenizer.from_pretrained(admission["model_directory"], local_files_only=True, trust_remote_code=False)
    return model, tokenizer


def sequence(record, completion_key):
    import torch
    prefix, completion = record["prefix_ids"], record[completion_key]
    if not prefix or not completion or len(prefix) + len(completion) > 2048:
        raise ValueError("No context truncation is permitted")
    return torch.tensor([prefix + completion], device="cuda"), len(prefix)


def thermal_check(samples, target):
    current = bounded_gpu_sample()
    samples.append(current)
    if current["temperature_c"] >= target:
        raise RuntimeError("Reached device-reported operating target; stop this workload and preserve diagnostic")
    if current["total_mib"] - current["used_mib"] < 2 * 1024:
        raise RuntimeError("Current device memory no longer maintains declared2GiB reserve; stop without changing other applications")
    return current


def agent_allocation_used_seconds():
    from aurora.agent_budget import completed_agent_wall_seconds
    return completed_agent_wall_seconds(ROOT / "reports/execution")["completed_full_wall_seconds"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["qualify", "train"], required=True)
    parser.add_argument("--model", choices=["Qwen3-1.7B", "Qwen3-4B"], default="Qwen3-1.7B")
    parser.add_argument("--objective", choices=["sft", "dpo", "ipo"], default="sft")
    parser.add_argument("--seed", type=int, choices=[41, 73, 101], default=41)
    parser.add_argument("--sft-adapter")
    parser.add_argument("--examples-cap", type=int, default=256)
    parser.add_argument("--pairs-cap", type=int, default=32)
    parser.add_argument("--resume-report")
    parser.add_argument("--duty-pause-seconds", type=float, default=5.)
    args = parser.parse_args()
    if not 5 <= args.duty_pause_seconds <= 30:
        raise ValueError("Qualified local duty pause must stay in bounded5..30s profile")
    study = Study(ROOT, "e10_agent_" + args.stage + "_" + args.objective)
    resource_contract = json.loads((ROOT / "config/resources.json").read_text())
    expected_growth = 4 * 1024**3  # bounded rank8 adapter+Adam checkpoints
    storage = storage_admission(study.runtime, ROOT, expected_growth_bytes=expected_growth, contract=resource_contract)
    corpus = data_files()
    profile_pointer = json.loads((ROOT / "reports/agent/RECIPE_PROFILE_FREEZE.json").read_text())
    profile_path = ROOT / "config/agent_recipe_profile.json"
    if digest(profile_path) != profile_pointer["config_sha256"] or digest(Path(profile_pointer["artifact"])) != profile_pointer["sha256"]:
        raise ValueError("Frozen prospective recipe profile changed")
    profile = json.loads(profile_path.read_text())
    if args.examples_cap != profile["sft_examples_cap"] or args.objective != "sft" and args.pairs_cap != profile["preference_pairs_cap"] or args.duty_pause_seconds != profile["duty_pause_seconds"]:
        raise ValueError("Unfrozen learning/health profile; do not tune from validation/final outcomes")
    admission = json.loads((ROOT / "reports/agent" / (args.model + "_ADMISSION.json")).read_text())
    allocation = 10 if args.model == "Qwen3-4B" else 8
    report = {"stage": args.stage, "objective": args.objective, "model": admission["repo_id"], "revision": admission["revision"], "tokenizer_revision": admission["tokenizer_revision"], "seed": args.seed, "corpus_sha256": corpus["sha256"], "parameters": {"rank": 8, "maximum_sequence_length": 2048, "microbatch": 1, "accumulation": 16, "beta": .1, "sft_lr": 1e-4, "preference_lr": 5e-5, "epochs": 1, "thinking": False, "duty_pause_seconds": args.duty_pause_seconds, "allocation_gib": allocation, "sft_examples_cap": args.examples_cap, "preference_pairs_cap": args.pairs_cap}, "telemetry": [check_gpu_room(allocation)], "status": "RUNNING", "optimizer_updates": 0, "examples": 0, "assistant_tokens": 0, "supervised_system_tool_tokens": 0, "contract_truncation": 0, "checkpoint": None}
    resume = None
    report["storage_admission"] = storage
    report["prospective_recipe_profile"] = profile_pointer
    qualification_name = args.model + ("" if args.objective == "sft" else "_" + args.objective.upper()) + "_DUTY_QUALIFICATION.json"
    if args.resume_report:
        resume_path = Path(args.resume_report).resolve()
        if not resume_path.is_relative_to(study.runtime / "runs") or resume_path.is_symlink() or args.stage != "train":
            raise ValueError("Resume only an owned actual training report")
        resume = json.loads(resume_path.read_text())
        if any(resume[key] != report[key] for key in ("stage", "objective", "revision", "tokenizer_revision", "seed", "corpus_sha256")) or any(resume["parameters"][key] != report["parameters"][key] for key in ("rank", "maximum_sequence_length", "microbatch", "accumulation", "beta", "sft_lr", "preference_lr", "epochs", "sft_examples_cap", "preference_pairs_cap")):
            raise ValueError("Resume changes frozen learning inputs")
        if not resume["checkpoint"] or "optimizer_state" not in resume:
            raise ValueError("No complete optimizer boundary to resume; retain failed attempt and start a fresh declared seed run")
        for filename, sha in resume["checkpoint_hashes"].items():
            if digest(Path(resume["checkpoint"]) / filename) != sha:
                raise ValueError("Resume adapter checkpoint changed")
        if digest(Path(resume["optimizer_state"]["path"])) != resume["optimizer_state"]["sha256"]:
            raise ValueError("Resume optimizer state changed")
        report["resume_parent"] = {"path": str(resume_path), "sha256": digest(resume_path), "discarded_uncommitted_gradients": "replay only after the last persisted optimizer boundary; no completed update is repeated"}
    target = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())["device_reported_target_c"]
    monitor = SampledResourceMonitor(bounded_gpu_sample, device_target_c=target)
    report["resource_monitoring"] = "latched_background_device_samples_nominal2s_query_timeout3s_plus_phase_boundaries_v1"
    used_seconds = agent_allocation_used_seconds()
    allocation_seconds = json.loads((ROOT / "config/resources.json").read_text())["gpu_hours_caps"]["agent"] * 3600
    report["allocation_accounting"] = {"prior_actual_wall_seconds_including_failures": used_seconds, "cap_seconds": allocation_seconds, "conservative_scope": "full recorded command wall, including startup and reference generation, not only busy CUDA seconds"}
    started = time.perf_counter()
    def workload_check():
        if used_seconds + time.perf_counter() - started >= allocation_seconds:
            raise RuntimeError("Agent allocation exhausted before next CUDA phase; preserve boundary")
        monitor.check()
        value = thermal_check(report["telemetry"], target)
        monitor.check()
        report["background_resource_monitor"] = monitor.snapshot()
        return value
    model = optimizer = None
    try:
        import numpy as np
        import torch
        from aurora.posttraining import suffix_completion_logp, preference_loss
        report["completion_projection"] = "full_attended_context_suffix_L_plus_1_v1"
        if args.model == "Qwen3-4B":
            token_pointer = json.loads((ROOT / "reports/agent/TOKENIZER_TRANSFER_QUALIFICATION.json").read_text())
            token_artifact = Path(token_pointer["artifact"])
            if not token_pointer["passed"] or digest(token_artifact) != token_pointer["sha256"]:
                raise ValueError("Exact finalist tokenizer/corpus compatibility qualification required")
            token_report = json.loads(token_artifact.read_text())
            revisions = token_report["resolved_revisions"][args.model]
            if token_report["corpus_sha256"] != corpus["sha256"] or any(revisions[key] != admission[key] for key in ("revision", "tokenizer_revision", "chat_template_revision")):
                raise ValueError("Finalist token/corpus/revision compatibility mismatch")
            for filename, sha in token_report["byte_hashes"][args.model].items():
                if digest(Path(admission["model_directory"]) / filename) != sha:
                    raise ValueError("Finalist tokenizer bytes changed after qualification")
            report["tokenizer_transfer_qualification_sha256"] = token_pointer["sha256"]
        if args.stage == "train":
            if args.model == "Qwen3-4B":
                finalists = json.loads((ROOT / "reports/agent/DEV_RECIPE_SELECTION.json").read_text())
                if args.objective not in finalists["qualified_finalist_recipes"] or not finalists["frozen_before_final_scoring"]:
                    raise ValueError("Only prospectively selected, actually qualified1.7B finalist recipes may transfer to4B")
            qualification_path = ROOT / "reports/agent" / qualification_name
            qualification = json.loads(qualification_path.read_text())
            if not qualification["passed"] or qualification["objective"] != args.objective or qualification["revision"] != admission["revision"] or qualification["corpus_sha256"] != corpus["sha256"] or qualification["parameters"]["duty_pause_seconds"] != args.duty_pause_seconds or qualification.get("completion_projection") != report["completion_projection"] or qualification.get("resource_monitoring") != report["resource_monitoring"]:
                raise ValueError("Matched actual objective/base/corpus/context/duty qualification required")
            study.ledger.update("E10", "RUNNING")
        if args.objective != "sft" and not args.sft_adapter:
            raise ValueError("DPO/IPO require explicit same-SFT checkpoint")
        if args.objective == "sft" and args.sft_adapter and not args.resume_report:
            raise ValueError("SFT must initialize from pinned pretrained weights, not a disposable qualifier")
        if args.sft_adapter and not args.resume_report:
            adapter = Path(args.sft_adapter).resolve()
            if not adapter.is_relative_to(study.runtime / "runs") or adapter.is_symlink():
                raise ValueError("SFT parent must be an owned actual training checkpoint")
            parent = json.loads((adapter.parent / "result.json").read_text())
            if not parent.get("passed") or parent["stage"] != "train" or parent["objective"] != "sft" or parent["seed"] != args.seed or parent["revision"] != admission["revision"] or parent["corpus_sha256"] != corpus["sha256"]:
                raise ValueError("Same seed/base/revision/corpus SFT parent is required")
            for filename, sha in parent["checkpoint_hashes"].items():
                if digest(adapter / filename) != sha:
                    raise ValueError("Frozen same-SFT checkpoint changed")
            report["same_sft_parent"] = {"checkpoint": str(adapter), "result_sha256": digest(adapter.parent / "result.json"), "weights_sha256": digest(adapter / "adapter_model.safetensors")}
        with cuda_lease(study.runtime), monitor:
            workload_check()
            model, tokenizer = load_model(admission, allocation, args.seed, resume["checkpoint"] if resume else args.sft_adapter)
            workload_check()
            trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
            if not trainable or any(parameter.dtype != torch.float32 for parameter in trainable):
                raise ValueError("Qualified FP32 adapters required")
            optimizer = torch.optim.AdamW(trainable, lr=1e-4 if args.objective == "sft" else 5e-5)
            torch.cuda.reset_peak_memory_stats()
            sft = json.loads(Path(corpus["files"]["sft"]["path"]).read_text())
            preferences = json.loads(Path(corpus["files"]["preferences"]["path"]).read_text())
            if not 1 <= args.examples_cap <= len(sft) or not 1 <= args.pairs_cap <= len(preferences):
                raise ValueError("Explicit compute caps exceed admitted corpus")
            # Deterministic prefix subset of the round-robin corpus, frozen before
            # validation. Same pairs and token budgets in DPO and IPO, all seeds.
            sft = sft[:args.examples_cap] if args.stage == "train" else sft
            preferences = preferences[:args.pairs_cap]
            if args.stage == "qualify" and args.objective != "sft":
                preferences = sorted(preferences, key=lambda record: len(record["prefix_ids"]) + max(len(record["chosen_ids"]), len(record["rejected_ids"])), reverse=True)[:16]
            references = []
            if args.objective != "sft" and resume:
                reference_path = Path(resume["reference_logps"]["path"])
                if digest(reference_path) != resume["reference_logps"]["sha256"]:
                    raise ValueError("Frozen SFT reference log probabilities changed")
                references = json.loads(reference_path.read_text())["values"]
                report["reference_logps"] = resume["reference_logps"]
                report["same_sft_parent"] = resume["same_sft_parent"]
            elif args.objective != "sft":
                model.eval()
                for record in preferences:
                    if used_seconds + time.perf_counter() - started >= allocation_seconds:
                        raise RuntimeError("Agent allocation exhausted during frozen-reference generation")
                    workload_check()
                    values = []
                    with torch.no_grad():
                        for key in ("chosen_ids", "rejected_ids"):
                            if used_seconds + time.perf_counter() - started >= allocation_seconds:
                                raise RuntimeError("Agent allocation exhausted during frozen-reference generation")
                            workload_check()
                            ids, prefix = sequence(record, key)
                            values.append(float(suffix_completion_logp(model, ids, prefix, average=args.objective == "ipo")))
                            workload_check()
                            time.sleep(args.duty_pause_seconds)
                    references.append(values)
                    workload_check()
                atomic_json(study.directory / "frozen_reference_logps.json", {"same_sft_checkpoint": args.sft_adapter, "adapter_sha256": digest(Path(args.sft_adapter) / "adapter_model.safetensors"), "preference_sha256": corpus["files"]["preferences"]["sha256"], "objective": args.objective, "normalization": "completion mean" if args.objective == "ipo" else "completion sum", "values": references})
                report["reference_logps"] = {"path": str(study.directory / "frozen_reference_logps.json"), "sha256": digest(study.directory / "frozen_reference_logps.json")}
            records = sft if args.objective == "sft" else preferences
            if args.stage == "qualify" and args.objective == "sft":
                # Include longest admitted prefixes, not only an easy short task.
                records = sorted(sft, key=lambda record: len(record["prefix_ids"]) + len(record["completion_ids"]), reverse=True)[:16]
            order = np.random.default_rng(args.seed).permutation(len(records))
            report["ordered_task_turn_ids"] = [{"task_id": records[int(index)]["task_id"], "turn": records[int(index)].get("turn")} for index in order]
            losses = []
            example_wall_seconds = []
            report["losses"] = losses
            report["example_wall_seconds"] = example_wall_seconds
            model.train()
            optimizer.zero_grad(set_to_none=True)
            resume_position = 0
            if resume:
                persisted = torch.load(resume["optimizer_state"]["path"], map_location="cpu", weights_only=True)
                if persisted["order"] != order.tolist() or persisted["objective"] != args.objective or persisted["seed"] != args.seed or persisted["corpus_sha256"] != corpus["sha256"]:
                    raise ValueError("Persisted optimizer/sampler identity mismatch")
                optimizer.load_state_dict(persisted["optimizer"])
                torch.set_rng_state(persisted["cpu_rng"])
                torch.cuda.set_rng_state(persisted["cuda_rng"])
                resume_position = persisted["next_position"]
                if resume_position % 16 and resume_position != len(order):
                    raise ValueError("Resume state is not a complete optimizer boundary")
                report["optimizer_updates"] = resume_position // 16 + int(bool(resume_position % 16))
                report["examples"] = resume_position
                report["assistant_tokens"] = sum(len(records[int(index)]["completion_ids"]) if args.objective == "sft" else len(records[int(index)]["chosen_ids"]) + len(records[int(index)]["rejected_ids"]) for index in order[:resume_position])
                report["checkpoint"] = resume["checkpoint"]
                report["optimizer_state"] = resume["optimizer_state"]
                available_losses = resume.get("losses", [])
                losses.extend(available_losses[:resume_position])
                report["prior_loss_history"] = {"committed_examples": resume_position, "available_loss_count": len(losses), "missing_historical_losses_not_recomputed_or_invented": max(0, resume_position - len(losses))}
            for position, index in enumerate(order):
                if position < resume_position:
                    continue
                if used_seconds + time.perf_counter() - started >= allocation_seconds:
                    raise RuntimeError("Agent allocation exhausted; preserve checkpoint, no silent expansion")
                example_start = time.perf_counter()
                workload_check()
                record = records[int(index)]
                effective_accumulation = min(16, len(records) - (position // 16) * 16)
                if args.objective == "sft":
                    ids, prefix = sequence(record, "completion_ids")
                    loss = -suffix_completion_logp(model, ids, prefix, average=True)
                    (loss / effective_accumulation).backward()
                    report["assistant_tokens"] += len(record["completion_ids"])
                else:
                    # Two independent recomputations avoid retaining two4B graphs.
                    # Exact scalar chain rule verified against joint FP64 fixture;
                    # dropout0 and unchanged weights within a pair are required.
                    model.train()  # dropout0; same mode in no-grad and recompute
                    with torch.no_grad():
                        values = []
                        for key in ("chosen_ids", "rejected_ids"):
                            workload_check()
                            ids, prefix = sequence(record, key)
                            values.append(float(suffix_completion_logp(model, ids, prefix, average=args.objective == "ipo")))
                            workload_check()
                            time.sleep(args.duty_pause_seconds)
                    a, b = [torch.tensor(value, device="cuda", requires_grad=True) for value in values]
                    reference_c, reference_r = [torch.tensor(value, device="cuda") for value in references[int(index)]]
                    loss = preference_loss(a, b, reference_c, reference_r, objective=args.objective)
                    derivatives = torch.autograd.grad(loss, (a, b))
                    model.train()
                    for key, derivative in zip(("chosen_ids", "rejected_ids"), derivatives):
                        workload_check()
                        ids, prefix = sequence(record, key)
                        logp = suffix_completion_logp(model, ids, prefix, average=args.objective == "ipo")
                        torch.testing.assert_close(logp.detach(), torch.tensor(values[0 if key == "chosen_ids" else 1], device="cuda"), rtol=1e-5, atol=1e-4)
                        (derivative.detach() * logp / effective_accumulation).backward()
                        report["assistant_tokens"] += len(record[key])
                        workload_check()
                        time.sleep(args.duty_pause_seconds)
                if not torch.isfinite(loss) or any(parameter.grad is not None and not torch.isfinite(parameter.grad).all() for parameter in trainable):
                    raise FloatingPointError("Nonfinite actual pretrained loss or gradient")
                losses.append(float(loss.detach()))
                report["examples"] += 1
                if (position + 1) % 16 == 0 or position + 1 == len(order):
                    torch.nn.utils.clip_grad_norm_(trainable, 1.)
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    report["optimizer_updates"] += 1
                    checkpoint = study.directory / ("adapter_step" + str(report["optimizer_updates"]))
                    model.save_pretrained(checkpoint)
                    report["checkpoint"] = str(checkpoint)
                    state_path = checkpoint / "optimizer_state.pt"
                    torch.save({"optimizer": optimizer.state_dict(), "next_position": position + 1, "order": order.tolist(), "cpu_rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state(), "objective": args.objective, "seed": args.seed, "corpus_sha256": corpus["sha256"]}, state_path)
                    report["optimizer_state"] = {"path": str(state_path), "sha256": digest(state_path)}
                workload_check()
                example_wall_seconds.append(time.perf_counter() - example_start)
                atomic_json(study.directory / "progress.json", report)
                time.sleep(args.duty_pause_seconds)
            report.update(status="DUTY_QUALIFIED" if args.stage == "qualify" else "POSTTRAINING_EXECUTED", passed=True, losses=losses, example_wall_seconds=example_wall_seconds, peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(), peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(), checkpoint_hashes={path.name: digest(path) for path in Path(report["checkpoint"]).glob("*") if path.is_file()}, reference_scope="same frozen SFT" if args.objective != "sft" else None)
    except Exception as error:
        report.update(status="FAILED_AGENT_" + args.stage.upper(), passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    finally:
        del model, optimizer
        gc.collect()
    report["background_resource_monitor"] = monitor.snapshot()
    report["wall_seconds"] = time.perf_counter() - started
    if report["checkpoint"]:
        report["checkpoint_hashes"] = {path.name: digest(path) for path in Path(report["checkpoint"]).glob("*") if path.is_file()}
    export = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(export, report)
    if args.stage == "qualify":
        atomic_json(ROOT / "reports/agent" / qualification_name, report | {"artifact": str(export), "sha256": digest(export)})
    else:
        atomic_json(ROOT / "reports/agent" / (args.model + "_" + args.objective + "_seed" + str(args.seed) + "_LATEST.json"), {"artifact": str(export), "sha256": digest(export), "checkpoint": report["checkpoint"], "passed": report["passed"]})
        transition = training_checkpoint_transition(study.ledger.read()["nodes"]["E10"], passed=report["passed"], artifact=export)
        study.ledger.update("E10", transition.pop("status"), **transition)
        study.export_state()
    print(json.dumps({"status": report["status"], "artifact": str(export), "examples": report["examples"], "optimizer_updates": report["optimizer_updates"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
