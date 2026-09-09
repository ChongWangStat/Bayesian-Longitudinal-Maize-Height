#!/usr/bin/env python
"""Held-out pole/band validation of the projective pixel-to-height calibration.

This validates only the pole calibration itself (pixel -> physical distance
along the pole), using the poles as known geometric objects. It does not
require, and does not use, any manual plant height.

Two checks, both clustered by physical pole (camera), not by band-pair:

1. Band holdout: for each image with a passing automatic pole fit, fit the
   projective calibration on a held-in subset of detected bands and predict
   the held-out bands' known relative height. Reports both an interpolation
   split (alternating bands) and an extrapolation split (fit on the lower
   half, predict the upper half).
2. Pseudo-plant segments: every pair of held-out bands defines a vertical
   object of known height |j-k| x 30.48 cm. Predicted segment height is the
   difference of the two held-out predictions. This mimics validating a
   plant of that height without needing a real plant or manual measurement.

Cameras are split by the year recorded in the pole camera registry: 2024
cameras are the development set (used only to pick this script's own
defaults, not to peek at 2025), 2025 cameras are the locked test set.

Important caveat: all current band detections are unverified automated
candidates (see automatic_pole_landmarks.csv annotation_status). Occasional
false-positive bands (e.g. from the on-image timestamp) would bias this
validation optimistically if they happen to fit smoothly. Treat results here
as a methodological pilot, not a claimable paper number, until a human spot
check verifies a sample of the band detections.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from calibrate_from_poles import fit_projective_calibration, transform_y  # noqa: E402


FT_TO_CM = 30.48


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--landmarks", type=Path, default=Path("data/processed/automatic_pole_landmarks.csv")
    )
    parser.add_argument(
        "--calibrations",
        type=Path,
        default=Path("data/processed/automatic_pole_calibrations.csv"),
    )
    parser.add_argument(
        "--registry", type=Path, default=Path("data/reference/pole_camera_registry.csv")
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def band_holdout_one_image(group: pd.DataFrame) -> list[dict]:
    """Return per-split residual records for one image's detected bands."""
    g = group.dropna(subset=["y_px", "relative_height_ft"]).sort_values("relative_height_ft")
    g = g[g["relative_height_ft"] == g["relative_height_ft"].round()]  # keep integer bands only
    n = len(g)
    if n < 8:
        return []

    records: list[dict] = []
    idx = np.arange(n)

    splits = {
        "interpolation_alternating": (idx % 2 == 0, idx % 2 == 1),
        "extrapolation_lower_to_upper": (idx < n // 2, idx >= n // 2),
        # DOWNWARD extrapolation: fit on the UPPER bands, predict BELOW the fitted range.
        # This is the situation the plant ROOT is actually in (it sits below the lowest
        # band in ~96% of observations), so it is the direction that matters for the
        # height bias; the lower_to_upper split above tests the opposite direction.
        "extrapolation_upper_to_lower": (idx >= n - n // 2, idx < n - n // 2),
    }
    for split_name, (calib_mask, test_mask) in splits.items():
        calib = g.iloc[calib_mask]
        test = g.iloc[test_mask]
        if len(calib) < 4 or len(test) == 0:
            continue
        try:
            fit = fit_projective_calibration(calib.assign(image_id=group.name))
        except ValueError:
            continue
        predicted_ft = transform_y(test["y_px"].to_numpy(), fit)
        true_ft = test["relative_height_ft"].to_numpy()
        for pred, true, band_id in zip(predicted_ft, true_ft, test["landmark_id"]):
            records.append(
                {
                    "split": split_name,
                    "landmark_id": band_id,
                    "true_relative_height_ft": true,
                    "predicted_relative_height_ft": pred,
                    "error_in": (pred - true) * 12.0,
                    "calib_n": len(calib),
                    "test_predicted_ft": pred,
                    "test_true_ft": true,
                }
            )
    return records


def pseudo_plant_segments(records: pd.DataFrame) -> pd.DataFrame:
    """Build pseudo-plant segments from held-out test-band predictions."""
    rows = []
    keys = ["camera_setup_id", "image_id", "split"]
    for key, grp in records.groupby(keys):
        preds = grp["test_predicted_ft"].to_numpy()
        trues = grp["test_true_ft"].to_numpy()
        n = len(preds)
        for i in range(n):
            for j in range(i + 1, n):
                true_h_cm = abs(trues[i] - trues[j]) * FT_TO_CM
                pred_h_cm = abs(preds[i] - preds[j]) * FT_TO_CM
                rows.append(
                    {
                        "camera_setup_id": key[0],
                        "image_id": key[1],
                        "split": key[2],
                        "true_segment_height_cm": true_h_cm,
                        "predicted_segment_height_cm": pred_h_cm,
                        "error_cm": pred_h_cm - true_h_cm,
                    }
                )
    return pd.DataFrame(rows)


def cluster_summary(df: pd.DataFrame, error_col: str, group_col: str = "camera_setup_id") -> pd.DataFrame:
    """Two-level summary: average within camera first, then across cameras."""
    per_camera = df.groupby(group_col)[error_col].agg(
        n="count", bias="mean", mae=lambda s: s.abs().mean(), rmse=lambda s: np.sqrt((s**2).mean())
    )
    pooled = pd.DataFrame(
        {
            "n_cameras": [per_camera.shape[0]],
            "n_obs_total": [int(per_camera["n"].sum())],
            "bias_mean_of_camera_means": [per_camera["bias"].mean()],
            "bias_sd_across_cameras": [per_camera["bias"].std(ddof=1)],
            "mae_mean_of_camera_means": [per_camera["mae"].mean()],
            "rmse_mean_of_camera_means": [per_camera["rmse"].mean()],
        }
    )
    return per_camera, pooled


def main() -> None:
    args = parse_args()
    landmarks = pd.read_csv(args.landmarks)
    calibrations = pd.read_csv(args.calibrations)
    registry = pd.read_csv(args.registry)

    passing_images = set(calibrations.loc[calibrations["pole_fit_pass"] == True, "image_id"])  # noqa: E712
    landmarks = landmarks[landmarks["image_id"].isin(passing_images)].copy()
    landmarks = landmarks.merge(
        registry[["camera_genotype", "pole_reference_year"]],
        left_on="camera_setup_id",
        right_on="camera_genotype",
        how="left",
    )

    all_records: list[dict] = []
    for image_id, group in landmarks.groupby("image_id"):
        group = group.copy()
        group.name = image_id
        recs = band_holdout_one_image(group)
        for r in recs:
            r["image_id"] = image_id
            r["camera_setup_id"] = group["camera_setup_id"].iloc[0]
            r["pole_reference_year"] = group["pole_reference_year"].iloc[0]
        all_records.extend(recs)

    band_df = pd.DataFrame(all_records)
    if band_df.empty:
        raise SystemExit("No image had enough detected bands for a holdout split.")

    args.output.mkdir(parents=True, exist_ok=True)
    band_df.to_csv(args.output / "band_holdout_errors.csv", index=False)

    segments = pseudo_plant_segments(band_df)
    segments.to_csv(args.output / "pseudo_plant_segment_errors.csv", index=False)

    print("=== Band holdout (pixel -> known relative pole height), by dev/test year ===")
    for year_label, year_values in [("2024 (development)", [2024]), ("2025 (locked test)", [2025])]:
        for split in band_df["split"].unique():
            sub = band_df[
                band_df["split"].eq(split) & band_df["pole_reference_year"].isin(year_values)
            ]
            if sub.empty:
                continue
            per_camera, pooled = cluster_summary(sub, "error_in")
            print(f"\n-- {year_label} | {split} --")
            print(per_camera.round(3).to_string())
            print(pooled.round(3).to_string(index=False))

    print("\n=== Pseudo-plant segment heights (cm), by dev/test year ===")
    for year_label, year_values in [("2024 (development)", [2024]), ("2025 (locked test)", [2025])]:
        seg_year = segments.merge(
            registry[["camera_genotype", "pole_reference_year"]],
            left_on="camera_setup_id",
            right_on="camera_genotype",
            how="left",
        )
        for split in seg_year["split"].unique():
            sub = seg_year[seg_year["split"].eq(split) & seg_year["pole_reference_year"].isin(year_values)]
            if sub.empty:
                continue
            per_camera, pooled = cluster_summary(sub, "error_cm")
            print(f"\n-- {year_label} | {split} --")
            print(per_camera.round(2).to_string())
            print(pooled.round(2).to_string(index=False))

    print(
        "\nCAVEAT: all bands used here are unverified automated candidates "
        "(annotation_status='automated_candidate_unverified'). Verify a sample "
        "against the source images before reporting these numbers in the paper."
    )


if __name__ == "__main__":
    main()
