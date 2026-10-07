#!/usr/bin/env python3
"""One bounded official R3 member-to-Parquet conversion; clock admission separate."""
from __future__ import annotations

import io
import json
import shutil
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as csv
import pyarrow.parquet as pq
from aurora.artifacts import atomic_json, digest
from aurora.data import BoundedReader, R3_COLUMNS, SCHEMAS, valid_rows
from aurora.resources import storage_admission
from aurora.studies import Study


def reader_options() -> tuple:
    # Actual source has no header. Names/order are exactly the publisher README
    # and frozen23-field source schema, not inferred from values or invented.
    return (csv.ReadOptions(column_names=list(R3_COLUMNS), block_size=1024**2, use_threads=False),
            csv.ParseOptions(delimiter="\t"), csv.ConvertOptions(column_types={key: pa.string() for key in R3_COLUMNS}))


def numeric_table(batch: pa.RecordBatch) -> pa.Table:
    table = pa.Table.from_batches([batch])
    for key in (*SCHEMAS["criteo_search"].binary, *SCHEMAS["criteo_search"].numeric):
        try:
            values = pc.cast(table[key], pa.float64())
        except pa.ArrowInvalid:
            parsed = []
            for value in table[key].to_pylist():
                try:
                    parsed.append(float(value) if value is not None else None)
                except (ValueError, TypeError):
                    parsed.append(None)
            values = pa.array(parsed, type=pa.float64())
        table = table.set_column(table.schema.get_field_index(key), key, values)
    return table


def main() -> int:
    study = Study(ROOT, "r3_streaming_schema_conversion")
    started = time.perf_counter()
    report = {"status": "RUNNING", "source_id": "criteo_search", "evidence_domain": "R3",
              "analysis_admitted": False, "clock_valid": False, "schema_valid": False,
              "rows_seen": 0, "rows_valid": 0, "quarantined": 0, "reasons": {}, "partitions": [],
              "header": "ABSENT_OBSERVED; publisher README23-column order applied explicitly",
              "argv": sys.argv, "started_at_unix": time.time(), "code_sha256": digest(Path(__file__)),
              "eligible_features": list(SCHEMAS["criteo_search"].features),
              "native_clock_min": None, "native_clock_max": None, "source_sorted": True,
              "label_sums": {"Sale": 0}, "receipt_clock": "NOT_ADMITTED; reporting availability is not observed"}
    try:
        pointer = json.loads((ROOT / "reports/data/R3_CONTAINER_INVENTORY.json").read_text())
        inventory_path = Path(pointer["artifact"])
        if digest(inventory_path) != pointer["sha256"]:
            raise ValueError("Container inventory identity changed")
        inventory = json.loads(inventory_path.read_text())
        if inventory["status"] != "CONTAINER_SAFE_INVENTORY_EOF_CRC_VALID":
            raise ValueError("Complete bounded archive/CRC qualification required")
        source = Path(inventory["source"]["path"])
        if digest(source) != inventory["source"]["sha256"]:
            raise ValueError("Publisher archive identity changed")
        expected = json.loads((ROOT / "config/datasets.json").read_text())
        member_name = next(item["archive_member_expected"] for item in expected["datasets"] if item["id"] == "criteo_search")
        matches = [m for m in inventory["members"] if not m["directory"] and Path(m["name"]).name == member_name]
        if len(matches) != 1:
            raise ValueError("Exactly one publisher-declared data member required")
        member = matches[0]
        resources = json.loads((ROOT / "config/resources.json").read_text())
        report.update(source=inventory["source"], container_inventory_sha256=pointer["sha256"],
                      member=member, container_valid=True,
                      storage_admission=storage_admission(study.runtime, ROOT,
                          expected_growth_bytes=16 * 1024**3, contract=resources))
        atomic_json(study.directory / "protocol_before_conversion.json", report)
        options = reader_options()
        with tarfile.open(source, mode="r|gz") as archive:
            for item in archive:
                if item.name != member["name"]:
                    continue
                if not item.isfile() or item.size != member["bytes"]:
                    raise ValueError("Data member differs from verified inventory")
                content = archive.extractfile(item)
                assert content is not None
                bounded = BoundedReader(content, item.size)
                batches = csv.open_csv(io.BufferedReader(bounded), read_options=options[0], parse_options=options[1], convert_options=options[2])
                for index, batch in enumerate(batches):
                    if min(shutil.disk_usage(ROOT).free, shutil.disk_usage(study.runtime).free) < 21 * 1024**3:
                        raise ValueError("Dual-volume reserve approached; retain partial conversion")
                    table = numeric_table(batch)
                    valid, reasons = valid_rows(table, SCHEMAS["criteo_search"])
                    good, bad = table.filter(valid), table.filter(pc.invert(valid))
                    report["rows_seen"] += len(table)
                    report["rows_valid"] += len(good)
                    report["quarantined"] += len(bad)
                    for key, count in reasons.items():
                        report["reasons"][key] = report["reasons"].get(key, 0) + count
                    report["label_sums"]["Sale"] += pc.sum(good["Sale"]).as_py() or 0
                    if len(good):
                        low, high = pc.min(good["click_timestamp"]).as_py(), pc.max(good["click_timestamp"]).as_py()
                        if report["native_clock_max"] is not None and low < report["native_clock_max"]:
                            report["source_sorted"] = False
                        times = good["click_timestamp"].to_numpy()
                        if (times[1:] < times[:-1]).any():
                            report["source_sorted"] = False
                        report["native_clock_min"] = low if report["native_clock_min"] is None else min(low, report["native_clock_min"])
                        report["native_clock_max"] = high if report["native_clock_max"] is None else max(high, report["native_clock_max"])
                    destination = study.directory / "parquet" / f"chunk_{index // 100:03d}" / f"part_{index:06d}.parquet"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    pq.write_table(good, destination, compression="zstd", row_group_size=8192)
                    report["partitions"].append({"path": str(destination), "rows": len(good), "sha256": digest(destination)})
                    if len(bad):
                        quarantine = study.directory / "quarantine" / destination.name
                        quarantine.parent.mkdir(parents=True, exist_ok=True)
                        pq.write_table(bad, quarantine, compression="zstd")
                    if index % 100 == 0:
                        atomic_json(study.directory / "progress.json", report)
                        print(json.dumps({"partitions": len(report["partitions"]), "rows_seen": report["rows_seen"]}), flush=True)
                if bounded.count != item.size:
                    raise ValueError("Incomplete declared member conversion")
                report["converted_member_bytes"] = bounded.count
                break
        report.update(status="CONTAINER_SCHEMA_VALID_PENDING_CLOCK_LINEAGE", schema_valid=True,
                      limitations=["No clock-unit or M41+C54 admission yet", "Raw sentinels preserved, not zero-filled labels",
                        "No unique purchase/order IDs inferred; value is source attributed revenue",
                        "No downstream model or final outcomes evaluated", "No full source redistribution permitted"])
    except Exception as error:
        report.update(status="CONVERSION_INVALID", diagnostic={"type": type(error).__name__, "message": str(error)[:400]})
    report.update(wall_seconds=time.perf_counter() - started, finished_at_unix=time.time())
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/data" / (study.name + ".json")
    atomic_json(export, report)
    atomic_json(ROOT / "reports/data/R3_SCHEMA_CONVERSION.json", {"artifact": str(export), "sha256": digest(export)})
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0 if report["status"] == "CONTAINER_SCHEMA_VALID_PENDING_CLOCK_LINEAGE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
