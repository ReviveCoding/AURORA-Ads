#!/usr/bin/env python3
"""Actual CPU-only MCP crash/restart and replay correctness, not serving SLO."""
from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
import signal
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
        raise ValueError("Unexpected MCP error: " + str(result.content)[:1000])
    return json.loads(result.content[0].text)


def rejection(result, expected_text: str) -> dict:
    text = " ".join(item.text for item in result.content if hasattr(item, "text"))
    if not result.isError or expected_text.lower() not in text.lower():
        raise ValueError("Required actual host rejection not observed: " + expected_text)
    return {"is_error": True, "actual_reason": text[:500]}


def kill_owned_server(receipt: Path, study: Study) -> dict:
    if receipt.is_symlink() or not receipt.resolve().is_relative_to(study.directory):
        raise ValueError("Only this study's PID receipt admitted")
    record = json.loads(receipt.read_text())
    known_command = [sys.executable, str(ROOT / "tools/mcp_server.py"), "--tenant", study.name, "--caller", "mcp_recovery", "--mock-preauthorized"]
    if record["expected_exec_command"] != known_command:
        raise ValueError("Receipt does not belong to this exact study tenant/caller; do not inspect/terminate another process")
    pid = record["pid"]
    if type(pid) is not int or pid <= 1 or pid == os.getpid():
        raise ValueError("Invalid owned server PID")
    process = Path("/proc") / str(pid)
    arguments = [entry.decode() for entry in (process / "cmdline").read_bytes().split(b"\0") if entry]
    start_ticks = (process / "stat").read_text().rsplit(")", 1)[1].split()[19]
    expected = record["expected_exec_command"]
    if arguments != expected or start_ticks != record["start_ticks"] or len(expected) < 2 or expected[1] != str(ROOT / "tools/mcp_server.py"):
        raise ValueError("PID identity/reuse check failed; do not terminate anything")
    os.kill(pid, signal.SIGKILL)
    return {"owned_pid": pid, "start_ticks": start_ticks, "signal": "SIGKILL", "exact_owned_argv_verified": True, "unrelated_processes_touched": False}


async def execute(study: Study, report: dict):
    state = StateHost(study.runtime / "state/tool_host.sqlite")
    tenant, caller = study.name, "mcp_recovery"
    state.create_campaign(tenant, "main", 100)
    state.create_campaign(tenant, "short", 99)
    state.create_campaign(tenant, "zero", 0)
    report["tenant"] = tenant
    report["state_database"] = str(state.path)
    def parameters(phase: str, authorized=True):
        arguments = [str(ROOT / "tools/mcp_recovery_launch.py"), "--pid-file", str(study.directory / (phase + "_pid.json")), "--tenant", tenant, "--caller", caller]
        if authorized:
            arguments.append("--mock-preauthorized")
        return StdioServerParameters(command=sys.executable, args=arguments, env={"PYTHONDONTWRITEBYTECODE": "1"})
    first_action = {"campaign": "main", "snapshot_version": 0, "action": "BID_MULTIPLIER_DOWN"}
    second_action = first_action | {"action": "PACE_UP"}
    killed = False
    try:
        async with stdio_client(parameters("before_crash")) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                schemas = await client.list_tools()
                if {tool.name for tool in schemas.tools} != set(CATALOG):
                    raise ValueError("Nine-tool ABI mismatch")
                payload(await client.call_tool("validate_action", first_action))
                first = payload(await client.call_tool("prepare_action", first_action))
                second = payload(await client.call_tool("prepare_action", second_action))
                before = payload(await client.call_tool("get_campaign_snapshot", {"campaign": "main"}))
                if before["data"]["spent"] != 0 or before["data"]["reserved"] != 0:
                    raise ValueError("Prepare unexpectedly charges/reserves")
                first_args = first_action | {"prepared_id": first["data"]["prepared_id"], "idempotency_key": "restart_once"}
                second_args = second_action | {"prepared_id": second["data"]["prepared_id"], "idempotency_key": "stale_second"}
                committed = payload(await client.call_tool("commit_mock_action", first_args))
                report["pre_crash_commit"] = {"first_arguments": first_args, "second_arguments": second_args, "response": committed}
                atomic_json(study.directory / "pre_crash_checkpoint.json", report["pre_crash_commit"])
                report["crash_injection"] = kill_owned_server(study.directory / "before_crash_pid.json", study)
                killed = True
    except Exception as error:
        # A terminated transport may report EOF/exception-group during cleanup.
        # It is expected only AFTER exact-identity kill and committed checkpoint.
        if not killed:
            raise
        report["crashed_transport_cleanup"] = {"type": type(error).__name__, "message": str(error)[:1000], "classified": "post-injected-crash transport cleanup, not hidden task success"}
    if not killed:
        raise ValueError("Actual process crash was not injected")
    async with stdio_client(parameters("after_crash")) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            snapshot = payload(await client.call_tool("get_campaign_snapshot", {"campaign": "main"}))
            if snapshot["data"]["spent"] != 100 or snapshot["data"]["reserved"] != 0 or snapshot["snapshot_version"] != 1:
                raise ValueError("Committed spend/version lost after actual SIGKILL")
            before_integrity = state.verify()
            retry = payload(await client.call_tool("commit_mock_action", first_args))
            if retry["data"] != committed["data"] or state.verify() != before_integrity:
                raise ValueError("Restart replay changed applied result or audit chain")
            altered = rejection(await client.call_tool("commit_mock_action", first_args | {"action": "PACE_UP"}), "Idempotency payload conflict")
            stale = rejection(await client.call_tool("commit_mock_action", second_args), "Stale state")
            short = rejection(await client.call_tool("prepare_action", {"campaign": "short", "snapshot_version": 0, "action": "PACE_DOWN"}), "Insufficient unreserved budget")
            noop = {"campaign": "zero", "snapshot_version": 0, "action": "NO_CHANGE"}
            no_prepared = payload(await client.call_tool("prepare_action", noop))
            payload(await client.call_tool("commit_mock_action", noop | {"prepared_id": no_prepared["data"]["prepared_id"], "idempotency_key": "zero_noop"}))
            zero = payload(await client.call_tool("get_campaign_snapshot", {"campaign": "zero"}))
            if zero["data"]["spent"] or zero["data"]["reserved"]:
                raise ValueError("Zero-budget NO_CHANGE invented a charge")
            report["after_restart"] = {"snapshot": snapshot, "duplicate_data_identical": True, "duplicate_audit_unchanged": True, "altered_payload_rejection": altered, "stale_prepared_intent_rejection": stale, "independent_short_budget_rejection": short, "zero_budget_noop_spend": 0}
    async with stdio_client(parameters("revoked_context", authorized=False)) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            unauthorized = rejection(await client.call_tool("commit_mock_action", first_args), "preauthorization")
            report["revoked_host_context"] = {"previous_committed_replay_is_not_current_authorization": True, "actual_rejection": unauthorized}
    main = state.snapshot(tenant, "main")
    if main["spent"] != 100 or main["reserved"] != 0:
        raise ValueError("Final budget changed after blocked retries")
    connection = state.connect()
    try:
        count = connection.execute("SELECT COUNT(*) FROM committed WHERE tenant=? AND campaign='main' AND caller=?", (tenant, caller)).fetchone()[0]
    finally:
        connection.close()
    if count != 1:
        raise ValueError("More than one unique applied main action after restart/retries")
    report["final_ledger"] = {"main_unique_commits": count, "main_spent_units_1e4": main["spent"], "main_reserved_units_1e4": main["reserved"], "integrity": state.verify()}


