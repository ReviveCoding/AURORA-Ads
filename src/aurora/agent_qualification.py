"""Seed/checkpoint-specific inference admission; no model inference or scoring."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping


def inference_pointer_name(model: str, recipe: str, training_seed: int) -> str:
    if model not in {"Qwen3-1.7B", "Qwen3-4B"} or recipe not in {"prompt_only", "sft", "dpo", "ipo"} or type(training_seed) is not int or training_seed not in {41, 73, 101}:
        raise ValueError("Declared exact model/recipe/finalist seed required")
    return f"{model}_{recipe}_seed{training_seed}_INFERENCE_DUTY_QUALIFICATION.json"


def verify_inference_identity(
    qualification: Mapping[str, Any],
    *,
    model: str,
    recipe: str,
    training_seed: int,
    revision: str,
    corpus_sha256: str,
    trained_parent_sha256: str | None,
    pointer_duty: float,
) -> None:
    """Caller verifies immutable file SHA separately; this verifies its meaning."""
    inference_pointer_name(model, recipe, training_seed)
    expected = {"model": model, "recipe": recipe, "training_seed": training_seed, "revision": revision, "corpus_sha256": corpus_sha256, "context_tokens": 2048, "final_tasks_loaded": 0, "semantic_task_scoring": False}
    if not qualification.get("passed") or any(qualification.get(key) != value for key, value in expected.items()):
        raise ValueError("Inference qualification model/recipe/seed/corpus/context mismatch")
    if qualification.get("trained_parent_sha256") != trained_parent_sha256:
        raise ValueError("Actual trained-checkpoint parent mismatch")
    if (recipe == "prompt_only") != (trained_parent_sha256 is None):
        raise ValueError("Pretrained baseline and trained recipe parent distinction required")
    if qualification.get("duty_pause_seconds") not in (5., 10., 30.) or qualification["duty_pause_seconds"] != pointer_duty:
        raise ValueError("Immutable qualified duty must not be weakened")
    if qualification.get("status") != "BOUNDED_DECODE_DUTY_QUALIFIED" or len(qualification.get("decodes", [])) != 8:
        raise ValueError("Complete bounded eight-prefix actual decode qualification required")
    for record in qualification["decodes"]:
        prefix = record.get("prefix_tokens")
        wall = record.get("wall_seconds_cuda_synchronized")
        if type(prefix) is not int or not 0 < prefix < 2048 or record.get("generation_tokens") != min(512, 2048 - prefix) or record.get("resource_stop_reason") is not None or record.get("forced_decode_stress_not_task_answer") is not True or not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall < 0:
            raise ValueError("Each actual decode must complete its admitted worst-prefix length")


def pointer_path(root: Path, model: str, recipe: str, training_seed: int) -> Path:
    return root / "reports/agent" / inference_pointer_name(model, recipe, training_seed)
