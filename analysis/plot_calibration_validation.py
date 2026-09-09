#!/usr/bin/env python
"""Plot camera-clustered interpolation and root-direction calibration validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FT_TO_CM = 30.48
IN_TO_CM = 2.54
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_SEED = 20260908


def release_path(path: Path) -> str:
    """Return a repository-relative path when the source is inside the release."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--band-holdout",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "pole_holdout_validation_daily" / "band_holdout_errors.csv",
    )
    parser.add_argument(
        "--downward",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "pole_downward_bias" / "downward_extrapolation_errors.csv",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=PROJECT_ROOT / "data" / "reference" / "pole_camera_registry.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "manuscript" / "figures",
    )
    return parser.parse_args()


def camera_bootstrap(values: np.ndarray, rng: np.random.Generator) -> dict[str, float | int]:
    """Mean and percentile interval, resampling whole camera summaries."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        raise ValueError("Cannot bootstrap an empty camera set")
    draws = rng.choice(values, size=(BOOTSTRAP_REPLICATES, len(values)), replace=True).mean(axis=1)
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {
        "n_cameras": int(len(values)),
        "camera_mean": float(values.mean()),
        "camera_median": float(np.median(values)),
        "ci95_low": float(lo),
        "ci95_high": float(hi),
    }


def spread_labels(values: dict[str, float], low: float, high: float, gap: float) -> dict[str, float]:
    """Spread direct labels vertically while preserving their rank."""
    ordered = sorted(values, key=values.get)
    positions: dict[str, float] = {}
    cursor = low
    for key in ordered:
        cursor = max(values[key], cursor)
        positions[key] = cursor
        cursor += gap
    overflow = max(positions.values()) - high
    if overflow > 0:
        for key in positions:
            positions[key] -= overflow
    cursor = high
    for key in reversed(ordered):
        cursor = min(positions[key], cursor)
        positions[key] = cursor
        cursor -= gap
    underflow = low - min(positions.values())
    if underflow > 0:
        for key in positions:
            positions[key] += underflow
    return positions


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.16, 1.06, label, transform=ax.transAxes, ha="left", va="top",
            fontsize=10, fontweight="bold")


def main() -> None:
    args = parse_args()
    band = pd.read_csv(args.band_holdout)
    downward = pd.read_csv(args.downward)
    registry = pd.read_csv(args.registry)[["camera_genotype", "pole_reference_year"]]
    registry_map = dict(zip(registry["camera_genotype"], registry["pole_reference_year"]))

    band = band.loc[band["split"].eq("interpolation_alternating")].copy()
    band["error_cm"] = band["error_in"] * IN_TO_CM
    downward["pole_reference_year"] = downward["camera"].map(registry_map)
    if downward["pole_reference_year"].isna().any():
        missing = sorted(downward.loc[downward["pole_reference_year"].isna(), "camera"].unique())
        raise ValueError(f"Downward-validation cameras missing from registry: {missing}")

    all_cameras = sorted(set(band["camera_setup_id"]) | set(downward["camera"]))
    camera_labels: dict[str, str] = {}
    for year, prefix in [(2024, "D"), (2025, "T")]:
        cameras = sorted(camera for camera in all_cameras if int(registry_map[camera]) == year)
        camera_labels.update({camera: f"{prefix}{index}" for index, camera in enumerate(cameras, 1)})

    interp_camera = (
        band.groupby(["pole_reference_year", "camera_setup_id"], as_index=False)
        .agg(
            n_predictions=("error_cm", "size"),
            n_images=("image_id", "nunique"),
            bias_cm=("error_cm", "mean"),
            mae_cm=("error_cm", lambda values: values.abs().mean()),
            rmse_cm=("error_cm", lambda values: float(np.sqrt(np.mean(values**2)))),
        )
    )
    down_camera = (
        downward.groupby(["pole_reference_year", "camera", "below_ft"], as_index=False)
        .agg(
            n_predictions=("error_cm", "size"),
            n_images=("image_id", "nunique"),
            bias_cm=("error_cm", "mean"),
            mae_cm=("error_cm", lambda values: values.abs().mean()),
            rmse_cm=("error_cm", lambda values: float(np.sqrt(np.mean(values**2)))),
        )
    )

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    interpolation_summary: dict[str, dict] = {}
    downward_summary: dict[str, dict] = {}
    for year in (2024, 2025):
        year_values = interp_camera.loc[interp_camera["pole_reference_year"].eq(year), "mae_cm"].to_numpy()
        entry = camera_bootstrap(year_values, rng)
        year_band = band.loc[band["pole_reference_year"].eq(year)]
        entry.update(
            {
                "n_predictions": int(len(year_band)),
                "n_images": int(year_band["image_id"].nunique()),
                "unit": "cm",
            }
        )
        interpolation_summary[str(year)] = entry
        downward_summary[str(year)] = {}
        for distance in sorted(down_camera["below_ft"].unique()):
            group = down_camera.loc[
                down_camera["pole_reference_year"].eq(year)
                & down_camera["below_ft"].eq(distance)
            ]
            signed = camera_bootstrap(group["bias_cm"].to_numpy(), rng)
            absolute = camera_bootstrap(group["mae_cm"].to_numpy(), rng)
            raw = downward.loc[
                downward["pole_reference_year"].eq(year)
                & downward["below_ft"].eq(distance)
            ]
            downward_summary[str(year)][str(float(distance))] = {
                "distance_below_retained_range_ft": float(distance),
                "distance_below_retained_range_cm": float(distance * FT_TO_CM),
                "signed_error_cm": signed,
                "absolute_error_cm": absolute,
                "n_predictions": int(len(raw)),
                "n_images": int(raw["image_id"].nunique()),
            }

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8.7,
            "axes.linewidth": 0.7,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    colors = {2024: "#D55E00", 2025: "#0072B2"}
    markers = {2024: "o", 2025: "^"}
    offsets = {2024: -0.045, 2025: 0.045}
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 3.35), constrained_layout=True)

    # A: interpolation, preserving cameras as the independent display units.
    ax = axes[0]
    year_positions = {2024: 0.0, 2025: 1.0}
    for year in (2024, 2025):
        group = interp_camera.loc[interp_camera["pole_reference_year"].eq(year)].sort_values("camera_setup_id")
        jitter = np.linspace(-0.13, 0.13, len(group)) if len(group) > 1 else np.array([0.0])
        x = year_positions[year] + jitter
        ax.scatter(
            x, group["mae_cm"], s=28, marker=markers[year], color=colors[year],
            edgecolor="white", linewidth=0.6, alpha=0.86, zorder=3,
        )
        for x_value, (_, row) in zip(x, group.iterrows()):
            ax.annotate(
                camera_labels[row["camera_setup_id"]], (x_value, row["mae_cm"]),
                xytext=(0, 5), textcoords="offset points", ha="center", va="bottom",
                color=colors[year], fontsize=6.5, fontweight="bold",
            )
        summary = interpolation_summary[str(year)]
        center = year_positions[year]
        ax.errorbar(
            center, summary["camera_mean"],
            yerr=[[summary["camera_mean"] - summary["ci95_low"]],
                  [summary["ci95_high"] - summary["camera_mean"]]],
            marker="D", ms=6.2, color="black", markerfacecolor=colors[year],
            markeredgecolor="black", elinewidth=1.4, capsize=3, zorder=5,
        )
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(0, max(0.8, interp_camera["mae_cm"].max() + 0.12))
    ax.set_xticks([0, 1])
    ax.set_xticklabels(
        [
            "Development\n2024; 6 cameras",
            "Locked test\n2025; 3 cameras",
        ]
    )
    ax.set_ylabel("Held-out interpolation MAE (cm)")
    ax.set_title("Alternating-band interpolation")
    panel_label(ax, "A")

    # B/C: correct root direction—fit upper bands and predict below the fitted range.
    metric_specs = [
        ("bias_cm", "Mean signed error within camera (cm)", "Root-direction signed error", axes[1]),
        ("mae_cm", "Mean absolute error within camera (cm)", "Root-direction absolute error", axes[2]),
    ]
    distance_values = np.array(sorted(down_camera["below_ft"].unique()), dtype=float)
    small_sample_cameras = set(
        downward.groupby("camera")["image_id"].nunique().loc[lambda values: values < 10].index
    )
    for metric, ylabel, title, ax in metric_specs:
        for year in (2024, 2025):
            year_group = down_camera.loc[down_camera["pole_reference_year"].eq(year)]
            for camera, camera_group in year_group.groupby("camera"):
                camera_group = camera_group.sort_values("below_ft")
                ax.plot(
                    camera_group["below_ft"], camera_group[metric],
                    color=colors[year], marker=markers[year], ms=3.0,
                    lw=0.8, alpha=0.38, zorder=2,
                )
            means, lows, highs = [], [], []
            for distance in distance_values:
                key = "signed_error_cm" if metric == "bias_cm" else "absolute_error_cm"
                item = downward_summary[str(year)][str(float(distance))][key]
                means.append(item["camera_mean"])
                lows.append(item["ci95_low"])
                highs.append(item["ci95_high"])
            means = np.asarray(means)
            lows = np.asarray(lows)
            highs = np.asarray(highs)
            x_summary = distance_values + offsets[year]
            ax.plot(
                x_summary, means, color=colors[year], lw=1.8, marker="D", ms=4.5,
                markeredgecolor="black", markeredgewidth=0.45, zorder=5,
            )
            ax.errorbar(
                x_summary, means, yerr=[means - lows, highs - means],
                color=colors[year], lw=0, elinewidth=1.1, capsize=2.2, zorder=4,
            )
        if metric == "bias_cm":
            ax.axhline(0, color="#555555", lw=0.8, ls="--", zorder=1)
        ax.set_xlim(0.72, 3.42)
        ax.set_xticks(distance_values)
        ax.set_xticklabels([f"{distance:.0f} ft\n({distance * FT_TO_CM:.1f} cm)" for distance in distance_values])
        ax.set_xlabel("Distance below fitted range")
        ax.set_ylabel(ylabel)
        ax.set_title(title)

        endpoint = down_camera.loc[down_camera["below_ft"].eq(distance_values[-1])]
        raw_positions = {row["camera"]: float(row[metric]) for _, row in endpoint.iterrows()}
        if metric == "bias_cm":
            y_low = min(-3.2, min(raw_positions.values()) - 0.8)
            y_high = max(18.2, max(raw_positions.values()) + 1.0)
            gap = 0.72
        else:
            y_low = 0.0
            y_high = max(21.0, max(raw_positions.values()) + 1.0)
            gap = 0.72
        ax.set_ylim(y_low, y_high)
        label_positions = spread_labels(raw_positions, y_low + 0.45, y_high - 0.45, gap)
        for camera, y_value in raw_positions.items():
            year = int(registry_map[camera])
            short = camera_labels[camera] + ("*" if camera in small_sample_cameras else "")
            label_y = label_positions[camera]
            ax.plot([3.02, 3.15], [y_value, label_y], color=colors[year], lw=0.5, alpha=0.8)
            ax.text(3.18, label_y, short, color=colors[year], fontsize=5.9,
                    ha="left", va="center", fontweight="bold")

    panel_label(axes[1], "B")
    panel_label(axes[2], "C")

    for ax in axes:
        ax.grid(color="#E4E4E4", linewidth=0.5, alpha=0.9)
        ax.set_axisbelow(True)
    legend_handles = [
        Line2D([0], [0], color=colors[2024], marker=markers[2024], lw=0.9,
               alpha=0.75, label="Development 2024 camera"),
        Line2D([0], [0], color=colors[2025], marker=markers[2025], lw=0.9,
               alpha=0.75, label="Locked 2025 camera"),
        Line2D([0], [0], color="black", marker="D", markerfacecolor="white", lw=1.5,
               label="Year mean and 95% camera-bootstrap CI"),
    ]
    fig.legend(handles=legend_handles, loc="outside lower center", ncol=3, frameon=False)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    png_path = args.output_dir / "calibration_validation.png"
    pdf_path = args.output_dir / "calibration_validation.pdf"
    fig.savefig(png_path, dpi=450, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    camera_details = {}
    for camera in all_cameras:
        camera_details[camera_labels[camera]] = {
            "camera_setup_id": camera,
            "year": int(registry_map[camera]),
            "interpolation_images": int(
                band.loc[band["camera_setup_id"].eq(camera), "image_id"].nunique()
            ),
            "downward_images": int(
                downward.loc[downward["camera"].eq(camera), "image_id"].nunique()
            ),
            "small_sample_flag": camera in small_sample_cameras,
        }
    notes = {
        "figure": "calibration_validation",
        "source_files": {
            "interpolation": release_path(args.band_holdout),
            "downward_root_direction": release_path(args.downward),
            "camera_registry": release_path(args.registry),
        },
        "experimental_unit": (
            "Camera. Metrics are first computed within camera and then averaged "
            "without weighting cameras by their number of bands or images. The 95% "
            "intervals resample whole camera summaries. Individual bands are not "
            "treated as independent replicates."
        ),
        "bootstrap": {
            "replicates": BOOTSTRAP_REPLICATES,
            "seed": BOOTSTRAP_SEED,
            "method": "Percentile bootstrap resampling cameras with replacement.",
        },
        "interpolation_definition": (
            "Alternating integer-height bands are retained for calibration and held "
            "out for interpolation. Error is predicted minus known band height."
        ),
        "downward_definition": (
            "For each image, the lowest one to three bands are removed, a projective "
            "calibration is fit to the remaining upper bands, and removed bands are "
            "predicted 1-3 ft below the retained range. This is the plant-root "
            "direction. Negative signed error places the inferred point too low and "
            "would inflate top-minus-root plant height."
        ),
        "interpolation_summary": interpolation_summary,
        "downward_summary": downward_summary,
        "camera_key": camera_details,
        "quality_caveat": (
            "The source bands are automatically detected candidates, so this is a "
            "held-out self-consistency test rather than comparison with manually "
            "annotated red-band truth. The completed 2021 human audit concerns a "
            "different physical object: the stationary-camera support poles."
        ),
    }
    (args.output_dir / "calibration_validation.figure_notes.json").write_text(
        json.dumps(notes, indent=2), encoding="utf-8"
    )
    interp_2024 = interpolation_summary["2024"]
    interp_2025 = interpolation_summary["2025"]
    caption = (
        "Camera-clustered validation of projective pole calibration. (A) Alternating "
        "known-height bands were held out within images to test interpolation. Each "
        "labeled point is the within-camera MAE; diamonds and intervals are the "
        "unweighted camera mean and 95% camera-bootstrap CI. Camera-level MAE was "
        f"{interp_2024['camera_mean']:.2f} cm (95% CI, {interp_2024['ci95_low']:.2f}-"
        f"{interp_2024['ci95_high']:.2f}; six development cameras) in 2024 and "
        f"{interp_2025['camera_mean']:.2f} cm (95% CI, {interp_2025['ci95_low']:.2f}-"
        f"{interp_2025['ci95_high']:.2f}; three locked-test cameras) in 2025. "
        "(B, C) Root-direction extrapolation was tested by dropping the lowest "
        "one to three bands, fitting only the retained upper bands, and predicting "
        "1-3 ft below the fitted range. Thin lines show within-camera signed error "
        "and MAE; thick lines and intervals show year-specific camera means and "
        "camera-bootstrap CIs. Negative signed error means the predicted lower point "
        "was placed too low, which would inflate a top-minus-root height. D6 was "
        "retained but is flagged because only five images were available. Bands are "
        "automatically detected candidates; inferential summaries use cameras, not "
        "individual band predictions, as units."
    )
    (args.output_dir / "calibration_validation.caption.txt").write_text(
        caption + "\n", encoding="utf-8"
    )
    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")
    print(json.dumps({"interpolation": interpolation_summary, "downward": downward_summary}, indent=2))


if __name__ == "__main__":
    main()
