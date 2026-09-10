#!/usr/bin/env python3
"""Regenerate the core manuscript summaries from the released derived data."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(*parts: str) -> None:
    print("+", " ".join(parts), flush=True)
    subprocess.run(parts, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-filter",
        action="store_true",
        help="also rerun both 5,000-particle daily filters from the released measurement table",
    )
    args = parser.parse_args()

    py = sys.executable
    if args.full_filter:
        depth = "outputs/online_study/depth_corrected_heights_daily.csv"
        hyper_path = "outputs/online_study/calibrated_growth_hyperparameters_daily.json"
        run(
            py, "analysis/calibrate_growth_noise.py", "--input", depth,
            "--height-column", "depth_corrected_height_cm", "--output", hyper_path,
            "--development-year", "2024", "--nominal-interval-days", "1",
        )
        hyper = json.loads((ROOT / hyper_path).read_text(encoding="utf-8"))
        common = [
            py, "analysis/bayesian_online_height_filter.py", "--input", depth,
            "--measurement-col", "depth_corrected_height_cm",
            "--measurement-sd-col", "depth_corrected_measurement_sd_cm",
        ]
        run(
            *common, "--output", "outputs/online_study/pole_camera_bayesian_daily_guessed_revised",
            "--process-height-sd-cm-sqrt-day", "1.5",
            "--outlier-probability", "0.08", "--outlier-sd-cm", "60.0",
        )
        run(
            *common, "--output", "outputs/online_study/pole_camera_bayesian_daily_revised",
            "--process-height-sd-cm-sqrt-day", str(hyper["process_height_sd_cm_sqrt_day"]),
            "--outlier-probability", str(hyper["outlier_probability"]),
            "--outlier-sd-cm", str(hyper["outlier_sd_cm"]),
        )

    run(py, "analysis/all_plants_primary_2021.py")
    run(py, "analysis/field_baseline_comparison_2021.py")
    run(py, "analysis/manual_height_uncertainty_2021.py")
    run(py, "analysis/pole_repeatability_2021.py")
    run(py, "analysis/real_image_candidate_ablation_2021.py")
    run(py, "analysis/summarize_uncertainty_revision.py")
    run(py, "manuscript/generate_numbers.py")
    run(py, "verify_release.py")


if __name__ == "__main__":
    main()
