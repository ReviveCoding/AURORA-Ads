#!/usr/bin/env python3
"""Resumable fully mature observable auction collection; no latent training labels."""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from aurora.artifacts import atomic_json, digest, immutable_json
from aurora.auction_dataset import AuctionCollector
from aurora.fast_bidder import RandomizedGridBidder
from aurora.resources import storage_admission
from aurora.simulator import FAMILIES, StaticController, WorldSpec, run_world
from aurora.studies import Study


def observed_archive_payload(data):
    """Only declared observable arrays; evaluator sidecar cannot enter by merging."""
    return {"context": data.context, "submitted_bid": data.submitted_bid, "eligible": data.eligible, "won": data.won, "payment": data.payment, "observed_gross": data.observed_gross, "executed_bid_probability": data.executed_bid_probability, "origin_id": np.asarray(data.origin_ids)}


def collect_world(task):
    number, stage, mode, directory, protocol_sha = task
    destination = Path(directory) / f"{stage}_{number}"
    if destination.is_symlink():
        raise ValueError("World destination cannot be a symlink")
    destination.mkdir(exist_ok=True)
    existing = destination / "manifest.json"
    if existing.exists():
        record = json.loads(existing.read_text())
        identity = "fast_bid_observed_" + mode + "_" + stage + "_" + str(number)
        files = ("observed_arrays", "mature_clocks", "evaluator_only")
        if record["protocol_sha256"] != protocol_sha or record["world_id"] != identity or record["stage"] != stage or record["payment_mode"] != mode or any(Path(record[key]["path"]).resolve().parent != destination.resolve() or digest(Path(record[key]["path"])) != record[key]["sha256"] for key in files):
            raise ValueError("Existing collected world changed; no silent recollection")
        return record
    if any(destination.iterdir()):
        raise ValueError("Unfinished world evidence preserved; no silent orphan overwrite")
    started = time.perf_counter()
    collector = AuctionCollector()
    clocks = []
    def observe(row):
        collector.observe_auction(row)
        clocks.append({"cohort_id": row.cohort_id, "origin_interval": row.origin_interval, "observed_at_day": row.observed_at_day})
    identity = "fast_bid_observed_" + mode + "_" + stage + "_" + str(number)
    block = (0 if stage == "train" else 32) + number
    spec = WorldSpec(identity, FAMILIES[number % 4], payment_mode=mode, stage=stage, parameter_index=block)
    evaluation = run_world(spec, StaticController(), bidder=RandomizedGridBidder(identity, seed=735), auction_observer=observe)
    data = collector.dataset()
    if len(data.cohort_ids) != 8 * 14 * 96 or len(clocks) != len(data.cohort_ids) or data.executed_bid_probability is None:
        raise ValueError("Complete unique origin cohort lineage and actual logging probabilities required")
    # Economic counterfactual results never enter this learner array archive.
    target = destination / "observed_arrays.npz"
    np.savez_compressed(target, **observed_archive_payload(data))
    clock_path = destination / "mature_cohort_clocks.json"
    atomic_json(clock_path, clocks)
    evaluator_path = destination / "evaluator_only.json"
    atomic_json(evaluator_path, {"evaluation": asdict(evaluation), "utility": evaluation.utility, "permitted_use": "physics/whole-world evaluator only; never learner target or public per-impression ground truth"})
    record = {"world_id": identity, "stage": stage, "parameter_block": block, "payment_mode": mode, "protocol_sha256": protocol_sha, "observed_arrays": {"path": str(target), "sha256": digest(target)}, "mature_clocks": {"path": str(clock_path), "sha256": digest(clock_path)}, "evaluator_only": {"path": str(evaluator_path), "sha256": digest(evaluator_path)}, "cohorts": len(data.cohort_ids), "opportunities": len(data.origin_ids), "eligible_positive_submissions": int(data.eligible.sum()), "exposures": int(data.won.sum()), "recorded_purchases": int(np.count_nonzero(data.observed_gross)), "wall_seconds": time.perf_counter() - started, "not_final_worlds": True}
    atomic_json(existing, record)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payment-mode", choices=["first_price", "second_price"], required=True)
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    study = Study(ROOT, "fast_bidder_observed_collection")
    started = time.perf_counter()
    qualification_pointer = json.loads((ROOT / "reports/simulator/BIDDER_PHYSICS_QUALIFICATION.json").read_text())
    qualification_path = Path(qualification_pointer["artifact"])
    if digest(qualification_path) != qualification_pointer["sha256"]:
        raise ValueError("Full-world physics qualification changed")
    qualification = json.loads(qualification_path.read_text())
    if qualification["status"] != "FULL_HORIZON_PHYSICS_COMPATIBILITY_PASSED" or qualification["current_simulator_sha256"] != digest(ROOT / "src/aurora/simulator.py"):
        raise ValueError("Actual current simulator whole-world qualification required")
    cpu_paths = sorted((ROOT / "reports/environment").glob("cpu_qualification_*.json"))
    cpu = json.loads(cpu_paths[-1].read_text())
    cpu_paths_checked = ("src/aurora/simulator.py", "tools/fast_bidder_collect.py", "src/aurora/auction_dataset.py", "src/aurora/auction_context.py", "src/aurora/auction_settlement.py", "src/aurora/fast_bidder.py")
    if cpu["status"] != "CPU_QUALIFIED" or any(cpu["code_sha256"].get(relative) != digest(ROOT / relative) for relative in cpu_paths_checked):
        raise ValueError("Coherent full CPU regression after simulator extension required")
    contract = json.loads((ROOT / "config/resources.json").read_text())
    storage = storage_admission(study.runtime, ROOT, expected_growth_bytes=512 * 1024**2, contract=contract)
    source_files = ("tools/fast_bidder_collect.py", "src/aurora/simulator.py", "src/aurora/auction_context.py", "src/aurora/auction_settlement.py", "src/aurora/auction_learning.py", "src/aurora/auction_dataset.py", "src/aurora/fast_bidder.py", "reports/design/FAST_BIDDER_STUDY_PROTOCOL.md")
    protocol = {"version": "OBSERVED_AUCTION_COLLECTION_V1", "payment_mode": args.payment_mode, "train_blocks": list(range(4)), "calibration_blocks": list(range(32, 36)), "families": list(FAMILIES), "campaigns": 8, "decision_intervals": 1344, "maturation_days": 7, "nominal_arrivals": 32, "budget_per_campaign": 10000, "slow_action": "NO_CHANGE", "fast_proposal": "uniform_declared_8_grid_seed735_exact_executed_mass", "workers": 2, "source_sha256": {relative: digest(ROOT / relative) for relative in source_files}, "physics_sha256": qualification_pointer["sha256"], "cpu_qualification_sha256": digest(cpu_paths[-1]), "final_worlds_scored": 0}
    if args.resume is not None:
        directory = args.resume.resolve()
        if not directory.is_relative_to(study.runtime / "runs") or args.resume.is_symlink() or not directory.name.startswith("fast_bidder_observed_collection_") or json.loads((directory / "protocol.json").read_text()) != protocol:
            raise ValueError("Unchanged owned protocol collection required for resume")
        study.directory, study.name = directory, directory.name
    else:
        atomic_json(study.directory / "protocol.json", protocol)
    protocol_sha = digest(study.directory / "protocol.json")
    tasks = [(number, stage, args.payment_mode, str(study.directory), protocol_sha) for stage in ("train", "calibration") for number in range(4)]
    records = []
    try:
        with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as pool:
            for record in pool.map(collect_world, tasks):
                records.append(record)
                atomic_json(study.directory / "progress.json", {"status": "RUNNING", "completed": len(records), "total": len(tasks), "records": records, "protocol_sha256": protocol_sha})
        report = {"status": "MATURE_OBSERVED_AUCTION_COLLECTION_EXECUTED", "protocol": protocol, "protocol_sha256": protocol_sha, "worlds": records, "storage_admission": storage, "wall_seconds": time.perf_counter() - started, "limitations": ["Synthetic observed-auction evidence, not randomized real ad lift or public-data value calibration", "Collection only; value/price fits and full-world bidder selection still required", "Four TRAIN and four CAL worlds do not establish independent external mechanism generalization"]}
        atomic_json(study.directory / "result.json", report)
        export = ROOT / "reports/policy" / (study.name + ".json")
        atomic_json(export, report)
        atomic_json(ROOT / "reports/policy" / (args.payment_mode + "_OBSERVED_AUCTION_COLLECTION.json"), {"artifact": str(export), "sha256": digest(export)})
        print(json.dumps({"status": report["status"], "artifact": str(export)}))
        return 0
    except Exception as error:
        failure = immutable_json(study.directory / "failed_attempts", {"type": type(error).__name__, "message": str(error), "protocol_sha256": protocol_sha, "returned_completed_worlds": len(records), "wall_seconds": time.perf_counter() - started, "resume_requires_exact_protocol": True})
        atomic_json(study.directory / "FAILURE_LATEST.json", {"artifact": str(failure), "sha256": digest(failure)})
        raise


if __name__ == "__main__":
    raise SystemExit(main())
