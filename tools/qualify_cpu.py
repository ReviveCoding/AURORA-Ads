#!/usr/bin/env python3
"""CPU-only candidate imports/numerics/one-update; never implies GPU qualification."""
from __future__ import annotations

import importlib
import importlib.metadata
import json
import platform
import subprocess
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest


def main() -> int:
    runtime = Path.home() / ".local/share/aurora-ads"
    report = {"python": platform.python_version(), "stage": "CPU", "GPU_QUALIFIED": False, "imports": {}, "tests": []}
    started = time.perf_counter()
    for module in ("numpy", "scipy", "pandas", "pyarrow", "duckdb", "sklearn", "fastapi", "pydantic", "pytest", "matplotlib"):
        loaded = importlib.import_module(module)
        report["imports"][module] = getattr(loaded, "__version__", "imported")
    import numpy as np
    from sklearn.linear_model import SGDClassifier
    x = np.array([[0., 0.], [1., 1.], [0., 1.], [1., 0.]])
    model = SGDClassifier(loss="log_loss", random_state=11)
    model.partial_fit(x, [0, 1, 0, 1], classes=[0, 1])
    assert np.isfinite(model.predict_proba(x)).all()
    report["one_update"] = "PASSED_CPU_SKLEARN_FIXTURE_NOT_EXPERIMENT"
    run = runtime / "runs" / f"cpu_qualification_{time.time_ns()}"
    run.mkdir()
    lint_paths = ["src", "tools/run_node.py", "tools/source_metadata.py", "tools/bootstrap_cpu.py", "tools/admit_source.py", "tools/batch_admit.py", "tools/audit_sources.py", "tools/qualify_cpu.py", "tools/qualify_simulator.py", "tools/checkpoint.py", "tools/mcp_server.py", "tests/test_workflow.py", "tests/test_numerical.py", "tests/test_state.py", "tests/test_simulator.py", "tests/test_tools.py"]
    lint_paths += ["tools/freeze_agent_confirmation.py", "tools/agent_confirmation.py", "tests/test_agent_confirmation_plan.py", "tests/test_agent_evidence.py", "tests/test_agent_lifecycle.py", "tests/test_agent_attempt.py", "tests/test_agent_ledger_admission.py"]
    lint_paths += ["tools/mcp_recovery_study.py", "tools/mcp_recovery_launch.py", "tests/test_mcp_recovery_guard.py"]
    lint_paths += ["tests/test_auction_context.py", "tests/test_agent_render_compat.py"]
    lint_paths += ["tools/qualify_agent_render.py", "tools/qualify_bidder_world.py", "tests/test_simulator_auction.py"]
    lint_paths += ["tools/fast_bidder_collect.py", "tests/test_fast_bidder_collect.py"]
    lint_paths += ["tools/recover_r3_source.py", "tests/test_r3_exception.py"]
    lint_paths += ["tools/policy_ablation_study.py", "tests/test_policy_diagnostics.py"]
    lint_paths += ["tools/admit_r3_clock.py", "tests/test_r3_clock.py"]
    lint_paths += ["tools/diagnose_r3_delay_schema.py", "tests/test_r3_targets.py"]
    lint_paths += ["tools/prepare_r3_development.py", "tests/test_r3_cohort_query.py", "tests/test_r3_exponential.py", "tests/test_r3_missingness.py"]
    lint_paths += ["tools/r3_cpu_baselines.py", "tests/test_r3_cpu_targets.py"]
    lint_paths += ["tools/r3_parametric_delay_study.py", "tests/test_r3_sparse_exponential.py"]
    lint_paths += ["tools/r3_feedback_shift_study.py", "tests/test_r3_feedback_shift.py"]
    lint_paths += ["tools/r3_value_study.py", "tests/test_r3_value_bounds.py", "tools/record_agent_duty_exhaustion.py"]
    lint_paths += ["tools/policy_pilot_study.py", "tests/test_policy_confirmation.py", "tools/freeze_policy_confirmation.py", "tools/policy_confirmation_study.py"]
    lint_paths += ["tools/policy_ablation_analysis.py", "tests/test_policy_ablation_analysis.py"]
    lint_paths += ["tools/policy_negative_diagnosis.py", "tests/test_policy_diagnosis.py"]
    lint_paths += ["tools/inspect_r3_container.py", "tests/test_r3_container.py", "tools/convert_r3_source.py", "tests/test_r3_conversion.py"]
    lint_paths += ["tools/finish_admission.py", "tools/research_run.py", "tools/bootstrap_stage.py", "tools/qualify_gpu.py", "tools/qualify_mcp.py", "tools/model_prepare.py", "tools/qualify_agent_model.py", "tools/ope_study.py", "tools/causal_study.py", "tools/predictive_study.py", "tools/simulator_study.py", "tools/incident_study.py", "tools/policy_study.py", "tests/test_causal.py", "tests/test_ope.py", "tests/test_prediction.py", "tests/test_incidents.py", "tests/test_policies.py"]
    lint_paths += ["tools/agent_data.py", "tools/agent_study.py", "tests/test_agent_tasks.py", "tests/test_posttraining.py"]
    lint_paths += ["tools/freeze_agent_taxonomy.py", "tools/source_blockers.py"]
    lint_paths += ["tools/agent_validation.py"]
    lint_paths += ["tests/test_delay_interfaces.py"]
    lint_paths += ["tests/test_serving.py"]
    lint_paths += ["tests/test_inference.py"]
    lint_paths += ["tools/statistics_qualification.py"]
    lint_paths += ["tools/freeze_agent_recipe_profile.py"]
    lint_paths += ["tests/test_resources.py"]
    lint_paths += ["tools/policy_cost_audit.py"]
    lint_paths += ["tools/data_reports.py"]
    lint_paths += ["tests/test_agent_safety.py"]
    lint_paths += ["tools/verify_training_checkpoint.py"]
    lint_paths += ["tools/qualify_trained_restart.py"]
    lint_paths += ["tools/attribution_study.py", "tests/test_attribution.py"]
    lint_paths += ["tests/test_support.py"]
    lint_paths += ["tests/test_bidder.py"]
    lint_paths += ["tools/policy_support_audit.py"]
    lint_paths += ["tools/qualify_policy_support.py"]
    lint_paths += ["tools/qualify_agent_inference.py"]
    lint_paths += ["tests/test_policy_repairs.py"]
    lint_paths += ["tools/qualify_policy_repairs.py"]
    lint_paths += ["tools/qualify_tokenizer_transfer.py"]
    lint_paths += ["tools/policy_repair_study.py", "tests/test_auction_learning.py"]
    lint_paths += ["tools/completed_track_reports.py"]
    lint_paths += ["tests/test_numerical_policy_state.py"]
    lint_paths += ["tools/qualify_completion_projection.py"]
    lint_paths += ["tests/test_auction_dataset.py"]
    lint_paths += ["tests/test_inference_monitor.py"]
    lint_paths += ["tests/test_numerical_policy_bundle.py"]
    lint_paths += ["tools/clock_audit_report.py"]
    lint_paths += ["tools/verify_evidence_tables.py"]
    lint_paths += ["tests/test_evidence_tables.py"]
    lint_paths += ["tools/build_public_figures.py"]
    lint_paths += ["tests/test_public_figures.py"]
    lint_paths += ["tests/test_agent_evaluation.py"]
    lint_paths += ["tests/test_agent_qualification.py"]
    lint_paths += ["tools/completion_audit.py", "tests/test_completion.py"]
    lint_paths += ["tests/test_agent_case_roster.py"]
    lint_paths += ["tools/qualify_preference_restart.py", "tests/test_preference_restart.py"]
    lint_paths += ["tests/test_agent_result_admission.py"]
    lint_paths += ["tests/test_training_monitor.py"]
    lint_paths += ["tests/test_agent_budget.py"]
    lint_paths += ["tools/agent_budget_audit.py", "tools/agent_ablation_study.py", "tests/test_agent_ablation.py"]
    lint_paths += ["tools/prediction_server.py", "tools/serving_study.py", "tools/qualify_serving_source.py", "tests/test_serving_models.py"]
    lint_paths += ["tests/test_serving_isolation.py"]
    lint_paths += ["tools/serving_cpu_study.py"]
    lint_paths += ["tests/test_serving_cpu_recovery.py"]
    lint_paths += ["tests/test_final_evidence.py"]
    lint_paths += ["tools/prepare_final_evidence.py"]
    lint_paths += ["tools/terminalize_systems.py", "tools/preserve_stalled_serving.py", "tools/build_final_reports.py", "tools/verify_final_package.py"]
    lint_paths += ["tests/test_final_package_exports.py"]
    lint_paths += ["tools/final_manifest_details.py"]
    lint_paths += ["tools/terminalize_resource_tracks.py", "tests/test_resource_dispositions.py"]
    report["code_sha256"] = {str(path.relative_to(ROOT)): digest(path) for path in sorted((ROOT / "src").rglob("*.py"))}
    report["code_sha256"].update({relative: digest(ROOT / relative) for relative in lint_paths if relative.endswith(".py")})
    for command in ([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], [sys.executable, "tools/validate_design.py", "--no-hashes"], [str(Path(sys.executable).parent / "ruff"), "check", *lint_paths]):
        output = run / f"check_{len(report['tests'])}.txt"
        clock = time.perf_counter()
        with output.open("w") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, cwd=ROOT, check=False)
        report["tests"].append({"command": command, "exit_code": result.returncode, "wall_seconds": time.perf_counter() - clock, "output": str(output), "sha256": digest(output)})
    report["wall_seconds"] = time.perf_counter() - started
    passed = all(record["exit_code"] == 0 for record in report["tests"])
    report["status"] = "CPU_QUALIFIED" if passed else "CPU_CHECK_FAILED"
    report["packages"] = sorted(f"{distribution.metadata['Name']}=={distribution.version}" for distribution in importlib.metadata.distributions())
    atomic_json(run / "qualification.json", report)
    atomic_json(ROOT / "reports/environment" / (run.name + ".json"), report)
    export_directory = ROOT / "reports/environment" / run.name
    shutil.copytree(run, export_directory)
    if passed:
        atomic_json(ROOT / "reports/environment/CPU_LOCK.json", {"qualification_sha256": digest(run / "qualification.json"), "python": report["python"], "packages": report["packages"], "notice": "Qualified CPU subset only. GPU/post-training matrix pending."})
    with (ROOT / "IMPLEMENTATION_LOG.md").open("a") as stream:
        stream.write(f"\n## CPU qualification\n\nCommand `{sys.executable} tools/qualify_cpu.py`; status {report['status']}; wall {report['wall_seconds']:.3f}s; evidence `reports/environment/{run.name}.json`; exact qualified CPU package list in CPU_LOCK.json only if passed.\n")
    print(json.dumps({"status": report["status"], "artifact": str(run / "qualification.json")}))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
