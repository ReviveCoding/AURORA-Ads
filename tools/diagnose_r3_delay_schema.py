#!/usr/bin/env python3
"""TRAIN-only source-gate diagnosis; never changes admission or final outcomes."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main() -> int:
    study = Study(ROOT, "r3_train_delay_schema_diagnosis")
    started = time.perf_counter()
    pointer = json.loads((ROOT / "reports/data/R3_SCHEMA_CONVERSION.json").read_text())
    path = Path(pointer["artifact"])
    if digest(path) != pointer["sha256"]:
        raise ValueError("Conversion identity changed")
    conversion = json.loads(path.read_text())
    connection = duckdb.connect()
    connection.execute("SET threads=2")
    connection.execute("SET memory_limit='512MB'")
    connection.read_parquet([item["path"] for item in conversion["partitions"]]).create_view("events")
    keys = ("positive_delay_min", "positive_delay_max", "bad_nonconversion_delays",
            "missing_positive_delays", "positive_delays_beyond30days", "positive_delays_beyond7days")
    values = connection.execute("SELECT MIN(time_delay_for_conversion) FILTER(WHERE Sale=1),"
        "MAX(time_delay_for_conversion) FILTER(WHERE Sale=1),"
        "COUNT(*) FILTER(WHERE Sale=0 AND time_delay_for_conversion != -1),"
        "COUNT(*) FILTER(WHERE Sale=1 AND time_delay_for_conversion < 0),"
        "COUNT(*) FILTER(WHERE Sale=1 AND time_delay_for_conversion > 2592000),"
        "COUNT(*) FILTER(WHERE Sale=1 AND time_delay_for_conversion > 604800) "
        "FROM events WHERE click_timestamp < ?", [conversion["native_clock_min"] + 41 * 86400]).fetchone()
    report = {"scope": "M41 source quality diagnosis only", "final_model_outcomes_scored": 0,
              "conversion_sha256": pointer["sha256"], "diagnostics": dict(zip(keys, values)),
              "argv": sys.argv, "code_sha256": digest(Path(__file__)),
              "wall_seconds": time.perf_counter() - started, "no_admission_or_contract_mutation": True}
    path = ROOT / "reports/data" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(path, report)
    print(json.dumps(report | {"artifact": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
