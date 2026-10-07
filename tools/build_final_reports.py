#!/usr/bin/env python3
"""Build final presentation from verified saved artifacts, never train or rescore."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.final_evidence import EVIDENCE_CLASSES, final_reporting_gate
from aurora.workflow import Ledger
from serving_study import active_project_compute

OUT = ROOT / "reports/final"


def pointer(relative):
    p = json.loads((ROOT / relative).read_text())
    path = Path(p["artifact"])
    if path.is_symlink() or digest(path) != p["sha256"]:
        raise ValueError("Artifact identity failed: " + relative)
    return path, json.loads(path.read_text()), p["sha256"]


def write_md(name, title, body):
    path = OUT / name
    if path.exists():
        raise ValueError("Final artifact already exists: " + name)
    path.write_text("# " + title + "\n\n" + body.strip() + "\n", encoding="utf-8")


def main():
    state = Ledger(ROOT / "config/experiments.json", Path.home() / ".local/share/aurora-ads/state/experiment_state.json").read()
    final_reporting_gate(state, active_owned_compute=active_project_compute())
    bundle_path, bundle, bundle_sha = pointer("reports/analysis/FINAL_EVIDENCE_BUNDLE.json")
    if bundle["captured_generation"] != state["generation"]:
        raise ValueError("Terminal handoff no longer matches canonical state")
    OUT.mkdir(exist_ok=True)
    records = list(bundle["records"])
    sources = dict(bundle["verified_artifacts_sha256"])
    supplements = {}

    def read_pointer(name):
        path, report, sha = pointer(name)
        sources[str(path)] = sha
        supplements[name] = {"artifact": str(path), "sha256": sha, "report": report}
        return path, report, sha

    def add(identifier, domain, candidate, metric, value, unit, path, sha, location,
            *, role="DEVELOPMENT_ONLY", n=None, ci=None, interval_target="UNAVAILABLE", outcome="NOT_ESTABLISHED", note="", baseline="not a paired contrast"):
        records.append({"result_id": identifier, "record_status": "MEASURED", "evidence_domain": domain,
            "evidence_class": EVIDENCE_CLASSES[domain], "role": role, "estimand_id": identifier,
            "comparison_id": identifier, "candidate": candidate, "baseline": baseline,
            "population": "R3 frozen development known outcomes" if domain == "R3" else "saved local measurement population",
            "metric": metric, "estimate": value, "difference": None, "unit": unit,
            "horizon": "7-day recorded conversion; selection origins[54,60), matured at67; M41+C54" if domain == "R3" else "saved measurement protocol",
            "n_independent_units": n, "independent_unit": "not established for descriptive scores" if n is None else "recorded clusters",
            "uncertainty_method": "unavailable; descriptive point, not inferential interval" if ci is None else "saved artifact method",
            "ci_lower": None if ci is None else ci[0], "ci_upper": None if ci is None else ci[1],
            "interval_target": interval_target, "scientific_outcome": outcome, "execution_status": "EXECUTED",
            "artifact": str(path.relative_to(ROOT)), "artifact_sha256": sha, "artifact_location": location,
            "source_hashes": [sha], "config_hash": None, "model_calibrator_id": candidate,
            "scope_limits": [note], "missingness_handling": "46 unknown R3 selection labels excluded from complete-case scores, identification bounds retained separately" if domain == "R3" else "all scheduled HTTP outcomes included"})

    # No predictions are opened. Every exported scalar is already in a saved result.
    for name in ("R3_CPU_BASELINES", "R3_FEEDBACK_SHIFT_DEVELOPMENT", "R3_PARAMETRIC_DELAY_DEVELOPMENT"):
        path, report, sha = read_pointer("reports/delay/" + name + ".json")
        for i, recipe in enumerate(report["recipes"]):
            for j, variant in enumerate(recipe["variants"]):
                for metric in ("logloss", "brier", "pr_auc", "auroc", "fixed_bin_ece"):
                    if metric not in variant["scores"]:
                        continue
                    add(f"R3_{name}_{i}_{j}_{metric}", "R3", variant["id"], metric, variant["scores"][metric],
                        "nats/click" if metric == "logloss" else "dimensionless", path, sha,
                        f"/recipes/{i}/variants/{j}/scores/{metric}",
                        outcome="INVALID" if name == "R3_PARAMETRIC_DELAY_DEVELOPMENT" else "NOT_ESTABLISHED",
                        note="Both D3 recipes nonconverged, ineligible for final selection" if name == "R3_PARAMETRIC_DELAY_DEVELOPMENT" else "Development only; all calibration variants preserved. Not full H_delay comparison.")
    path, report, sha = read_pointer("reports/delay/R3_VALUE_DEVELOPMENT.json")
    for i, row in enumerate(report["results"]):
        for metric in ("complete_case_MSE", "complete_case_MAE"):
            add(f"R3_value_{i}_{metric}", "R3", row["id"], metric, row["scores"][metric],
                "publisher attributed Euro units squared" if metric.endswith("MSE") else "publisher attributed Euro units",
                path, sha, f"/results/{i}/scores/{metric}", note="Recorded attributed value, not incremental or unique-purchase value. Identification bounds are not confidence intervals.")
    path, diagnosis, sha = read_pointer("reports/policy/E13_DIAGNOSTIC_ANALYSIS.json")
    for name, row in diagnosis["contrasts_vs_locked_conventional"].items():
        if row["mean_development_difference"] is not None:
            add("S1_E13_" + name, "S1", name, "mean_development_utility_difference", row["mean_development_difference"],
                "normalized net utility per initial budget", path, sha,
                "/contrasts_vs_locked_conventional/" + name + "/mean_development_difference",
                n=12, baseline="static_bid0.25", note="Same12 development worlds reused across recipes; not new confirmation units.")
            records[-1].update(population="S1 corrected-development twelve paired worlds", horizon="14 decision days plus7-day maturation and declared receipt flush")
    policy_path, policy_report, policy_sha = read_pointer("reports/policy/POLICY_CONFIRMATION_RESULT.json")
    block = policy_report["analysis"]["parameter_block_cluster_sensitivity"]
    add("S1_parameter_block_sensitivity", "S1", "locked_MSCP", "parameter_block_paired_utility_difference", block["mean"],
        "normalized net utility per initial budget", policy_path, policy_sha, "/analysis/parameter_block_cluster_sensitivity",
        role="PRIMARY_CONFIRMATION", n=block["units"], ci=(block["lower"], block["upper"]), interval_target="difference",
        outcome="UNDERPOWERED", baseline="static_bid0.25", note="16 equally weighted catalog blocks within families; separate dependence sensitivity, not new external mechanisms.")
    records[-1].update(difference=block["mean"], population="Frozen finite synthetic parameter catalog", independent_unit="family/parameter block", horizon="14 decision days plus7-day maturation and receipt flush")
    for key in ("candidate_mean", "baseline_mean"):
        add("S1_confirmation_" + key, "S1", "locked_MSCP" if key == "candidate_mean" else "static_bid0.25", "mean_completed_episode_utility",
            policy_report[key], "normalized net utility per initial budget", policy_path, policy_sha, "/" + key,
            role="PRIMARY_CONFIRMATION", n=200, outcome="UNDERPOWERED", note="Absolute saved arm mean; no paired contrast CI attached to absolute point. Relative effect unavailable because comparator is near zero.")
    # Retain saved R1 paired comparator summaries including UID/time sensitivity.
    r1path = ROOT / "reports/model/e15_r1_confirmation_1790881991684526040.json"
    r1 = json.loads(r1path.read_text())
    supplements["R1_saved_paired_analysis"] = {"artifact": str(r1path), "sha256": digest(r1path), "report": r1}
    for candidate, row in r1["final_results"].items():
        for metric in ("brier", "pr_auc", "auroc", "fixed_bin_ece"):
            add("R1_" + candidate + "_" + metric, "R1", candidate, metric, row[metric], "dimensionless", r1path, digest(r1path),
                "/final_results/" + candidate + "/" + metric, role="SECONDARY_FROZEN_BENCHMARK",
                note="Saved temporal benchmark summary; no inferential CI assigned to calibration/ranking points.")
            records[-1].update(population="R1 final temporal benchmark replication", horizon="publisher temporal split; recorded response")
    for name in ("reports/causal/e04_assignment_replication_1790881140397659915.json", "reports/ope/e05_fixed_policy_ope_1790880719890434701.json"):
        path = ROOT / name
        supplements[name] = {"artifact": name, "sha256": digest(path), "report": json.loads(path.read_text())}
    for candidate, row in r1["paired_logloss_vs_prior"].items():
        for label, value in [("vs_prior", row)] + [(key, row[key]) for key in ("native_time20block_sensitivity", "paired_vs_development_selected_conventional", "conventional_time_block_sensitivity") if key in row]:
            location = "/paired_logloss_vs_prior/" + candidate + ("" if label == "vs_prior" else "/" + label)
            add("R1_paired_" + candidate + "_" + label, "R1", candidate, "paired_logloss_difference", value["estimate"],
                "nats/impression", r1path, digest(r1path), location, role="SECONDARY_FROZEN_BENCHMARK",
                n=value["n_profile_clusters"], ci=value["ci95"], interval_target="difference",
                baseline="P2_depth4" if "conventional" in label else "P0_prior",
                note="Historical n_profile_clusters label is preserved; UID clusters for primary,20 temporal blocks for time sensitivity. Replication, not virgin external validation.")
            records[-1].update(difference=value["estimate"], population="R1 final temporal benchmark replication", horizon="publisher temporal split; recorded response",
                               uncertainty_method=value["uncertainty_method"])
    cpu = bundle["CPU_systems"]["report"]
    cp = Path(bundle["CPU_systems"]["artifact"])
    cs = bundle["CPU_systems"]["sha256"]
    for i, row in enumerate(cpu["model_measurements"]):
        for section in ("inference_only", "feature_to_provisional_ranking"):
            if section not in row:
                continue
            for metric in ("p50_ms", "p95_ms", "p99_ms"):
                add(f"CPU_component_{i}_{section}_{metric}", "LOCAL_SYSTEMS", f"CPU_batch{row['batch']}_compiled{row['compile']}",
                    section + "_" + metric, row[section][metric], "milliseconds", cp, cs, f"/model_measurements/{i}/{section}/{metric}",
                    role="SECONDARY_FROZEN_BENCHMARK", note="Empirical convenience-window percentiles, no population CI; numerical component only.")
    for i, row in enumerate(cpu["network_measurements"]):
        values = {key: (value, "all_requests_latency/" + key) for key, value in row["all_requests_latency"].items() if key in ("p50_ms", "p95_ms", "p99_ms")}
        values["error_fraction"] = (row["error_fraction"], "error_fraction")
        for key, (value, location) in values.items():
            add(f"CPU_HTTP_{i}_{key}", "LOCAL_SYSTEMS", f"CPU_HTTP_connections{row['connections']}_window{row['window']}_offered{row['offered_rps']}", key, value,
                "milliseconds" if key.endswith("_ms") else "fraction", cp, cs,
                f"/network_measurements/{i}/{location}", role="SECONDARY_FROZEN_BENCHMARK",
                note="Scheduled-arrival latency includes queue delay/failures. Local read-only component, not production SLO. Achieved throughput was not separately recorded.")
    failed_path, failed, failed_sha = read_pointer("reports/serving/CPU_FAILED_ATTEMPT.json")
    for i, row in enumerate(failed["network_partial"]):
        add(f"CPU_FAILED_attempt_window{i}_p95", "LOCAL_SYSTEMS", "Original_dependency_profile_failed_attempt",
            "all_requests_p95_ms", row["all_requests_latency"]["p95_ms"], "milliseconds", failed_path, failed_sha,
            f"/network_partial/{i}/all_requests_latency/p95_ms", role="SECONDARY_FROZEN_BENCHMARK",
            note="Original completed window retained. Later HTTP phase stopped after1126s stat-storm diagnosis; unrecorded pending outcomes unknown. Intrusive diagnostic interval is not latency evidence.")
    supplements["CPU_retry_scope"] = {"original_failure": {"artifact": str(failed_path), "sha256": failed_sha},
        "reused_components": cpu.get("reused_component_measurements"), "new_HTTP_dependency": "sniffio==1.3.1",
        "historical_environment_lock_rewritten": False}
    unavailable = []
    for row in bundle["unavailable_records"]:
        unavailable.append({**row, "result_id": "unavailable_" + row["node"], "role": "UNAVAILABLE",
            "estimand_id": row["node"], "comparison_id": row["node"], "metric": "unavailable_required_endpoint",
            "artifact": row["artifacts"][0]["path"], "artifact_sha256": row["artifacts"][0]["sha256"], "artifact_location": ""})
    all_records = records + unavailable
    if len({r["result_id"] for r in all_records}) != len(all_records):
        raise ValueError("Duplicate measurement IDs")
    claims = [{"claim_id": "claim_" + r["result_id"], "result_id": r["result_id"],
        "claim": ("Unavailable: " + r["reason"]) if r["record_status"] != "MEASURED" else
            f"{r['candidate']}: saved {r['metric']} in the specified evidence domain; {r['scientific_outcome']}",
        **{k: r.get(k) for k in ("evidence_class", "role", "execution_status", "scientific_outcome", "estimand_id", "comparison_id", "population", "candidate", "baseline", "estimate", "difference", "ci_lower", "ci_upper", "interval_target", "n_independent_units", "independent_unit", "unit", "horizon", "artifact", "artifact_sha256", "artifact_location", "scope_limits")},
        "unsupported_extrapolation": "No production deployment, commercial lift, fresh external validation or learned-agent safety claim"} for r in all_records]
    atomic_json(OUT / "FINAL_METRICS.json", {"records": all_records, "claims": claims, "saved_supplements": supplements,
        "sources": sources, "handoff_sha256": bundle_sha, "no_new_predictions_or_scoring": True})
    for relative in ("reports/agent/Qwen3-1.7B_sft_seed41_LATEST.json", "reports/agent/Qwen3-1.7B_dpo_seed41_LATEST.json",
                     "reports/agent/Qwen3-1.7B_ipo_seed41_LATEST.json", "reports/agent/Qwen3-1.7B_SFT_RESTART_QUALIFICATION.json",
                     "reports/agent/Qwen3-1.7B_dpo_seed41_RESTART_QUALIFICATION.json", "reports/agent/Qwen3-1.7B_ipo_seed41_RESTART_QUALIFICATION.json",
                     "reports/data/R3_ANALYSIS_ADMISSION.json", "reports/serving/MCP_RECOVERY_QUALIFICATION.json"):
        path, report, sha = read_pointer(relative)
        for checkpoint_name, checkpoint_sha in report.get("checkpoint_hashes", {}).items():
            checkpoint = json.loads((ROOT / relative).read_text()).get("checkpoint")
            if checkpoint and digest(Path(checkpoint) / checkpoint_name) != checkpoint_sha:
                raise ValueError("Historical adapter checkpoint integrity failed")
    for relative in ("reports/environment/ENVIRONMENT_LOCK.json", "config/datasets.json", "config/interface_contracts.json", "config/resources.json"):
        sources[str(ROOT / relative)] = digest(ROOT / relative)
    manifest = {"captured_terminal_generation": state["generation"], "handoff": {"artifact": str(bundle_path), "sha256": bundle_sha},
        "source_artifacts": sources, "code_sha256": digest(Path(__file__)), "historical_provenance": "Original recorded hashes retained; current report-builder hash is not retroactive experiment provenance"}
    atomic_json(OUT / "REPRODUCIBILITY_MANIFEST.json", manifest)
    for name, selector in (("ENVIRONMENT", ("environment",)), ("DATA_SOURCE", ("data",)), ("MODEL", ("model", "delay", "causal", "ope")),
                           ("POLICY", ("policy", "simulator", "incidents")), ("AGENT", ("agent",)), ("SERVING", ("serving",))):
        chosen = {p: sha for p, sha in sources.items() if any("/reports/" + domain + "/" in p for domain in selector)}
        atomic_json(OUT / (name + "_MANIFEST.json"), {"evidence": chosen, "captured_generation": state["generation"], "notes": "Restricted raw/source-derived artifacts remain local ext4; no redistribution."})
    registry = json.loads((ROOT / "config/experiments.json").read_text())["nodes"]
    final_nodes = {n["id"]: {"execution_status": state["nodes"][n["id"]]["execution_status"],
        "scientific_outcome": state["nodes"][n["id"]]["scientific_outcome"], "primary_artifact": state["nodes"][n["id"]]["artifacts"][-1] if state["nodes"][n["id"]]["artifacts"] else None,
        "blocker_reason": state["nodes"][n["id"]].get("reason", ""), "evidence_class": n["evidence_domain"], "all_artifacts": state["nodes"][n["id"]]["artifacts"]} for n in registry}
    atomic_json(OUT / "FINAL_STATUS.json", {"status": "FINAL_PACKAGE_AWAITING_INDEPENDENT_VERIFICATION", "captured_generation": state["generation"],
        "nodes": final_nodes, "completion_layers": bundle["completion_layers"], "runnable_core_experiments": [], "E16_not_yet_committed": True})
    summary = """The closed research project does not establish AURORA algorithmic superiority or production advertising lift. The fixed200-world synthetic confirmation favored the conventional controller; the predeclared practical-margin power designation remains UNDERPOWERED. Public prediction and randomized-release analyses remain benchmark replication, logged-bandit OPE remains calendar-underpowered, and agent semantic evaluation remains unscored under the hardware monitoring hold.

