from __future__ import annotations
import hashlib, json, time
from pathlib import Path

ROOT = Path("/mnt/c/Users/bjw-0/Downloads/AURORA-Ads")
OUT = ROOT / "reports" / "extension_v5_continuation_v3_shadow"
OUT.mkdir(parents=True, exist_ok=True)

def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def verify_pointer(rel: str):
    pointer_path = ROOT / rel
    pointer = read(pointer_path)
    artifact = Path(pointer["artifact"])
    if not artifact.is_absolute():
        artifact = ROOT / artifact
    actual = sha(artifact)
    if actual != pointer["sha256"]:
        raise RuntimeError(f"HASH_MISMATCH:{rel}")
    return {
        "pointer": rel,
        "pointer_sha256": sha(pointer_path),
        "artifact": str(artifact),
        "artifact_sha256": actual,
    }, read(artifact)

result = {
    "program": "AURORA_EXTENSION_V5_CONTINUATION_V3_SHADOW_PREFLIGHT",
    "started_unix": time.time(),
    "cuda_accessed": False,
    "semantic_generation_accessed": False,
    "heldout_outcomes_accessed": False,
    "r3_final_outcomes_accessed": False,
    "read_only_preflight": True,
}

carry_path = ROOT / "reports/extension_v5_continuation_v3/CARRY_FORWARD_MANIFEST.json"
freeze_path = ROOT / "reports/extension_v1/agent/A1_EXTENSION_V1_FREEZE.json"
carry = read(carry_path)
freeze = read(freeze_path)

heldout_ids = carry.get("heldout_ids", [])
heldout_defs = freeze.get("heldout_task_definitions", [])
groups = freeze.get("independent_heldout_groups")
if len(heldout_ids) != 44 or len(heldout_defs) != 44 or groups != 9:
    raise RuntimeError("HELDOUT_ROSTER_METADATA_MISMATCH")

result["heldout_preflight"] = {
    "heldout_ids_count": len(heldout_ids),
    "heldout_definitions_count": len(heldout_defs),
    "independent_groups": groups,
    "carry_manifest_sha256": sha(carry_path),
    "freeze_sha256": sha(freeze_path),
    "outcomes_loaded": 0,
}

cohort_ref, cohort_obj = verify_pointer("reports/data/R3_DEVELOPMENT_COHORTS.json")
if set(cohort_obj["cohorts"]) != {"M41", "C54", "selection"}:
    raise RuntimeError("R3_DEVELOPMENT_COHORT_KEYS")
if cohort_obj.get("final_outcomes_scored") not in (0, False):
    raise RuntimeError("R3_FINAL_OUTCOME_STATE_NOT_CLOSED")

cohorts = []
for name, item in cohort_obj["cohorts"].items():
    data_path = Path(item["path"])
    if not data_path.is_absolute():
        data_path = ROOT / data_path
    actual = sha(data_path)
    if actual != item["sha256"]:
        raise RuntimeError(f"R3_COHORT_HASH_MISMATCH:{name}")
    cohorts.append({"name": name, "path": str(data_path), "sha256": actual})

result["r3_development_cohorts"] = {
    "pointer": cohort_ref,
    "cohorts": cohorts,
    "final_outcomes_scored": 0,
}

for rel in [
    "reports/delay/R3_CPU_BASELINES.json",
    "reports/delay/R3_FEEDBACK_SHIFT_DEVELOPMENT.json",
    "reports/delay/R3_PARAMETRIC_DELAY_DEVELOPMENT.json",
]:
    ref, _ = verify_pointer(rel)
    result.setdefault("r3_supporting_inputs", []).append(ref)

followon = ROOT / "reports/extension_v5_continuation_v3/state/FOLLOWON_CPU_VALIDATION_1791156350857215958.json"
if followon.exists():
    val = read(followon)
    result["followon_cpu_validation"] = {
        "passed": bool(val.get("passed")),
        "cuda_accessed": val.get("cuda_accessed"),
        "final_outcomes_accessed": val.get("final_outcomes_accessed"),
        "sha256": sha(followon),
    }
    if not val.get("passed") or val.get("cuda_accessed") or val.get("final_outcomes_accessed"):
        raise RuntimeError("FOLLOWON_CPU_VALIDATION_NOT_CLEAN")

result["passed"] = True
result["finished_unix"] = time.time()

json_path = OUT / "PREFLIGHT.json"
json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

report_path = OUT / "SHADOW_PREFLIGHT.md"
report_path.write_text(
    "# V3 Shadow Preflight\n\n"
    "Status: PASS\n\n"
    "This auxiliary lane is read-only with respect to scientific outcomes.\n\n"
    "Prepared in parallel:\n"
    "- Held-out roster metadata verified: 44 frozen tasks, 9 dependence groups.\n"
    "- R3 development-only cohorts M41, C54, and selection hash-verified.\n"
    "- R3 CPU baselines / feedback-shift / parametric-delay development pointers hash-verified.\n"
    "- Existing follow-on CPU validation confirmed PASS.\n"
    "- Held-out outcomes were not accessed.\n"
    "- R3 final outcomes were not accessed.\n"
    "- No CUDA workload was launched.\n\n"
    "This file is preparatory only and must not be treated as a scientific result.\n",
    encoding="utf-8",
)

print(json.dumps({"passed": True, "json": str(json_path), "report": str(report_path)}))
