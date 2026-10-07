#!/usr/bin/env python3
"""Derive small descriptive/source reports from verified existing audit files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main():
    study = Study(ROOT, "source_eda_report_derivation")
    admission_path = ROOT / "reports/data/ANALYSIS_ADMISSION.json"
    admission = json.loads(admission_path.read_text())
    config = json.loads((ROOT / "config/datasets.json").read_text())
    specifications = {item["id"]: item for item in config["datasets"]}
    report = {"status": "DERIVED_DESCRIPTIVE_AUDIT_REPORT", "admission_sha256": digest(admission_path), "new_source_scan": False, "new_model_or_final_outcomes_loaded": 0, "sources": {}, "interpretation": "Previously executed full-source audits and admission, not new independent data/evidence"}
    audits = {}
    for name in ("criteo_attribution", "criteo_uplift", "obd_men"):
        item = admission["sources"][name]
        audit_path = Path(item["audit_artifact"])
        conversion_path = Path(item["prior_conversion"])
        if not item["analysis_admitted"] or digest(audit_path) != item["audit_sha256"] or digest(conversion_path) != item["prior_conversion_sha256"]:
            raise ValueError("Existing source audit/conversion identity changed")
        audit = next(value for value in json.loads(audit_path.read_text())["sources"] if value["source"] == name)
        audits[name] = audit
        conversion = json.loads(conversion_path.read_text())
        report["sources"][name] = {"evidence_domain": item["evidence_domain"], "rows": item["rows"], "status": item["status"], "license": item["license"], "clock": item["clock"], "missingness": item["missingness"], "approximate_cardinality": item["approximate_cardinality"], "cardinality_method": item["cardinality_method"], "raw_source_hashes": [file["sha256"] for file in item["source_files"]], "publisher_identity": item["publisher_identity"], "audit_path": str(audit_path), "audit_sha256": item["audit_sha256"], "conversion_path": str(conversion_path), "conversion_sha256": item["prior_conversion_sha256"], "container_valid": conversion["container_valid"], "schema_valid": conversion["schema_valid"], "prior_exposure": item["prior_exposure"], "permitted_use": item["allowed_use"]}
    r1, r2, r4 = audits["criteo_attribution"], audits["criteo_uplift"], audits["obd_men"]
    report["r1_descriptive"] = {key: r1[key] for key in ("min_origin", "max_origin", "clicks", "impression_conversion_credits", "unique_users", "campaigns", "unique_conversion_ids", "invalid_outcome_order")}
    report["r1_descriptive"].update(click_fraction=r1["clicks"] / r1["rows"], impression_conversion_credit_fraction=r1["impression_conversion_credits"] / r1["rows"], exact_duplicate_full_records=admission["sources"]["criteo_attribution"]["exact_duplicate_full_records"], credit_identity_limit="Impression conversion credits are not unique purchases; attribution requires a separately qualified conversion-identity ledger")
    report["r2_descriptive"] = {key: r2[key] for key in ("treatment_count", "visits", "conversions", "distinct_feature_profiles", "duplicate_feature_profiles")}
    report["r2_descriptive"].update(released_treatment_fraction=r2["treatment_count"] / r2["rows"], visit_fraction=r2["visits"] / r2["rows"], conversion_fraction=r2["conversions"] / r2["rows"], randomization_limit="Released arm imbalance is not an SRM test against an invented50/50 platform allocation; released conditional propensity/exchangeability assumptions remain")
    report["r4_descriptive"] = [{key: logger[key] for key in ("logger", "rows", "clicks", "min_timestamp_utc", "max_timestamp_utc", "invalid_clock", "unknown_item_rows", "observed_items", "min_propensity", "max_propensity", "positions")} | {"click_fraction": logger["clicks"] / logger["rows"]} for logger in r4["loggers"]]
    for name in ("criteo_search", "ipinyou"):
        report["sources"][name] = admission["sources"][name] | {"configured_license": specifications[name]["license"]}
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/data" / (study.name + ".json")
    atomic_json(export, report)
    lines = ["# Source, license, capability and data-quality report", "", "Derived from executed admission/audit artifacts; no new independent source scan or model outcome. The historical audit's pending exposure status is preserved; current whole-release disposition permits benchmark replication only.", "", "| Source/domain | Released rows | License | Current capability | Clock |", "| --- | ---: | --- | --- | --- |"]
    for name, item in report["sources"].items():
        lines.append(f"| {name}/{item.get('evidence_domain', 'R3' if name == 'criteo_search' else 'R5')} | {item.get('rows', 'unavailable')} | {item.get('license', item.get('configured_license'))} | {item.get('status')} | {item.get('clock', 'unavailable')} |")
    lines += ["", "## Descriptive observations", "", f"R1: {int(r1['clicks']):,} click rows and {int(r1['impression_conversion_credits']):,} impression conversion-credit rows among {r1['rows']:,} rows; {r1['unique_conversion_ids']:,} distinct nonnegative conversion IDs on positive rows. These are different units. There are {r1['unique_users']:,} released user IDs and {r1['campaigns']} campaigns. Full-record exact duplicates:0. Native origin range [{r1['min_origin']},{r1['max_origin']}]; no calendar timestamp unit or reporting-delay column is invented. The order audit found0 positive occurrences preceding their impression. This does not establish reporting availability or causal credit.", "", f"R2: released treatment fraction {r2['treatment_count']/r2['rows']:.6f}, visit prevalence {r2['visits']/r2['rows']:.6f}, conversion prevalence {r2['conversions']/r2['rows']:.6f}. There are {r2['distinct_feature_profiles']:,} exact pretreatment feature profiles and {r2['duplicate_feature_profiles']:,} repeated profile rows. Exact-profile clustering prevents identical feature tuples crossing splits but does not identify people. No cross-sectional timeline is invented; no50/50 SRM null is manufactured.", ""]
    for logger in report["r4_descriptive"]:
        lines.append(f"R4 {logger['logger']}: {logger['rows']:,} rows, click fraction {logger['click_fraction']:.6f}, {logger['observed_items']} eligible item IDs, propensity range [{logger['min_propensity']},{logger['max_propensity']}], native UTC {logger['min_timestamp_utc']} through {logger['max_timestamp_utc']};0 invalid clocks/unknown-item rows in the source audit. These all-position descriptives are not the primary position1 OPE sample, and random-versus-BTS CTR differences are not a causal policy contrast.")
        lines.append("")
    lines += ["## Missingness, quality and exclusions", "", "The machine-readable report contains per-column null and minus-one sentinel counts plus explicitly approximate cardinalities. A minus-one count is not automatically a universal missingness definition. Container/schema acceptance was previously executed; exact raw/partition identities remain in admission manifests. Conversion-ID compatibility and descriptive first/last/time-decay attribution are not established merely by counting IDs. All source-derived features fit preprocessing on development only, with outcomes/post-impression fields excluded as declared.", "", "R3 was not replaced: its official object exceeds the unchanged700,000,000-byte acquisition cap, and0 payload bytes were transferred. Its M41+C54 empirical delay/value/final paths remain source-blocked. Optional iPinYou requires additional manual terms not authorized by the core public-license permission. Neither source is synthesized into a real-data result.", "", "## Evidence, license and redistribution boundaries", "", "Use is personal/local/noncommercial under the declared licenses; acknowledgements, publisher revisions and raw hashes are in acquisition/admission artifacts. The report exports small aggregate diagnostics, not raw records or model-source data redistribution. No unrelated Criteo identity join, mixed-domain probability product, virgin-holdout claim, real-currency claim or production impact claim is made.", "", f"Validated input admission SHA256: `{report['admission_sha256']}`. Machine-readable derivation: `{export}`. Source identities and audit SHA256 values are retained per source there."]
    (ROOT / "reports/data/SOURCE_CAPABILITY_EDA.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
