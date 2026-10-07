#!/usr/bin/env python3
"""Add exact saved identity pointers to final manifests without historical relabeling."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest


def main():
    out = ROOT / "reports/final"
    pointer = json.loads((ROOT / "reports/serving/CPU_COMPONENT_MEASUREMENTS.json").read_text())
    cpu_path = Path(pointer["artifact"])
    if digest(cpu_path) != pointer["sha256"]:
        raise ValueError("CPU identity changed")
    cpu = json.loads(cpu_path.read_text())
    path = out / "ENVIRONMENT_MANIFEST.json"
    value = json.loads(path.read_text())
    value["CPU_HTTP_repaired_environment"] = {"artifact": str(cpu_path), "sha256": digest(cpu_path),
        "exact_packages_json_pointer": "/protocol/current_packages", "packages": cpu["protocol"]["current_packages"],
        "repair": "sniffio==1.3.1; only project environment", "historical_ENVIRONMENT_LOCK_rewritten": False,
        "GPU_hold_cleared": False}
    atomic_json(path, value)
    path = out / "DATA_SOURCE_MANIFEST.json"
    value = json.loads(path.read_text())
    catalog = json.loads((ROOT / "config/datasets.json").read_text())
    value["declared_sources"] = [{key: row.get(key) for key in ("id", "license", "source_page", "repo_id", "prior_exposure", "prohibited_uses")} for row in catalog["datasets"]]
    value["admission_notice"] = "Actual E01/R3 immutable admission receipts supersede historical preparation availability notes; license does not authorize raw redistribution or new terms."
    atomic_json(path, value)
    path = out / "AGENT_MANIFEST.json"
    value = json.loads(path.read_text())
    value.update(model="Qwen/Qwen3-1.7B", model_revision="70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
        optional4B_revision="1cfa9a7208912126459214e8b04321603b3df60c", corpus_sha256="6a964869f299b61ea617e07c4c6d4cc9a016c3b996e46a3f45daa9dce98ab3e0",
        semantic_dependence_groups=9, semantic_evaluation="UNSCORED_BLOCKED_HARDWARE",
        prospective_power_status="UNDERPOWERED", trained_finalist=None, actual_agent_confirmation=None,
        evidence_note="Training/restart compatibility only; no trained recipe selected by loss.")
    atomic_json(path, value)
    path = out / "POLICY_MANIFEST.json"
    value = json.loads(path.read_text())
    value.update(freeze=json.loads((ROOT / "reports/policy/POLICY_CONFIRMATION_FREEZE.json").read_text()),
        confirmation=json.loads((ROOT / "reports/policy/POLICY_CONFIRMATION_RESULT.json").read_text()),
        fixed_pairs=200, comparator="static_bid0.25", candidate="MSCP_v2_eta0.01_max5.0_beta1.0",
        prior_negative_development_preserved=True, post_final_tuning=False)
    atomic_json(path, value)
    print("FINAL_MANIFEST_DETAILS_BOUND_TO_SAVED_IDENTITIES")


if __name__ == "__main__":
    main()
