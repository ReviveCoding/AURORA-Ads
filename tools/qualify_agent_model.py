#!/usr/bin/env python3
"""Actual pinned pretrained NF4/BF16 QLoRA update/reload/context qualification."""
from __future__ import annotations

import gc
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.resources import check_gpu_room, cuda_lease, telemetry
from aurora.studies import Study
from aurora.tools import CATALOG


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["Qwen3-1.7B", "Qwen3-4B"], default="Qwen3-1.7B")
    parser.add_argument("--allocation-gib", type=int, choices=[8, 10, 12], default=8)
    args = parser.parse_args()
    study = Study(ROOT, "actual_pretrained_qlora_context_qualification")
    admission = json.loads((ROOT / "reports/agent" / (args.model + "_ADMISSION.json")).read_text())
    if not admission["weights_downloaded"]:
        raise ValueError("Pinned weights not admitted")
    report = {"status": "RUNNING", "passed": False, "model_id": admission["repo_id"], "model_revision": admission["revision"], "tokenizer_revision": admission["tokenizer_revision"], "thinking": False, "scope": f"One real pretrained{args.model} NF4/BF16 QLoRA update,2048 context,r8; own allocation cap{args.allocation_gib}GiB; not sustained-training/performance qualification", "telemetry": [check_gpu_room(args.allocation_gib)]}
    start = time.perf_counter()
    try:
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from peft.utils import get_peft_model_state_dict
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        gpu = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())
        with cuda_lease(study.runtime):
            torch.cuda.set_per_process_memory_fraction(args.allocation_gib * 1024**3 / torch.cuda.get_device_properties(0).total_memory)
            if args.allocation_gib > 8:
                if json.loads((ROOT / "config/resources.json").read_text())["gpu_planned_peak_gib"] < args.allocation_gib:
                    raise ValueError("Extension exceeds declared resource ceiling")
                # A separate stepped admission below the declared12GiB ceiling.
                # Sparse allocator touch is explicitly not sustained stress.
                for gib in range(8, args.allocation_gib + 1, 2):
                    buffer = torch.empty(gib * 1024**3, dtype=torch.uint8, device="cuda")
                    buffer[::1024**2] = 19
                    torch.cuda.synchronize()
                    current = telemetry()
                    report["telemetry"].append(current)
                    if current["temperature_c"] >= gpu["device_reported_target_c"]:
                        raise ValueError("Allocator extension reached reported operating target")
                    del buffer
                    torch.cuda.empty_cache()
                report["allocator_extension"] = f"8..{args.allocation_gib}GiB sparse-touch passed; no sustained bandwidth stress claim"
            torch.manual_seed(733)
            model = AutoModelForCausalLM.from_pretrained(admission["model_directory"], local_files_only=True, trust_remote_code=False, torch_dtype=torch.bfloat16, device_map={"": 0}, quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16), attn_implementation="sdpa")
            model.config.use_cache = False
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False})
            lora = LoraConfig(r=8, lora_alpha=16, target_modules="all-linear", lora_dropout=0., task_type="CAUSAL_LM")
            model = get_peft_model(model, lora)
            tokenizer = AutoTokenizer.from_pretrained(admission["model_directory"], local_files_only=True, trust_remote_code=False)
            tools = [{"type": "function", "function": {"name": name, "description": f"Source-tagged local mock {name}; deterministic authorization and no live advertising.", "parameters": schema.model_json_schema()}} for name, schema in CATALOG.items()]
            messages = [{"role": "system", "content": admission["system_instruction"]}, {"role": "user", "content": "Inspect the local qualification campaign named qualification. Do not mutate it."}]
            prefix = tokenizer.apply_chat_template(messages, tools=tools, tokenize=True, add_generation_prompt=True, enable_thinking=False)
            assistant = tokenizer.encode('<tool_call>\n{"name":"get_campaign_snapshot","arguments":{"campaign":"qualification"}}\n</tool_call>' + tokenizer.eos_token, add_special_tokens=False)
            sequence = prefix + assistant
            if len(sequence) + 256 > 2048:
                raise ValueError("Complete system/tool/assistant target plus generation reserve exceeds effective context")
            pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id
            input_ids = torch.tensor([sequence + [pad_id] * (2048 - len(sequence))], device="cuda")
            attention = torch.tensor([[1] * len(sequence) + [0] * (2048 - len(sequence))], device="cuda")
            labels = input_ids.clone()
            labels[:, :len(prefix)] = -100
            labels[:, len(sequence):] = -100
            assert int((labels != -100).sum()) == len(assistant)
            optimizer = torch.optim.AdamW([parameter for parameter in model.parameters() if parameter.requires_grad], lr=1e-4)
            torch.cuda.reset_peak_memory_stats()
            model.train()
            before = {key: value.detach().cpu().clone() for key, value in get_peft_model_state_dict(model).items()}
            output = model(input_ids=input_ids, attention_mask=attention, labels=labels)
            output.loss.backward()
            assert torch.isfinite(output.loss) and all(parameter.grad is None or torch.isfinite(parameter.grad).all() for parameter in model.parameters())
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            after = get_peft_model_state_dict(model)
            changed = sum(not torch.equal(before[name], value.detach().cpu()) for name, value in after.items())
            assert changed > 0
            checkpoint = study.directory / "adapter"
            model.save_pretrained(checkpoint)
            model.eval()
            model.gradient_checkpointing_disable()
            with torch.no_grad():
                original = model(input_ids=input_ids[:, :len(sequence)], attention_mask=attention[:, :len(sequence)]).logits[:, -1].float().cpu()
            # Allocate reload adapter in original FP32 precision before loading.
            # Otherwise BF16-base default allocation can round FP32 weights.
            model.add_adapter("reloaded", lora)
            for name, parameter in model.named_parameters():
                if ".reloaded." in name:
                    parameter.data = parameter.data.float()
            model.load_adapter(checkpoint, adapter_name="reloaded", autocast_adapter_dtype=False)
            model.set_adapter("reloaded")
            model.eval()
            reload_state = get_peft_model_state_dict(model, adapter_name="reloaded")
            for key, value in after.items():
                torch.testing.assert_close(value.float().cpu(), reload_state[key].float().cpu(), atol=0, rtol=0)
            with torch.no_grad():
                replay = model(input_ids=input_ids[:, :len(sequence)], attention_mask=attention[:, :len(sequence)]).logits[:, -1].float().cpu()
            torch.testing.assert_close(original, replay, atol=0, rtol=0)
            observed = telemetry()
            report["telemetry"].append(observed)
            if observed["temperature_c"] >= gpu["device_reported_target_c"]:
                raise ValueError("Operating target reached; heavier sustained model runs not qualified")
            report.update(status="PRETRAINED_QLORA_CONTEXT_QUALIFIED", passed=True, loss=float(output.loss.detach().cpu()), adapter_tensors_updated=changed, prefix_tokens=len(prefix), assistant_tokens=len(assistant), padded_sequence_length=2048, contract_truncation=0, supervised_system_or_tool_tokens=0, optimizer_updates=1, rank=8, adapter_dtype="float32", adapter_reload_exact=True, logits_reload_exact=True, peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(), peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(), checkpoint_hashes={path.name: digest(path) for path in checkpoint.glob("*") if path.is_file()})
            del model, optimizer, output, before, after, reload_state
            gc.collect(); torch.cuda.empty_cache()
    except Exception as error:
        report.update(status="FAILED_MODEL_CONTEXT_QUALIFICATION", diagnostic={"type": type(error).__name__, "message": str(error)[:1200], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - start
    export = ROOT / "reports/environment" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(export, report)
    pointer = "DEV_MODEL_QUALIFICATION.json" if args.model == "Qwen3-1.7B" else "FINAL_MODEL_QUALIFICATION.json"
    atomic_json(ROOT / "reports/agent" / pointer, report | {"artifact": str(export), "sha256": digest(export)})
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
