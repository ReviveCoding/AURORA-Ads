#!/usr/bin/env python3
"""Official bounded metadata snapshots; no payload or authenticated access."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.error import HTTPError

from acquire_data import ROOT, atomic_json, open_url, resolve_sources


def main() -> int:
    report = {"measured_at_unix": time.time(), "sources": []}
    for spec in json.loads((ROOT / "config/datasets.json").read_text())["datasets"]:
        if "core" not in spec["profiles"]:
            continue
        record = {"id": spec["id"], "license": spec["license"], "source_page": spec["source_page"], "prior_exposure": spec["prior_exposure"], "analysis_admitted": False}
        try:
            with open_url(spec["source_page"]) as stream:
                page = stream.read(4 * 1024**2 + 1)
            if len(page) > 4 * 1024**2:
                raise ValueError("Page ceiling exceeded")
            record["source_page_sha256"] = hashlib.sha256(page).hexdigest()
            snapshots = Path.home() / ".local/share/aurora-ads/data/manifests/pages"
            snapshots.mkdir(parents=True, exist_ok=True)
            snapshot = snapshots / (record["source_page_sha256"] + ".html")
            if not snapshot.exists():
                snapshot.write_bytes(page)
            record["terms_snapshot"] = str(snapshot)
            record["license_marker_present"] = (b"NonCommercial-ShareAlike 4.0" in page if spec["license"] == "CC-BY-NC-SA-4.0" else b"cc-by-4.0" in page)
            if not record["license_marker_present"]:
                raise ValueError("Expected authorized source-license marker absent")
            files, identity = resolve_sources(spec)
            record.update(files=files, identity=identity, status="METADATA_RESOLVED")
        except HTTPError as error:
            record.update(status="BLOCKED_SOURCE", diagnostic={"type": "HTTPError", "http_status": error.code})
        except Exception as error:
            # These exceptions contain no request credentials. Never emit HTTP URLs/query strings.
            record.update(status="BLOCKED_SOURCE", diagnostic={"type": type(error).__name__, "message": "Publisher metadata/identity check failed"})
        report["sources"].append(record)
    path = ROOT / "reports/data" / f"source_metadata_{time.time_ns()}.json"
    atomic_json(path, report)
    print(path)
    return 0 if all(item["status"] == "METADATA_RESOLVED" for item in report["sources"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
