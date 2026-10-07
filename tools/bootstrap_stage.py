#!/usr/bin/env python3
"""Finite pinned compatibility stages in the owned WSL venv; no device compute."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["gpu", "mcp"])
    args = parser.parse_args()
    runtime = Path.home() / ".local/share/aurora-ads"
    if json.loads((runtime / "AURORA_RUNTIME.json").read_text())["repo_wsl"] != str(ROOT):
        raise ValueError("Runtime ownership mismatch")
    inventory_path = sorted((ROOT / "reports/environment").glob("E00_*.json"))[-1]
    inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
    if time.time() - inventory_path.stat().st_mtime > 900 or inventory["host_ram_available_bytes"] < 2 * 1024**3:
        raise ValueError("Fresh inventory with2GiB host free required for bounded installation")
    growth = 15 if args.stage == "gpu" else 1
    if min(shutil.disk_usage(ROOT).free, shutil.disk_usage(runtime).free) < (20 + growth) * 1024**3:
        raise ValueError("Predicted environment growth plus reserve unavailable")
    run = runtime / "runs" / f"bootstrap_{args.stage}_{time.time_ns()}"
    run.mkdir()
    cpu_lock = json.loads((ROOT / "reports/environment/CPU_LOCK.json").read_text())
    constraints = run / "constraints.txt"
    constraints.write_text("\n".join(cpu_lock["packages"]) + "\n")
    python = runtime / "envs/core/bin/python"
    uv = shutil.which("uv")
    if not uv and (Path.home() / ".local/bin/uv").is_file():
        uv = str(Path.home() / ".local/bin/uv")
    if not uv:
        raise ValueError("Existing uv not available")
    base = [uv, "pip", "install", "--python", str(python), "--constraint", str(constraints)]
    if args.stage == "gpu":
        commands = [base + ["torch==2.7.1", "--index-url", "https://download.pytorch.org/whl/cu128"], base + ["-r", str(ROOT / "config/requirements-gpu-candidate.txt")]]
    else:
        commands = [base + ["-r", str(ROOT / "config/requirements-mcp-candidate.txt")]]
    report = {"stage": args.stage, "inventory": str(inventory_path), "candidate_sha256": digest(ROOT / f"config/requirements-{args.stage}-candidate.txt"), "constraints_sha256": digest(constraints), "records": [], "GPU_QUALIFIED": False}
    for index, command in enumerate(commands):
        clock = time.perf_counter()
        log = run / f"command_{index}.txt"
        with log.open("w") as output:
            process = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, env=os.environ | {"UV_CACHE_DIR": str(runtime / "cache/uv"), "UV_CONCURRENT_DOWNLOADS": "2", "UV_CONCURRENT_INSTALLS": "2"}, check=False)
        report["records"].append({"command": command, "exit_code": process.returncode, "wall_seconds": time.perf_counter() - clock, "log_sha256": digest(log)})
        atomic_json(run / "report.json", report)
        if process.returncode:
            break
    report["status"] = "INSTALLED_PENDING_COMPATIBILITY" if all(row["exit_code"] == 0 for row in report["records"]) else "INSTALL_FAILED"
    atomic_json(run / "report.json", report)
    export = ROOT / "reports/environment" / run.name
    shutil.copytree(run, export)
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a", encoding="utf-8") as output:
        output.write(f"\n## {args.stage} candidate installation\n\nExact commands/status/timing: `{export / 'report.json'}`. No device/model computation; qualification is a separate gate.\n")
    print(json.dumps({"status": report["status"], "artifact": str(export / "report.json")}))
    return 0 if report["status"] == "INSTALLED_PENDING_COMPATIBILITY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
