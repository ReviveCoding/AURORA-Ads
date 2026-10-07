#!/usr/bin/env python3
"""Owned recovery-test child PID receipt, then exec the unchanged MCP server."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid-file", type=Path, required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--caller", required=True)
    parser.add_argument("--mock-preauthorized", action="store_true")
    args = parser.parse_args()
    runtime = Path.home() / ".local/share/aurora-ads"
    if json.loads((runtime / "AURORA_RUNTIME.json").read_text())["repo_wsl"] != str(ROOT):
        raise ValueError("Owned runtime required")
    if not args.pid_file.is_absolute() or not args.pid_file.resolve().is_relative_to(runtime / "runs") or args.pid_file.exists():
        raise ValueError("New owned PID receipt required")
    command = [sys.executable, str(ROOT / "tools/mcp_server.py"), "--tenant", args.tenant, "--caller", args.caller]
    if args.mock_preauthorized:
        command.append("--mock-preauthorized")
    start_ticks = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]
    atomic_json(args.pid_file, {"pid": os.getpid(), "start_ticks": start_ticks, "expected_exec_command": command, "scope": "This recovery test's owned child only; never unrelated applications"})
    os.execv(sys.executable, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
