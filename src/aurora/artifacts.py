"""Durable, content-addressed evidence without overwriting prior run outputs."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError("Artifact path contains a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        temporary = stream.name
    os.replace(temporary, path)
    if os.name == "posix":
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def immutable_json(directory: Path, payload: Any) -> Path:
    data = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
    path = directory / (hashlib.sha256(data).hexdigest() + ".json")
    if path.exists():
        if json.loads(path.read_text()) != payload:
            raise ValueError("Content-address collision")
    else:
        atomic_json(path, payload)
    return path
