#!/usr/bin/env python3
"""Full bounded CRC/schema scan into immutable chunk Parquet, then clock/lineage gates."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pyarrow.compute as pc
import pyarrow.parquet as pq
from aurora.artifacts import atomic_json, digest
from aurora.data import SCHEMAS, open_batches, valid_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=["criteo_uplift", "criteo_attribution", "obd_men"])
    args = parser.parse_args()
    runtime = Path.home() / ".local/share/aurora-ads"
    if json.loads((runtime / "AURORA_RUNTIME.json").read_text())["repo_wsl"] != str(ROOT):
        raise ValueError("Runtime identity mismatch")
    schema = SCHEMAS[args.source]
    lock = json.loads((runtime / f"data/manifests/{args.source}.source_lock.json").read_text())
    run = runtime / "runs" / f"admit_{args.source}_{time.time_ns()}"
    run.mkdir()
    report = {"source_id": args.source, "evidence_domain": schema.evidence_domain, "status": "RUNNING", "container_valid": False, "schema_valid": False, "clock_valid": False, "analysis_admitted": False, "identity": lock["source_identity"], "source_lock_sha256": digest(runtime / f"data/manifests/{args.source}.source_lock.json"), "files": [], "lineage_status": "PRIOR_EXPOSURE_UNRESOLVED; no virgin confirmation claim", "eligible_features": list(schema.features), "parameters": {"cpu_workers": 2, "parser_threads": 1, "block_bytes": 1024**2, "decompressed_ceiling_per_file": 8 * 1024**3, "compression_ratio_ceiling": 100}}
    started = time.perf_counter()
    for file in lock["files"]:
        if args.source == "obd_men" and file["path"].endswith("item_context.csv"):
            # Mapping is validated in the R4 clock/item gate, not parsed as event data.
            continue
        path = runtime / "data/raw" / args.source / file["path"]
        entry = {"path": str(path), "rows_seen": 0, "rows_valid": 0, "quarantined": 0, "reasons": {}, "label_sums": {}, "partitions": [], "min_timestamp": None, "max_timestamp": None}
        report["files"].append(entry)
        try:
            actual = digest(path)
            if file["expected_sha256"] and actual != file["expected_sha256"]:
                raise ValueError("Source hash mismatch before conversion")
            entry["source_sha256"] = actual
            for index, (table, bounded) in enumerate(open_batches(path, schema)):
                if min(shutil.disk_usage(runtime).free, shutil.disk_usage(ROOT).free) < 21 * 1024**3:
                    raise ValueError("Runtime/backing reserve reached")
                valid, reasons = valid_rows(table, schema)
                good = table.filter(valid)
                bad = table.filter(pc.invert(valid))
                entry["rows_seen"] += len(table)
                entry["rows_valid"] += len(good)
                entry["quarantined"] += len(bad)
                for key, count in reasons.items():
                    entry["reasons"][key] = entry["reasons"].get(key, 0) + count
                for key in schema.binary:
                    entry["label_sums"][key] = entry["label_sums"].get(key, 0) + (pc.sum(good[key]).as_py() or 0)
                if schema.evidence_domain == "R1" and len(good):
                    low = pc.min(good["timestamp"]).as_py()
                    high = pc.max(good["timestamp"]).as_py()
                    if entry["max_timestamp"] is not None and low < entry["max_timestamp"]:
                        raise ValueError("R1 sorted clock violated")
                    entry["min_timestamp"] = low if entry["min_timestamp"] is None else min(low, entry["min_timestamp"])
                    entry["max_timestamp"] = high
                part = run / "parquet" / file["path"].replace("/", "_") / f"part_{index:06d}.parquet"
                part.parent.mkdir(parents=True, exist_ok=True)
                pq.write_table(good, part, compression="zstd", row_group_size=8192)
                entry["partitions"].append({"path": str(part), "rows": len(good), "sha256": digest(part)})
                if len(bad):
                    quarantine = run / "quarantine" / part.parent.name
                    quarantine.mkdir(parents=True, exist_ok=True)
                    pq.write_table(bad, quarantine / part.name)
                entry["decompressed_bytes"] = bounded.count
                if index % 100 == 0:
                    atomic_json(run / "admission.json", report)
                    print(json.dumps({"source": args.source, "file": file["path"], "rows": entry["rows_seen"]}), flush=True)
            entry["container_status"] = "CONTAINER_VALID_EOF_CRC"
            entry["schema_status"] = "SCHEMA_VALID_WITH_QUARANTINE"
        except Exception as error:
            entry["status"] = "INVALID"
            entry["error"] = {"type": type(error).__name__, "message": str(error)[:500]}
            report["status"] = "INVALID"
            break
    if report["status"] != "INVALID":
        report.update(status="CONTAINER_SCHEMA_VALID_PENDING_CLOCK_LINEAGE", container_valid=True, schema_valid=True)
    report["wall_seconds"] = time.perf_counter() - started
    atomic_json(run / "admission.json", report)
    export = ROOT / "reports/data" / (run.name + ".json")
    atomic_json(export, report)
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a") as stream:
        stream.write(f"\n## Source conversion {run.name}\n\nCommand: `{sys.executable} tools/admit_source.py {args.source}`; status {report['status']}; wall {report['wall_seconds']:.3f}s; evidence `{export}`. Clock/lineage admission remains separate.\n")
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0 if report["status"] != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
