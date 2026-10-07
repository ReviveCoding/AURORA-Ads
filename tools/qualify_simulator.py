#!/usr/bin/env python3
"""Development-only full-horizon smoke and independent statistical reference controls."""
from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from scipy.stats import t
from aurora.artifacts import atomic_json, digest
from aurora.simulator import FAMILIES, StaticController, WorldSpec, run_world


def main() -> int:
    start = time.perf_counter()
    results = []
    for family in FAMILIES:
        spec = WorldSpec(f"development-reference-{family}", family)
        result = run_world(spec, StaticController())
        record = asdict(result) | {"utility": result.utility}
        assert record["matured_cohorts"] == 8 * 14 * 96
        assert record["snapshot_reward_updates_before_day7"] == 0
        assert record["spend"] + record["operating_cost"] <= record["initial_budget"]
        assert record["final_pending_exposures"] == 0
        results.append(record)
    # Independent simple parametric reference, not the S1 equations/candidate.
    # This checks interval coverage only; it is not policy uncertainty qualification.
    random = np.random.default_rng(712)
    samples = random.normal(.02, .04, (2000, 40))
    means = samples.mean(1)
    half_width = t.ppf(.975, 39) * samples.std(1, ddof=1) / math.sqrt(40)
    covered = np.sum((means - half_width <= .02) & (means + half_width >= .02))
    coverage = covered / len(samples)
    assert .925 <= coverage <= .975
    report = {"status": "DEVELOPMENT_REFERENCE_EXECUTED_NOT_POLICY_QUALIFIED", "evidence_domain": "S1_ENGINEERING", "config_sha256": digest(ROOT / "config/simulator.json"), "implementation_sha256": digest(ROOT / "src/aurora/simulator.py"), "full_horizon_reference_worlds": results, "independent_normal_reference_coverage": {"trials": len(samples), "worlds_per_trial": 40, "known_mean": .02, "coverage": coverage, "method": "two-sided paired-mean t interval; independent normal reference only"}, "wall_seconds": time.perf_counter() - start, "limitations": ["No learned controller or action-value warm-start", "No train/validation/final mechanism-block qualification yet", "No H_policy inference", "No source-marginal anchoring or realism claim", "No GPU execution"], "next_gates": ["development mechanism blocks and randomized S1 data", "incident detector roster", "full policy roster and observed-cohort callbacks", "Monte Carlo S1 estimator/cluster coverage", "freeze before final generation"]}
    runtime = Path.home() / ".local/share/aurora-ads"
    directory = runtime / "runs" / f"simulator_reference_{time.time_ns()}"
    atomic_json(directory / "qualification.json", report)
    export = ROOT / "reports/simulator" / (directory.name + ".json")
    atomic_json(export, report)
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a") as stream:
        stream.write(f"\n## Full-horizon simulator development reference\n\nCommand `{sys.executable} tools/qualify_simulator.py`; wall {report['wall_seconds']:.3f}s; evidence `{export}`. Four reference worlds only; H_policy NOT_RUN.\n")
    print(json.dumps({"status": report["status"], "wall_seconds": report["wall_seconds"], "artifact": str(export)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
