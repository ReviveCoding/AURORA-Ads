"""Local-only SQLite budget and action host. LLM output never supplies approval."""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterator

SCALE = 10_000


class Action(StrEnum):
    NO_CHANGE = "NO_CHANGE"
    BID_MULTIPLIER_DOWN = "BID_MULTIPLIER_DOWN"
    BID_MULTIPLIER_UP = "BID_MULTIPLIER_UP"
    PACE_DOWN = "PACE_DOWN"
    PACE_UP = "PACE_UP"
    PAUSE_SEGMENT = "PAUSE_SEGMENT"


def canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hash_payload(payload: object) -> str:
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


def reserve_units(value: float) -> int:
    if not math.isfinite(value) or value < 0:
        raise ValueError("Nonfinite/negative cost")
    return math.ceil(value * SCALE)


@dataclass(frozen=True)
class ActionRequest:
    tenant: str
    campaign: str
    caller: str
    version: int
    action: Action
    max_spend_units: int
    evidence_hash: str

    def __post_init__(self):
        if not all(isinstance(value, str) and value for value in (self.tenant, self.campaign, self.caller)):
            raise ValueError("Identity required")
        if type(self.version) is not int or self.version < 0 or type(self.max_spend_units) is not int or self.max_spend_units < 0:
            raise ValueError("Integer version and conservative cost required")
        if not isinstance(self.action, Action):
            raise ValueError("Unknown action")
        if len(self.evidence_hash) != 64 or any(c not in "0123456789abcdef" for c in self.evidence_hash):
            raise ValueError("Evidence SHA256 required")

    def payload(self) -> dict:
        return {"tenant": self.tenant, "campaign": self.campaign, "caller": self.caller, "version": self.version, "action": self.action.value, "max_spend_units": self.max_spend_units, "evidence_hash": self.evidence_hash}


class Conflict(ValueError):
    pass


