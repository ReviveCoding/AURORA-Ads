#!/usr/bin/env python3
"""Freeze bounded learning inputs before any preference training/model scoring."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest, immutable_json
from aurora.studies import Study


def main():
    study = Study(ROOT, "agent_recipe_profile_freeze")
    if (ROOT / "reports/agent/DEV_RECIPE_SELECTION.json").exists() or any((ROOT / "reports/agent").glob("e10_agent_train_dpo_*.json")) or any((ROOT / "reports/agent").glob("e10_agent_train_ipo_*.json")):
        raise ValueError("Do not change the prospective learning profile after recipe outcomes/training")
    profile_path = ROOT / "config/agent_recipe_profile.json"
    profile = json.loads(profile_path.read_text())
    artifact = immutable_json(ROOT / "reports/agent/recipe_profiles", {"profile": profile, "config_sha256": digest(profile_path), "taxonomy_freeze": json.loads((ROOT / "reports/agent/TAXONOMY_V2_FREEZE.json").read_text()), "frozen_before_preference_training_and_model_scoring": True})
    pointer = {"artifact": str(artifact), "sha256": digest(artifact), "config_sha256": digest(profile_path), "frozen_before_preference_training_and_model_scoring": True}
    destination = ROOT / "reports/agent/RECIPE_PROFILE_FREEZE.json"
    if destination.exists() and json.loads(destination.read_text()) != pointer:
        raise ValueError("Existing prospective profile differs; preserve history and refuse overwrite")
    atomic_json(destination, pointer)
    atomic_json(study.directory / "result.json", pointer)
    print(json.dumps(pointer))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
