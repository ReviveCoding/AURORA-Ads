"""Independent read-only local ledger reconciliation for saved agent outcomes."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from aurora.agent_evidence import owned_file
from aurora.artifacts import digest


def reconcile_saved_actions(result: dict, independent: dict, expected_pairs: list[tuple[str, str]]) -> None:
    actual = sorted(tuple(pair) for pair in result["actual_commits"])
    ledger_actual = sorted(tuple(pair) for pair in independent["actual_application_commits"])
    expected = sorted(tuple(pair) for pair in result["expected_commits"])
    if actual != ledger_actual or expected != sorted(expected_pairs) or any(result["host_integrity"][key] != independent[key] for key in ("integrity", "audit_head", "audit_events")):
        raise ValueError("Saved counters/gold differ from independent actual ledger/frozen expected actions")


def read_agent_ledger(path: Path, tenant: str, allowed_root: Path) -> dict:
    path = owned_file(path, (allowed_root,))
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Read-only SQLite integrity failure")
        head = "0" * 64
        events = connection.execute("SELECT * FROM audit ORDER BY sequence").fetchall()
        for event in events:
            expected = hashlib.sha256((head + event["event"]).encode()).hexdigest()
            if event["previous_hash"] != head or event["event_hash"] != expected:
                raise ValueError("Read-only audit chain mismatch")
            head = expected
        campaigns = connection.execute("SELECT * FROM campaign WHERE tenant=? ORDER BY id", (tenant,)).fetchall()
        if not campaigns:
            raise ValueError("Saved task tenant absent from actual ledger")
        for campaign in campaigns:
            reservation, spend = connection.execute("SELECT COALESCE(SUM(CASE WHEN settled IS NULL THEN reserve ELSE 0 END),0), COALESCE(SUM(settled),0) FROM committed WHERE tenant=? AND campaign=?", (tenant, campaign["id"])).fetchone()
            if reservation != campaign["reserved"] or spend != campaign["spent"] or min(campaign["budget"], spend, reservation) < 0 or spend + reservation > campaign["budget"]:
                raise ValueError("Independent budget/settlement reconciliation failed")
        commits = connection.execute("SELECT c.campaign,p.payload FROM committed c JOIN prepared p ON p.id=c.prepared_id WHERE c.tenant=? AND c.caller='application' ORDER BY c.campaign,c.idempotency_key", (tenant,)).fetchall()
        pairs = sorted([row["campaign"], json.loads(row["payload"])["action"]] for row in commits)
        return {"audit_events": len(events), "audit_head": head, "integrity": "ok", "actual_application_commits": pairs, "tenant": tenant, "campaigns": [dict(row) for row in campaigns]}
    finally:
        connection.close()


def snapshot_agent_ledger(source: Path, target: Path, allowed_root: Path) -> dict:
    """SQLite online backup captures committed WAL state, unlike copying main DB."""
    source = owned_file(source, (allowed_root,))
    if not target.is_absolute() or target.exists() or any(item.is_symlink() for item in (target, *target.parents)) or not target.resolve().is_relative_to(allowed_root.resolve()):
        raise ValueError("New owned ledger evidence snapshot required")
    target.parent.mkdir(parents=True, exist_ok=True)
    original = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    snapshot = sqlite3.connect(target)
    try:
        original.backup(snapshot)
    finally:
        snapshot.close()
        original.close()
    return {"path": str(target), "sha256": digest(target), "method": "read-only SQLite online backup includes committed WAL state; no source mutation"}
