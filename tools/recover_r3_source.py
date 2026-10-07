#!/usr/bin/env python3
"""User-v2.1 authorized R3-only publisher acquisition exception; no admission."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.resources import storage_admission
from aurora.studies import Study
from acquire_data import ByteMeter, download_file, no_symlink, open_url, resolve_sources, safe_relative

R3_CAP = 2_100_000_000


class DualReserveMeter(ByteMeter):
    """Check both backing volumes during bounded streaming, not just preflight."""
    def __init__(self, runtime: Path, root: Path, reserve: int):
        super().__init__(R3_CAP)
        self.runtime, self.root, self.reserve = runtime, root, reserve
        self.last_checked = -128 * 1024**2

    def charge(self, n: int):
        super().charge(n)
        if self.used - self.last_checked >= 128 * 1024**2:
            if min(shutil.disk_usage(self.runtime).free, shutil.disk_usage(self.root).free) < self.reserve:
                raise ValueError("WSL/backing reserve breached; partial source preserved")
            self.last_checked = self.used


def validate_exception(spec: dict, url: str, headers: dict, status: int) -> int:
    """Fail closed on a different source, credentials, absent length or HTML."""
    parsed = urlparse(url)
    if (spec["id"] != "criteo_search" or spec["license"] != "CC-BY-NC-SA-4.0"
            or spec["max_total_download_bytes"] != 700_000_000
            or parsed.scheme != "https" or parsed.hostname != "go.criteo.net"
            or parsed.path != "/criteo-research-search-conversion.tar.gz"
            or parsed.query or parsed.username or parsed.password or status != 200):
        raise ValueError("Exact configured unauthenticated R3 publisher and unchanged default cap required")
    length = headers.get("Content-Length", "")
    if not length.isdecimal() or not 0 < int(length) <= R3_CAP:
        raise ValueError("Declared publisher length absent or outside R3-only authorization")
    if ("text/html" in headers.get("Content-Type", "").lower()
            or headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}):
        raise ValueError("Expected identity-encoded archive, not interactive/legal HTML")
    return int(length)


def main() -> int:
    study = Study(ROOT, "r3_publisher_cap_exception_v21")
    started = time.perf_counter()
    report = {"status": "PREFLIGHT", "source_id": "criteo_search", "analysis_admitted": False,
              "authorization": "Explicit user Continuation Master Prompt v2.1 section7",
              "argv": sys.argv, "started_at_unix": time.time(), "network_payload_bytes": 0,
              "old_failure_preserved": "reports/data/R3_BLOCKED_SOURCE.json"}
    meter = DualReserveMeter(study.runtime, ROOT, 20 * 1024**3)
    mutex = study.runtime / "data/.acquisition.lock"
    owns_mutex = False
    try:
        manifest = json.loads((ROOT / "config/datasets.json").read_text())
        spec = next(x for x in manifest["datasets"] if x["id"] == "criteo_search")
        with open_url(spec["source_page"]) as response:
            page = response.read(4 * 1024**2 + 1)
        if len(page) > 4 * 1024**2 or b"NonCommercial-ShareAlike 4.0" not in page:
            raise ValueError("Configured authorized publisher license marker not verified")
        page_path = study.directory / "publisher_page.html"
        page_path.write_bytes(page)
        files, identity = resolve_sources(spec)
        if len(files) != 1:
            raise ValueError("Exactly one configured R3 publisher object required")
        file = files[0]
        old_lock = study.runtime / "data/manifests/criteo_search.source_lock.json"
        previous = json.loads(old_lock.read_text())
        if previous["files"][0]["url"] != file["url"]:
            raise ValueError("Official publisher object differs from preserved original lock")
        # Header-only GET observation: do not read/transfer payload before exception freeze.
        with open_url(file["url"]) as response:
            headers = {k: response.headers.get(k, "") for k in
                       ("Content-Length", "Content-Type", "Content-Encoding", "ETag", "Last-Modified")}
            length = validate_exception(spec, file["url"], headers, response.getcode())
        resources = json.loads((ROOT / "config/resources.json").read_text())
        # Separate conservative ceilings for safe extracted source, Parquet and temp.
        forecast = length + 3 * 8 * 1024**3
        storage = storage_admission(study.runtime, ROOT, expected_growth_bytes=forecast, contract=resources)
        exception = {"version": "R3_SOURCE_SPECIFIC_CAP_EXCEPTION_V21_1", "frozen_at_unix": time.time(),
                     "source_id": spec["id"], "configured_source_url": file["url"], "publisher_identity": identity,
                     "publisher_page": {"path": str(page_path), "sha256": digest(page_path)},
                     "metadata_headers": headers, "declared_payload_bytes": length,
                     "generic_cap_unchanged_bytes": spec["max_total_download_bytes"],
                     "R3_only_cap_bytes": R3_CAP, "license_acknowledgment": spec["license"],
                     "storage_admission": storage, "forecast": {"payload": length,
                     "extraction_max": 8 * 1024**3, "parquet_max": 8 * 1024**3, "temporary_max": 8 * 1024**3},
                     "no_mirror_no_auth_no_clickthrough": True, "not_analysis_admission": True,
                     "source_hashes": {str(p.relative_to(ROOT)): digest(p) for p in
                     (Path(__file__), ROOT / "tools/acquire_data.py", ROOT / "config/datasets.json",
                      ROOT / "config/resources.json", ROOT / "config/hypotheses.json", ROOT / "config/experiments.json",
                      ROOT / "reports/environment/ENVIRONMENT_LOCK.json")},
                     "previous_source_lock_sha256": digest(old_lock)}
        exception_path = study.directory / "EXCEPTION_BEFORE_TRANSFER.json"
        atomic_json(exception_path, exception)
        report.update(status="EXCEPTION_FROZEN_BEFORE_TRANSFER", exception=exception,
                      exception_sha256=digest(exception_path))
        atomic_json(study.directory / "progress.json", report)
        print(json.dumps({"status": report["status"], "run": str(study.directory),
                          "declared_payload_bytes": length}), flush=True)
        dest = study.runtime / "data/raw/criteo_search" / safe_relative(file["path"])
        no_symlink(mutex)
        descriptor = os.open(mutex, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        owns_mutex = True
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()))
        meter.reserve = storage["reserve_bytes"]
        # Retain original lock and generic manifest, including old failed-acquisition records.
        acquired = download_file(file["url"], dest, file.get("expected_sha256"), length,
                                 R3_CAP, storage["reserve_bytes"], meter=meter)
        report.update(status="ACQUIRED_PENDING_CONTAINER_SCHEMA_CLOCK_ADMISSION", file=acquired,
                      no_fresh_external_validation_claim=True)
    except Exception as error:
        report.update(status="BLOCKED_SOURCE", diagnostic={"type": type(error).__name__,
                      "message": str(error)[:400] if isinstance(error, ValueError)
                      else "Publisher/runtime acquisition failed; preserve local diagnostics, no request tokens logged"})
    finally:
        if owns_mutex and mutex.read_text() == str(os.getpid()):
            mutex.unlink()
    report.update(network_payload_bytes=meter.used, wall_seconds=time.perf_counter() - started,
                  finished_at_unix=time.time())
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/data" / (study.name + ".json")
    atomic_json(export, report)
    atomic_json(ROOT / "reports/data/R3_RECOVERY_LATEST.json", {"artifact": str(export), "sha256": digest(export),
                                                             "status": report["status"]})
    print(json.dumps({"status": report["status"], "artifact": str(export)}), flush=True)
    return 0 if report["status"] == "ACQUIRED_PENDING_CONTAINER_SCHEMA_CLOCK_ADMISSION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
