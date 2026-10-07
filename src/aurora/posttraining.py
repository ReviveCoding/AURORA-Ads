"""Auditable assistant-only SFT and documented DPO/IPO loss primitives."""
from __future__ import annotations

import torch
import torch.nn.functional as F


def completion_logp(logits: torch.Tensor, ids: torch.Tensor, prefix_length: int, *, average: bool = False) -> torch.Tensor:
    if ids.ndim != 2 or ids.shape[0] != 1 or not 0 < prefix_length < ids.shape[1]:
        raise ValueError("One nonempty assistant completion required")
    scores = F.log_softmax(logits[:, prefix_length - 1:-1].float(), dim=-1)
    selected = scores.gather(-1, ids[:, prefix_length:].unsqueeze(-1)).squeeze(-1)
    return selected.mean() if average else selected.sum()


def suffix_completion_logp(model, ids: torch.Tensor, prefix_length: int, *, average: bool = False) -> torch.Tensor:
    """Full attended context, projecting ONLY completion predecessor states.

    Qwen3/Transformers4.52.4 logits_to_keep slices AFTER the decoder. Prefix
    attention/gradients are intact; no context, tool contract or target is cut.
    Keep L+1 states for L targets, then discard the last (unused) prediction.
    """
    if ids.ndim != 2 or ids.shape[0] != 1 or not 0 < prefix_length < ids.shape[1]:
        raise ValueError("One full-context nonempty assistant completion required")
    targets = ids[:, prefix_length:]
    output = model(input_ids=ids, logits_to_keep=targets.shape[1] + 1)
    logits = output.logits
    if logits.ndim != 3 or logits.shape[:2] != (1, targets.shape[1] + 1):
        raise ValueError("Qualified suffix projection interface required; no fallback/truncation")
    scores = F.log_softmax(logits[:, :-1].float(), dim=-1)
    selected = scores.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
    return selected.mean() if average else selected.sum()


def preference_loss(chosen: torch.Tensor, rejected: torch.Tensor, reference_chosen: torch.Tensor, reference_rejected: torch.Tensor, *, objective: str, beta: float = .1) -> torch.Tensor:
    if beta <= 0 or objective not in {"dpo", "ipo"}:
        raise ValueError("Documented DPO/IPO objective and positive beta required")
    ratio = (chosen - rejected) - (reference_chosen - reference_rejected)
    return -F.logsigmoid(beta * ratio) if objective == "dpo" else (ratio - 1 / (2 * beta)) ** 2


def assistant_labels(ids: torch.Tensor, prefix_length: int) -> torch.Tensor:
    if not 0 < prefix_length < ids.shape[-1]:
        raise ValueError("Assistant target cannot be empty")
    labels = ids.clone()
    labels[:, :prefix_length] = -100
    return labels
