#!/usr/bin/env python3
"""Bounded safe R3 archive inventory/CRC; no extraction or analysis admission."""
from __future__ import annotations

import gzip
import io
import json
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.data import BoundedReader
from aurora.resources import storage_admission
from aurora.studies import Study
from acquire_data import safe_relative


def validate_member(member: tarfile.TarInfo, seen: set[str]) -> str:
    name = member.name.rstrip("/") if member.isdir() else member.name
    safe_relative(name)
    key = name.casefold()
    if key in seen or not (member.isdir() or member.isfile()) or member.size < 0:
        raise ValueError("Duplicate/nonportable/link/device archive member")
    seen.add(key)
    return name


def main() -> int:
    study = Study(ROOT, "r3_bounded_container_inventory")
    started = time.perf_counter()
    report = {"status": "RUNNING", "analysis_admitted": False, "members": [],
              "argv": sys.argv, "started_at_unix": time.time(), "code_sha256": digest(Path(__file__)),
              "decompressed_total_ceiling_bytes": 8 * 1024**3, "member_count_ceiling": 64}
    try:
        pointer = json.loads((ROOT / "reports/data/R3_RECOVERY_LATEST.json").read_text())
        recovery_path = Path(pointer["artifact"])
        if digest(recovery_path) != pointer["sha256"]:
            raise ValueError("Recovery source artifact changed")
        recovered = json.loads(recovery_path.read_text())
        if recovered["status"] != "ACQUIRED_PENDING_CONTAINER_SCHEMA_CLOCK_ADMISSION":
            raise ValueError("Verified acquired source required")
        source = Path(recovered["file"]["path"])
        if digest(source) != recovered["file"]["sha256"]:
            raise ValueError("Acquired publisher object changed")
        report["source"] = recovered["file"]
        report["recovery_sha256"] = pointer["sha256"]
        report["storage_admission"] = storage_admission(study.runtime, ROOT,
            expected_growth_bytes=1024**2, contract=json.loads((ROOT / "config/resources.json").read_text()))
        atomic_json(study.directory / "protocol_before_scan.json", report)
        seen, total = set(), 0
        with source.open("rb") as raw, gzip.GzipFile(fileobj=raw) as decoded:
            bounded = BoundedReader(decoded, report["decompressed_total_ceiling_bytes"])
            stream = io.BufferedReader(bounded)
            with tarfile.open(fileobj=stream, mode="r|") as archive:
                for member in archive:
                    name = validate_member(member, seen)
                    if len(seen) > report["member_count_ceiling"]:
                        raise ValueError("Archive member count exceeds declared ceiling")
                    total += member.size
                    if total > report["decompressed_total_ceiling_bytes"]:
                        raise ValueError("Declared member total exceeds decompressed ceiling")
                    item = {"name": name, "bytes": member.size, "directory": member.isdir()}
                    # Documentation only. No event/label prefixes or final data are scored.
                    if member.isfile() and member.size <= 65536 and ("readme" in name.lower() or name.lower().endswith((".txt", ".md"))):
                        content = archive.extractfile(member)
                        assert content is not None
                        item["documentation"] = content.read(65537).decode("utf-8", errors="replace")
                    report["members"].append(item)
                    atomic_json(study.directory / "progress.json", report)
            # TAR end markers alone are not gzip CRC/EOF qualification.
            while stream.read(1024**2):
                pass
            report["decompressed_bytes"] = bounded.count
        report.update(status="CONTAINER_SAFE_INVENTORY_EOF_CRC_VALID", declared_file_bytes=total,
                      schema_valid=False, clock_valid=False, no_extraction_performed=True)
    except Exception as error:
        report.update(status="CONTAINER_INVALID", diagnostic={"type": type(error).__name__, "message": str(error)[:400]})
    report.update(wall_seconds=time.perf_counter() - started, finished_at_unix=time.time())
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/data" / (study.name + ".json")
    atomic_json(export, report)
    atomic_json(ROOT / "reports/data/R3_CONTAINER_INVENTORY.json", {"artifact": str(export), "sha256": digest(export)})
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0 if report["status"] == "CONTAINER_SAFE_INVENTORY_EOF_CRC_VALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
