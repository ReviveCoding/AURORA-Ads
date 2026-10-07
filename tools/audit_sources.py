#!/usr/bin/env python3
"""Bounded full-source EDA/clock/item mapping; unknown prior exposure stays explicit."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb
from aurora.artifacts import atomic_json, digest


def main() -> int:
    runtime = Path.home() / ".local/share/aurora-ads"
    directory = runtime / "runs" / f"source_audit_{time.time_ns()}"
    directory.mkdir()
    connection = duckdb.connect()
    connection.execute("SET threads=2")
    connection.execute("SET memory_limit='256MB'")
    connection.execute("SET TimeZone='UTC'")
    connection.execute("SET temp_directory=?", [str(directory / "spill")])
    report = {"sources": [], "wall_seconds": None, "prior_exposure_discovery": "Known previous project exposure per design; no matching named project directories found in Downloads. Old split ledgers unresolved. Treat every public-source study as replication, never virgin external confirmation.", "scientific_claims": "NONE; source description/admission only"}
    started = time.perf_counter()
    for source in ("criteo_uplift", "criteo_attribution", "obd_men"):
        admission = sorted((ROOT / "reports/data").glob(f"admit_{source}_*.json"))[-1]
        data = json.loads(admission.read_text())
        item = {"source": source, "admission_artifact": str(admission), "admission_sha256": digest(admission), "clock_status": "PENDING", "prior_exposure_status": "UNRESOLVED_LEDGER_REPLICATION_ONLY", "analysis_admitted": False}
        report["sources"].append(item)
        try:
            if not data["container_valid"] or not data["schema_valid"]:
                raise ValueError("Container/schema not valid")
            files = [part["path"] for file in data["files"] for part in file["partitions"]]
            connection.read_parquet(files).create_view("events", replace=True)
            if source == "criteo_uplift":
                features = ",".join(f"f{i}" for i in range(12))
                # Exact profiles exceed the bounded memory envelope in one
                # aggregation. Partition predicates preserve exact tuple identity;
                # hash collisions only co-locate profiles, never merge them.
                row = connection.execute("SELECT COUNT(*),SUM(treatment),SUM(visit),SUM(conversion) FROM events").fetchone()
                distinct = 0
                for bucket in range(64):
                    distinct += connection.execute(f"SELECT COUNT(DISTINCT ({features})) FROM events WHERE hash({features})%64=?", [bucket]).fetchone()[0]
                    if bucket % 8 == 0:
                        print(json.dumps({"source": source, "profile_bucket": bucket}), flush=True)
                row = (*row, distinct)
                item.update(rows=row[0], treatment_count=row[1], visits=row[2], conversions=row[3], distinct_feature_profiles=row[4], duplicate_feature_profiles=row[0] - row[4], unit="released row; exact-profile clusters for splits", clock_status="VALID_CROSS_SECTIONAL_NO_TIMELINE", clock_unit="NOT_APPLICABLE", propensity_status="released_sample_assignment_propensity_must_be_estimated_or_documented; original platform allocation not recovered", permitted_features=[f"f{i}" for i in range(12)], forbidden_features=["treatment", "exposure", "visit", "conversion"])
            elif source == "criteo_attribution":
                row = connection.execute("SELECT COUNT(*),MIN(timestamp),MAX(timestamp),SUM(click),SUM(conversion),COUNT(DISTINCT uid),COUNT(DISTINCT campaign),COUNT(DISTINCT conversion_id) FILTER(WHERE conversion=1 AND conversion_id>=0),COUNT(*) FILTER(WHERE conversion=1 AND conversion_timestamp<timestamp) FROM events").fetchone()
                item.update(rows=row[0], min_origin=row[1], max_origin=row[2], clicks=row[3], impression_conversion_credits=row[4], unique_users=row[5], campaigns=row[6], unique_conversion_ids=row[7], invalid_outcome_order=row[8], clock_status="VALID_NATIVE_ORDER_ONLY" if row[8] == 0 else "INVALID", clock_unit="native source timestamp; calendar unit not asserted", cost_unit="transformed source cost; never actual currency", permitted_features=["campaign"] + [f"cat{i}" for i in range(1, 10)], duplicate_conversion_credit_warning="conversion may be credited to multiple impressions; unique conversion ledger required for descriptive attribution")
            else:
                item["loggers"] = []
                for file in data["files"]:
                    logger = "random" if "/random/" in file["path"] else "bts"
                    connection.read_parquet([part["path"] for part in file["partitions"]]).create_view("logger_events", replace=True)
                    context_path = runtime / f"data/raw/obd_men/{logger}/men/item_context.csv"
                    connection.read_csv(str(context_path), header=True).create_view("items", replace=True)
                    row = connection.execute("SELECT COUNT(*),MIN(TRY_CAST(timestamp AS TIMESTAMPTZ)),MAX(TRY_CAST(timestamp AS TIMESTAMPTZ)),COUNT(*) FILTER(WHERE TRY_CAST(timestamp AS TIMESTAMPTZ) IS NULL),COUNT(DISTINCT item_id),MIN(propensity_score),MAX(propensity_score),SUM(click) FROM logger_events").fetchone()
                    items = connection.execute("SELECT item_id FROM items ORDER BY item_id").fetchall()
                    unknown = connection.execute("SELECT COUNT(*) FROM logger_events e ANTI JOIN items i ON e.item_id=i.item_id").fetchone()[0]
                    positions = connection.execute("SELECT position,COUNT(*),COUNT(DISTINCT item_id),MIN(propensity_score),MAX(propensity_score) FROM logger_events GROUP BY position ORDER BY position").fetchall()
                    item["loggers"].append({"logger": logger, "rows": row[0], "min_timestamp_utc": str(row[1]), "max_timestamp_utc": str(row[2]), "invalid_clock": row[3], "observed_items": row[4], "min_propensity": row[5], "max_propensity": row[6], "clicks": row[7], "unknown_item_rows": unknown, "eligible_item_ids": [x[0] for x in items], "item_context_sha256": digest(context_path), "positions": positions})
                item["clock_status"] = "VALID_UTC_POSITION_MARGINAL" if all(x["invalid_clock"] == 0 and x["unknown_item_rows"] == 0 for x in item["loggers"]) else "INVALID"
                item["mapping_equal_between_loggers"] = item["loggers"][0]["eligible_item_ids"] == item["loggers"][1]["eligible_item_ids"]
                item["official_propensity_reference"] = "https://github.com/st-tech/zr-obp/blob/master/obp/dataset/real.py: load_raw_data / obtain_batch_bandit_feedback; position-specific action choice probability, no joint-slate inference"
                item["clock_unit"] = "UTC timestamp"
            item["status"] = "CLOCK_CAPABILITY_CHECKED_PRIOR_LEDGER_PENDING"
        except Exception as error:
            item.update(status="AUDIT_FAILED", diagnostic={"type": type(error).__name__, "message": str(error)[:400]})
        atomic_json(directory / "audit.json", report)
        print(json.dumps({"source": source, "status": item["status"]}), flush=True)
    connection.close()
    report["wall_seconds"] = time.perf_counter() - started
    atomic_json(directory / "audit.json", report)
    export = ROOT / "reports/data" / (directory.name + ".json")
    atomic_json(export, report)
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a") as stream:
        stream.write(f"\n## Source capability audit\n\nCommand `{sys.executable} tools/audit_sources.py`; wall {report['wall_seconds']:.3f}s; evidence `{export}`. Prior split lineage remains unresolved; no virgin external confirmation claim.\n")
    return 0 if all(item["status"] != "AUDIT_FAILED" for item in report["sources"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
