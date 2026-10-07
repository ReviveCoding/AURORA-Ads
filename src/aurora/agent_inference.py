"""Pinned local Qwen inference callback for the single bounded application agent."""
from __future__ import annotations

import time
from pathlib import Path

from .agent_render_compat import encode_prefix_compatible as encode_prefix
from .artifacts import immutable_json
from .inference_monitor import DecodeResourceMonitor


class LocalGenerator:
    def __init__(self, model, tokenizer, *, context_tokens=2048, records: Path | None = None, before_generation=None, after_generation=None, prefix_encoder=None, input_variant="frozen_full_context"):
        self.model = model
        self.tokenizer = tokenizer
        self.context_tokens = context_tokens
        self.measurements = []
        self.records = records
        self.before_generation = before_generation
        self.after_generation = after_generation
        self.prefix_encoder = prefix_encoder
        self.input_variant = input_variant

    def __call__(self, task, trace, remaining):
        import torch
        from transformers import StoppingCriteriaList
        if self.before_generation is not None:
            self.before_generation()
        prefix = (self.prefix_encoder or encode_prefix)(self.tokenizer, task, trace)
        if remaining <= 0 or len(prefix) + 1 > self.context_tokens:
            raise ValueError("CONTEXT_OR_GENERATION_ADMISSION_FAILED; never truncate a tool contract")
        input_ids = torch.tensor([prefix], device=next(self.model.parameters()).device)
        maximum = min(remaining, self.context_tokens - len(prefix))
        self.model.eval()
        self.model.gradient_checkpointing_disable()
        self.model.config.use_cache = True
        torch.cuda.synchronize()
        start = time.perf_counter()
        monitor = DecodeResourceMonitor(self.before_generation) if self.before_generation is not None else None
        with torch.inference_mode():
            output = self.model.generate(input_ids=input_ids, attention_mask=torch.ones_like(input_ids), do_sample=False, max_new_tokens=maximum, pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id, eos_token_id=self.tokenizer.eos_token_id, use_cache=True, stopping_criteria=StoppingCriteriaList([] if monitor is None else [monitor]))
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        completion = output[0, len(prefix):]
        text = self.tokenizer.decode(completion, skip_special_tokens=True)
        record = {"task_id": task.task_id, "round": len(trace), "prefix_tokens": len(prefix), "completion_tokens": len(completion), "prefix_ids": prefix, "raw_completion": text, "generation_wall_seconds_cuda_synchronized": elapsed, "context_truncation": 0, "input_variant": self.input_variant, "sampled_resource_stop_reason": None if monitor is None else monitor.failure}
        if self.records is not None:
            artifact = immutable_json(self.records, record)
            record["generation_artifact"] = str(artifact)
        self.measurements.append(record)
        if monitor is not None and monitor.failure is not None:
            raise RuntimeError(monitor.failure)
        # Persist raw output before a post-generation health check can stop the
        # task. A thermal stop must not erase an unfavorable/invalid response.
        if self.after_generation is not None:
            self.after_generation()
        return text, len(completion)
