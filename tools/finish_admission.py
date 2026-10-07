#!/usr/bin/env python3
"""Final source gates; conservatively exposed benchmark replication only."""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb
import numpy as np
import pyarrow.parquet as pq
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main() -> int:
    study = Study(ROOT, "e01_analysis_admission")
    audit_path = sorted((ROOT / "reports/data").glob("source_audit_*.json"))[-1]
    audits = {item["source"]: item for item in json.loads(audit_path.read_text())["sources"]}
    config = json.loads((ROOT / "config/datasets.json").read_text())
    connection = duckdb.connect()
    connection.execute("SET threads=2")
    connection.execute("SET memory_limit='256MB'")
    connection.execute("SET TimeZone='UTC'")
    connection.execute("SET preserve_insertion_order=false")
    connection.execute("SET temp_directory=?", [str(study.directory / "spill")])
    report = {"sources": {}, "dataset_contract_sha256": digest(ROOT / "config/datasets.json"), "exposure_resolution_sha256": digest(ROOT / "reports/design/SPEC_AMENDMENT.md"), "scope": "public-benchmark replication only; entire release potentially prior-exposed; no old metrics/weights reused"}
    start = time.perf_counter()
    capabilities = {"R3": False, "R5": False}
    for source, domain in (("criteo_attribution", "R1"), ("criteo_uplift", "R2"), ("obd_men", "R4")):
        prior_path = sorted((ROOT / "reports/data").glob(f"admit_{source}_*.json"))[-1]
        prior = json.loads(prior_path.read_text())
        item = {"source_id": source, "evidence_domain": domain, "analysis_admitted": False, "prior_conversion": str(prior_path), "prior_conversion_sha256": digest(prior_path), "audit_artifact": str(audit_path), "audit_sha256": digest(audit_path), "prior_exposure": "CONSERVATIVE_FULL_RELEASE_EXPOSURE", "allowed_use": "benchmark replication only", "source_files": [], "partition_paths": []}
        report["sources"][source] = item
        try:
            if not prior["container_valid"] or not prior["schema_valid"] or not audits[source]["clock_status"].startswith("VALID"):
                raise ValueError("Container/schema/clock gate not valid")
            spec = next(value for value in config["datasets"] if value["id"] == source)
            item["license"] = spec["license"]
            item["publisher_identity"] = prior["identity"]
            item["acquisition_acknowledgment"] = "Explicit separate implementation prompt; downloader license acknowledgments recorded in runtime acquisition ledger"
            previous_time = None
            for file in prior["files"]:
                raw = Path(file["path"])
                if digest(raw) != file["source_sha256"]:
                    raise ValueError("Raw source changed")
                item["source_files"].append({"path": str(raw), "sha256": file["source_sha256"]})
                for partition in file["partitions"]:
                    path = Path(partition["path"])
                    if digest(path) != partition["sha256"]:
                        raise ValueError("Converted partition changed")
                    item["partition_paths"].append(str(path))
                    if domain == "R1":
                        times = pq.read_table(path, columns=["timestamp"])["timestamp"].to_numpy()
                        if np.any(np.diff(times) < 0) or (len(times) and previous_time is not None and times[0] < previous_time):
                            raise ValueError("Native origin order violated")
                        if len(times):
                            previous_time = times[-1]
            connection.read_parquet(item["partition_paths"]).create_view("events", replace=True)
            columns = connection.execute("DESCRIBE events").fetchall()
            missing = {}
            cardinality = {}
            for name, dtype, *_ in columns:
                escaped = '"' + name.replace('"', '""') + '"'
                query = f"SELECT COUNT(*) FILTER(WHERE {escaped} IS NULL),COUNT(*) FILTER(WHERE CAST({escaped} AS VARCHAR) IN ('-1','-1.0')),APPROX_COUNT_DISTINCT({escaped}) FROM events"
                null, sentinel, distinct = connection.execute(query).fetchone()
                missing[name] = {"null_rows": null, "minus_one_sentinel_rows": sentinel, "interpretation": "source-specific missing sentinel only; outcome-free feature preprocessing fits on training"}
                cardinality[name] = distinct
            item.update(missingness=missing, approximate_cardinality=cardinality, cardinality_method="DuckDB approximate_count_distinct, descriptive only", rows=connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
            if domain == "R1":
                names = ','.join('"' + row[0].replace('"', '""') + '"' for row in columns)
                duplicates = 0
                for bucket in range(64):
                    if min(shutil.disk_usage(study.runtime).free, shutil.disk_usage(ROOT).free) < 21 * 1024**3:
                        raise ValueError("Storage reserve before duplicate audit")
                    count, unique = connection.execute(f"SELECT COUNT(*),COUNT(DISTINCT ({names})) FROM events WHERE hash(uid,campaign,timestamp)%64=?", [bucket]).fetchone()
                    duplicates += count - unique
                item["exact_duplicate_full_records"] = duplicates
                item["duplicate_handling"] = "retained; no unique impression ID proves repeats are logging duplicates. Source-specific sensitivity required"
                item["clock"] = "native ordered timestamp; no calendar-unit assertion or measured label-arrival clock"
            elif domain == "R2":
                item["exact_duplicate_feature_profiles"] = audits[source]["duplicate_feature_profiles"]
                item["grouping_rule"] = "all identical pretreatment f0-f11 tuples share internal split and inference cluster; no claim they identify people"
                item["clock"] = "cross-sectional assignment benchmark, no timeline invented"
            else:
                item["clock"] = "native UTC timestamp, one predeclared position only, marginal propensities"
                item["positions"] = [1, 2, 3]
                item["eligible_item_ids"] = audits[source]["loggers"][0]["eligible_item_ids"]
                item["primary_position"] = 1
                item["random_logger_uniform_probability"] = 1 / len(item["eligible_item_ids"])
                if not audits[source]["mapping_equal_between_loggers"]:
                    raise ValueError("Item ID mapping mismatch")
                illegal = connection.execute("SELECT COUNT(*) FROM events WHERE item_id != trunc(item_id) OR position NOT IN (1,2,3)").fetchone()[0]
                if illegal:
                    raise ValueError("Invalid action/position mapping")
            item["analysis_admitted"] = True
            item["status"] = "ANALYSIS_ADMITTED_REPLICATION_ONLY"
            capabilities[domain] = True
            capabilities[domain + "_ANALYSIS_ADMITTED"] = True
        except Exception as error:
            item.update(status="BLOCKED_SOURCE", diagnostic={"type": type(error).__name__, "message": str(error)[:500]})
            capabilities[domain] = False
        print(json.dumps({"source": source, "status": item["status"]}), flush=True)
        atomic_json(study.directory / "admission.json", report)
    report["sources"]["criteo_search"] = {"analysis_admitted": False, "status": "BLOCKED_SOURCE", "reason": "Configured700MB ceiling below official2,002,864,638-byte object; zero payload bytes transferred", "artifact": "reports/data/R3_BLOCKED_SOURCE.json"}
    report["sources"]["ipinyou"] = {"analysis_admitted": False, "status": "BLOCKED_SOURCE", "reason": "Manual noncommercial source terms not authorized; optional extended track"}
    report["wall_seconds"] = time.perf_counter() - start
    connection.close()
    atomic_json(ROOT / "reports/data/ANALYSIS_ADMISSION.json", report)
    export = study.finish("E01", report, "data", science="NOT_RUN", capabilities=capabilities | {"admitted_sources": any(capabilities.values())})
    print(export)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