Engineering execution includes source admission/conversion, as-of modeling, delayed observed-reward control, simulator qualification, deterministic budget/authorization transactions, one MCP application-agent architecture, actual bounded SFT/DPO/IPO training/restart evidence, and isolated local CPU component serving/recovery. Core tracks have terminal dispositions, but CORE_EMPIRICAL_COMPLETE is false. No real advertising writes, spend or production deployment occurred."""
    policy = next(r for r in records if r["result_id"] == "S1_primary_confirmation")
    primary = f"Frozen MSCP-minus-static completed-episode contrast: {policy['estimate']:.12g}, 95% paired interval [{policy['ci_lower']:.12g}, {policy['ci_upper']:.12g}], n=200 complete exogenous worlds conditional on the finite catalog. Practical margin0.01; planning power{policy['planning_power']:.8g}; scientific status UNDERPOWERED. Negative direction is observed in this synthetic catalog. It is not proof of production harm or a universal no-benefit theorem."
    write_md("EXECUTIVE_SUMMARY.md", "AURORA-Ads executive summary", summary + "\n\n" + primary + "\n\nEvidence: [final metrics](FINAL_METRICS.json), [track status](FINAL_STATUS.json), [technical report](FINAL_TECHNICAL_REPORT.md).")
    sections = """
