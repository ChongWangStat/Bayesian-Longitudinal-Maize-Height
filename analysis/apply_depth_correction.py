#!/usr/bin/env python
"""Apply the ground-plane depth correction to pole-calibrated heights.

The pole calibration in ``calibrate_from_poles.py`` fits pixel position to
physical height along the pole itself, i.e. at the pole's own depth from the
camera. Because the pole sits farther from the camera than the imaged plant
row (confirmed via Yawei Li's camera-settings table: ~10 ft to the pole vs.
~8.5 ft to the row for the 2024/2025 cameras), applying that fit directly to
plant pixels overstates plant height.

Under a pinhole ground-plane model with camera height H, camera-to-object
distance D, and no lens distortion, the image row for a point at height z is

    y - y_horizon = f_px * (H - z) / D

where y_horizon is the (depth-invariant) row corresponding to real height
z = H. Applying a calibration fit at D_pole to pixels actually formed at
D_row and taking a *height difference* (top - base) makes the unknown H and
y_horizon terms cancel exactly, leaving

    height_true = height_pole_estimate * (D_row / D_pole)

This holds exactly for vertical extents (not for absolute root height above
ground) under the stated assumptions: level, shared ground plane; no lens
distortion; camera axis not rolled; D_row/D_pole approximated by the row-level
values in the registry rather than measured per plant.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("data/reference/pole_camera_registry.csv"),
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--height-column",
        default="pole_calibrated_height_cm",
        help="Column holding the pole-calibrated (uncorrected) height in cm.",
    )
    parser.add_argument(
        "--sd-column",
        default="measurement_sd_cm",
        help=(
            "Column holding the measurement-noise SD in cm, in the same "
            "(uncorrected) units as --height-column. Scaled by the same "
            "depth-correction factor so it stays consistent with the "
            "corrected height; pass '' to skip if not present."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    heights = pd.read_csv(args.input)
    registry = pd.read_csv(args.registry)

    if args.height_column not in heights.columns:
        raise ValueError(f"{args.input} has no column '{args.height_column}'.")

    merged = heights.merge(
        registry[
            [
                "camera_genotype",
                "camera_to_row_ft",
                "camera_to_pole_ft",
                "camera_height_ft",
                "depth_correction_factor",
            ]
        ],
        on="camera_genotype",
        how="left",
    )
    missing_factor = merged["depth_correction_factor"].isna()
    if missing_factor.any():
        cameras = sorted(merged.loc[missing_factor, "camera_genotype"].unique())
        raise ValueError(
            "No registry depth-correction factor for camera(s): "
            f"{', '.join(cameras)}"
        )

    merged["depth_corrected_height_cm"] = (
        merged[args.height_column] * merged["depth_correction_factor"]
    )
    merged["depth_correction_shift_cm"] = (
        merged["depth_corrected_height_cm"] - merged[args.height_column]
    )

    if args.sd_column:
        if args.sd_column not in merged.columns:
            raise ValueError(
                f"{args.input} has no column '{args.sd_column}'; pass --sd-column '' to skip."
            )
        # The SD is a linear (cm-scale) quantity computed on the same
        # uncorrected pole-depth scale as the height; it must be rescaled by
        # the same factor kappa = D_row/D_pole to stay consistent with the
        # corrected height, exactly as the height itself is (Section 3.2).
        merged[f"depth_corrected_{args.sd_column}"] = (
            merged[args.sd_column] * merged["depth_correction_factor"]
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)

    valid = merged[merged[args.height_column].notna()]
    print(f"Rows with a pole-calibrated height: {len(valid)}")
    print(
        "Uncorrected mean/median height (cm): "
        f"{valid[args.height_column].mean():.2f} / "
        f"{valid[args.height_column].median():.2f}"
    )
    print(
        "Depth-corrected mean/median height (cm): "
        f"{valid['depth_corrected_height_cm'].mean():.2f} / "
        f"{valid['depth_corrected_height_cm'].median():.2f}"
    )
    print(
        "Mean shift from correction (cm): "
        f"{valid['depth_correction_shift_cm'].mean():.2f} "
        f"({100 * (valid['depth_correction_factor'].iloc[0] - 1):.1f}% of uncorrected)"
    )
    by_camera = (
        valid.groupby("camera_genotype")[args.height_column]
        .agg(["count", "mean"])
        .rename(columns={"mean": "uncorrected_mean_cm"})
    )
    by_camera["depth_corrected_mean_cm"] = valid.groupby("camera_genotype")[
        "depth_corrected_height_cm"
    ].mean()
    print(by_camera.round(2).to_string())


if __name__ == "__main__":
    main()
