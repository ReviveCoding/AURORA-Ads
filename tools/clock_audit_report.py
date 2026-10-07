#!/usr/bin/env python3
"""Hash-bound clock/leakage reporting from existing admission, not a new scan."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def main():
    started = time.perf_counter()
    study = Study(ROOT, "clock_leakage_audit_derivation")
    admission_path = ROOT / "reports/data/ANALYSIS_ADMISSION.json"
    contract_path = ROOT / "config/contract.json"
    admission = json.loads(admission_path.read_text())
    contract = json.loads(contract_path.read_text())
    identities = {str(admission_path): digest(admission_path), str(contract_path): digest(contract_path)}
    sources = {}
    for source_id in ("criteo_attribution", "criteo_uplift", "obd_men"):
        source = admission["sources"][source_id]
        if not source["analysis_admitted"]:
            raise ValueError("Existing source is no longer admitted")
        for key, hash_key in (("audit_artifact", "audit_sha256"), ("prior_conversion", "prior_conversion_sha256")):
            path = Path(source[key])
            if digest(path) != source[hash_key]:
                raise ValueError("Source clock audit identity changed")
            identities[str(path)] = source[hash_key]
        sources[source_id] = {"clock": source["clock"], "evidence_domain": source["evidence_domain"],
                              "prior_exposure": source["prior_exposure"], "allowed_use": source["allowed_use"],
                              "audit_sha256": source["audit_sha256"]}
    r3 = contract["primary_r3"]
    expected = {"model_snapshot_day": 41, "calibrator_available_day": 54,
                "training_origin_interval": [0, 41], "calibration_origin_interval": [41, 47],
                "selection_origin_interval": [54, 60], "final_origin_interval": [70, 82],
                "interval_convention": "half_open", "refit_at_freeze": False}
    if any(r3.get(key) != value for key, value in expected.items()):
        raise ValueError("Primary M41+C54 clock contract differs; do not silently reinterpret")
    for source_id in ("criteo_search", "ipinyou"):
        sources[source_id] = {"status": admission["sources"][source_id]["status"],
                              "evidence_domain": "R3" if source_id == "criteo_search" else "R5"}
    report = {"status": "DERIVED_CLOCK_LEAKAGE_REPORT_NOT_NEW_QUALIFICATION", "inputs": identities,
              "sources": sources, "primary_r3": r3, "policy_clock_contract": contract["policy"],
              "new_source_scan": False, "final_model_outcomes_loaded": 0,
              "limitations": ["Reuses existing hash-verified audits, no new independent scan",
                              "Reporting availability is not identified by R1 occurrence ordering",
                              "R3 source is blocked; no empirical M41+C54 result inferred",
                              "Current scientific-control chronology is not rewritten"]}
    text = f"""# Clock, lineage and leakage audit

This is a derivation from existing hash-verified source admission/audits and
active contracts, not a new scan, empirical delay result or new qualification.
No final model predictions/outcomes are loaded by this command.

## Source clocks and permitted features

R1 has a publisher-native ordered timestamp, not an asserted calendar-day unit.
Its occurrence-order audit is not a measured reporting-availability clock. The
predictive study excludes click, click position/count, conversion, conversion
timestamp/ID, attribution, conversion-dependent cpo, realized cost, UID and
unverified history features. Campaign/category features are fitted on development
only. Counting distinct conversion IDs does not complete duplicate-credit or
attribution-path qualification; the separate source-derived attribution scan is
still pending. No identities are joined across unrelated Criteo sources.

R2 is cross-sectional. Treatment-derived exposure, visit and conversion are not
pretreatment inputs; no timestamps are invented. Exact feature-profile grouping
prevents exact-tuple overlap, not all person-level dependence. Released conditional
propensity estimates do not recover the undocumented original platform assignment
or undo nonuniform release subsampling.

R4 preserves native UTC chronology. The fixed-policy OPE uses one predeclared
position and marginal item propensities, not a fabricated joint-slate probability.
Reward-model fitting, target selection and the two final UTC days are separate.
Two final-day dependence clusters remain UNDERPOWERED. This does not certify an
adaptive budget controller or cross-logger population transport.

## Unexecuted empirical delay contract

R3 remains source-blocked, not replaced by synthetic observations. If admitted,
M41 trains on[0,41), mature-only targets require origin+7<=41, C54 uses[41,47)
available by54, selection uses[54,60) available by67, and freeze is at70. Final
origins[70,82) mature by89. Half-open boundaries and M41+C54 stay fixed; no day70
refit with an old calibrator. Occurrence and availability remain distinct; the
declared availability assumption is `{r3['received_at_assumption']}` because
publisher reporting lag is unavailable. These are contracts, not observed results.

## Synthetic policy clocks and information boundary

The S1 decision horizon is14 days plus7-day occurrence maturation, with the
explicit reporting-lag flush where required. Rewards update only when the whole
origin interval is mature and recorded outcomes are available. Receipt-time bins
are not origin-time labels; pending estimates never become pseudo-observed reward.
The evaluator alone sees no-ad purchases, mechanism/fault labels and actual market
thresholds before bids. Public callbacks see only admitted contemporaneous state
and fully mature observed rows. The original completed constant-bid sweep and its
correction supplement are separate from the prospective bidder/25-state closure.
New callbacks/models are not yet empirical qualification merely because fixtures
pass. Age0 nowcast usesF(0)=0, not the[0,1) bin's cumulativeF(1).

## Split and prior-exposure limits

R1/R2/R4 retain conservative whole-release prior exposure and benchmark-replication
status; no virgin external holdout is claimed. The agent's immutable taxonomy
keeps complete semantic dependence groups split-owned. Its nine final groups are
not multiplied by templates/seeds. Final-agent outcomes remain unscored at this
derivation. Existing post-aggregate publication controls are not retroactively
described as pre-confirmation controls. Schema refusal and deliberately forbidden
field fixtures are not substitutes for an empirical trained leaky comparator.

Machine-readable derivation: `{study.name}.json`. Input SHA256 identities are in
that artifact; raw/partition lineage remains in the existing admission manifests.
No restricted raw/source-derived records are exported by this report.
"""
    destination = ROOT / "reports/analysis" / study.name
    destination.mkdir(parents=True)
    document = destination / "CLOCK_LEAKAGE_AUDIT.md"
    document.write_text(text, encoding="utf-8")
    if any(digest(Path(path)) != sha for path, sha in identities.items()):
        raise ValueError("Audit inputs changed during reporting")
    report["document"] = {"path": str(document), "sha256": digest(document)}
    report["wall_seconds"] = time.perf_counter() - started
    artifact = ROOT / "reports/analysis" / (study.name + ".json")
    atomic_json(study.directory / "result.json", report)
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/analysis/CLOCK_LEAKAGE_AUDIT.json",
                {"artifact": str(artifact), "sha256": digest(artifact), "status": report["status"]})
    print(json.dumps({"artifact": str(artifact), "status": report["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