class StateHost:
    """Independent connections serialize writes with BEGIN IMMEDIATE; WAL on ext4."""

    def __init__(self, path: Path, *, clock=time.time, fixture: bool = False):
        if not fixture and (not str(path.resolve()).startswith(str(Path.home() / ".local/share/aurora-ads/state") + "/") or str(path).startswith("/mnt/")):
            raise ValueError("Production state must be in the owned WSL-native runtime")
        for component in (path, *path.parents):
            if component.is_symlink():
                raise ValueError("State symlink rejected")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.clock = clock
        with closing(self.connect()) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS campaign(
                  tenant TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
                  budget INTEGER NOT NULL CHECK(budget>=0), spent INTEGER NOT NULL DEFAULT 0 CHECK(spent>=0),
                  reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved>=0), cooldown_until REAL NOT NULL DEFAULT 0,
                  PRIMARY KEY(tenant,id), CHECK(spent+reserved<=budget));
                CREATE TABLE IF NOT EXISTS prepared(
                  id TEXT PRIMARY KEY, tenant TEXT NOT NULL, campaign TEXT NOT NULL, caller TEXT NOT NULL,
                  version INTEGER NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL, expiry REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS approval(
                  digest TEXT PRIMARY KEY, prepared_id TEXT NOT NULL, tenant TEXT NOT NULL, caller TEXT NOT NULL,
                  expiry REAL NOT NULL, scope TEXT NOT NULL CHECK(scope='MOCK_ONLY'));
                CREATE TABLE IF NOT EXISTS committed(
                  caller TEXT NOT NULL, tenant TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                  request_hash TEXT NOT NULL, prepared_id TEXT NOT NULL UNIQUE,
                  campaign TEXT NOT NULL, reserve INTEGER NOT NULL, settled INTEGER,
                  version INTEGER NOT NULL, PRIMARY KEY(tenant,caller,idempotency_key));
                CREATE TABLE IF NOT EXISTS audit(
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
                  previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS public_observation(
                  tenant TEXT NOT NULL,campaign TEXT NOT NULL,version INTEGER NOT NULL,
                  payload TEXT NOT NULL,payload_hash TEXT NOT NULL,available_at REAL NOT NULL,
                  expires_at REAL NOT NULL,PRIMARY KEY(tenant,campaign));
            """)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def audit(self, connection: sqlite3.Connection, event: dict) -> None:
        last = connection.execute("SELECT event_hash FROM audit ORDER BY sequence DESC LIMIT 1").fetchone()
        previous = last[0] if last else "0" * 64
        event_json = canonical(event)
        digest = hashlib.sha256((previous + event_json).encode()).hexdigest()
        connection.execute("INSERT INTO audit(event,previous_hash,event_hash) VALUES (?,?,?)", (event_json, previous, digest))

    def create_campaign(self, tenant: str, campaign: str, budget_units: int) -> None:
        if type(budget_units) is not int or budget_units < 0 or not tenant or not campaign:
            raise ValueError("Invalid budget/identity")
        with self.transaction() as connection:
            connection.execute("INSERT INTO campaign(tenant,id,budget) VALUES (?,?,?)", (tenant, campaign, budget_units))
            self.audit(connection, {"event": "create_campaign", "tenant": tenant, "campaign": campaign, "budget_units": budget_units})

    def snapshot(self, tenant: str, campaign: str) -> dict:
        connection = self.connect()
        try:
            row = connection.execute("SELECT * FROM campaign WHERE tenant=? AND id=?", (tenant, campaign)).fetchone()
            if row is None:
                raise ValueError("Unknown campaign in tenant")
            return dict(row)
        finally:
            connection.close()

    def validate(self, request: ActionRequest, snapshot: dict) -> None:
        if snapshot["tenant"] != request.tenant or snapshot["id"] != request.campaign:
            raise ValueError("Tenant/campaign mismatch")
        if snapshot["version"] != request.version:
            raise Conflict("Stale state")
        if request.action != Action.NO_CHANGE and snapshot["cooldown_until"] > self.clock():
            raise Conflict("Action cooldown")
        if request.max_spend_units > snapshot["budget"] - snapshot["spent"] - snapshot["reserved"]:
            raise Conflict("Insufficient unreserved budget")

    def publish_observation(self, tenant: str, campaign: str, version: int, payload: dict, *, ttl_seconds: float = 900.) -> None:
        """Host-only observation ingestion; never offered as an LLM tool."""
        from .simulator import Snapshot
        from .incidents import features
        observation = Snapshot(**payload)
        features(observation)
        if not math.isfinite(ttl_seconds) or not 0 < ttl_seconds <= 900:
            raise ValueError("Observation freshness bound")
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM campaign WHERE tenant=? AND id=?", (tenant, campaign)).fetchone()
            if not row or row["version"] != version:
                raise Conflict("Observation state version mismatch")
            if observation.initial_budget_units != row["budget"] or observation.spent_units != row["spent"] or observation.available_budget_units != row["budget"] - row["spent"] - row["reserved"]:
                raise Conflict("Observed ledger quantities disagree with authoritative budget")
            encoded = canonical(payload)
            connection.execute("INSERT OR REPLACE INTO public_observation VALUES (?,?,?,?,?,?,?)", (tenant, campaign, version, encoded, hash_payload(payload), self.clock(), self.clock() + ttl_seconds))
            self.audit(connection, {"event": "publish_public_observation", "tenant": tenant, "campaign": campaign, "version": version, "payload_hash": hash_payload(payload)})

    def public_observation(self, tenant: str, campaign: str, version: int):
        from .simulator import Snapshot
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM public_observation WHERE tenant=? AND campaign=?", (tenant, campaign)).fetchone()
            if not row or row["version"] != version or not row["available_at"] <= self.clock() < row["expires_at"]:
                raise Conflict("Public model observation unavailable or stale")
            payload = json.loads(row["payload"])
            if hash_payload(payload) != row["payload_hash"]:
                raise ValueError("Public observation integrity failure")
            return Snapshot(**payload)

    def prepare(self, request: ActionRequest, ttl_seconds: float = 900.) -> str:
        if not math.isfinite(ttl_seconds) or not 0 < ttl_seconds <= 900:
            raise ValueError("Prepare expiry must fit one controller interval")
        with self.transaction() as connection:
            snapshot = connection.execute("SELECT * FROM campaign WHERE tenant=? AND id=?", (request.tenant, request.campaign)).fetchone()
            if not snapshot:
                raise ValueError("Unknown campaign in tenant")
            self.validate(request, dict(snapshot))
            identifier = secrets.token_hex(16)
            connection.execute("INSERT INTO prepared VALUES (?,?,?,?,?,?,?,?)", (identifier, request.tenant, request.campaign, request.caller, request.version, canonical(request.payload()), hash_payload(request.payload()), self.clock() + ttl_seconds))
            self.audit(connection, {"event": "prepare", "id": identifier, "payload_hash": hash_payload(request.payload())})
            return identifier

    def issue_mock_authorization(self, prepared_id: str, tenant: str, caller: str) -> str:
        """Host entry point; NEVER expose this method as an agent tool."""
        with self.transaction() as connection:
            prepared = connection.execute("SELECT * FROM prepared WHERE id=? AND tenant=? AND caller=?", (prepared_id, tenant, caller)).fetchone()
            if not prepared or prepared["expiry"] <= self.clock():
                raise Conflict("Unknown/expired prepare")
            token = secrets.token_urlsafe(32)
            connection.execute("INSERT INTO approval VALUES (?,?,?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), prepared_id, tenant, caller, prepared["expiry"], "MOCK_ONLY"))
            self.audit(connection, {"event": "host_mock_authorization", "prepared_id": prepared_id, "tenant": tenant, "caller": caller})
            return token

    def commit(self, prepared_id: str, request: ActionRequest, idempotency_key: str, host_token: str) -> dict:
        if not idempotency_key or not isinstance(host_token, str):
            raise ValueError("Host authorization and idempotency required")
        request_hash = hash_payload({"prepared_id": prepared_id, "payload": request.payload()})
        with self.transaction() as connection:
            existing = connection.execute("SELECT * FROM committed WHERE tenant=? AND caller=? AND idempotency_key=?", (request.tenant, request.caller, idempotency_key)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise Conflict("Idempotency payload conflict")
                return dict(existing)
            prepared = connection.execute("SELECT * FROM prepared WHERE id=? AND tenant=? AND caller=?", (prepared_id, request.tenant, request.caller)).fetchone()
            if not prepared or prepared["payload_hash"] != hash_payload(request.payload()) or prepared["expiry"] <= self.clock():
                raise Conflict("Prepare identity/payload/expiry mismatch")
            authorization = connection.execute("SELECT * FROM approval WHERE digest=? AND prepared_id=? AND tenant=? AND caller=? AND scope='MOCK_ONLY'", (hashlib.sha256(host_token.encode()).hexdigest(), prepared_id, request.tenant, request.caller)).fetchone()
            if not authorization or authorization["expiry"] <= self.clock():
                raise Conflict("Host authorization absent/expired")
            snapshot = connection.execute("SELECT * FROM campaign WHERE tenant=? AND id=?", (request.tenant, request.campaign)).fetchone()
            self.validate(request, dict(snapshot))
            version = request.version + 1
            connection.execute("UPDATE campaign SET reserved=reserved+?,version=?,cooldown_until=? WHERE tenant=? AND id=?", (request.max_spend_units, version, self.clock() + 900 if request.action != Action.NO_CHANGE else snapshot["cooldown_until"], request.tenant, request.campaign))
            connection.execute("INSERT INTO committed VALUES (?,?,?,?,?,?,?,?,?)", (request.caller, request.tenant, idempotency_key, request_hash, prepared_id, request.campaign, request.max_spend_units, None, version))
            self.audit(connection, {"event": "commit_mock", "prepared_id": prepared_id, "reserve_units": request.max_spend_units, "version": version})
            row = connection.execute("SELECT * FROM committed WHERE tenant=? AND caller=? AND idempotency_key=?", (request.tenant, request.caller, idempotency_key)).fetchone()
            return dict(row)

    def settle(self, tenant: str, caller: str, idempotency_key: str, spent_units: int) -> dict:
        """Host-only reconciliation. Expiry alone never releases pending reservations."""
        if type(spent_units) is not int or spent_units < 0:
            raise ValueError("Integer nonnegative settlement required")
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM committed WHERE tenant=? AND caller=? AND idempotency_key=?", (tenant, caller, idempotency_key)).fetchone()
            if not row or spent_units > row["reserve"]:
                raise Conflict("Unknown reservation or payment exceeds reserve")
            if row["settled"] is not None:
                if row["settled"] != spent_units:
                    raise Conflict("Settlement retry payload conflict")
                return dict(row)
            connection.execute("UPDATE campaign SET reserved=reserved-?,spent=spent+? WHERE tenant=? AND id=?", (row["reserve"], spent_units, tenant, row["campaign"]))
            connection.execute("UPDATE committed SET settled=? WHERE tenant=? AND caller=? AND idempotency_key=?", (spent_units, tenant, caller, idempotency_key))
            self.audit(connection, {"event": "settle", "prepared_id": row["prepared_id"], "spent_units": spent_units})
            return dict(connection.execute("SELECT * FROM committed WHERE tenant=? AND caller=? AND idempotency_key=?", (tenant, caller, idempotency_key)).fetchone())

    def verify(self) -> dict:
        connection = self.connect()
        try:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite integrity failure")
            previous = "0" * 64
            rows = connection.execute("SELECT * FROM audit ORDER BY sequence").fetchall()
            for row in rows:
                expected = hashlib.sha256((previous + row["event"]).encode()).hexdigest()
                if row["previous_hash"] != previous or row["event_hash"] != expected:
                    raise ValueError("Audit chain mismatch")
                previous = expected
            for campaign in connection.execute("SELECT * FROM campaign"):
                reservations = connection.execute("SELECT COALESCE(SUM(reserve),0) FROM committed WHERE tenant=? AND campaign=? AND settled IS NULL", (campaign["tenant"], campaign["id"])).fetchone()[0]
                spends = connection.execute("SELECT COALESCE(SUM(settled),0) FROM committed WHERE tenant=? AND campaign=?", (campaign["tenant"], campaign["id"])).fetchone()[0]
                if reservations != campaign["reserved"] or spends != campaign["spent"]:
                    raise ValueError("Budget/event reconciliation mismatch")
            return {"audit_events": len(rows), "audit_head": previous, "integrity": "ok"}
        finally:
            connection.close()
