"""Per-recipe attempts must not erase a completed development comparison."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping


def training_checkpoint_transition(previous: Mapping, *, passed: bool, artifact: Path) -> dict:
    """Return ledger arguments, not mutation; actual caller owns atomic update.

    E10 means the complete actual development screen. Later finalist-transfer
    evidence is additional, not a replacement of that screen. Final freeze still
    requires independently admitted successful actual transfer checkpoints.
    """
    if type(passed) is not bool:
        raise ValueError("Actual recipe execution boolean required")
    if previous["execution_status"] == "EXECUTED":
        paths = tuple(Path(item["path"]) for item in previous["artifacts"])
        if not paths:
            raise ValueError("Completed development node lacks artifact evidence")
        return {"status": "EXECUTED", "science": previous["scientific_outcome"], "artifacts": (*paths, artifact), "reason": "Preserve completed development screen; additional transfer attempt " + ("passed" if passed else "failed; no final transfer admission implied")}
    return {"status": "CHECKPOINTED" if passed else "FAILED", "science": "NOT_RUN", "artifacts": (artifact,), "reason": "Per-recipe checkpoint; complete actual development screening remains required"}