## Architecture and economic boundaries

The fast plane is typed numerical state/features, observed-outcome models, policy scores and budget mechanics. The slow plane is one pinned Qwen3 tool-using application agent with bounded rounds. Nine typed tools expose snapshot, metrics, outcomes, simulation/recommendation, validation, prepare/commit and measurement reporting. Deterministic host code owns authorization, SQL allowlisting, version/expiry checks, idempotency and atomic reservation/settlement. All mutations are mock/local. Simulator oracle truth is evaluator-only. Public sources are never joined by fabricated identities or multiplied into a calibrated cross-domain impression value.

## 1. Public prediction, causal replication and OPE

R1 internally frozen temporal replication remains NOT_ESTABLISHED. The selected DCNv2 logloss reduction against the conventional XGBoost comparator was about0.00054007 nats/impression, below the declared practical gate. Natural prevalence, calibrator pairing and all losing predictor recipes are preserved. UID and time-block uncertainty are distinct sensitivities, not known-person independence.

R2 released randomized-assignment analysis remains NOT_ESTABLISHED. Assignment DR visit contrast and20% allocation comparisons are descriptive released-sample benchmark estimates under documented exchangeability/release assumptions. Original deployment assignment probability and calendar outcome horizon are not reconstructed. The unspecified assignment ratio prevents an invented50/50 SRM null. Conversion allocation intervals included zero.

