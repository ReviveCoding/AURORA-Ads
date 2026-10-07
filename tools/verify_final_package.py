#!/usr/bin/env python3
"""Independent saved-file/JSON-pointer verification; no fitting or rescoring."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.final_evidence import final_reporting_gate
from aurora.studies import Study
from serving_study import active_project_compute

REQUIRED = ("FINAL_TECHNICAL_REPORT.md", "EXECUTIVE_SUMMARY.md", "RESULTS_MATRIX.csv", "CLAIM_EVIDENCE_LEDGER.csv",
            "RESUME_EVIDENCE.md", "INTERVIEW_GUIDE.md", "FINAL_STATUS.json", "FINAL_METRICS.json",
            "LIMITATIONS_THREATS_TO_VALIDITY.md", "ENVIRONMENT_MANIFEST.json", "DATA_SOURCE_MANIFEST.json",
            "MODEL_MANIFEST.json", "POLICY_MANIFEST.json", "AGENT_MANIFEST.json", "SERVING_MANIFEST.json",
            "REPRODUCIBILITY_MANIFEST.json", "REQUIREMENT_COVERAGE.md", "REPORT_FAMILY_INDEX.md",
            "SERVING_PERFORMANCE_RECOVERY_REPORT.md", "SOURCE_DATA_CAPABILITY_REPORT.md", "CSV_AUTHORING_MANIFEST.json", "figures/POLICY_CONFIRMATION.svg")


def locate(value, location):
    for token in location.strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def flattened(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def verify_csv(path, expected, identity):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames
        rows = list(reader)
    if len(rows) != len(expected) or len({row[identity] for row in rows}) != len(rows):
        raise ValueError("Missing/duplicated CSV records")
    for saved, original in zip(rows, expected, strict=True):
        for key in headers:
            value = original.get(key)
            if isinstance(value, (float, int)) and not isinstance(value, bool):
                if not saved[key] or float(saved[key]) != value:
                    raise ValueError("CSV numeric mismatch: " + key)
            elif saved[key] != flattened(value):
                raise ValueError("CSV field mismatch: " + key)
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    study = Study(ROOT, "e16_independent_saved_package_verification")
    state = study.ledger.read()
    final_reporting_gate(state, active_owned_compute=active_project_compute())
    out = ROOT / "reports/final"
    for name in REQUIRED:
        path = out / name
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError("Required final artifact missing: " + name)
    metrics = json.loads((out / "FINAL_METRICS.json").read_text())
    counts = {"results": verify_csv(out / "RESULTS_MATRIX.csv", metrics["records"], "result_id"),
              "claims": verify_csv(out / "CLAIM_EVIDENCE_LEDGER.csv", metrics["claims"], "claim_id")}
    verified_sources = {}
    for row in metrics["records"]:
        raw = row["artifact"]
        path = Path(raw) if raw.startswith("/") else ROOT / raw
        if digest(path) != row["artifact_sha256"]:
            raise ValueError("CSV/report source artifact changed")
        verified_sources[str(path)] = digest(path)
        if row["record_status"] != "MEASURED":
            if any(row.get(key) is not None for key in ("estimate", "difference", "ci_lower", "ci_upper", "n_independent_units")):
                raise ValueError("Unavailable evidence filled with a measured value")
            continue
        original = locate(json.loads(path.read_text()), row["artifact_location"])
        if isinstance(original, dict):
            point = original.get("estimate", original.get("mean"))
        else:
            point = original
        if point != row["estimate"]:
            raise ValueError("Saved scalar mismatch: " + row["result_id"])
        if row["ci_lower"] is not None:
            interval = original.get("ci95", [original.get("ci_lower", original.get("lower")), original.get("ci_upper", original.get("upper"))])
            if interval != [row["ci_lower"], row["ci_upper"]]:
                raise ValueError("Saved interval mismatch")
    for path, sha in metrics["sources"].items():
        if digest(Path(path)) != sha:
            raise ValueError("Canonical/handoff evidence hash mismatch")
    authoring = json.loads((out / "CSV_AUTHORING_MANIFEST.json").read_text())
    if authoring["source_sha256"] != digest(out / "FINAL_METRICS.json"):
        raise ValueError("CSV authoring input changed")
    for output in authoring["outputs"]:
        if digest(out / output["file"]) != output["sha256"]:
            raise ValueError("Saved CSV bytes changed")
    for name in REQUIRED:
        if name.endswith("_MANIFEST.json") and name != "CSV_AUTHORING_MANIFEST.json":
            manifest = json.loads((out / name).read_text())
            for path, sha in manifest.get("evidence", manifest.get("source_artifacts", {})).items():
                if digest(Path(path)) != sha:
                    raise ValueError("Final manifest binding changed")
    status = json.loads((out / "FINAL_STATUS.json").read_text())
    for node, saved in status["nodes"].items():
        if node == "E16":
            continue
        actual = state["nodes"][node]
        if (saved["execution_status"], saved["scientific_outcome"], saved["all_artifacts"]) != (actual["execution_status"], actual["scientific_outcome"], actual["artifacts"]):
            raise ValueError("Final report disagrees with canonical node: " + node)
    if status["completion_layers"]["CORE_EMPIRICAL_COMPLETE"] or status["completion_layers"]["agent_semantic_outcomes"] != "UNSCORED":
        raise ValueError("Blocked required evidence was promoted")
    for path in out.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if not target.startswith("http") and not (path.parent / target).exists():
                raise ValueError("Broken final report evidence link: " + target)
    report = {"status": "FINAL_SAVED_FILES_VERIFIED", "counts": counts, "verified_sources": verified_sources,
              "output_sha256": {name: digest(out / name) for name in REQUIRED}, "code_sha256": digest(Path(__file__)),
              "final_predictions_rescored": False, "canonical_generation_before_commit": state["generation"],
              "limitations": ["Saved-file/meaning checks are not independent replication of empirical fitting or production validation"]}
    artifact = ROOT / "reports/analysis" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(out / "SAVED_FILE_VERIFICATION.json", {"artifact": str(artifact), "sha256": digest(artifact)})
    if args.commit:
        if state["nodes"]["E16"]["execution_status"] != "PENDING":
            raise ValueError("E16 already committed; do not duplicate closure")
        study.ledger.update("E16", "EXECUTED", artifacts=(artifact,) + tuple(out / name for name in REQUIRED if name != "FINAL_STATUS.json"),
            reason="Evidence-bounded terminal closure; blocked empirical domains retained. Final saved files independently verified, no runnable core work.")
        study.export_state()
        final = study.ledger.read()
        status.update(status="CLOSED_WITH_DOCUMENTED_EVIDENCE_LIMITS", canonical_generation=final["generation"], E16_not_yet_committed=False)
        status["nodes"]["E16"].update(execution_status="EXECUTED", scientific_outcome="NOT_RUN",
            primary_artifact={"path": str(artifact), "sha256": digest(artifact)}, all_artifacts=final["nodes"]["E16"]["artifacts"],
            blocker_reason="No remaining runnable core action; required empirical domains remain blocked, not fully validated")
        atomic_json(out / "FINAL_STATUS.json", status)
        atomic_json(out / "FINAL_STATUS_IDENTITY.json", {"sha256": digest(out / "FINAL_STATUS.json"), "generation": final["generation"]})
    print(json.dumps({"status": report["status"], "counts": counts, "committed": args.commit, "artifact": str(artifact)}))


if __name__ == "__main__":
    main()
