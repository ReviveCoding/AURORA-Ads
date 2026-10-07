"""Resumable capability DAG with distinct execution and scientific dispositions."""
from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any

from .artifacts import atomic_json, digest, immutable_json

EXECUTION = {"PENDING", "RUNNING", "CHECKPOINTED", "EXECUTED", "FAILED", "BLOCKED_SOURCE", "BLOCKED_HARDWARE", "BLOCKED_ENVIRONMENT", "INVALID", "NOT_APPLICABLE"}
SCIENCE = {"NOT_RUN", "SUPPORTED", "NOT_ESTABLISHED", "UNDERPOWERED", "INVALID", "BLOCKED_SOURCE", "BLOCKED_HARDWARE"}


class Ledger:
    """One writer; lock prevents concurrent state mutation, events survive export failure."""

    def __init__(self, registry: Path, state: Path):
        self.registry = registry
        self.state = state
        self.nodes = json.loads(registry.read_text())["nodes"]
        self.by_id = {node["id"]: node for node in self.nodes}

    def read(self) -> dict[str, Any]:
        if self.state.exists():
            value = json.loads(self.state.read_text())
            if value["registry_sha256"] != digest(self.registry):
                raise ValueError("Registry changed; migration required")
        else:
            value = {"registry_sha256": digest(self.registry), "generation": 0, "capabilities": {}, "nodes": {
                node["id"]: {"execution_status": "PENDING", "scientific_outcome": "NOT_RUN", "artifacts": []} for node in self.nodes}}
        # The immutable intent is the commit point; an interrupted export/cache
        # replacement can be reconstructed without inventing a successful run.
        events = []
        for path in (self.state.parent / "events").glob("*.json"):
            if path.is_symlink():
                raise ValueError("Event symlink rejected")
            event = json.loads(path.read_text())
            expected = hashlib.sha256(json.dumps(event, sort_keys=True, allow_nan=False).encode()).hexdigest()
            if path.stem != expected:
                raise ValueError("Immutable event hash mismatch")
            events.append((path, event))
        while True:
            candidates = [(path, event) for path, event in events if event["generation"] == value["generation"] + 1]
            if not candidates:
                break
            if len(candidates) != 1:
                raise ValueError("Ambiguous interrupted state; manual reconciliation required")
            path, event = candidates[0]
            if event.get("registry_sha256") != value["registry_sha256"]:
                raise ValueError("Interrupted event lacks matching registry identity")
            if event["previous"] != value["nodes"][event["node_id"]]:
                raise ValueError("Event previous-state mismatch")
            value["nodes"][event["node_id"]] = event["next"]
            value["capabilities"].update(event["capabilities"])
            value["generation"] = event["generation"]
            value["last_event"] = str(path)
        return value

    def ready(self) -> list[str]:
        value = self.read()
        result = []
        for node in self.nodes:
            if value["nodes"][node["id"]]["execution_status"] not in {"PENDING", "CHECKPOINTED"}:
                continue
            if node["trigger"] == "all_declared_tracks_terminal":
                if all(v["execution_status"] not in {"PENDING", "RUNNING", "CHECKPOINTED"} for key, v in value["nodes"].items() if key != node["id"]):
                    result.append(node["id"])
                continue
            if all(value["nodes"][dependency]["execution_status"] == "EXECUTED" for dependency in node["requires"]):
                result.append(node["id"])
        return result

    def update(self, node_id: str, status: str, *, science: str = "NOT_RUN", artifacts: tuple[Path, ...] = (), reason: str = "", capabilities: dict[str, bool] | None = None) -> dict[str, Any]:
        if node_id not in self.by_id or status not in EXECUTION or science not in SCIENCE:
            raise ValueError("Unknown node/status")
        if science == "SUPPORTED" and status != "EXECUTED":
            raise ValueError("Unexecuted hypothesis cannot be supported")
        self.state.parent.mkdir(parents=True, exist_ok=True)
        lock = self.state.with_suffix(".lock")
        with lock.open("x"):
            try:
                value = self.read()
                if status in {"RUNNING", "EXECUTED"} and not all(value["nodes"][dep]["execution_status"] == "EXECUTED" for dep in self.by_id[node_id]["requires"]):
                    raise ValueError("Dependencies not executed")
                refs = [{"path": str(path.resolve()), "sha256": digest(path)} for path in artifacts]
                if status == "EXECUTED" and not refs:
                    raise ValueError("Execution requires artifact evidence")
                if status.startswith("BLOCKED") and not reason:
                    raise ValueError("Blocker requires actionable reason")
                previous = value["nodes"][node_id]
                record = {"execution_status": status, "scientific_outcome": science, "artifacts": refs, "reason": reason}
                event = {"registry_sha256": value["registry_sha256"], "generation": value["generation"] + 1, "node_id": node_id, "previous": previous, "next": record, "capabilities": capabilities or {}, "at_unix": time.time()}
                event_path = immutable_json(self.state.parent / "events", event)
                value["generation"] += 1
                value["nodes"][node_id] = record
                value["capabilities"].update(capabilities or {})
                value["last_event"] = str(event_path)
                atomic_json(self.state, value)
                return value
            finally:
                lock.unlink()