R4 fixed-policy DM/IPS/SNIPS/DR remains UNDERPOWERED:41536 final rows but only two UTC-day clusters. Exact executed logging support, ESS and raw/clipped weights remain explicit. Uniform-policy identity agrees with the observed random mean. One-step OPE does not certify the adaptive budget controller. Potential historical release exposure limits every public track to replication rather than virgin external confirmation.

## 2. Simulator and incident qualification

S1 uses14 decision days,15-minute actions, seven-day conversion maturation and separately declared receipt-lag flush. Keyed exogenous draws preserve pairing under action-dependent state divergence. Unique synthetic purchase value is scored once. Spend and operational/intervention costs are charged; scarcity dual is an additional control price. Only matured origin cohorts update learned rewards; nowcasts inform state, never pseudo-observations. The E07 baseline/current-code numerical physics checks are compatibility evidence, not proof of economic realism. E08 incident study remains UNDERPOWERED and synthetic, not production incident-detection validation.

## 3. Original policy study, audit and corrected development

Original E09 completed540 development worlds. Score/cost units and support diagnostics exposed implementation deficiencies; original artifacts and original selection were archived, not overwritten. The prospective correction re-executed only33 affected recipes on12 same development worlds (396 executions). Locked corrected conventional static_bid0.25 mean utility was+0.0005047961742146698; locked MSCP_v2_eta0.01_max5.0_beta1.0 was-0.5281473661952677. These are development values, not confirmation. Selection was not rescued by later tuning.

