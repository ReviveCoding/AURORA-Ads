#!/usr/bin/env python3
"""Real subprocess stdio MCP roundtrip/restart, not a fabricated transport test."""
from __future__ import annotations

import asyncio
import importlib.metadata
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from aurora.artifacts import atomic_json, digest
from aurora.state import StateHost
from aurora.studies import Study
from aurora.tools import CATALOG


def payload(result):
    if result.isError:
        raise ValueError("MCP returned an error: " + str(result.content))
    return json.loads(result.content[0].text)


async def execute(study):
    state = StateHost(study.runtime / "state/tool_host.sqlite")
    tenant = "qualification_" + str(time.time_ns())
    state.create_campaign(tenant, "campaign", 10000)
    parameters = StdioServerParameters(command=sys.executable, args=[str(ROOT / "tools/mcp_server.py"), "--tenant", tenant, "--caller", "qualifier", "--mock-preauthorized"], env={"PYTHONDONTWRITEBYTECODE": "1"})
    trace = []
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as client:
            initialization = await client.initialize()
            schema = await client.list_tools()
            assert {tool.name for tool in schema.tools} == set(CATALOG)
            assert all("tenant" not in tool.inputSchema.get("properties", {}) for tool in schema.tools)
            trace.append({"stage": "initialize_schema", "protocol": initialization.protocolVersion, "tools": len(schema.tools)})
            snapshot = payload(await client.call_tool("get_campaign_snapshot", {"campaign": "campaign"}))
            assert snapshot["snapshot_version"] == 0
            action = {"campaign": "campaign", "snapshot_version": 0, "action": "BID_MULTIPLIER_DOWN"}
            prepared = payload(await client.call_tool("prepare_action", action))
            args = action | {"prepared_id": prepared["data"]["prepared_id"], "idempotency_key": "once"}
            committed = payload(await client.call_tool("commit_mock_action", args))
            retry = payload(await client.call_tool("commit_mock_action", args))
            assert committed["data"] == retry["data"]
            forged = await client.call_tool("query_metrics", {"campaign": "campaign", "metric": "spent", "tenant": "forged"})
            assert forged.isError
            unavailable = payload(await client.call_tool("estimate_outcomes", {"campaign": "campaign"}))
            assert unavailable["status"] == "MODEL_NOT_QUALIFIED"
            trace.append({"stage": "prepare_commit_duplicate_forged_context", "once_spend_units": 100, "duplicate_same_result": True, "forged_context_blocked": True, "unqualified_model_explicit": True})
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            snapshot = payload(await client.call_tool("get_campaign_snapshot", {"campaign": "campaign"}))
            assert snapshot["data"]["spent"] == 100 and snapshot["data"]["reserved"] == 0
            measured = payload(await client.call_tool("build_measurement_report", {"campaign": "campaign"}))
            assert measured["data"]["integrity"]["integrity"] == "ok"
            trace.append({"stage": "real_process_restart", "spent_units": snapshot["data"]["spent"], "reserved_units": snapshot["data"]["reserved"], "audit_integrity": True})
    return trace


def main():
    study = Study(ROOT, "mcp_transport_qualification")
    started = time.perf_counter()
    report = {"status": "RUNNING", "mcp_version": importlib.metadata.version("mcp"), "scope": "Real local stdio MCP host transport; not agent learning or end-to-end model qualification"}
    try:
        report["trace"] = asyncio.run(asyncio.wait_for(execute(study), timeout=60))
        report.update(status="MCP_TRANSPORT_QUALIFIED", passed=True)
    except Exception as error:
        report.update(status="FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1500], "traceback": traceback.format_exc()[-8000:]})
    report["wall_seconds"] = time.perf_counter() - started
    report["code_hashes"] = {relative: digest(ROOT / relative) for relative in ("tools/mcp_server.py", "src/aurora/tools.py", "src/aurora/state.py", "tools/qualify_mcp.py")}
    export = ROOT / "reports/agent" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(export, report)
    atomic_json(ROOT / "reports/environment/MCP_QUALIFICATION.json", report | {"artifact": str(export), "sha256": digest(export)})
    prior_node = study.ledger.read()["nodes"]["E10_TOOLS"]
    status = prior_node["execution_status"] if report["passed"] and prior_node["execution_status"] == "EXECUTED" else "PENDING" if report["passed"] else "FAILED"
    preserved = tuple(Path(item["path"]) for item in prior_node["artifacts"])
    corpus_pointer = ROOT / "reports/agent/CORPUS_LATEST.json"
    if report["passed"] and status == "EXECUTED" and corpus_pointer.exists() and corpus_pointer not in preserved:
        preserved += (corpus_pointer,)
    study.ledger.update("E10_TOOLS", status, science=prior_node["scientific_outcome"], artifacts=preserved + (export,), reason="Current transport requalification; preserve already completed task admission and historical artifacts" if report["passed"] else "Transport diagnostic retained; fix before dependent execution", capabilities={"MCP_TRANSPORT_QUALIFIED": report["passed"]})
    study.export_state()
    if report["passed"]:
        previous = json.loads((ROOT / "reports/environment/ENVIRONMENT_LOCK.json").read_text())
        previous.update(packages=sorted(f"{dist.metadata['Name']}=={dist.version}" for dist in importlib.metadata.distributions()), mcp_qualification_sha256=digest(export))
        atomic_json(ROOT / "reports/environment/ENVIRONMENT_LOCK.json", previous)
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
