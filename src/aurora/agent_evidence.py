"""Owned hash-bound agent evidence admission, without model or task evaluation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aurora.artifacts import digest


def owned_file(path: Path, allowed_roots: tuple[Path, ...]) -> Path:
    if not path.is_absolute() or any(component.is_symlink() for component in (path, *path.parents)):
        raise ValueError("Absolute nonsymlink owned evidence path required")
    resolved = path.resolve()
    if not any(resolved.is_relative_to(root.resolve()) for root in allowed_roots) or not resolved.is_file():
        raise ValueError("Evidence is outside admitted source/runtime roots or missing")
    return resolved


def verified_pointer(pointer: Path, allowed_roots: tuple[Path, ...]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return independently read payload and reference; never trust inline metrics."""
    pointer = owned_file(pointer, allowed_roots)
    reference = json.loads(pointer.read_text())
    path = owned_file(Path(reference["artifact"]), allowed_roots)
    sha = reference["sha256"]
    if not isinstance(sha, str) or len(sha) != 64 or digest(path) != sha:
        raise ValueError("Referenced agent artifact identity mismatch")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("Agent evidence must be a typed JSON object")
    return payload, {"pointer": str(pointer), "pointer_sha256": digest(pointer), "artifact": str(path), "sha256": sha}


def verified_checkpoint(report: dict, runtime: Path) -> dict:
    """Verify every actual adapter file and serialized optimizer boundary."""
    checkpoint = Path(report["checkpoint"])
    if not checkpoint.is_absolute() or checkpoint.is_symlink() or not checkpoint.resolve().is_relative_to(runtime.resolve() / "runs"):
        raise ValueError("Actual checkpoint must be inside the owned runtime runs")
    hashes = report.get("checkpoint_hashes")
    if not isinstance(hashes, dict) or "adapter_model.safetensors" not in hashes or "adapter_config.json" not in hashes:
        raise ValueError("Complete trained adapter hashes required")
    for name, sha in hashes.items():
        if Path(name).name != name:
            raise ValueError("Checkpoint filename cannot escape adapter directory")
        path = owned_file(checkpoint / name, (runtime / "runs",))
        if digest(path) != sha:
            raise ValueError("Actual trained checkpoint changed")
    optimizer = report.get("optimizer_state")
    if not isinstance(optimizer, dict) or digest(owned_file(Path(optimizer["path"]), (runtime / "runs",))) != optimizer["sha256"]:
        raise ValueError("Serialized actual optimizer/RNG boundary missing or changed")
    return {"checkpoint": str(checkpoint), "checkpoint_hashes": hashes, "optimizer_state": optimizer}


def verified_model_files(admission: dict, runtime: Path) -> dict[str, str]:
    directory = Path(admission["model_directory"])
    if not directory.is_absolute() or directory.is_symlink() or not directory.resolve().is_relative_to(runtime.resolve()) or admission.get("weights_downloaded") is not True:
        raise ValueError("Actual downloaded owned model required")
    hashes = admission["file_hashes"]
    if not hashes or not any(name.endswith(".safetensors") for name in hashes):
        raise ValueError("Pinned tokenizer/chat/model-weight file hashes required")
    result = {}
    for name, sha in hashes.items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Model-relative evidence filename required")
        path = owned_file(directory / name, (directory,))
        if digest(path) != sha:
            raise ValueError("Pinned actual model/tokenizer/chat-template file changed")
        result[str(path)] = sha
    return result
