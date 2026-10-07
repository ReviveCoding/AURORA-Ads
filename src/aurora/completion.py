"""Conservative registry completion audit, distinct from favorable science."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from aurora.workflow import EXECUTION, SCIENCE

TERMINAL_DISPOSITIONS = {"EXECUTED", "BLOCKED_SOURCE", "BLOCKED_HARDWARE", "BLOCKED_ENVIRONMENT", "INVALID", "NOT_APPLICABLE"}


def completion_matrix(nodes: Sequence[Mapping[str, Any]], state: Mapping[str, Any]) -> dict:
    declared = {node["id"] for node in nodes}
    if len(declared) != len(nodes) or set(state["nodes"]) != declared:
        raise ValueError("Exact registry/state node identity required")
    rows = []
    for node in nodes:
        identity = node["id"]
        value = state["nodes"][identity]
        execution, science = value["execution_status"], value["scientific_outcome"]
        if execution not in EXECUTION or science not in SCIENCE or science == "SUPPORTED" and execution != "EXECUTED":
            raise ValueError("Invalid engineering/science disposition")
        if execution == "EXECUTED" and not value["artifacts"]:
            raise ValueError("Executed node lacks artifact evidence")
        if execution.startswith("BLOCKED") and not value.get("reason"):
            raise ValueError("Blocker lacks actionable diagnostics")
        dependencies = {dependency: state["nodes"][dependency]["execution_status"] for dependency in node["requires"]}
        declared_capabilities = {name: bool(state["capabilities"].get(name, False)) for name in node["capabilities"]}
        rows.append({"node": identity, "name": node["name"], "evidence_domain": node["evidence_domain"], "execution_status": execution, "scientific_status": science, "terminal_disposition": execution in TERMINAL_DISPOSITIONS, "dependencies": dependencies, "declared_capabilities": declared_capabilities, "artifact_count": len(value["artifacts"]), "artifacts": value["artifacts"], "reason": value.get("reason", ""), "routine_retry_is_not_a_blocker": execution == "FAILED"})
    required = [row for row in rows if row["node"] != "E16"]
    unfinished = [row["node"] for row in required if not row["terminal_disposition"]]
    final = next((row for row in rows if row["node"] == "E16"), None)
    return {"registry_node_count": len(rows), "state_generation": state["generation"], "rows": rows, "unfinished_or_repair_required": unfinished, "all_nonreport_tracks_have_terminal_dispositions": not unfinished, "final_reporting_executed": final is not None and final["execution_status"] == "EXECUTED", "overall_project_complete": not unfinished and final is not None and final["execution_status"] == "EXECUTED", "supported_scientific_nodes": [row["node"] for row in rows if row["scientific_status"] == "SUPPORTED"], "interpretation": "Engineering dispositions and scientific support are separate. Failed commands require repair or a diagnosed valid blocker; they alone do not establish completion. Artifact byte checks do not validate every scientific requirement."}