## 4. E13 diagnosis and OOD

E13 completed136 arm/world runs:96 same-world development ablations and40 fixed-arm OOD runs. Every permitted component removal remained unfavorable against static. Locked difference-0.528652162369482 decomposed into additional purchase value+0.168409715130518, additional spend-0.6968008775 and operational costs-0.000261. Frequent NO_CHANGE retains the default bid and is not NO_BID. The declared comparison includes static bid0.25 versus MSCP default bid1.0, so this is a selected-system contrast, not an isolated learning-effect experiment.

Support gates affected almost all candidate sets, but do not imply every arm had zero support. Uncertainty/support/dual/reliability interactions and calibration diagnostics are recorded in [E13 diagnosis](../policy/E13_DEVELOPMENT_DIAGNOSIS.md). Predicted gross purchase value is not incremental value calibration. Twelve reused development worlds are not96 independent units. Each OOD family/mechanism cell has only one world, so no within-cell interval is invented. Diagnostics explain the loss without redefining H_policy.

## 5. Bidder and current physics

Current-hash16-case physics qualification passed. The separate observed-auction/25-field state extension is secondary prospective infrastructure, not the primary fixed-bid result. Censored losing-auction prices are not filled with evaluator truth. Historical compatibility does not establish a new fitted bidder winner. This extension never replaces the locked MSCP.

## 6. R3 recovery, clocks and CPU development

The original generic-cap blocker and failed sentinel admission remain. A publisher-only source-specific exception admitted the2,002,864,638-byte archive under2.1GB, without changing the default cap, adding mirrors/authentication or new terms. Streaming conversion yielded15,995,634 valid rows. Source order is unsorted. Seconds are inferred from documented release duration, not independently supplied calendar metadata. Conversion occurrence and assumed immediate receipt are separate concepts; reporting lag is unobserved. The20,958 exact full-record repetitions are retained because purchase identity is unavailable.

M41[0,41) and C54[41,47), calibrated at54, remain unchanged. Selection origins[54,60) mature at67. Unknown positive delay labels remain unknown;46 selection unknowns produce identification bounds rather than confidence intervals. Same-source mature incidence/value development executed. Finite-H feedback-shift correction did not beat the best mature-only CPU logloss. Both fixed100-iteration D3 profiles failed convergence and are ineligible despite attractive descriptive scores. The required GPU ladder and primary R3 freeze/confirmation remain BLOCKED_HARDWARE; no final R3 rows were scored.

## 7. Agent training and inference resource blocker

Bounded Qwen3-1.7B SFT, same-SFT DPO retry and IPO seed41 training/restart qualifications passed. Training completion is not semantic improvement. The first DPO attempt stopped thermally before optimizer updates and remains recorded. Completion projection was prospectively repaired without truncating attended tool context. Exact model/tokenizer revisions, corpus and render contracts remain pinned.

The original two-workflow underpowered audit remains. Prospective taxonomyV2 froze nine held-out semantic dependence groups before substantive post-training or final scoring. Nine groups remain prospectively underpowered; paraphrases, seeds and retries are not independent families. Prompt5-second inference duty failed and10-second passed. Original SFT5-second profile failed thermally;10 and30 seconds failed on the frozen three-second monitoring timeout. No failed profile was replayed and no fourth cadence was invented. Idle telemetry cannot qualify sustained decode monitoring. DPO/IPO inference and every semantic endpoint remain UNSCORED, not agent failures. No trained finalist, agent freeze,2x2 integration or agent confirmation exists. E11 and optional4B transfer are not applicable to this closure.

## 8. Pilot, freeze and untouched policy confirmation

Twenty excluded pilot pairs estimated variance only. The prospectively fixed sample was200, planning power about0.0656 for distinguishing0.02 from the0.01 null boundary. The full roster, catalog/budgets, policies, simulator, nuisance/support identities, code/config hashes and analysis were frozen before final outcomes. All200 pairs completed with400 SHA-verified full-maturation arm receipts. Frozen analysis executed once. No sample adaptation, early outcome stopping, final-world tuning or reselection occurred.

## 9. Local systems and recovery

Isolated CPU measurements use the frozen observed-only numerical mean head with batch1/16/64, eager/compile modes and bounded local HTTP connections/rates/windows. Inference-only, feature-to-provisional ranking and HTTP latency are distinct. Scheduled-arrival latency includes queue delay and failed requests. Cold means new process/first call, not forced OS cache eviction. Startup, compile and shutdown costs remain recorded. The matched CPU/CUDA comparison, CUDA OOM, full adaptive-policy and complete agent-task domains are unavailable under the GPU hold.

Actual local HTTP cancellation/retry/restart fixtures are read-only: client cancellation is not proof of backend interruption, and duplicate prediction is not economic idempotency. Independent retained MCP crash/replay fixtures exercise mock commit replay, audit/state/charge equality and stale/authorization/budget rejection. Host-blocked errors do not prove the model learned safe behavior. Full E14 is terminal BLOCKED_HARDWARE with CPU evidence retained, not a full serving qualification or Amazon-scale production SLO.

