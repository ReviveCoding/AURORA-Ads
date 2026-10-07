#!/usr/bin/env python3
"""Install bounded CPU admission/test dependencies in the marked project venv."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

from acquire_data import ROOT, atomic_json


def main() -> int:
    runtime = Path.home() / ".local/share/aurora-ads"
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise ValueError("WSL required")
    if json.loads((runtime / "AURORA_RUNTIME.json").read_text())["repo_wsl"] != str(ROOT):
        raise ValueError("Foreign runtime")
    inventory_path = sorted((ROOT / "reports/environment").glob("E00_*.json"))[-1]
    inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
    # This small wheel-install stage has no model/CUDA workload. A larger stage
    # needs a new resource plan, not reuse of this admission.
    if time.time() - inventory_path.stat().st_mtime > 600 or inventory["host_ram_available_bytes"] < 1024**3:
        raise ValueError("Fresh host inventory with >=1GiB free needed for bounded CPU wheel install")
    if min(shutil.disk_usage(ROOT).free, shutil.disk_usage(runtime).free) < 22 * 1024**3:
        raise ValueError("CPU environment growth plus reserve unavailable")
    uv = shutil.which("uv")
    python = Path.home() / ".local/bin/python3.11"
    if not uv or not python.exists():
        raise ValueError("Existing user-space uv/Python3.11 unavailable; no global install")
    environment = runtime / "envs/core"
    commands = []
    if not environment.exists():
        commands.append([uv, "venv", "--python", str(python), str(environment)])
    elif not (environment / "pyvenv.cfg").exists():
        raise ValueError("Existing env path is not a venv")
    commands.append([uv, "pip", "install", "--python", str(environment / "bin/python"), "-r", str(ROOT / "config/requirements-cpu-candidate.txt")])
    report = {"stage": "CPU_CANDIDATE_ONLY", "gpu_qualified": False, "records": [], "inventory": str(inventory_path)}
    directory = runtime / "runs" / f"bootstrap_cpu_{time.time_ns()}"
    directory.mkdir()
    for index, command in enumerate(commands):
        start = time.perf_counter()
        with (directory / f"command_{index}.txt").open("w") as stream:
            result = subprocess.run(command, env=os.environ | {"UV_CACHE_DIR": str(runtime / "cache/uv"), "UV_CONCURRENT_DOWNLOADS": "2", "UV_CONCURRENT_INSTALLS": "2"}, stdout=stream, stderr=subprocess.STDOUT, check=False)
        report["records"].append({"command": command, "exit_code": result.returncode, "wall_seconds": time.perf_counter() - start})
        if result.returncode:
            break
    atomic_json(directory / "report.json", report)
    export = ROOT / "reports/environment" / directory.name
    shutil.copytree(directory, export)
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a") as stream:
        stream.write(f"\n## CPU environment candidate installation\n\nEvidence: `{export / 'report.json'}`. This does not establish GPU compatibility or a qualified lock.\n")
    print(json.dumps(report))
    return 0 if all(record["exit_code"] == 0 for record in report["records"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
