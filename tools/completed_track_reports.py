#!/usr/bin/env python3
"""Derive completed public-track reports from existing aggregates, never rescore."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study

INPUTS = {
    "R1": "reports/model/e15_r1_confirmation_1790881991684526040.json",
    "R2": "reports/causal/e04_assignment_replication_1790881140397659915.json",
    "R4": "reports/ope/e05_fixed_policy_ope_1790880719890434701.json",
    "R3": "reports/data/R3_BLOCKED_SOURCE.json",
}


def interval(row):
    return f"{row['estimate']:.9g} [{row['ci95'][0]:.9g}, {row['ci95'][1]:.9g}]"


def main():
    started = time.perf_counter()
    study = Study(ROOT, "completed_public_track_analysis")
    reports = {key: json.loads((ROOT / path).read_text()) for key, path in INPUTS.items()}
    before = {path: digest(ROOT / path) for path in INPUTS.values()}
    r1, r2, r4 = (reports[key] for key in ("R1", "R2", "R4"))
    if r1["freeze_sha256"] != digest(ROOT / "reports/model/R1_FREEZE.json") or not r1["no_reselection"] or r1["scientific_outcome"] != "NOT_ESTABLISHED" or r2["scientific_outcome"] != "NOT_ESTABLISHED" or r4["scientific_outcome"] != "UNDERPOWERED":
        raise ValueError("Frozen identity/status boundary changed; inspect before reporting")
    documents = {}
    rows = ["| Model | Log loss | Brier | PR-AUC | AUROC | Fixed-bin ECE |", "|---|---:|---:|---:|---:|---:|"]
    for name, metrics in r1["final_results"].items():
        rows.append(f"| {name} | {metrics['logloss']:.9f} | {metrics['brier']:.9f} | {metrics['pr_auc']:.6f} | {metrics['auroc']:.6f} | {metrics['fixed_bin_ece']:.6f} |")
    chosen = r1["selected_on_development"]
    conventional = r1["development_selected_conventional"]
    paired = r1["paired_logloss_vs_prior"][chosen]
    documents["MODEL_CALIBRATION_REPORT.md"] = f"""# R1 frozen model comparison and calibration

Scientific status: **NOT_ESTABLISHED**. This is internal temporal benchmark
replication on318445 selected impressions at natural prevalence, not virgin
external confirmation, calibrated economic value or incremental advertising lift.
Selection remains {chosen} versus development-selected conventional {conventional}.
No final-outcome reselection or new scoring was performed by this analysis.

{chr(10).join(rows)}

Paired chosen-minus-conventional log loss: {interval(paired['paired_vs_development_selected_conventional'])}
nats/impression,292126 source-UID clusters.20 publisher-native time-block sensitivity:
{interval(paired['conventional_time_block_sensitivity'])}. The generic estimator's
historical `n_profile_clusters` label means UID clusters here, not identified exact
feature profiles. Cross-UID campaign/time dependence is not eliminated by this CI.
Native time units have not been converted into invented calendar days.

The MLP's lower final log loss is retained in the table, not used to replace the
development-selected DCNv2. Fixed-bin ECE/reliability are secondary, not a new
calibrator-selection criterion. Model-specific training/search exposure is in the
original development artifacts; unequal finite exposure is not an equal-FLOP claim.
Features are campaign plus cat1..9; post-impression fields, UID, costs and unverified
histories are excluded. All calibrators remain their frozen fitted bytes.

Limitations: entire release conservatively potentially prior-exposed; hash sampling
does not create a virgin source. No R1×R3 probability product, unique-conversion
causal inference, transport claim or production effect. Empirical pre-final R1
label-shuffle and a trained deliberately leaky comparator are not recorded; CPU
schema/leakage fixtures are narrower evidence, not replacements for those runs.

Source result: `{INPUTS['R1']}`; SHA256 `{before[INPUTS['R1']]}`.
"""
    causal_rows = ["| Outcome /20% allocation method | DR policy value | Paired vs random (95% CI) |", "|---|---:|---|"]
    for outcome, values in r2["results"].items():
        for name, row in values["policies"]["0.2"].items():
            paired_row = row.get("paired_difference_vs_random")
            causal_rows.append(f"| {outcome}/{name} | {row['estimate']:.9g} | {interval(paired_row) if paired_row else 'reference'} |")
    documents["CAUSAL_OPE_REPORT.md"] = f"""# R2 assignment replication and R4 fixed-policy OPE

