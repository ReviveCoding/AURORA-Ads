#!/usr/bin/env python3
"""Full released-ID compatibility audit and descriptive credited-touch allocation."""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.attribution import ALLOCATION_SQL
from aurora.resources import storage_admission
from aurora.studies import Study


def main():
    import duckdb
    study = Study(ROOT, "r1_descriptive_attribution")
    started = time.perf_counter()
    report = {"status": "RUNNING", "evidence_domain": "R1_DESCRIPTIVE_BENCHMARK_REPLICATION", "predictive_final_rescored": False, "incrementality_ground_truth": False, "limitations": ["Allocation among released positive credited rows, not a reconstructed all-exposure purchase path", "Released conversion IDs are not independently verified purchases", "Native timestamps only; half-life is not asserted in seconds or calendar days", "No currency/cpo or causal conversion value", "Previously exposed public release; no virgin confirmation"]}
    try:
        source = study.source("criteo_attribution")
        conversion_path = Path(source["prior_conversion"])
        if digest(conversion_path) != source["prior_conversion_sha256"]:
            raise ValueError("Conversion manifest changed")
        converted = json.loads(conversion_path.read_text())
        parts = [part for file in converted["files"] for part in file["partitions"]]
        if sorted(part["path"] for part in parts) != sorted(source["partition_paths"]):
            raise ValueError("Admitted partition identity differs")
        for part in parts:
            if digest(Path(part["path"])) != part["sha256"]:
                raise ValueError("Source partition changed")
        report["input_manifest_sha256"] = source["prior_conversion_sha256"]
        report["storage_admission"] = storage_admission(study.runtime, ROOT, expected_growth_bytes=1024**3, contract=json.loads((ROOT / "config/resources.json").read_text()))
        with duckdb.connect() as connection:
            connection.execute("SET threads=1; SET memory_limit='256MB'; SET max_temp_directory_size='768MB'")
            connection.execute("SET temp_directory=?", [str(study.directory / "spill")])
            connection.read_parquet(source["partition_paths"]).create_view("events")
            total, positive, unassigned, low, high = connection.execute("SELECT COUNT(*),COUNT(*) FILTER(WHERE conversion=1),COUNT(*) FILTER(WHERE conversion=1 AND (conversion_id IS NULL OR conversion_id<0)),MIN(timestamp),MAX(timestamp) FROM events").fetchone()
            if total != source["rows"] or high <= low:
                raise ValueError("Full source count/clock mismatch")
            half_life = (high - low) / 20.
            report["time_decay_protocol"] = {"half_life_native": half_life, "choice": "Observed full origin-clock span/20, fixed metadata-only rule before credit aggregation", "no_outcome_based_half_life_selection": True}
            connection.execute("CREATE TEMP TABLE identity_audit AS SELECT conversion_id,COUNT(*) AS rows,COUNT(DISTINCT uid) AS users,COUNT(DISTINCT conversion_timestamp) AS occurrences,MIN(conversion_timestamp) AS occurrence,MAX(timestamp) AS last_origin FROM events WHERE conversion=1 AND conversion_id>=0 GROUP BY conversion_id")
            unique, incompatible, incompatible_rows = connection.execute("SELECT COUNT(*),COUNT(*) FILTER(WHERE users!=1 OR occurrences!=1 OR occurrence<last_origin),COALESCE(SUM(rows) FILTER(WHERE users!=1 OR occurrences!=1 OR occurrence<last_origin),0) FROM identity_audit").fetchone()
            quarantine = study.directory / "incompatible_released_conversion_ids.parquet"
            connection.execute("COPY (SELECT * FROM identity_audit WHERE users!=1 OR occurrences!=1 OR occurrence<last_origin) TO ? (FORMAT PARQUET)", [str(quarantine)])
            connection.execute("CREATE TEMP VIEW credited AS SELECT e.* FROM events e JOIN identity_audit i USING(conversion_id) WHERE e.conversion=1 AND i.users=1 AND i.occurrences=1 AND i.occurrence>=i.last_origin")
            rows = connection.execute(ALLOCATION_SQL, [half_life]).fetchall()
            campaigns = [{"campaign": row[0], "credited_rows": row[1], "first_touch": row[2], "last_touch": row[3], "time_decay": row[4]} for row in rows]
            eligible = unique - incompatible
            for key in ("first_touch", "last_touch", "time_decay"):
                if abs(sum(row[key] for row in campaigns) - eligible) > 1e-7 * max(1, eligible):
                    raise ValueError("Credit duplication: each compatible conversion ID must allocate exactly one unit")
            if sum(row["credited_rows"] for row in campaigns) + incompatible_rows + unassigned != positive:
                raise ValueError("Source credit-row admission funnel does not reconcile")
            path_histogram = connection.execute("SELECT rows,COUNT(*) FROM identity_audit WHERE users=1 AND occurrences=1 AND occurrence>=last_origin GROUP BY rows ORDER BY rows").fetchall()
            report.update(status="DESCRIPTIVE_ATTRIBUTION_EXECUTED", passed=True, source_rows=total, positive_credit_rows=positive, nonnegative_unique_conversion_ids=unique, unassigned_positive_rows=unassigned, incompatible_conversion_ids=incompatible, incompatible_credit_rows=incompatible_rows, compatible_conversion_ids=eligible, campaign_allocations=campaigns, credited_path_length_histogram=path_histogram, quarantine={"path": str(quarantine), "sha256": digest(quarantine), "raw_source_derived_IDs_retained_only_in_runtime": True}, excluded_id_policy="Quarantine inconsistent released ID; never fabricate compound user-conversion identity", credit_conservation=True)
    except Exception as error:
        report.update(status="DESCRIPTIVE_ATTRIBUTION_FAILED", passed=False, diagnostic={"type": type(error).__name__, "message": str(error)[:1000], "traceback": traceback.format_exc()[-5000:]})
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/attribution" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    print(json.dumps({"artifact": str(artifact), "passed": report["passed"]}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
