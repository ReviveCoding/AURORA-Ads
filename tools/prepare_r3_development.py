#!/usr/bin/env python3
"""M41+C54 development cohorts only; source-natural hash sample, no final labels."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb
import numpy as np
from aurora.artifacts import atomic_json, digest
from aurora.data import SCHEMAS
from aurora.r3_targets import asof_targets
from aurora.resources import storage_admission
from aurora.studies import Study

DEVELOPMENT_WINDOWS = {"M41": (0., 41., 41.), "C54": (41., 47., 54.), "selection": (54., 60., 67.)}


def cohort_query(features: tuple[str, ...]) -> str:
    if features != SCHEMAS["criteo_search"].features:
        raise ValueError("Only frozen source-eligible fields permitted")
    codes = ",".join(f'CASE WHEN "{name}" IS NULL OR "{name}" IN (\'-1\',\'-1.0\') THEN 0 ELSE 1+hash("{name}")%1023 END AS "{name}"' for name in features)
    return (f"SELECT {codes}, Sale, time_delay_for_conversion, SalesAmountInEuro, click_timestamp, user_id "
            "FROM events WHERE click_timestamp>=? AND click_timestamp<? "
            "AND hash(user_id,click_timestamp,product_id,partner_id,41)%8=0 ORDER BY click_timestamp, user_id, product_id, partner_id")


def main() -> int:
    study = Study(ROOT, "e03_r3_M41_C54_development_cohorts")
    started = time.perf_counter()
    pointer = json.loads((ROOT / "reports/data/R3_ANALYSIS_ADMISSION.json").read_text())
    path = Path(pointer["artifact"])
    if digest(path) != pointer["sha256"]:
        raise ValueError("Source admission identity changed")
    source = json.loads(path.read_text())
    if not source["analysis_admitted"] or source["frozen_primary_model_calibrator"] != "M41+C54":
        raise ValueError("Qualified source and unchanged M41+C54 required")
    features = SCHEMAS["criteo_search"].features
    protocol = {"source_admission_sha256": pointer["sha256"], "source_sha256": source["source"]["sha256"],
                "features": list(features), "windows": DEVELOPMENT_WINDOWS,
                "horizon_days": 7, "primary_refit_at70": False, "final_outcomes_scored": 0,
                "sampling": "outcome-blind hash(user_id,click_timestamp,product_id,partner_id,41)%8=0",
                "sampling_probability": .125, "sampling_unit": "released key tuple, not verified unique person/click",
                "negative_downsampling": False, "natural_selected_cohort_prevalence": True,
                "category_encoding": "stateless DuckDB1.3 hashmod1023+1; designated missing reserved0; no learned vocabulary",
                "receipt_clock": source["receipt_clock"], "day_zero_native": source["day_zero_native"],
                "clock_scale": source["clock"]["seconds_per_native_unit"],
                "source_order_ignored": True, "argv": sys.argv, "started_at_unix": time.time(),
                "code_hashes": {relative: digest(ROOT / relative) for relative in
                    ("tools/prepare_r3_development.py", "src/aurora/r3_targets.py", "src/aurora/data.py")},
                "environment_lock_sha256": digest(ROOT / "reports/environment/ENVIRONMENT_LOCK.json"),
                "config_hashes": {path.name: digest(path) for path in (ROOT / "config").glob("*.json")},
                "storage_admission": storage_admission(study.runtime, ROOT, expected_growth_bytes=2 * 1024**3,
                    contract=json.loads((ROOT / "config/resources.json").read_text()))}
    atomic_json(study.directory / "protocol_before_cohort_queries.json", protocol)
    for partition in source["partition_manifest"]:
        if digest(Path(partition["path"])) != partition["sha256"]:
            raise ValueError("Converted source partition changed")
    connection = duckdb.connect()
    connection.execute("SET threads=1")
    connection.execute("SET memory_limit='512MB'")
    connection.execute("SET temp_directory=?", [str(study.directory / "spill")])
    connection.read_parquet(source["partition_paths"]).create_view("events")
    report = {"protocol": protocol, "cohorts": {}, "status": "DEVELOPMENT_COHORTS_ONLY", "final_outcomes_scored": 0}
    for name, (lower, upper, cutoff) in DEVELOPMENT_WINDOWS.items():
        factor, zero = protocol["clock_scale"], protocol["day_zero_native"]
        frame = connection.execute(cohort_query(features), [zero + lower * 86400 / factor, zero + upper * 86400 / factor]).fetchdf()
        if name == "M41" and not 500000 <= len(frame) <= 2000000:
            raise ValueError("Declared500k-2M development profile unavailable; do not change sample after outcomes")
        if not len(frame):
            raise ValueError("Empty frozen development window")
        origin = (frame.click_timestamp.to_numpy() - zero) * factor / 86400
        raw_delay = frame.time_delay_for_conversion.to_numpy()
        delay = np.where(raw_delay >= 0, raw_delay * factor / 86400, raw_delay)
        targets = asof_targets(origin, frame.Sale.to_numpy(), delay, frame.SalesAmountInEuro.to_numpy(), cutoff_day=cutoff)
        destination = study.directory / (name + ".npz")
        np.savez_compressed(destination, codes=frame[list(features)].to_numpy(dtype=np.int64),
            origin_days=origin, user_id=frame.user_id.fillna("-1").to_numpy(dtype=str),
            age_days=targets.age_days, event_bin=targets.observed_event_bin,
            observed_delay_days=targets.observed_delay_days, mature=targets.mature,
            within_horizon_label=targets.within_horizon_label, available_value=targets.available_value,
            valid_delay=targets.valid_delay)
        report["cohorts"][name] = {"path": str(destination), "sha256": digest(destination), "rows": len(frame),
            "mature_rows": int(targets.mature.sum()), "unknown_horizon_rows": int((~targets.valid_delay).sum()),
            "missing_mature_value_rows": int((targets.mature & ~np.isfinite(targets.available_value)).sum()),
            "observed_positive_rows_at_cutoff": int((targets.observed_event_bin >= 0).sum()),
            "cutoff_day": cutoff, "native_interval": [lower, upper], "half_open": True}
        atomic_json(study.directory / "progress.json", report)
        print(json.dumps({"cohort": name, "rows": len(frame), "final_outcomes_scored": 0}), flush=True)
        del frame
    report.update(wall_seconds=time.perf_counter() - started, finished_at_unix=time.time(),
                  limitations=["Key-hash sample clusters may repeat; row counts are not independent people",
                    "Source-derived arrays stay restricted local runtime; no redistribution",
                    "Unknown horizons and missing revenue remain missing; full-cohort bounds/sensitivity required",
                    "Development cohorts only; no model fitting or scientific hypothesis claim"])
    artifact = ROOT / "reports/data" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/data/R3_DEVELOPMENT_COHORTS.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    study.ledger.update("E03", "CHECKPOINTED", artifacts=(artifact,), reason="Source-grounded M41+C54 cohorts prepared; empirical delay/value fitting next, no final outcomes")
    study.export_state()
    print(json.dumps({"artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