def main() -> int:
    study = Study(ROOT, "mcp_crash_replay_correctness")
    started = time.perf_counter()
    report = {"status": "RUNNING", "passed": False, "evidence_domain": "LOCAL_MOCK_RELIABILITY",
        "command": [sys.executable, str(ROOT / "tools/mcp_recovery_study.py"), *sys.argv[1:]],
        "python": sys.version, "mcp_version": importlib.metadata.version("mcp"),
        "started_at_unix": time.time(),
        "no_llm_invocations": True, "not_agent_model_outcomes": True,
        "not_isolated_serving_latency_or_slo_evidence": True,
        "scope": "Actual owned stdio MCP subprocess SIGKILL after acknowledged commit, fresh process replay; no live ads or unrelated application changes"}
    try:
        asyncio.run(asyncio.wait_for(execute(study, report), timeout=55))
        report.update(status="MCP_CRASH_REPLAY_CORRECTNESS_QUALIFIED", passed=True)
    except Exception as error:
        report.update(status="MCP_CRASH_REPLAY_CORRECTNESS_FAILED", diagnostic={"type": type(error).__name__, "message": str(error)[:1500], "traceback": traceback.format_exc()[-6000:]})
    report["wall_seconds"] = time.perf_counter() - started
    report["code_sha256"] = {name: digest(ROOT / name) for name in ("tools/mcp_recovery_study.py", "tools/mcp_recovery_launch.py", "tools/mcp_server.py", "src/aurora/tools.py", "src/aurora/state.py")}
    report["environment_lock_sha256"] = digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json")
    artifact = ROOT / "reports/serving" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/serving/MCP_RECOVERY_QUALIFICATION.json", {"artifact": str(artifact), "sha256": digest(artifact), "passed": report["passed"]})
    # This contributes correctness evidence only. Do not close E14 or change
    # scientific status before complete isolated performance/recovery studies.
    previous = study.ledger.read()["nodes"]["E14"]
    preserved = tuple(Path(item["path"]) for item in previous["artifacts"])
    study.ledger.update("E14", previous["execution_status"], science=previous["scientific_outcome"], artifacts=(*preserved, artifact), reason="Append CPU local-MCP crash/replay correctness only; isolated performance and other recovery gates remain", capabilities={"MCP_CRASH_REPLAY_CORRECTNESS": report["passed"]})
    study.export_state()
    print(json.dumps({"status": report["status"], "artifact": str(artifact), "wall_seconds": report["wall_seconds"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
