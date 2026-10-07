#!/usr/bin/env python3
"""Bounded preparation/source commands, captured with exact timing and immutable evidence."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["checks", "acquire", "runtime", "source-metadata"])
    parser.add_argument("--source", choices=["criteo_uplift", "criteo_attribution", "criteo_search", "obd_men"])
    args = parser.parse_args()
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        parser.error("Qualified execution requires WSL")
    runtime = Path.home() / ".local/share/aurora-ads"
    marker = json.loads((runtime / "AURORA_RUNTIME.json").read_text())
    if marker["repo_wsl"] != str(ROOT):
        raise ValueError("Foreign runtime")
    reserve = 20 * 1024**3
    growth = 5 * 1024**3 if args.mode == "acquire" else 1024**2
    if min(shutil.disk_usage(runtime).free, shutil.disk_usage(ROOT).free) < reserve + growth:
        raise ValueError("Backing/ext4 storage reserve insufficient")
    identifier = f"{args.mode}_{args.source or 'all'}_{time.time_ns()}"
    directory = runtime / "runs" / identifier
    directory.mkdir()
    if args.mode == "checks":
        commands = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], [sys.executable, "tools/validate_design.py", "--no-hashes"]]
    elif args.mode == "runtime":
        commands = [[sys.executable, "tools/prepare_runtime.py", "--repo", str(ROOT)]]
    elif args.mode == "source-metadata":
        commands = [[sys.executable, "tools/source_metadata.py"]]
    else:
        if not args.source:
            parser.error("Acquire exactly one source per resumable node invocation")
        commands = [[sys.executable, "tools/acquire_data.py", "--only", args.source, "--accept-license", "CC-BY-NC-SA-4.0", "--accept-license", "CC-BY-4.0", "--apply"]]
    records = []
    for index, command in enumerate(commands):
        started = time.time()
        clock = time.perf_counter()
        output = directory / f"command_{index}.txt"
        with output.open("w") as stream:
            process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}, check=False)
        record = {"command": command, "exit_code": process.returncode, "started_at_unix": started, "wall_seconds": time.perf_counter() - clock, "output_path": str(output), "output_sha256": digest(output)}
        records.append(record)
        print(json.dumps(record), flush=True)
    evidence = {"run_id": identifier, "python": platform.python_version(), "records": records, "scientific_claim": "NONE; admission/engineering only"}
    atomic_json(directory / "commands.json", evidence)
    export = ROOT / "reports" / "execution" / identifier
    export.mkdir(parents=True)
    for path in directory.iterdir():
        shutil.copy2(path, export / path.name)
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a", encoding="utf-8") as stream:
        stream.write(f"\n## Recorded run {identifier}\n\n")
        for record in records:
            stream.write(f"- Command argv `{json.dumps(record['command'])}`; exit {record['exit_code']}; wall {record['wall_seconds']:.3f}s; evidence `{export / 'commands.json'}` and `{export / Path(record['output_path']).name}`.\n")
    return 0 if all(record["exit_code"] == 0 for record in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
