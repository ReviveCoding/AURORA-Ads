#!/usr/bin/env python3
"""Versioned R3 clock/lineage admission; no final model outcomes are scored."""
from __future__ import annotations

import json
import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb
from aurora.artifacts import atomic_json, digest
from aurora.data import R3_COLUMNS, SCHEMAS
from aurora.r3_clock import check_delay_schema, infer_clock_scale
from aurora.studies import Study


def verified(relative: str) -> tuple[dict, dict]:
    pointer = json.loads((ROOT / relative).read_text())
    path = Path(pointer["artifact"])
    if digest(path) != pointer["sha256"]:
        raise ValueError("Source pointer identity mismatch")
    return pointer, json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    study = Study(ROOT, "e01_r3_clock_lineage_admission")
    started = time.perf_counter()
    report = {"analysis_admitted": False, "source_id": "criteo_search", "evidence_domain": "R3",
              "argv": sys.argv, "started_at_unix": time.time(), "code_sha256": digest(Path(__file__)),
              "clock_code_sha256": digest(ROOT / "src/aurora/r3_clock.py"),
              "final_model_outcomes_scored": 0, "source_label_quality_only": True}
    try:
        conversion_pointer, conversion = verified("reports/data/R3_SCHEMA_CONVERSION.json")
        inventory_pointer, inventory = verified("reports/data/R3_CONTAINER_INVENTORY.json")
        recovery_pointer, recovery = verified("reports/data/R3_RECOVERY_LATEST.json")
        if conversion["status"] != "CONTAINER_SCHEMA_VALID_PENDING_CLOCK_LINEAGE" or not conversion["schema_valid"]:
            raise ValueError("Completed container/schema conversion required")
        if conversion["container_inventory_sha256"] != inventory_pointer["sha256"] or inventory["recovery_sha256"] != recovery_pointer["sha256"]:
            raise ValueError("Acquisition/container/conversion lineage mismatch")
        documentation = next(item["documentation"] for item in inventory["members"]
                             if Path(item["name"]).name == "README.md")
        if "sample of 90 days" not in documentation or "time between click and conversion" not in documentation:
            raise ValueError("Publisher duration/delay semantics absent")
        scale = infer_clock_scale(conversion["native_clock_max"] - conversion["native_clock_min"])
        report.update(source=conversion["source"], conversion_sha256=conversion_pointer["sha256"],
                      container_sha256=inventory_pointer["sha256"], recovery_sha256=recovery_pointer["sha256"],
                      clock=scale, day_zero_native=conversion["native_clock_min"],
                      day_zero_rule="chronologically first valid source timestamp; source physically unsorted",
                      source_sorted_observed=conversion["source_sorted"],
                      publisher_sorted_claim_verified=conversion["source_sorted"],
                      publisher_documentation_sha256=__import__("hashlib").sha256(documentation.encode()).hexdigest(),
                      receipt_clock="ASSUMED occurrence availability; reporting lag not observed",
                      receipt_assumption="received_at=click_timestamp+conversion_delay; sensitivity required",
                      eligible_features=list(SCHEMAS["criteo_search"].features),
                      feature_exclusions=["nb_clicks_1week", "product_gender", "product_age_group", "user_id", "outcome fields"],
                      frozen_primary_model_calibrator="M41+C54", row_funnel={key: conversion[key] for key in ("rows_seen", "rows_valid", "quarantined", "reasons")})
        atomic_json(study.directory / "protocol_before_audit.json", report)
        paths = []
        for part in conversion["partitions"]:
            path = Path(part["path"])
            if digest(path) != part["sha256"]:
                raise ValueError("Converted partition changed")
            paths.append(str(path))
        connection = duckdb.connect()
        connection.execute(f"SET threads={args.threads}")
        connection.execute("SET memory_limit='512MB'")
        connection.execute("SET preserve_insertion_order=false")
        connection.execute("SET temp_directory=?", [str(study.directory / "spill")])
        connection.read_parquet(paths).create_view("events")
        zero, factor = report["day_zero_native"], scale["seconds_per_native_unit"]
        # Delay unit/schema check uses only M41 origins; no final calibration,
        # performance, recipes or label distributions are opened for tuning.
        delay_min, delay_max, bad_negative, missing_positive, invalid_positive = connection.execute(
            "SELECT MIN(time_delay_for_conversion) FILTER(WHERE Sale=1 AND time_delay_for_conversion>=0), "
            "MAX(time_delay_for_conversion) FILTER(WHERE Sale=1 AND time_delay_for_conversion>=0), "
            "COUNT(*) FILTER(WHERE Sale=0 AND time_delay_for_conversion != -1), "
            "COUNT(*) FILTER(WHERE Sale=1 AND time_delay_for_conversion=-1), "
            "COUNT(*) FILTER(WHERE Sale=1 AND time_delay_for_conversion<0 AND time_delay_for_conversion != -1) "
            "FROM events WHERE (click_timestamp-?)*? < 41*86400", [zero, factor]).fetchone()
        report["M41_delay_schema"] = {"min_observed": delay_min, "max_observed": delay_max,
            "invalid_nonconversion_delay_rows": bad_negative, "missing_positive_delay_rows": missing_positive,
            "invalid_positive_delay_rows": invalid_positive}
        report["unknown_horizon_label_handling"] = "Sale1/delay-1 remains unknown, never negative; exclude from point-score eligibility and report full-cohort bounds/missingness sensitivity"
        if invalid_positive:
            raise ValueError("Positive delay has a negative value other than declared missing sentinel")
        check_delay_schema(min_positive_delay=delay_min, max_positive_delay=delay_max,
                           clock_scale=factor, bad_nonconversion_delays=bad_negative)
        names = ",".join('"' + name + '"' for name in R3_COLUMNS)
        report["exact_duplicate_full_records"] = 0
        # Structural identity audit is not model scoring. Keep repeated rows;
        # unavailable order IDs cannot establish duplicate purchases.
        for bucket in range(16):
            if min(shutil.disk_usage(ROOT).free, shutil.disk_usage(study.runtime).free) < 21 * 1024**3:
                raise ValueError("Dual-volume reserve before identity audit")
            count, unique = connection.execute(f"SELECT COUNT(*),COUNT(DISTINCT ({names})) FROM events WHERE hash(user_id,click_timestamp)%16=?", [bucket]).fetchone()
            report["exact_duplicate_full_records"] += count - unique
        report["duplicate_handling"] = "retained; no unique click/order key released; exact-record sensitivity required"
        report["missingness_M41"] = {}
        for name in R3_COLUMNS:
            nulls, missing = connection.execute(f'SELECT COUNT(*) FILTER(WHERE "{name}" IS NULL),COUNT(*) FILTER(WHERE CAST("{name}" AS VARCHAR) IN (\'-1\',\'-1.0\')) FROM events WHERE (click_timestamp-?)*? < 41*86400', [zero, factor]).fetchone()
            report["missingness_M41"][name] = {"null": nulls, "minus_one_sentinel": missing}
        report["partition_paths"] = paths
        report["partition_manifest"] = conversion["partitions"]
        report.update(analysis_admitted=True, clock_valid=True, status="ANALYSIS_ADMITTED_REPLICATION_ASSUMED_RECEIPT_CLOCK",
                      license="CC-BY-NC-SA-4.0", allowed_use="personal local noncommercial benchmark replication",
                      prior_exposure="CONSERVATIVE_FULL_RELEASE_EXPOSURE",
                      limitations=["Clock seconds inferred jointly from documented duration/schema, not explicitly declared units",
                        "Physical source order contradicts README; all as-of partitions use explicit native timestamps",
                        "No observed reporting-arrival time, unique purchase IDs or causal effects",
                        "Missing conversion delay partially identifies within7-day outcome; complete-case metrics require bounds/sensitivity and cannot silently represent all clicks",
                        "Publisher object identity recorded; local SHA is not publisher cryptographic attestation",
                        "Source attributed revenue, not advertiser incrementality; no cross-source ID join"])
        connection.close()
    except Exception as error:
        report.update(status="BLOCKED_SOURCE", diagnostic={"type": type(error).__name__, "message": str(error)[:500]})
    report.update(wall_seconds=time.perf_counter() - started, finished_at_unix=time.time())
    artifact = ROOT / "reports/data" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/data/R3_ANALYSIS_ADMISSION.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    if report["analysis_admitted"]:
        admission_path = ROOT / "reports/data/ANALYSIS_ADMISSION.json"
        previous = json.loads(admission_path.read_text())
        atomic_json(study.directory / "previous_admission.json", previous)
        previous["sources"]["criteo_search"] = report
        atomic_json(admission_path, previous)
        previous_refs = tuple(Path(item["path"]) for item in study.ledger.read()["nodes"]["E01"]["artifacts"])
        study.ledger.update("E01", "EXECUTED", artifacts=(*previous_refs, artifact), capabilities={"R3": True, "R3_ANALYSIS_ADMITTED": True,
            "R3_CONTAINER_SCHEMA_VALID": True}, reason="Versioned R3-only recovery and clock/schema lineage admission; old source blocker preserved")
        study.ledger.update("E03", "CHECKPOINTED", artifacts=(artifact,), reason="R3 admitted with explicit clock assumptions; M41+C54 delay/value development next")
        study.ledger.update("E15_R3_FREEZE", "CHECKPOINTED", artifacts=(artifact,), reason="R3 acquired/admitted; development and prospective freeze remain required")
        study.ledger.update("E15_R3", "CHECKPOINTED", artifacts=(artifact,), reason="No frozen R3 confirmation executed; no final outcomes used for tuning")
        study.export_state()
    print(json.dumps({"status": report["status"], "artifact": str(artifact)}))
    return 0 if report["analysis_admitted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
