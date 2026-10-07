#!/usr/bin/env python3
"""Independent numerical Monte Carlo; no empirical/final outcomes are opened."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from scipy.stats import t

from aurora.artifacts import atomic_json
from aurora.inference import paired_cluster_estimate, superiority_power
from aurora.studies import Study


def main():
    study = Study(ROOT, "statistics_reference_qualification")
    started = time.perf_counter()
    random = np.random.default_rng(984173)
    replicates, bootstrap_draws = 2000, 1000
    covered = claimed = 0
    strata = [str(number // 10) for number in range(40)]
    shifts = np.repeat(np.array([-.006, -.002, .002, .006]), 10)
    for number in range(replicates):
        # Known zero-sum stratum offsets; genuinely new independent Gaussian
        # units each replicate. These are references, not simulator policy data.
        effects = .02 + shifts + random.normal(0, .025, 40)
        result = paired_cluster_estimate([str(index) for index in range(40)], effects[:, None], np.zeros((40, 1)), strata=strata, bootstrap_draws=bootstrap_draws, seed=2000 + number)
        covered += int(result.lower <= .02 <= result.upper)
        planning = random.normal(.1, .25, 9)
        lower = planning.mean() - t.ppf(.975, 8) * planning.std(ddof=1) / 3
        claimed += int(lower > 0)
    coverage = covered / replicates
    power = claimed / replicates
    expected_power = superiority_power(9, .25, alternative=.1, null_boundary=0.)
    passed = .925 <= coverage <= .975 and abs(power - expected_power) <= .035
    report = {"status": "NUMERICAL_QUALIFIED" if passed else "FAILED_NUMERICAL_GATE", "passed": passed, "seed": 984173, "replicates": replicates, "bootstrap_draws_per_reference": bootstrap_draws, "primary_estimator_default_bootstrap_draws": 10000, "gaussian_stratified40_unit_coverage": coverage, "coverage_gate": [.925, .975], "nine_unit_paired_t_empirical_power": power, "analytic_noncentral_t_power": expected_power, "absolute_power_tolerance": .035, "wall_seconds": time.perf_counter() - started, "scope": "Synthetic Gaussian numerical reference only; not S1 policy confirmation or A1 model scoring", "empirical_or_final_outcomes_loaded": 0, "limitations": ["Normal planning variance model need not describe bounded family successes", "Percentile bootstrap small-cluster and convenience-population limitations persist", "Monte Carlo tolerance is a numerical diagnostic, not a scientific superiority threshold"]}
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/environment" / (study.name + ".json")
    atomic_json(export, report)
    print(json.dumps({"status": report["status"], "artifact": str(export), "coverage": coverage, "power": power}))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
