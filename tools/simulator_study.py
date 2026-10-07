#!/usr/bin/env python3
"""E07 qualification, oracle isolation, known-effect/null statistical controls."""
from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from scipy.stats import t

from aurora.artifacts import atomic_json, digest
from aurora.simulator import BLOCK_STAGES, FAMILIES, MaturedObservation, Snapshot, StaticController, WorldSpec, rng, run_world
from aurora.studies import Study


class RandomizedCollector:
    policy_seed = 731

    def __init__(self):
        self.rows = []

    def probabilities(self, snapshot):
        p = np.full(6, .1 / 6)
        p[0] += .9
        return p

    def observe(self, row):
        self.rows.append(row)


def main():
    study = Study(ROOT, "e07_simulator_qualification")
    study.ledger.update("E07", "RUNNING", reason="Full synthetic clock/cohort/oracle/block qualification; no policy superiority claim")
    declaration = json.loads((ROOT / "config/simulator_blocks.json").read_text())
    assert declaration["stage_blocks"] == {name: list(bounds) for name, bounds in BLOCK_STAGES.items()}
    catalog = []
    for index in range(80):
        entry = {"block_index": index, "organic_campaign_shock": [], "weak_delta": [], "segment_offsets": []}
        for campaign in range(8):
            entry["organic_campaign_shock"].append(float(rng(declaration["catalog_world_key"], campaign, index, "organic_campaign_shock").uniform(-.03, .03)))
            parameters = rng(declaration["catalog_world_key"], campaign, index, "campaign_parameters")
            entry["weak_delta"].append(float(parameters.choice([-.25, 0, .25])))
            entry["segment_offsets"].append(rng(declaration["catalog_world_key"], campaign, index, "campaign_parameters").uniform(-.2, .2, 5).tolist())
        catalog.append(entry)
    assert len({json.dumps(entry["organic_campaign_shock"]) for entry in catalog}) == 80
    atomic_json(study.directory / "evaluator_only_parameter_catalog.json", {"catalog": catalog, "stage_blocks": declaration["stage_blocks"]})
    forbidden = {"family", "fault", "delta", "oracle", "true_effect", "true_reward", "organic_value", "parameter_index", "ood_mechanism"}
    assert not forbidden & set(Snapshot.__dataclass_fields__)
    assert not forbidden & set(MaturedObservation.__dataclass_fields__)
    full = []
    for number, family in enumerate(FAMILIES):
        collector = RandomizedCollector()
        spec = WorldSpec(f"qualification-full-{family}", family, stage="train", parameter_index=number)
        evaluated = run_world(spec, collector)
        assert len(collector.rows) == 8 * 14 * 96
        assert len({row.cohort_id for row in collector.rows}) == len(collector.rows)
        assert all(row.observed_at_day >= (row.origin_interval + 1) / 96 + 7 and row.horizon_complete and row.receipt_available for row in collector.rows)
        assert all(row.executed_probability is not None and 0 < row.executed_probability <= 1 for row in collector.rows)
        assert evaluated.final_pending_exposures == 0 and evaluated.snapshot_reward_updates_before_day7 == 0
        assert evaluated.spend + evaluated.operating_cost <= evaluated.initial_budget
        gross = sum(row.observed_gross_value for row in collector.rows)
        actual_spend = sum(row.actual_spend for row in collector.rows)
        assert abs(actual_spend - evaluated.spend) < 1e-6
        full.append(asdict(evaluated) | {"utility": evaluated.utility, "observed_exposed_gross_value": gross, "cohort_rows": len(collector.rows), "logging_probability_counts": {str(p): sum(row.executed_probability == p for row in collector.rows) for p in sorted({row.executed_probability for row in collector.rows})}})
    nulls, signs = [], []
    for index in range(16):
        spec = WorldSpec(f"null-control-{index}", "weak_or_no_heterogeneity", campaigns=2, intervals=96, effect_override=0., stage="smoke")
        result = run_world(spec, StaticController())
        assert result.unique_purchase_value == result.no_ad_purchase_value
        assert abs(result.utility + (result.spend + result.operating_cost) / result.initial_budget) < 1e-12
        nulls.append(asdict(result) | {"utility": result.utility})
        if index < 8:
            positive = run_world(WorldSpec(f"signed-{index}", spec.family, campaigns=2, intervals=96, effect_override=1., stage="smoke"), StaticController())
            negative = run_world(WorldSpec(f"signed-{index}", spec.family, campaigns=2, intervals=96, effect_override=-1., stage="smoke"), StaticController())
            assert positive.unique_purchase_value >= positive.no_ad_purchase_value and negative.unique_purchase_value <= negative.no_ad_purchase_value
            signs.append({"positive_value_minus_noad": positive.unique_purchase_value - positive.no_ad_purchase_value, "negative_value_minus_noad": negative.unique_purchase_value - negative.no_ad_purchase_value})
    aa_spec = WorldSpec("aa-paired", FAMILIES[1], campaigns=2, intervals=96, stage="smoke")
    assert run_world(aa_spec, StaticController()) == run_world(aa_spec, StaticController())
    noad = run_world(aa_spec, StaticController(), no_ad=True)
    assert noad.utility == 0 and noad.spend == 0 and noad.operating_cost == 0
    # A distinct closed-form purchase generator, not candidate architecture or S1.
    # Common potential-outcome U implies incremental purchase count Binomial(100,.05).
    random = np.random.default_rng(715)
    counts = random.binomial(100, .05, size=(2000, 40))
    utilities = (2 * counts - 6) / 200
    known = (100 * .05 * 2 - 6) / 200
    means = utilities.mean(1)
    widths = t.ppf(.975, 39) * utilities.std(1, ddof=1) / math.sqrt(40)
    coverage = float(np.mean((means - widths <= known) & (means + widths >= known)))
    assert .925 <= coverage <= .975
    misspecified = run_world(WorldSpec("qualification-additive-misspecified", FAMILIES[1], stage="ood", parameter_index=16, ood_mechanism="additive_misspecified"), StaticController())
    report = {"status": "SIMULATOR_ENGINEERING_QUALIFIED", "scientific_outcome": "NOT_RUN", "source_domain": "S1_SYNTHETIC", "simulator_sha256": digest(ROOT / "src/aurora/simulator.py"), "declaration_sha256": digest(ROOT / "config/simulator_blocks.json"), "parameter_catalog_sha256": digest(study.directory / "evaluator_only_parameter_catalog.json"), "whole_parameter_blocks_disjoint": True, "oracle_observation_schema_isolated": True, "full_four_family_randomized_worlds": full, "null_controls": nulls, "signed_controls": signs, "same_policy_AA_exact": True, "noad_exact_zero": True, "independent_closed_form_purchase_generator": {"trials": 2000, "independent_worlds_per_trial": 40, "true_normalized_utility": known, "empirical_ci_coverage": coverage, "method": "world-level Student-t interval, independent Binomial incremental-purchase worlds", "scope": "Known-generator estimator diagnostic, not proof adaptive S1 policy intervals are calibrated in every regime"}, "misspecified_generator": asdict(misspecified) | {"utility": misspecified.utility}, "limitations": ["Synthetic transparent design, not digital twin or real causal fidelity", "Qualification does not establish H_policy", "Four randomized qualification worlds are not policy training/test replication units", "Final generation still requires frozen artifact binding current simulator", "Observation model reports exposed purchase value, not evaluator organic potential outcomes"]}
    artifact = study.finish("E07", report, "simulator", science="NOT_RUN", capabilities={"S1_SIMULATOR_QUALIFIED": True, "mock_executor": True, "exact_executed_propensity": True, "observed_matured_reward_only": True})
    print(json.dumps({"status": "EXECUTED", "artifact": str(artifact)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
