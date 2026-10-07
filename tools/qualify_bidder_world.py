#!/usr/bin/env python3
"""Full-horizon compatibility against immutable old physics; no final worlds."""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.simulator import FAMILIES, StaticController, WorldSpec, run_world
from aurora.fast_bidder import FixedBidder
from aurora.auction_dataset import AuctionCollector
from aurora.state import Action
from aurora.studies import Study

ORIGINAL_SHA = "baf0e3e02c261188c7ef35c731193f95f87b6bcbf0a05c393ef49ceeb4bc544a"
ORIGINAL_PATH = Path("/home/bjw-0/.local/share/aurora-ads/runs/e09_policy_repair_archive_1790907924656688978/original_evidence/src/aurora/simulator.py")


def qualify_one(item):
    family, mode, action, bid = item
    if digest(ORIGINAL_PATH) != ORIGINAL_SHA:
        raise ValueError("Archived independent old physics identity changed")
    module_spec = importlib.util.spec_from_file_location("aurora._archived_physics_reference", ORIGINAL_PATH)
    original = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = original
    module_spec.loader.exec_module(original)
    world_args = {"world_id": "bidder_compat_" + family + mode + action.value, "family": family, "payment_mode": mode, "stage": "validation", "parameter_index": 16 + FAMILIES.index(family)}
    archived = original.run_world(original.WorldSpec(**world_args), StaticController(action), base_bid=bid)
    constant = run_world(WorldSpec(**world_args), StaticController(action), base_bid=bid)
    collector = AuctionCollector()
    callback = run_world(WorldSpec(**world_args), StaticController(action), bidder=FixedBidder(bid), auction_observer=collector.observe_auction)
    if asdict(archived) != asdict(constant) or asdict(archived) != asdict(callback):
        raise ValueError("No-callback/optional fixed bidder changed completed-episode physics")
    data = collector.dataset()
    if len(data.cohort_ids) != 8 * 14 * 96 or abs(float(data.payment.sum()) - callback.spend) > 1e-8:
        raise ValueError("Mature auction lineage or observed spend does not reconcile")
    return {"world": world_args, "bid": bid, "action": action.value, "archived_constant_optional_exact": True, "evaluation": asdict(callback), "observed_auction_cohorts": len(data.cohort_ids), "observed_opportunities": len(data.origin_ids), "elapsed_horizon_days": 14, "maturation_days": 7, "final_worlds_scored": 0}


def main():
    study = Study(ROOT, "full_horizon_bidder_physics_qualification")
    started = time.perf_counter()
    matrix = [(family, mode, action, bid) for family in FAMILIES for mode in ("first_price", "second_price") for action, bid in ((Action.NO_CHANGE, .25), (Action.BID_MULTIPLIER_UP, 1.))]
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as pool:
        rows = list(pool.map(qualify_one, matrix))
    report = {"status": "FULL_HORIZON_PHYSICS_COMPATIBILITY_PASSED", "rows": rows, "workers": 2, "archived_simulator_sha256": ORIGINAL_SHA, "current_simulator_sha256": digest(ROOT / "src/aurora/simulator.py"), "code_sha256": {relative: digest(ROOT / relative) for relative in ("tools/qualify_bidder_world.py", "src/aurora/auction_context.py", "src/aurora/auction_settlement.py", "src/aurora/fast_bidder.py", "src/aurora/auction_learning.py", "src/aurora/auction_dataset.py")}, "wall_seconds": time.perf_counter() - started, "limitations": ["Compatibility/reference qualification, not learned bidder efficacy or calibrated model evidence", "Development validation blocks only; no final policy outcomes", "Observed auction value is recorded exposure value, not evaluator organic/incremental truth"]}
    atomic_json(study.directory / "result.json", report)
    export = ROOT / "reports/simulator" / (study.name + ".json")
    atomic_json(export, report)
    atomic_json(ROOT / "reports/simulator/BIDDER_PHYSICS_QUALIFICATION.json", {"artifact": str(export), "sha256": digest(export)})
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