## 10. Integrity, reproducibility and limitations

Immutable state events, source hashes, frozen pointers and durable receipts control resume. Failures remain append-only; newer verified ledger events supersede stale WORK_STATE narratives. Historical missing hashes are not retroactively filled with current hashes. All final exports read saved aggregate results only, retain negative recipes and unavailable metrics, and preserve interval targets/dependence units. Requirement-level coverage is in REQUIREMENT_COVERAGE.md. Green fixtures, narrow leakage refusal controls and post-scoring public control chronology do not replace untouched scientific tests. The retained bootstrap reference coverage92.95% is a limitation.

No algorithmic superiority, commercial impact, production availability or learned-agent safety claim is established. Future work requires prospectively qualified under-load monitoring/hardware, genuinely new action-effect data, independent semantic workflows and external validation, not repeated favorable-seeking runs or a hidden primary-policy replacement.
"""
    write_md("FINAL_TECHNICAL_REPORT.md", "AURORA-Ads final technical report", summary + "\n\n" + primary + "\n" + sections + "\nEvidence index: [metrics](FINAL_METRICS.json), [results CSV](RESULTS_MATRIX.csv), [claims CSV](CLAIM_EVIDENCE_LEDGER.csv), [manifests](REPRODUCIBILITY_MANIFEST.json).")
    write_md("LIMITATIONS_THREATS_TO_VALIDITY.md", "Final limitations and threats to validity", summary + "\n\n" + sections[sections.index("## 10."):] + "\n\nAdditional limits: public release selection and prior exposure, non-person feature-profile clusters, only two OPE days, assumed R3 receipt/unit clock, unknown delay labels and purchase identity, finite simulator catalog, fixed controller seed, singleton OOD cells, small bounded post-training corpus, blocked semantic comparison, sampled telemetry, CPU component-only serving and no human/operator or production study. See [historical threats](../analysis/THREATS_TO_VALIDITY_PROGRESS.md); later addenda supersede stale execution states without rewriting them.")
    write_md("RESUME_EVIDENCE.md", "Resume evidence", """Use the following only as local personal-research claims; no production ad spend or realized lift.

- Public benchmark replication: implemented temporal prediction/calibration and as-of conversion/value modeling on admitted Criteo releases. R1 superiority gate not established; R3 full empirical ladder hardware-blocked.
- Randomized benchmark replication: implemented released-assignment T-learner and cross-fitted DR comparisons with profile dependence/release limitations. Not a fresh live advertiser experiment.
- Logged-bandit OPE: implemented DM/IPS/SNIPS/DR with support/ESS/weight diagnostics and identity controls. Only two final UTC days; underpowered.
- Synthetic counterfactual control: evaluated strong conventional controllers and MSCP, preserved a score/support correction and negative ablations, then completed a frozen200-world paired confirmation. The simpler static controller won in this catalog; no business lift claim.
- Agent infrastructure: implemented one pinned Qwen3 MCP application agent, executable workflow data and bounded SFT/DPO/IPO training/restart paths. Semantic performance and learned safety remain unscored due the preserved inference-monitor hold.
- Local systems engineering: implemented deterministic mock budget reservation/settlement, version/authorization/expiry checks and idempotent replay. Measured isolated CPU numerical/HTTP components and exercised local cancellation/retry/restart. Not full agent, GPU or production latency.
- Research discipline: preserved failed thermal/monitoring attempts, D3 nonconvergence and unfavorable comparisons; froze code/data/analysis before untouched confirmation and produced SHA-bound claim/result ledgers.

Do not write “improved ad revenue,” “production-safe agent,” “Amazon SLO,” “DPO outperformed prompt-only,” or “fully empirically validated.” Sources: [technical report](FINAL_TECHNICAL_REPORT.md), [claim ledger](CLAIM_EVIDENCE_LEDGER.csv), [track status](FINAL_STATUS.json).""")
    write_md("INTERVIEW_GUIDE.md", "Interview guide", """**Architecture?** Fast numerical state/model/control plane; slow single Qwen3 tool plane. Typed host code, not the LLM, owns economic arithmetic and mock authorization/transactions.

**As-of and delayed feedback?** Origin cohorts mature before reward updates. Occurrence is not receipt; R3 immediate receipt is explicitly assumed. M41+C54 and half-open masks are frozen; unknown delays are not negative labels.

**Causal versus OPE?** R2 is released randomized-assignment replication under documented release assumptions. R4 is fixed-policy logged-bandit OPE with positivity/ESS diagnostics. Neither is adaptive whole-budget certification or live advertiser lift.

**Simulator?** Four distinct mechanism families, evaluator-only truth, unique purchases, keyed paired exogenous shocks,14 decision days plus maturation/reporting flush, real spend plus intervention cost. Catalog assumptions are not validated production physics.

**Why did MSCP lose?** Its extra purchase value did not cover extra spend. NO_CHANGE preserves default bid1.0 while the selected static uses0.25. Support/calibration/reliability diagnostics expose limitations; this selected-system contrast does not isolate a universal learning effect.

**Ablations?** Removing delay, support, uncertainty, dual pacing or reliability remained worse than static on the same12 development worlds. OOD cells were singleton worlds. We diagnosed instead of searching until the primary won.

