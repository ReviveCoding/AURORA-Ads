#!/usr/bin/env python3
"""Public-track figures from verified aggregate CSVs; no new predictions/scoring."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.studies import Study


def point_interval(row):
    point = float(row["estimate"])
    lower, upper = row["ci_lower"], row["ci_upper"]
    if not math.isfinite(point) or (lower == "") != (upper == ""):
        raise ValueError("Finite point and complete-or-unavailable interval required")
    if lower == "":
        return point, None
    lower, upper = float(lower), float(upper)
    if not math.isfinite(lower) or not math.isfinite(upper) or lower > point or point > upper:
        raise ValueError("Stored interval cannot be silently clipped or repaired")
    return point, (lower, upper)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="outputs/01a0f835-9bf7-71e0-b844-8e4f3bc2f7cc")
    args = parser.parse_args()
    directory = (ROOT / args.directory).resolve()
    directory.relative_to(ROOT / "outputs")
    started = time.perf_counter()
    study = Study(ROOT, "verified_public_track_figures")
    manifest = json.loads((directory / "evidence_tables_manifest.json").read_text())
    csv_path = directory / "RESULTS_MATRIX_PROGRESS.csv"
    verification = json.loads((ROOT / "reports/analysis/PROGRESS_CSV_VERIFICATION.json").read_text())
    if not verification["passed"] or digest(Path(verification["artifact"])) != verification["sha256"] or digest(csv_path) != manifest["outputs"][csv_path.name]["sha256"]:
        raise ValueError("Actual saved-file verification and exact CSV identity required")
    check = json.loads(Path(verification["artifact"]).read_text())
    if check["manifest"]["sha256"] != digest(directory / "evidence_tables_manifest.json"):
        raise ValueError("Figure inputs differ from independently verified tables")
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    r1 = [row for row in rows if row["evidence_domain"] == "R1" and row["artifact_location"].startswith("/records/")]
    sensitivities = [row for row in rows if row["result_id"].startswith("R1_paired_vs_") or row["result_id"] == "R1_conventional_time_block_sensitivity"]
    r4 = [row for row in rows if row["evidence_domain"] == "R4"]
    if len(r1) != 9 or len(sensitivities) != 2 or len(r4) != 8 or any(row["scientific_outcome"] != "NOT_ESTABLISHED" for row in r1 + sensitivities) or any(row["scientific_outcome"] != "UNDERPOWERED" or int(row["n_independent_units"]) != 2 for row in r4):
        raise ValueError("Frozen figure roster or status changed")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.ticker import ScalarFormatter

    destination = ROOT / "reports/final/figures" / study.name
    destination.mkdir(parents=True)
    outputs = {}
    with plt.rc_context({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}):
        figure, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1., 1.2]})
        indexes = np.arange(len(r1))
        axes[0].scatter([float(row["estimate"]) for row in r1], indexes, color="#34465a", s=30)
        axes[0].set_yticks(indexes, [row["candidate"] for row in r1])
        axes[0].invert_yaxis()
        axes[0].set_xlabel("Log loss (nats / impression)")
        axes[0].set_title("All frozen candidates; no final reselection", fontsize=11)
        for index, row in enumerate(sensitivities):
            point, lower, upper = (float(row[key]) for key in ("estimate", "ci_lower", "ci_upper"))
            axes[1].errorbar(point, index, xerr=[[point - lower], [upper - point]], fmt="o", color="#34465a", capsize=4)
        axes[1].set_yticks([0, 1], ["UID clusters (292,126)", "Native-time blocks (20)"])
        axes[1].set_xlabel("Paired log-loss difference (nats / impression)")
        axes[1].axvline(0, color="#777777", linewidth=1, linestyle="--")
        axes[1].set_ylim(-.5, 1.5)
        axes[1].set_title("Development-selected DCNv2 minus XGBoost", fontsize=11)
        formatter = ScalarFormatter(useMathText=True)
        formatter.set_powerlimits((-3, -3))
        axes[1].xaxis.set_major_formatter(formatter)
        figure.suptitle("R1 internal temporal benchmark replication", fontsize=13)
        figure.text(.02, .03, "Scientific status: NOT_ESTABLISHED. Prior exposure and cross-cluster dependence limits remain.\nClick prediction only; no purchase-value, incremental lift or production interpretation.", fontsize=9)
        figure.tight_layout(rect=(0, .12, 1, .93))
        for extension in ("png", "svg"):
            target = destination / ("r1_frozen_comparison." + extension)
            figure.savefig(target, dpi=160)
            outputs[target.name] = {"path": str(target), "sha256": digest(target)}
        plt.close(figure)

        figure, axis = plt.subplots(figsize=(10, 5))
        labels = []
        for index, row in enumerate(r4):
            point, interval = point_interval(row)
            if interval is None:
                axis.scatter([point], [index], marker="x", color="#34465a")
            elif row["interval_target"] != "estimate":
                raise ValueError("OPE interval is not a paired policy contrast")
            else:
                lower, upper = interval
                axis.errorbar(point, index, xerr=[[point - lower], [upper - point]], fmt="o", color="#34465a", capsize=4)
            labels.append(row["candidate"] + " / " + row["metric"].upper() + (" (CI unavailable)" if interval is None else ""))
        axis.set_yticks(np.arange(len(r4)), labels)
        axis.invert_yaxis()
        axis.axvline(0, color="#777777", linewidth=1, linestyle="--")
        axis.set_xlabel("Estimated click probability / logged position1 impression")
        axis.set_title("R4 fixed-policy OPE: raw estimates and available cluster intervals", fontsize=12)
        figure.text(.02, .025, "Scientific status: UNDERPOWERED, two final-day clusters. Missing intervals stay unavailable.\nRaw t intervals are not clipped to[0,1]. No adaptive full-budget or joint-slate certificate.", fontsize=9)
        figure.tight_layout(rect=(0, .11, 1, .98))
        for extension in ("png", "svg"):
            target = destination / ("r4_raw_ope_uncertainty." + extension)
            figure.savefig(target, dpi=160)
            outputs[target.name] = {"path": str(target), "sha256": digest(target)}
        plt.close(figure)
    metrics = {"R1_all_candidates": r1, "R1_clustering_sensitivities": sensitivities, "R4_raw_OPE": r4}
    atomic_json(destination / "figure_metrics.json", metrics)
    report = {"status": "VALIDATED_PUBLIC_TRACK_FIGURES_NOT_E16_COMPLETE", "passed": True,
              "source_csv": {"path": str(csv_path), "sha256": digest(csv_path)}, "verification": verification,
              "outputs": outputs, "figure_metrics": {"path": str(destination / "figure_metrics.json"), "sha256": digest(destination / "figure_metrics.json")},
              "new_predictions_or_scoring": 0, "scientific_statuses_unchanged": True,
              "wall_seconds": time.perf_counter() - started}
    atomic_json(study.directory / "result.json", report)
    artifact = ROOT / "reports/analysis" / (study.name + ".json")
    atomic_json(artifact, report)
    atomic_json(ROOT / "reports/analysis/PUBLIC_TRACK_FIGURES.json", {"artifact": str(artifact), "sha256": digest(artifact), "passed": True})
    print(json.dumps({"artifact": str(artifact), "passed": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
