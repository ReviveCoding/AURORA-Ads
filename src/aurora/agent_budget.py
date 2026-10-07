"""Conservative complete-command agent allocation, including failed replay jobs."""
from __future__ import annotations

import json
import math
from pathlib import Path

AGENT_COMMANDS = {
    "agent_study", "agent_validation", "qualify_agent_model",
    "qualify_trained_restart", "qualify_preference_restart",
    "qualify_agent_inference", "agent_confirmation", "agent_ablation_study",
}


def completed_agent_wall_seconds(execution_directory: Path) -> dict:
    """Full wrapped wall, not GPU utilization/busy time; no double counting.

    This scans exported terminal wrappers only. A live caller must add its own
    elapsed wall and separately reconcile any interrupted/unexported job before
    further budget admission. Unknown/incomplete exported wrappers are not zero.
    """
    records = []
    for path in sorted(execution_directory.glob("*/execution.json")):
        names = [name for name in AGENT_COMMANDS if path.parent.name.startswith("execution_" + name + "_")]
        if not names:
            continue
        if len(names) != 1 or path.is_symlink():
            raise ValueError("Unique owned agent execution identity required")
        record = json.loads(path.read_text())
        command = record.get("command", [])
        wall = record.get("wall_seconds")
        if len(command) < 2 or Path(command[1]).name != names[0] + ".py" or record.get("status") not in {"EXECUTED", "FAILED"} or type(record.get("exit_code")) is not int or not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall < 0:
            raise ValueError("Incomplete/mismatched exported command cannot be silently counted as zero")
        if (record["status"] == "EXECUTED") != (record["exit_code"] == 0):
            raise ValueError("Command status/exit identity mismatch")
        records.append({"artifact": str(path), "command": names[0], "exit_code": record["exit_code"], "full_wall_seconds": float(wall)})
    return {"completed_full_wall_seconds": math.fsum(item["full_wall_seconds"] for item in records), "command_count": len(records), "commands": records, "failed_startup_reference_restart_costs_included": True, "current_job_elapsed_must_be_added": True, "unexported_interrupted_jobs_require_reconciliation": True}
