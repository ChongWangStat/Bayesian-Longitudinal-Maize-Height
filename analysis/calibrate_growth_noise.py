#!/usr/bin/env python
"""Empirically calibrate the particle filter's process/outlier hyperparameters.

The filter previously used guessed defaults (process_height_sd_cm_sqrt_day =
1.5, outlier_probability = 0.08, outlier_sd_cm = 60.0) that were never fit to
data. This script fits them from the actual week-to-week height changes on
the *development* cameras only (2024, per the pole registry), so the locked
2025 test cameras are never used to tune the model -- the same
development/locked-test discipline used for the pole calibration itself.

Method: restrict to successive same-plant observations at the modal ~7-day
sampling interval (so all points are on a comparable time scale), then split
core vs. outlier transitions with a robust (MAD-based) z-score cutoff at 3,
since true week-to-week maize height changes should not exhibit gross
negative jumps -- height changes that far from the robust center are far
more consistent with a plant-tracking or keypoint-detection failure than
with biology.

Measurement noise and process noise are not separately identified from one
image per camera per week (no repeated same-time measurements exist to
isolate pure measurement error), so this calibrates their *combined*
one-step effect against the empirical core distribution rather than
independently guessing each term; the process-noise parameter therefore
also carries whatever measurement jitter cannot be distinguished from it.
This is stated explicitly rather than presented as a clean decomposition.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("data/processed/online_longitudinal_pole_heights.csv")
    )
    parser.add_argument(
        "--height-column",
        default="pole_calibrated_height_cm",
        help="Height column whose units will define the fitted noise scales.",
    )
    parser.add_argument(
        "--registry", type=Path, default=Path("data/reference/pole_camera_registry.csv")
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--development-year", type=int, default=2024)
    parser.add_argument("--nominal-interval-days", type=float, default=7.0)
    parser.add_argument("--interval-tolerance-days", type=float, default=0.5)
    parser.add_argument("--outlier-z-threshold", type=float, default=3.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    heights = pd.read_csv(args.input)
    registry = pd.read_csv(args.registry)

    if args.height_column not in heights:
        raise ValueError(f"{args.input} has no column '{args.height_column}'.")

    heights = heights.merge(
        registry[["camera_genotype", "pole_reference_year"]], on="camera_genotype", how="left"
    )
    heights["capture_datetime"] = pd.to_datetime(heights["capture_datetime"])

    dev = heights[
        (heights["provisional_quality_flag"] == True)  # noqa: E712
        & (heights["pole_reference_year"] == args.development_year)
    ].copy()
    dev = dev.sort_values(["plant_uid", "capture_datetime"])
    dev["prev_height_cm"] = dev.groupby("plant_uid")[args.height_column].shift(1)
    dev["prev_time"] = dev.groupby("plant_uid")["capture_datetime"].shift(1)
    dev["dt_days"] = (dev["capture_datetime"] - dev["prev_time"]).dt.total_seconds() / 86400
    dev["dh_cm"] = dev[args.height_column] - dev["prev_height_cm"]
    dev = dev.dropna(subset=["dt_days", "dh_cm"])

    lo = args.nominal_interval_days - args.interval_tolerance_days
    hi = args.nominal_interval_days + args.interval_tolerance_days
    weekly = dev[(dev["dt_days"] >= lo) & (dev["dt_days"] <= hi)].copy()
    if len(weekly) < 20:
        raise SystemExit(
            f"Only {len(weekly)} development intervals at the nominal cadence; "
            "too few to calibrate reliably."
        )

    median_dh = float(weekly["dh_cm"].median())
    mad = float((weekly["dh_cm"] - median_dh).abs().median())
    robust_sd = 1.4826 * mad
    z = (weekly["dh_cm"] - median_dh) / robust_sd
    is_outlier = z.abs() > args.outlier_z_threshold

    core = weekly.loc[~is_outlier, "dh_cm"]
    tail = weekly.loc[is_outlier, "dh_cm"]

    process_height_sd_cm_sqrt_day = float(core.std(ddof=1) / np.sqrt(args.nominal_interval_days))
    outlier_probability = float(len(tail) / len(weekly))
    outlier_sd_cm = float(tail.std(ddof=1)) if len(tail) > 1 else float(tail.abs().mean())

    result = {
        "development_year": args.development_year,
        "height_column": args.height_column,
        "n_weekly_intervals": int(len(weekly)),
        "n_core": int(len(core)),
        "n_outlier": int(len(tail)),
        "nominal_interval_days": args.nominal_interval_days,
        "process_height_sd_cm_sqrt_day": round(process_height_sd_cm_sqrt_day, 3),
        "outlier_probability": round(outlier_probability, 4),
        "outlier_sd_cm": round(outlier_sd_cm, 2),
        "note": (
            "process_height_sd_cm_sqrt_day is a combined process+measurement "
            "one-step noise scale, not a pure biological growth-rate variance; "
            "the two are not separately identified from one image per camera "
            "per week. Calibrated on development-year data only; never touches "
            "the locked test-year cameras."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
