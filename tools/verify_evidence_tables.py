#!/usr/bin/env python3
"""Independent saved-CSV audit; never rescore or promote scientific outcomes."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def nullable_number(text):
    if text == "":
        return None
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Nonfinite saved CSV number")
    return value


def pointer_value(document, pointer):
    value = document
    for token in pointer.split("/")[1:]:
        key = token.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="outputs/01a0f835-9bf7-71e0-b844-8e4f3bc2f7cc")
    args = parser.parse_args()
    directory = (ROOT / args.directory).resolve()
    directory.relative_to(ROOT / "outputs")
    study = Study(ROOT, "evidence_csv_saved_file_verification")
    started = time.perf_counter()
    manifest_path = directory / "evidence_tables_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["status"] != "PROGRESS_NOT_FINAL" or not manifest["no_new_final_scoring"] or not manifest["no_status_promotion"]:
        raise ValueError("Progress evidence boundary missing")
    tables = {}
    for filename, identity in manifest["outputs"].items():
        target = directory / filename
        if digest(target) != identity["sha256"]:
            raise ValueError("Authored CSV identity changed")
        with target.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        if len(rows) != identity["records"] or len(reader.fieldnames) != identity["columns"] or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV record/header shape changed")
        if any(None in row or any(value is None for value in row.values()) or row["export_status"] != "PROGRESS_NOT_FINAL" for row in rows):
            raise ValueError("CSV quoting or progress status failed")
        tables[filename] = rows
    results = tables["RESULTS_MATRIX_PROGRESS.csv"]
    ids = {row["result_id"]: row for row in results}
    if len(ids) != len(results):
        raise ValueError("Duplicate measurement identifiers")
    retained = {domain: set() for domain in ("R1", "R2", "R4")}
    snapshots = {}
    for row in results:
        artifact = (ROOT / row["artifact"]).resolve()
        artifact.relative_to(ROOT / "reports")
        if digest(artifact) != row["artifact_sha256"]:
            raise ValueError("CSV source artifact identity changed")
        source = json.loads(artifact.read_text())
        snapshots[row["artifact"]] = source
        original = pointer_value(source, row["artifact_location"])
        if row["scientific_outcome"] != source["scientific_outcome"] or row["execution_status"] != "EXECUTED" or row["record_status"] != "MEASURED":
            raise ValueError("Scientific or engineering status promoted")
        if nullable_number(row["estimate"]) != original["estimate"]:
            raise ValueError("Measurement rounding or substitution")
        interval = original.get("ci95", [original.get("ci_lower"), original.get("ci_upper")])
        if [nullable_number(row["ci_lower"]), nullable_number(row["ci_upper"])] != interval:
            raise ValueError("Interval changed or missing converted to zero")
        expected_target = "UNAVAILABLE" if interval[0] is None else "estimate"
        if row["interval_target"] != expected_target:
            raise ValueError("An absolute value interval was relabeled as a paired contrast")
        if row["artifact_location"].startswith("/records/"):
            for key in ("candidate", "baseline", "metric", "unit", "horizon", "population", "independent_unit", "uncertainty_method"):
                if row[key] != original[key]:
                    raise ValueError("Original record meaning changed")
            if nullable_number(row["difference"]) != original["difference"]:
                raise ValueError("Missing/zero/contrast distinction lost")
            retained[row["evidence_domain"]].add(int(row["artifact_location"].split("/")[-1]))
    for domain, indexes in retained.items():
        source = next(source for source in snapshots.values() if source["records"][0]["evidence_domain"] == domain)
        if indexes != set(range(len(source["records"]))):
            raise ValueError("An unfavorable original record was dropped")
    claims = tables["CLAIM_EVIDENCE_PROGRESS.csv"]
    for row in claims:
        if row["result_id"]:
            result = ids[row["result_id"]]
            for key in ("estimate", "ci_lower", "ci_upper", "interval_target", "artifact", "artifact_sha256", "artifact_location", "evidence_class", "unit", "horizon", "n_independent_units", "independent_unit"):
                if row[key] != result[key]:
                    raise ValueError("Claim does not match its exact measurement")
            if row["claim_status"] != result["scientific_outcome"]:
                raise ValueError("Unsupported scientific claim promotion")
        elif row["evidence_class"] != "PROSPECTIVE_DESIGN_NOT_MODEL_OUTCOME" or row["estimate"] != "" or row["claim_status"] != "UNDERPOWERED" or int(row["n_independent_units"]) != 9:
            raise ValueError("Planning assumptions became measured model outcomes")
    report = {"status": "SAVED_PROGRESS_CSV_VERIFIED_NOT_E16_COMPLETE", "passed": True,
              "manifest": {"path": str(manifest_path), "sha256": digest(manifest_path)},
              "result_rows": len(results), "claim_rows": len(claims),
              "retained_source_record_counts": {key: len(value) for key, value in retained.items()},
              "no_rescoring": True, "source_snapshot_scope": "Existing aggregate results only, not raw/final prediction arrays",
              "wall_seconds": time.perf_counter() - started}
    atomic_json(study.directory / "source_aggregate_snapshots.json", snapshots)
    report["immutable_aggregate_snapshot"] = {"path": str(study.directory / "source_aggregate_snapshots.json"), "sha256": digest(study.directory / "source_aggregate_snapshots.json")}
    atomic_json(study.directory / "result.json", report)
    artifact = ROOT / "reports/analysis" / (study.name + ".json")
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/analysis/PROGRESS_CSV_VERIFICATION.json", {"artifact": str(artifact), "sha256": digest(artifact), "passed": True})
    print(json.dumps({"artifact": str(artifact), "passed": True, "rows": len(results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