R2: **NOT_ESTABLISHED**, released-sample conditional benchmark estimates only.
The primary visit assignment DR contrast is {interval(r2['results']['visit']['assignment_DR_contrast'])},
278867 final released rows,246324 exact12-feature-profile clusters. Exact profiles
are not known people. The source's original allocation ratio is undocumented;
released assignment imbalance cannot be tested against a fabricated50/50 SRM null.
Nuisance training, policy selection and final profiles are separated; conditional
propensities are estimated, not recovered deployment randomization probabilities.

{chr(10).join(causal_rows)}

10%/40% allocation and conversion are secondary in the original artifact, not
retrospective primary replacements. The source outcome horizon is unspecified;
there is no invented calendar or individual CATE truth. Raw release contrast,
grouped calibration, overlap range and all unfavorable methods remain recorded.

R2 zero-effect and shuffled-development A/A diagnostics contain zero. Their
original executable chronology places diagnostic controls after aggregate scoring
and before publication; this report does not rewrite them as pre-scoring gates.
The deliberately leaky control is forbidden-field/label-copy detection, not a
trained leaky-model comparison. These narrow controls cannot establish causality.

R4: **UNDERPOWERED**. Fixed position1,34 eligible items; target/reward/selection/final
days remain disjoint as originally frozen. Final41536 rows have only TWO UTC-day
clusters; rows or repeated nuisance fits do not manufacture independent days.
DM/IPS/SNIPS/DR estimates, raw weight tails, support and ESS are in the linked
artifact. Clipping at10 is bias-sensitive secondary diagnostics, not a new primary
estimand. Uniform IPS/SNIPS identity equals the observed random mean:
{r4['identity_control']['observed_final_random_mean']:.9g}. This validates that
identity fixture, not an adaptive whole-budget policy or a joint slate.

The random/BTS feature-release discrepancy limits unadjusted direct transport;
both source logs remain explicit. No one-step OPE result certifies MSCP's long
horizon budget controller. R2/R4 are separate evidence domains, never joined by IDs.

R2 artifact: `{INPUTS['R2']}`; SHA256 `{before[INPUTS['R2']]}`.
R4 artifact: `{INPUTS['R4']}`; SHA256 `{before[INPUTS['R4']]}`.
"""
    documents["DELAY_VALUE_REPORT.md"] = f"""# R3 finite-horizon delay/value evidence boundary

Real-data status: **BLOCKED_SOURCE**. The configured official Sponsored Search
object advertises2002864638 bytes, exceeding the unchanged700000000-byte cap;
the preserved admission attempt transferred zero payload bytes. No mirror,
partial object or synthetic replacement is silently admitted. The M41+C54 pair,
half-open intervals and no-stale-calibrator refit contract remain unchanged.

Typed finite-horizon delay baselines and direct/two-part value models have CPU
numerical/censoring/maturity fixtures. This is implementation evidence, not a
measured R3 model ladder, calibration result or revenue column invention.
Simulator receipt delay includes its declared reporting assumption; this is not
empirical reporting latency exposed by Sponsored Search. Recorded conversion,
report availability, mature-origin rewards and synthetic nowcasts stay distinct.

Unsupported: real finite-horizon incidence/delay improvements, calibrated
per-impression monetary values, real lifetime value or production impact.
Required next action is a legally admitted official source within the unchanged
cap or an explicitly authorized prospective acquisition-contract amendment—not
a fabricated successful empirical experiment. Independent admitted tracks continue.

Source diagnostic: `{INPUTS['R3']}`; SHA256 `{before[INPUTS['R3']]}`.
"""
    directory = ROOT / "reports/analysis" / study.name
    directory.mkdir(parents=True)
    outputs = {}
    for name, body in documents.items():
        destination = directory / name
        destination.write_text(body, encoding="utf-8")
        outputs[name] = {"path": str(destination), "sha256": digest(destination)}
    if before != {path: digest(ROOT / path) for path in INPUTS.values()}:
        raise ValueError("Aggregate source changed during reporting")
    report = {"status": "EXISTING_PUBLIC_AGGREGATES_REPORTED", "inputs_sha256": before, "documents": outputs, "final_predictions_loaded": 0, "final_outcomes_rescored": 0, "original_artifacts_unchanged": True, "no_scientific_status_upgrade": True, "wall_seconds": time.perf_counter() - started}
    artifact = ROOT / "reports/analysis" / (study.name + ".json")
    atomic_json(artifact, report)
    atomic_json(study.directory / "result.json", report)
    atomic_json(ROOT / "reports/analysis/COMPLETED_PUBLIC_TRACK_REPORTS.json", report | {"artifact": str(artifact), "sha256": digest(artifact)})
    print(json.dumps({"artifact": str(artifact), "not_E16_completion": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
