#!/usr/bin/env python
"""Summarize unit-consistent predictive uncertainty by development/test year.

The particle filter operates on target-depth heights. This audit therefore requires
measurement, process, and outlier scales in the same target-depth centimetre units.
It reports coverage and width at several nominal levels, mean log score, and the
weighted interval score (WIS). The 2025 cameras are evaluated only after parameters
have been estimated from 2024 development data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


INTERVALS = {
    0.50: ("predictive_q25_cm", "predictive_q75_cm", 0.50),
    0.80: ("predictive_q10_cm", "predictive_q90_cm", 0.20),
    0.90: ("predictive_q05_cm", "predictive_q95_cm", 0.10),
    0.95: ("predictive_q025_cm", "predictive_q975_cm", 0.05),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--guessed",
        type=Path,
        default=Path(
            "outputs/online_study/pole_camera_bayesian_daily_guessed_revised/"
            "online_bayesian_height_posteriors.csv"
        ),
    )
    parser.add_argument(
        "--calibrated",
        type=Path,
        default=Path(
            "outputs/online_study/pole_camera_bayesian_daily_revised/"
            "online_bayesian_height_posteriors.csv"
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/uncertainty_revision")
    )
    return parser.parse_args()


def weighted_interval_score(data: pd.DataFrame, measurement_col: str) -> pd.Series:
    truth = data[measurement_col]
    numerator = 0.5 * (truth - data["predictive_median_cm"]).abs()
    for lower_col, upper_col, alpha in INTERVALS.values():
        lower = data[lower_col]
        upper = data[upper_col]
        interval_score = (
            (upper - lower)
            + (2.0 / alpha) * (lower - truth).clip(lower=0)
            + (2.0 / alpha) * (truth - upper).clip(lower=0)
        )
        numerator = numerator + (alpha / 2.0) * interval_score
    return numerator / 4.5


def summarize_group(
    data: pd.DataFrame, model: str, split: str, measurement_col: str
) -> tuple[dict[str, object], list[dict[str, object]]]:
    error = data["predictive_mean_cm"] - data[measurement_col]
    base = {
        "model": model,
        "split": split,
        "n": int(len(data)),
        "cameras": int(data["camera_genotype"].nunique()),
        "plants": int(data["plant_uid"].nunique()),
        "bias_cm": float(error.mean()),
        "mae_cm": float(error.abs().mean()),
        "rmse_cm": float(np.sqrt(np.mean(error**2))),
        "mean_log_score": float(data["predictive_log_score"].mean()),
        "mean_wis_cm": float(weighted_interval_score(data, measurement_col).mean()),
        "mean_pit": float(data["predictive_pit"].mean()),
    }
    interval_rows = []
    for nominal, (lower_col, upper_col, _alpha) in INTERVALS.items():
        covered = (
            (data[measurement_col] >= data[lower_col])
            & (data[measurement_col] <= data[upper_col])
        )
        width = data[upper_col] - data[lower_col]
        interval_rows.append(
            {
                "model": model,
                "split": split,
                "nominal_coverage": nominal,
                "empirical_coverage": float(covered.mean()),
                "mean_width_cm": float(width.mean()),
                "median_width_cm": float(width.median()),
                "n": int(len(data)),
            }
        )
    return base, interval_rows


def load(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    data["capture_datetime"] = pd.to_datetime(data["capture_datetime"])
    data["year"] = data["capture_datetime"].dt.year
    return data[data["predictive_q025_cm"].notna()].copy()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    measurement_col = "depth_corrected_height_cm"
    models = {"guessed": load(args.guessed), "unit_consistent": load(args.calibrated)}

    summary_rows: list[dict[str, object]] = []
    interval_rows: list[dict[str, object]] = []
    camera_rows: list[dict[str, object]] = []
    split_masks = {
        "all": lambda data: pd.Series(True, index=data.index),
        "2024_development": lambda data: data["year"].eq(2024),
        "2025_locked_test": lambda data: data["year"].eq(2025),
    }
    for model, data in models.items():
        for split, mask_function in split_masks.items():
            group = data.loc[mask_function(data)].copy()
            summary, intervals = summarize_group(group, model, split, measurement_col)
            summary_rows.append(summary)
            interval_rows.extend(intervals)
        for camera, group in data.groupby("camera_genotype", sort=True):
            year = int(group["year"].iloc[0])
            summary, _ = summarize_group(group, model, str(year), measurement_col)
            camera_rows.append({"camera_genotype": camera, **summary})

    summary_frame = pd.DataFrame(summary_rows)
    interval_frame = pd.DataFrame(interval_rows)
    camera_frame = pd.DataFrame(camera_rows)
    summary_frame.to_csv(args.output / "uncertainty_summary.csv", index=False)
    interval_frame.to_csv(args.output / "interval_calibration.csv", index=False)
    camera_frame.to_csv(args.output / "camera_uncertainty_summary.csv", index=False)

    payload = {
        "design": (
            "All noise scales are expressed after the 0.85 pole-to-target depth "
            "conversion. Parameters are estimated from 2024 only; 2025 is held out."
        ),
        "summary": summary_rows,
        "intervals": interval_rows,
    }
    (args.output / "summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    calibrated = interval_frame[interval_frame["model"] == "unit_consistent"]
    colors = {
        "all": "#1f4e79",
        "2024_development": "#4c9f70",
        "2025_locked_test": "#c45a2d",
    }
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 3.8))
    for split, group in calibrated.groupby("split", sort=False):
        axes[0].plot(
            100 * group["nominal_coverage"],
            100 * group["empirical_coverage"],
            marker="o",
            linewidth=2,
            label=split.replace("_", " "),
            color=colors[split],
        )
        axes[1].plot(
            100 * group["nominal_coverage"],
            group["mean_width_cm"],
            marker="o",
            linewidth=2,
            color=colors[split],
        )
    axes[0].plot([45, 100], [45, 100], linestyle="--", color="0.45", linewidth=1)
    axes[0].set(xlabel="Nominal coverage (%)", ylabel="Empirical coverage (%)")
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].set(xlabel="Nominal coverage (%)", ylabel="Mean interval width (cm)")

    test = models["unit_consistent"]
    test = test[test["year"] == 2025]
    axes[2].hist(
        test["predictive_pit"], bins=np.linspace(0, 1, 11), color="#c45a2d", edgecolor="white"
    )
    axes[2].axhline(len(test) / 10, color="0.35", linestyle="--", linewidth=1)
    axes[2].set(xlabel="Predictive probability integral transform", ylabel="Count")
    axes[2].set_title(f"2025 held-out test ($n={len(test)}$)")
    for panel, axis in zip("ABC", axes):
        axis.text(-0.16, 1.05, panel, transform=axis.transAxes, fontweight="bold")
        axis.grid(alpha=0.18)
    fig.tight_layout()
    fig.savefig(args.output / "uncertainty_calibration.pdf", bbox_inches="tight")
    fig.savefig(args.output / "uncertainty_calibration.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(summary_frame.round(4).to_string(index=False))
    print("\n" + interval_frame.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
