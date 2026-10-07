#!/usr/bin/env python3
"""Execute one named study command with frozen input/code provenance and failure logs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", choices=["finish_admission", "source_blockers", "data_reports", "attribution_study", "freeze_agent_taxonomy", "freeze_agent_recipe_profile", "verify_training_checkpoint", "qualify_trained_restart", "qualify_preference_restart", "qualify_agent_inference", "qualify_tokenizer_transfer", "qualify_completion_projection", "statistics_qualification", "policy_cost_audit", "policy_support_audit", "qualify_policy_support", "qualify_policy_repairs", "ope_study", "causal_study", "qualify_gpu", "qualify_mcp", "simulator_study", "incident_study", "policy_study", "policy_repair_study", "predictive_study", "qualify_serving_source", "serving_study", "agent_study", "agent_validation", "agent_data", "model_prepare", "qualify_agent_model", "completed_track_reports", "clock_audit_report", "completion_audit", "final_reports"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    script_action = next(action for action in parser._actions if action.dest == "script")
    script_action.choices = [*script_action.choices, "agent_budget_audit", "agent_ablation_study", "freeze_agent_confirmation", "agent_confirmation", "mcp_recovery_study"]
    args = parser.parse_args()
    runtime = Path.home() / ".local/share/aurora-ads"
    if json.loads((runtime / "AURORA_RUNTIME.json").read_text())["repo_wsl"] != str(ROOT):
        raise ValueError("Runtime mismatch")
    script = ROOT / "tools" / (args.script + ".py")
    if not script.is_file():
        raise ValueError("Study not implemented")
    run = runtime / "runs" / f"execution_{args.script}_{time.time_ns()}"
    run.mkdir()
    export = ROOT / "reports/execution" / run.name
    command = [sys.executable, str(script), *args.arguments]
    # An immutable evidence archive, not an editable WSL Git worktree. Include
    # imported tool helpers as well as the launch script. Earlier runs retain
    # their original hash-only provenance; do not imply retroactive archives.
    paths = {*sorted((ROOT / "src/aurora").glob("*.py")), *sorted((ROOT / "tools").glob("*.py")), *sorted((ROOT / "config").glob("*.json"))}
    paths.update(ROOT / relative for relative in ("WORK_STATE.md", "docs/FINAL_SPEC.md", "docs/SIMULATOR_CONTRACT.md", "DESIGN_KO.md", "docs/DESIGN_AUDIT_KO.md", "TEST_REPORT.md"))
    lock = ROOT / "reports/environment/ENVIRONMENT_LOCK.json"
    if not lock.exists():
        lock = ROOT / "reports/environment/CPU_LOCK.json"
    paths.add(lock)
    inputs = {}
    archive = run / "executed_source_snapshot.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as snapshot:
        for path in sorted(paths):
            payload = path.read_bytes()
            relative = str(path.relative_to(ROOT))
            inputs[relative] = hashlib.sha256(payload).hexdigest()
            snapshot.writestr(relative, payload)
    archive.chmod(0o444)
    report = {"command": command, "started_at_unix": time.time(), "inputs_sha256": inputs, "source_archive": {"path": str(archive), "sha256": digest(archive), "scope": "launch-time source/config/spec/environment-lock bytes; evidence only, never an editable worktree"}, "python": sys.version, "status": "RUNNING", "storage_before": {"ext4_free": shutil.disk_usage(runtime).free, "backing_free": shutil.disk_usage(ROOT).free}, "environment_lock_sha256": inputs[str(lock.relative_to(ROOT))], "environment_lock": str(lock)}
    atomic_json(run / "execution.json", report)
    start = time.perf_counter()
    with (run / "output.txt").open("w") as output:
        result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, env=os.environ | {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "PYTHONDONTWRITEBYTECODE": "1"}, check=False)
    report.update(exit_code=result.returncode, wall_seconds=time.perf_counter() - start, status="EXECUTED" if result.returncode == 0 else "FAILED", child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss, output_sha256=digest(run / "output.txt"), storage_after={"ext4_free": shutil.disk_usage(runtime).free, "backing_free": shutil.disk_usage(ROOT).free})
    report["input_changes_during_execution"] = {relative: {"launch_sha256": sha, "end_sha256": digest(ROOT / relative) if (ROOT / relative).is_file() else None} for relative, sha in inputs.items() if not (ROOT / relative).is_file() or digest(ROOT / relative) != sha}
    atomic_json(run / "execution.json", report)
    shutil.copytree(run, export)
    from aurora.studies import Study
    state_export = Study(ROOT, "execution_state_export")
    if result.returncode:
        expected_nodes = {"simulator_study": "E07", "causal_study": "E04", "ope_study": "E05", "predictive_study": "E15_R1" if "--confirm" in args.arguments else "E02", "incident_study": "E08", "policy_study": "E09"}
        node = expected_nodes.get(args.script)
        if node and state_export.ledger.read()["nodes"][node]["execution_status"] == "RUNNING":
            state_export.ledger.update(node, "FAILED", artifacts=(export / "execution.json",), reason="Actual command failed; immutable diagnostic retained; repair/retest before dependent execution")
    state_export.export_state()
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a", encoding="utf-8") as output:
        output.write(f"\n## Recorded study command {args.script}\n\nExit{result.returncode}, wall{report['wall_seconds']:.3f}s; exact argv, provenance and failure output: `{export / 'execution.json'}`.\n")
    print(json.dumps({"status": report["status"], "artifact": str(export / "execution.json")}))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