**Why underpowered despite a negative interval?** Prospective power for the small positive practical-margin alternative was low at the fixed cap200. The observed large negative direction can be described without changing that designation. Repeated shocks do not create new mechanism families;16-block sensitivity is separate.

**SFT/DPO/IPO outcome?** Training/reload paths executed, but semantic comparison was never admitted. Original SFT5/10/30 inference duty profiles exhausted thermal/monitoring gates. Training loss cannot select a finalist or stand in for task success.

**Hardware diagnosis?** Frozen telemetry queries timed out under load. Idle probes and bounded4B updates are not sustained qualification. We retained the hold and did not weaken timeout/cadence/87C target/2GiB reserve or close user applications.

**Safety and recovery?** Deterministic guards and atomic mock prepare/commit prevent specified tested failures. Actual MCP crash/replay checks retained charge/state/audit equality. Host blocking does not prove model safety; zero fixture breaches are not zero population risk.

**Serving?** Separate inference, provisional-ranking and local HTTP metrics, all scheduled outcomes/startup/compile/restart costs included. CPU-only numerical component, not full adaptive-policy/LLM/GPU or production latency.

**Reproducibility?** Canonical ext4 ledger events and SHA-bound reports/freeze/receipts take precedence over narratives. No historical source hash is invented retroactively. Final CSVs are checked against saved JSON, not rescored predictions.

**What would production validation require?** New licensed action-effect data, genuine logging propensities and reporting clocks, externally qualified serving hardware, prospective shadow authorization, independent operator workflows/human labels, then appropriately authorized randomized live validation. None was performed here.

Use exact numbers only from [results](RESULTS_MATRIX.csv) and state their domain, horizon, comparator, uncertainty and limitations.""")
    coverage_lines = ["| Node | Execution | Scientific outcome | Evidence |", "| --- | --- | --- | --- |"]
    for node, row in final_nodes.items():
        coverage_lines.append(f"| {node} | {row['execution_status']} | {row['scientific_outcome']} | {row['primary_artifact']['path'] if row['primary_artifact'] else 'E16 awaits verification'} |")
    write_md("REQUIREMENT_COVERAGE.md", "Requirement-level closure and gaps", "Terminal dispositions do not certify all requested empirical work. The ledger coverage below must be read with these explicit gaps: required R3 CUDA/neural ladder incomplete; agent four-arm semantic evaluation/finalist/seeds/confirmation and factorial integration unexecuted; matched GPU/full-policy/complete-agent latency and CUDA OOM unavailable. Public control chronology and narrow leaky-label/schema fixtures are not relabeled pre-confirmation trained negative controls. Bidder secondary infrastructure is not a fitted bidder winner. CPU fixtures complement, never replace, CUDA evidence.\n\n" + "\n".join(coverage_lines))
    write_md("REPORT_FAMILY_INDEX.md", "Final report families and evidence index", """All links point to retained saved evidence or chronological reports; stale historical execution paragraphs are history, not current status.

| Report family | Evidence / current conclusion |
| --- | --- |
| Desktop/prior art | [Nearest-method comparison](../literature/DESKTOP_STUDY.md) |
| Sources/license/EDA/quality | DATA_SOURCE_MANIFEST.json, E01 admission artifacts, R3 conversion/admission; benchmark replication, R5 gated |
| Clock/leakage | [Clock audit](../analysis/clock_leakage_audit_derivation_1790913542239331982/CLOCK_LEAKAGE_AUDIT.md), R3_CPU_DEVELOPMENT_STATUS; receipt assumption explicit |
| Model/calibration | [R1 analysis](../analysis/completed_public_track_analysis_1790906629762069705/MODEL_CALIBRATION_REPORT.md); NOT_ESTABLISHED |
| Delay/value | [R3 CPU evidence](../delay/R3_CPU_DEVELOPMENT_STATUS.md); D3 failed, full track hardware-blocked |
| Causal/OPE | [Released benchmark analysis](../analysis/completed_public_track_analysis_1790906629762069705/CAUSAL_OPE_REPORT.md); R2 NOT_ESTABLISHED, R4 UNDERPOWERED |
| Simulator/falsification/incidents | POLICY_MANIFEST.json and E07/E08 ledger artifacts; synthetic qualification, incident UNDERPOWERED |
| Policy/ablations/OOD/inference | [E13 diagnosis](../policy/E13_DEVELOPMENT_DIAGNOSIS.md), frozen E15 result, FINAL_METRICS.json; unfavorable/UNDERPOWERED |
| Agent/post-training | AGENT_MANIFEST.json, resource dispositions; training/restart executed, semantic comparison UNSCORED |
| Policy-agent integration | FINAL_STATUS.json; BLOCKED_HARDWARE, no manufactured2x2 results |
| Serving/recovery | SERVING_MANIFEST.json, CPU component results and MCP replay; partial CPU local engineering, full E14 blocked |
| Limitations/cost/reproducibility | LIMITATIONS_THREATS_TO_VALIDITY.md, manifests, actual saved wall times; no inferred costs or power energy total |
| Portfolio | RESUME_EVIDENCE.md and INTERVIEW_GUIDE.md; no business lift or deployment claim |
""")
    write_md("SOURCE_DATA_CAPABILITY_REPORT.md", "Source, license, quality and capability matrix", """Local personal non-commercial research. Publisher provenance, byte hashes, license acknowledgements and prior-exposure checks govern admission. Raw and restricted source-derived arrays/models stay in project-owned ext4; final reports do not authorize redistribution. No source IDs were silently joined.

