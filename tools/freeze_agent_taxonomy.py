#!/usr/bin/env python3
"""Prospective v2 workflow/split freeze; preserves the immutable two-family audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.agent_tasks import FAMILIES, FAMILY_GROUPS
from aurora.agent_taxonomy import NEW_WORKFLOWS, dependence_groups
from aurora.artifacts import atomic_json, digest, immutable_json
from aurora.studies import Study


def main():
    study = Study(ROOT, "prospective_agent_taxonomy_v2")
    pointer_path = ROOT / "reports/agent/TAXONOMY_V2_FREEZE.json"
    if pointer_path.exists():
        raise ValueError("V2 taxonomy already frozen; do not rewrite or pick after outcomes")
    old = ROOT / "reports/agent/e10_executable_agent_corpus_1790887880317165074.json"
    old_report = json.loads(old.read_text())
    if len(old_report["semantic_groups"]["final"]) != 2:
        raise ValueError("Historical underpowered audit is not the expected artifact")
    training_reports = list((ROOT / "reports/agent").glob("e10_agent_train_*.json"))
    final_reports = list((ROOT / "reports/agent").glob("e15_agent_confirmation_*.json"))
    if training_reports or final_reports:
        raise ValueError("Substantive training or final outcomes already exist; pre-outcome amendment not admissible")
    from scipy.optimize import brentq
    from scipy.stats import nct, t
    groups = dependence_groups(FAMILIES, FAMILY_GROUPS)
    split_groups = {split: sorted(name for name, item in groups.items() if item["split"] == split) for split in ("train", "validation", "final")}
    n = len(split_groups["final"])
    alpha = .05
    critical = t.ppf(1 - alpha / 2, n - 1)
    grid = [{"planning_difference": delta, "assumed_paired_family_sd": sigma, "n_families": n, "power": float(nct.sf(critical, n - 1, delta * n**.5 / sigma))} for delta in (.05, .1, .2) for sigma in (.1, .25, .5, 1.)]
    nominal = next(item for item in grid if item["planning_difference"] == .1 and item["assumed_paired_family_sd"] == .25)
    mde = brentq(lambda delta: nct.sf(critical, n - 1, delta * n**.5 / .25) - .8, 0., 2.)
    historical = {"artifact": str(old), "sha256": digest(old), "actual_final_semantic_groups": old_report["semantic_groups"]["final"], "scientific_status": "UNDERPOWERED", "corpus_files": old_report["files"], "disposition": "PRESERVED; not trained; not amended in place; retired from future substantive training by V2 freeze"}
    historical_path = immutable_json(ROOT / "reports/agent/taxonomy_history", historical)
    report = {"version": "A1_WORKFLOW_TAXONOMY_V2", "frozen": True, "historical_audit": {"artifact": str(historical_path), "sha256": digest(historical_path)}, "before_substantive_posttraining": True, "final_agent_model_outcomes_inspected": 0, "old_final_outcomes_moved_to_development": 0, "nominal_families": len(FAMILIES), "effective_dependence_groups": split_groups, "group_members": groups, "expanded_workflows": NEW_WORKFLOWS, "family_split": {name: {"split": item[0], "category": item[1], "dependence_group": FAMILY_GROUPS[name]} for name, item in FAMILIES.items()}, "merges_and_reassignments": ["The old budget-affordability branch shares direct guarded-execution eligibility and is merged into that training group, not retained as an independent held-out family", "The old conditional-report variant is kept with the entire fresh-report reconciliation group in final; its unused prior corpus remains historical, and no old corpus is fed to substantive training", "Reservation-expiry and actual-settlement cases remain in the same reservation-lifecycle group", "Preparation-abort and unsupported transfer are added train variants within existing proposal/refusal groups, not new independent units"], "power": {"primary_unit": "semantic workflow dependence group, averaged over templates and three training seeds", "final_tasks_target": 400, "actual_final_family_count": n, "nominal_family_target": 80, "alpha_two_sided": alpha, "method": "Prospective noncentral-t planning for lower paired-family95pctCI>0; requires independent approximately normal family contrasts; not observed performance", "sensitivity_grid": grid, "planning_reference": nominal, "reference_mde_for80pct_power": mde, "shared_generator_sensitivity_units": 1, "zero_observed_family_harm_upper95pct": 1 - alpha ** (1 / n), "scientific_status": "UNDERPOWERED", "reason": "Reference planning power<80pct; tiny convenience taxonomy/shared-host sensitivity cannot support broad family generalization; row/seed replication does not add independent families"}, "execution_profile": {"screening_model": "Qwen/Qwen3-1.7B", "qualified_finalists_only": "Qwen/Qwen3-4B", "sft_examples_cap": 256, "pairs_cap": 128, "seeds_finalists": [41, 73, 101], "same_sft_reference_pairs_and_completion_token_budgets": True, "thinking": False, "tool_rounds": 8, "generated_tokens_per_task": 2048, "context_tokens": 2048, "temperature_stop": "device-reported operating target; no universal invented threshold", "duty_monitoring": "temperature/VRAM/power before and after each microbatch; checkpoint/stop on resource failure; maintain original reserve"}, "code_sha256": {relative: digest(ROOT / relative) for relative in ("src/aurora/agent_tasks.py", "src/aurora/agent_taxonomy.py", "src/aurora/agent.py", "src/aurora/tools.py", "src/aurora/state.py")}, "frozen_tool_contract_sha256": digest(ROOT / "config/interface_contracts.json"), "estimand_preserved": "family-macro executable workflow success contrast vs matched prompt-only; separate proposal, host-blocked and committed violations", "limitations": ["Manually curated executable graphs are not a random population sample of all operators/tasks", "Nine semantic groups share one host/generator; worst-case shared-generator dependence sensitivity is one unit", "Clock/counter/reservation scenarios are explicitly synthetic local fixtures, not empirical campaign observations", "Delay or root-cause mechanism is not identified from public pending/supply counters; diagnoses are bounded descriptive checks", "The numerical S1 policy sweep and frozen empirical confirmations are untouched"]}
    manifest = immutable_json(ROOT / "reports/agent/taxonomy_freezes", report)
    atomic_json(study.directory / "result.json", report)
    atomic_json(pointer_path, {"artifact": str(manifest), "sha256": digest(manifest), "version": report["version"], "family_split": report["family_split"], "effective_dependence_groups": split_groups, "scientific_status": "UNDERPOWERED"})
    atomic_json(ROOT / "config/agent_taxonomy_v2.json", report)
    study.ledger.update("E10_TOOLS", "CHECKPOINTED", science="UNDERPOWERED", artifacts=(manifest, historical_path), reason="Prospective V2 freeze; unused V1 corpus preserved/retired, revised corpus and qualification required before substantive training", capabilities={"AGENT_TASKS_READY": False})
    study.export_state()
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a", encoding="utf-8") as output:
        output.write(f"\n## Prospective agent taxonomy correction (user-directed, pre-training)\n\nPreserved V1 audit `{historical_path}`. Froze V2 `{manifest}` with{n} final dependence groups, not80 or400 independent prompts. Planning power{nominal['power']:.6f} for10pp contrast/25pp paired-familySD; status UNDERPOWERED. No substantive training/final outcomes existed; E09 sweep is unchanged. Model screening uses1.7B; only qualified finalists transfer to4B.\n")
    print(json.dumps({"artifact": str(manifest), "preserved_audit": str(historical_path), "effective_final_groups": n, "prospective_reference_power": nominal["power"], "status": "UNDERPOWERED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
