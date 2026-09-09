#!/usr/bin/env python
"""Fit pole-based image calibration and convert annotated plant endpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


LANDMARK_COLUMNS = {
    "image_id",
    "camera_setup_id",
    "session_id",
    "image_path",
    "landmark_id",
    "x_px",
    "y_px",
    "relative_height_ft",
    "pole_depth_ft",
    "band_definition",
    "annotation_status",
}
PLANT_COLUMNS = {
    "image_id",
    "camera_setup_id",
    "session_id",
    "plant_uid",
    "x_top_px",
    "y_top_px",
    "x_base_px",
    "y_base_px",
    "depth_relation",
    "plant_depth_ft",
    "endpoint_annotation_status",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calibrate image y-coordinates from pole landmarks spaced at known "
            "physical heights."
        )
    )
    parser.add_argument("--landmarks", required=True, type=Path)
    parser.add_argument(
        "--plants",
        type=Path,
        help="Optional plant top/base annotation CSV.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory.",
    )
    parser.add_argument(
        "--max-pole-rmse-in",
        type=float,
        default=0.5,
        help="QC threshold for pole landmark fit residuals.",
    )
    return parser.parse_args()


def require_columns(data: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"{label} is missing columns: {', '.join(missing)}")


def fit_projective_calibration(group: pd.DataFrame) -> dict[str, object]:
    clean = group[["y_px", "relative_height_ft"]].dropna().astype(float)
    if len(clean) < 4:
        raise ValueError(
            f"{group['image_id'].iloc[0]} has {len(clean)} landmarks; at least 4 required."
        )
    if clean["relative_height_ft"].nunique() < 4:
        raise ValueError("At least four unique physical landmark heights are required.")

    y = clean["y_px"].to_numpy()
    z = clean["relative_height_ft"].to_numpy()
    y_center = float(y.mean())
    y_scale = float(y.std(ddof=0))
    if y_scale == 0:
        raise ValueError("Pole landmark y-coordinates have zero spread.")
    u = (y - y_center) / y_scale

    # z = (a*u + b) / (c*u + 1)
    design = np.column_stack([u, np.ones_like(u), -z * u])
    a, b, c = np.linalg.lstsq(design, z, rcond=None)[0]
    denominator = c * u + 1
    if np.min(np.abs(denominator)) < 0.1:
        raise ValueError("Unstable projective fit: denominator approaches zero.")
    fitted = (a * u + b) / denominator
    residual = z - fitted
    derivative_numerator = a - b * c
    if derivative_numerator >= 0:
        raise ValueError(
            "Calibration is not vertically monotone: check landmark height ordering."
        )

    return {
        "a": float(a),
        "b": float(b),
        "c": float(c),
        "y_center": y_center,
        "y_scale": y_scale,
        "n_landmarks": int(len(clean)),
        "min_landmark_y_px": float(y.min()),
        "max_landmark_y_px": float(y.max()),
        "min_relative_height_ft": float(z.min()),
        "max_relative_height_ft": float(z.max()),
        "pole_fit_rmse_ft": float(np.sqrt(np.mean(residual**2))),
        "pole_fit_rmse_in": float(12 * np.sqrt(np.mean(residual**2))),
        "pole_fit_max_abs_error_in": float(12 * np.max(np.abs(residual))),
        "monotone": True,
    }


def transform_y(y_px: float | np.ndarray, fit: dict[str, object]) -> np.ndarray:
    y = np.asarray(y_px, dtype=float)
    u = (y - float(fit["y_center"])) / float(fit["y_scale"])
    denominator = float(fit["c"]) * u + 1
    return (float(fit["a"]) * u + float(fit["b"])) / denominator


def calibration_table(
    landmarks: pd.DataFrame, max_rmse_in: float
) -> tuple[pd.DataFrame, dict[tuple[str, str, str], dict[str, object]]]:
    rows: list[dict[str, object]] = []
    fits: dict[tuple[str, str, str], dict[str, object]] = {}
    keys = ["image_id", "camera_setup_id", "session_id"]
    for key, group in landmarks.groupby(keys, dropna=False, sort=True):
        fit = fit_projective_calibration(group)
        fit["image_id"], fit["camera_setup_id"], fit["session_id"] = key
        fit["pole_depth_ft"] = pd.to_numeric(
            group["pole_depth_ft"], errors="coerce"
        ).median()
        fit["all_landmarks_verified"] = bool(
            group["annotation_status"].astype(str).str.lower().eq("verified").all()
        )
        fit["pole_fit_pass"] = bool(fit["pole_fit_rmse_in"] <= max_rmse_in)
        fits[key] = fit
        rows.append(fit.copy())
    return pd.DataFrame(rows), fits


def calibrate_plants(
    plants: pd.DataFrame,
    fits: dict[tuple[str, str, str], dict[str, object]],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in plants.to_dict(orient="records"):
        key = (
            record["image_id"],
            record["camera_setup_id"],
            record["session_id"],
        )
        if key not in fits:
            raise ValueError(f"No pole calibration found for plant annotation key {key}.")
        fit = fits[key]
        z_top = float(transform_y(record["y_top_px"], fit))
        z_base = float(transform_y(record["y_base_px"], fit))
        pole_min_y = float(fit["min_landmark_y_px"])
        pole_max_y = float(fit["max_landmark_y_px"])
        extrapolation = (
            float(record["y_top_px"]) < pole_min_y
            or float(record["y_top_px"]) > pole_max_y
            or float(record["y_base_px"]) < pole_min_y
            or float(record["y_base_px"]) > pole_max_y
        )
        depth_relation = str(record["depth_relation"]).strip().lower()
        depth_verified = depth_relation == "same"
        endpoint_verified = (
            str(record["endpoint_annotation_status"]).strip().lower() == "verified"
        )
        primary_quality = bool(
            fit["pole_fit_pass"]
            and fit["all_landmarks_verified"]
            and depth_verified
            and endpoint_verified
            and not extrapolation
        )
        record.update(
            {
                "top_relative_height_ft": z_top,
                "base_relative_height_ft": z_base,
                "pole_calibrated_height_ft": z_top - z_base,
                "pole_calibrated_height_cm": (z_top - z_base) * 30.48,
                "pole_fit_rmse_in": fit["pole_fit_rmse_in"],
                "pole_landmarks_verified": fit["all_landmarks_verified"],
                "pole_fit_pass": fit["pole_fit_pass"],
                "depth_match_verified": depth_verified,
                "vertical_extrapolation_flag": extrapolation,
                "primary_quality_flag": primary_quality,
            }
        )
        rows.append(record)
    return pd.DataFrame(rows)


def plot_calibration(
    group: pd.DataFrame, fit: dict[str, object], output: Path
) -> None:
    y_grid = np.linspace(
        float(fit["min_landmark_y_px"]),
        float(fit["max_landmark_y_px"]),
        300,
    )
    fig, axis = plt.subplots(figsize=(6, 5))
    axis.scatter(
        group["y_px"],
        group["relative_height_ft"],
        color="#b2182b",
        label="Annotated band centers",
        zorder=3,
    )
    axis.plot(
        y_grid,
        transform_y(y_grid, fit),
        color="#2166ac",
        label="Projective calibration",
    )
    axis.set_xlabel("Image y-coordinate (pixels)")
    axis.set_ylabel("Relative pole height (ft)")
    axis.set_title(
        f"Pole calibration\nRMSE = {float(fit['pole_fit_rmse_in']):.2f} in"
    )
    axis.grid(alpha=0.2)
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def draw_landmark_overlay(group: pd.DataFrame, output: Path) -> None:
    image_path = Path(str(group["image_path"].iloc[0]))
    if not image_path.exists():
        return
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for row in group.itertuples(index=False):
        x = float(row.x_px)
        y = float(row.y_px)
        radius = 7
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            outline=(255, 230, 0),
            width=3,
        )
        draw.text(
            (x + 10, y - 8),
            f"{float(row.relative_height_ft):g} ft",
            fill=(255, 230, 0),
            font=font,
            stroke_width=2,
            stroke_fill=(0, 0, 0),
        )
    image.save(output, quality=95)


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    figure_dir = args.output / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    landmarks = pd.read_csv(args.landmarks)
    require_columns(landmarks, LANDMARK_COLUMNS, "Landmark table")
    for column in ["x_px", "y_px", "relative_height_ft", "pole_depth_ft"]:
        landmarks[column] = pd.to_numeric(landmarks[column], errors="coerce")
    if landmarks[["y_px", "relative_height_ft"]].isna().any().any():
        raise ValueError("Pole y-coordinates and relative heights must be numeric.")

    calibrations, fits = calibration_table(landmarks, args.max_pole_rmse_in)
    calibrations.to_csv(args.output / "pole_calibration_parameters.csv", index=False)

    keys = ["image_id", "camera_setup_id", "session_id"]
    for key, group in landmarks.groupby(keys, dropna=False, sort=True):
        safe_id = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key[0])
        plot_calibration(group, fits[key], figure_dir / f"{safe_id}_calibration.png")
        draw_landmark_overlay(group, figure_dir / f"{safe_id}_landmarks.jpg")

    if args.plants:
        plants = pd.read_csv(args.plants)
        require_columns(plants, PLANT_COLUMNS, "Plant annotation table")
        calibrated = calibrate_plants(plants, fits)
        calibrated.to_csv(
            args.output / "pole_calibrated_plant_heights.csv", index=False
        )

    summary = {
        "n_images_calibrated": int(len(calibrations)),
        "n_calibrations_passing_fit_qc": int(calibrations["pole_fit_pass"].sum()),
        "n_calibrations_with_verified_landmarks": int(
            calibrations["all_landmarks_verified"].sum()
        ),
        "max_pole_rmse_in": args.max_pole_rmse_in,
        "important_limitation": (
            "Pole calibration is primary-quality only for plants at the same "
            "effective camera depth and within the annotated vertical range."
        ),
    }
    (args.output / "pole_calibration_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"Pole calibration complete: {args.output.resolve()}")


if __name__ == "__main__":
    main()