| Source | License | Admitted capability | Explicit missing capability / limit |
| --- | --- | --- | --- |
| R1 Criteo attribution | CC-BY-NC-SA-4.0 | Temporal impression recorded-response prediction and descriptive attribution anchors | Randomized action effects/logging propensities not supplied; transformed cost is not raw currency. Prior exposure conservatively replication-only. |
| R2 Criteo uplift | CC-BY-NC-SA-4.0 | Released binary-assignment visit/conversion replication | No individual CATE truth, calendar/campaign IDs or documented original allocation ratio. Exposure is not pretreatment feature. |
| R3 Sponsored Search | CC-BY-NC-SA-4.0 | Post-click7-day recorded conversion and attributed-value development | No impression denominator, purchase order ID or independent reporting-arrival clock. Inferred seconds, assumed immediate receipt and unknown-delay labels remain explicit. |
| R4 Open Bandit Dataset | CC-BY-4.0 | Fixed-position logged policy DM/IPS/SNIPS/DR | Only two final UTC-day clusters, random/BTS release discrepancy, no adaptive episode or whole-slate certification. |
| R5 iPinYou optional | Not newly accepted | Unavailable/source-terms gated | Manual terms not authorized; no mirror or fabricated auction prices. |

EDA/schema/exclusion and provenance receipts remain in DATA_SOURCE_MANIFEST.json and the canonical E01 artifacts. R3 conversion retained15,995,634 valid rows/zero quarantine and20,958 exact full-record repetitions (not known duplicated purchases). M41/C54/selection had281/44/46 unknown horizon labels. Complete-case141,288 selection rows are not141,288 independent causal subjects. Identity hashes attest local bytes, not publisher economic truth. Historical config acquisition estimates and preparation availability notes remain history; actual admission pointers supersede them.
""")
    http_rows = ["| Connections | Window | Offered RPS | All-request p95 ms | Error fraction | Local target met |", "| --- | --- | --- | --- | --- | --- |"]
    for row in cpu["network_measurements"]:
        target = row["offered_rps"] == 100 and row["all_requests_latency"]["p95_ms"] <= 50 and row["error_fraction"] <= .001
        http_rows.append(f"| {row['connections']} | {row['window']} | {row['offered_rps']} | {row['all_requests_latency']['p95_ms']:.6g} | {row['error_fraction']:.6g} | {'yes, in this window' if target else 'not established for100RPS' if row['offered_rps'] != 100 else 'no'} |")
    write_md("SERVING_PERFORMANCE_RECOVERY_REPORT.md", "Local CPU serving and recovery", "CPU-only frozen mean-head component. Six model batch/compile profiles reused from the original attempt and18 HTTP rate/window/connection profiles under the repaired pinned dependency. The original attempt stopped after a missing-sniffio import/stat storm, with one complete10RPS window preserved and pending outcomes unknown. Its1126s cost is not excluded. The intrusive five-second trace is diagnosis, not latency evidence. Installing project-local sniffio1.3.1 was an engineering repair, not a favorable-outcome search or a rewrite of historical environment locks. Percentiles are empirical, not confidence intervals. The target is local100RPS/p95<=50ms/error<=0.1%, not Amazon production. Passing one window does not establish availability or sustained production throughput.\n\n" + "\n".join(http_rows) + f"\n\nHTTP-only retry wall{cpu['wall_seconds']:.6g}s, separate from the original component/failed attempt. Full startup/compile/shutdown, resource samples, cold calls and fault receipts are in the saved CPU report (SHA{cs}). Achieved throughput is unavailable as a separately recorded summary; offered rate is not silently relabeled throughput. Client cancellation, read-only duplicate/restart output equivalence and injected deadline/stale/queue faults are distinct from the retained MCP economic replay fixtures. GPU/full-controller/complete-agent/OOM domains remain BLOCKED_HARDWARE.")
    # Small evidence-derived vector graphic, not a new statistical analysis.
    x = lambda v: 100 + (v + .65) / .75 * 600
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="230" viewBox="0 0 800 230"><rect width="800" height="230" fill="white"/><g font-family="Arial" fill="#1e293b"><text x="40" y="35" font-size="19">Frozen synthetic policy confirmation</text><text x="40" y="61" font-size="14">MSCP minus static_bid0.25. 200 paired worlds. UNDERPOWERED.</text><line x1="{x(0)}" y1="85" x2="{x(0)}" y2="160" stroke="#64748b"/><line x1="{x(policy['ci_lower'])}" y1="120" x2="{x(policy['ci_upper'])}" y2="120" stroke="#b91c1c" stroke-width="4"/><circle cx="{x(policy['estimate'])}" cy="120" r="6" fill="#b91c1c"/><text x="40" y="185" font-size="14">{policy['estimate']:.4f} [{policy['ci_lower']:.4f}, {policy['ci_upper']:.4f}] normalized utility</text><text x="40" y="210" font-size="13">95% paired interval conditional on finite simulator catalog. Not live lift.</text></g></svg>'''
    (OUT / "figures").mkdir(exist_ok=True)
    (OUT / "figures/POLICY_CONFIRMATION.svg").write_text(svg, encoding="utf-8")
    print(json.dumps({"records": len(all_records), "claims": len(claims), "status": "FINAL_PRESENTATION_PREPARED_NOT_COMMITTED"}))


if __name__ == "__main__":
    main()
