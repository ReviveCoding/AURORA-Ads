#!/usr/bin/env python3
"""Bounded worst-prefix decode duty qualification, training prefixes only."""
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
from aurora.artifacts import atomic_json, digest, immutable_json
from aurora.agent_qualification import pointer_path
from aurora.resources import check_gpu_room, cuda_lease
from aurora.studies import Study
from agent_study import agent_allocation_used_seconds, data_files, load_model, thermal_check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["Qwen3-1.7B", "Qwen3-4B"], default="Qwen3-1.7B")
    parser.add_argument("--recipe", choices=["prompt_only", "sft", "dpo", "ipo"], default="sft")
    parser.add_argument("--duty-pause-seconds", type=float, choices=[5., 10., 30.], default=5.)
    parser.add_argument("--seed", type=int, choices=[41, 73, 101], default=41)
    args = parser.parse_args()
    study = Study(ROOT, "agent_bounded_decode_duty_qualification")
    started = time.perf_counter()
    report = {"status": "RUNNING", "model": args.model, "recipe": args.recipe, "training_seed": args.seed, "duty_pause_seconds": args.duty_pause_seconds, "telemetry": [], "decodes": [], "final_tasks_loaded": 0, "semantic_task_scoring": False, "not_isolated_serving_SLO_evidence": True}
    try:
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList
        corpus = data_files()
        admission = json.loads((ROOT / "reports/agent" / (args.model + "_ADMISSION.json")).read_text())
        adapter = None
        if args.recipe != "prompt_only":
            pointer = json.loads((ROOT / "reports/agent" / (args.model + "_" + args.recipe + "_seed" + str(args.seed) + "_LATEST.json")).read_text())
            if not pointer["passed"] or digest(Path(pointer["artifact"])) != pointer["sha256"]:
                raise ValueError("Completed trained recipe identity required")
            parent = json.loads(Path(pointer["artifact"]).read_text())
            if parent["corpus_sha256"] != corpus["sha256"] or parent["revision"] != admission["revision"] or parent["objective"] != args.recipe or parent["seed"] != args.seed:
                raise ValueError("Recipe/base/corpus mismatch")
            adapter = pointer["checkpoint"]
            for name, sha in parent["checkpoint_hashes"].items():
                if digest(Path(adapter) / name) != sha:
                    raise ValueError("Trained checkpoint changed")
            report["trained_parent_sha256"] = pointer["sha256"]
        sft = json.loads(Path(corpus["files"]["sft"]["path"]).read_text())[:256]
        prefixes = sorted(enumerate(sft), key=lambda pair: (-len(pair[1]["prefix_ids"]), pair[0]))[:8]
        target = json.loads((ROOT / "reports/environment/GPU_QUALIFICATION.json").read_text())["device_reported_target_c"]
        prior = agent_allocation_used_seconds()
        cap = json.loads((ROOT / "config/resources.json").read_text())["gpu_hours_caps"]["agent"] * 3600
        allocation = 8 if args.model == "Qwen3-1.7B" else 10
        report["telemetry"].append(check_gpu_room(allocation))
        def health():
            if prior + time.perf_counter() - started >= cap:
                raise RuntimeError("Agent allocation exhausted during decode qualification")
            thermal_check(report["telemetry"], target)
        class ResourceStop(StoppingCriteria):
            def __init__(self):
                from aurora.inference_monitor import DecodeResourceMonitor
                self.monitor = DecodeResourceMonitor(health, cadence_seconds=2.)

            @property
            def failure(self):
                return self.monitor.failure

            def __call__(self, input_ids, scores, **kwargs):
                return self.monitor(input_ids, scores, **kwargs)
        with cuda_lease(study.runtime):
            health()
            model, tokenizer = load_model(admission, allocation, args.seed, adapter)
            model.eval()
            model.gradient_checkpointing_disable()
            model.config.use_cache = True
            torch.cuda.reset_peak_memory_stats()
            for index, record in prefixes:
                health()
                prefix = record["prefix_ids"]
                if len(prefix) >= 2048:
                    raise ValueError("Complete training prefix exceeds qualified context")
                maximum = min(512, 2048 - len(prefix))
                ids = torch.tensor([prefix], device="cuda")
                monitor = ResourceStop()
                torch.cuda.synchronize()
                begin = time.perf_counter()
                with torch.inference_mode():
                    output = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids), do_sample=False, min_new_tokens=maximum, max_new_tokens=maximum, stopping_criteria=StoppingCriteriaList([monitor]), eos_token_id=tokenizer.eos_token_id, pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id, use_cache=True)
                torch.cuda.synchronize()
                raw = {"training_prefix_index": index, "prefix_ids": prefix, "generated_ids": output[0, len(prefix):].cpu().tolist(), "prefix_tokens": len(prefix), "generation_tokens": output.shape[1] - len(prefix), "forced_decode_stress_not_task_answer": True, "wall_seconds_cuda_synchronized": time.perf_counter() - begin, "resource_stop_reason": monitor.failure}
                raw_path = immutable_json(study.directory / "raw_decodes", raw)
                report["decodes"].append({key: value for key, value in raw.items() if key not in {"prefix_ids", "generated_ids"}} | {"artifact": str(raw_path), "sha256": digest(raw_path)})
                atomic_json(study.directory / "progress.json", report)
                if monitor.failure:
                    raise RuntimeError(monitor.failure)
                if raw["generation_tokens"] != maximum:
                    raise ValueError("Forced worst-prefix decode did not exercise the admitted length")
                health()
                del ids, output
                time.sleep(args.duty_pause_seconds)
            report.update(status="BOUNDED_DECODE_DUTY_QUALIFIED", passed=True, revision=admission["revision"], corpus_sha256=corpus["sha256"], context_tokens=2048, peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(), peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(), monitoring="before/after decode plus2second stopping-criteria cadence; sampled, not continuous peaks")
            del model, tokenizer
            gc.collect()
            torch.cuda.empty_cache()
    except Exception as error:
        report.update(status="BOUNDED_DECODE_DUTY_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    if report["passed"]:
        pointer = {"artifact": str(artifact), "sha256": digest(artifact), "passed": True, "duty_pause_seconds": args.duty_pause_seconds, "training_seed": args.seed, "trained_parent_sha256": report.get("trained_parent_sha256")}
        atomic_json(pointer_path(ROOT, args.model, args.recipe, args.seed), pointer)
        # Retain the established seed41 alias for existing development readers;
        # it never substitutes for another seed's actual trained checkpoint.
        if args.seed == 41:
            atomic_json(ROOT / "reports/agent" / (args.model + "_" + args.recipe + "_INFERENCE_DUTY_QUALIFICATION.json"), pointer)
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
