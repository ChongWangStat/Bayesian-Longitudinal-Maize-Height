#!/usr/bin/env python
"""Later-year manual-height validation with 2021-only calibration fitting.

The numerical calibration is estimated from 2021 records with recovered source
coordinates. The 2024 manual outcomes are joined only after all 2024 image
updates have been generated. Camera distance is transferred using the field
settings (8.5 / 10.25). Biological rows, rather than the left and right camera
views, are the resampling units.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.stats import t

LOCKED_SOURCE_COMMIT = "59b42b74596c598017fdb0cd4b80af1aec7649d6"
PIXEL_SCALE_2021_CM = 0.415886
CAMERA_DISTANCE_2021_FT = 10.25
CAMERA_DISTANCE_2024_FT = 8.5
FILTER_SEED = 20260723
BOOTSTRAP_SEED = 20260915
BOOTSTRAP_REPLICATES = 20_000
BASELINE_COLUMNS = {
    "single_frame": "transferred_single_frame_cm",
    "ewma": "ewma_cm",
    "running_median3": "running_median3_cm",
    "holt": "holt_cm",
    "gaussian_kalman": "gaussian_kalman_cm",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/manual_height_transfer_2024"),
    )
    return parser.parse_args()


def load_filter_module(repo_root: Path) -> Any:
    path = repo_root / "analysis" / "bayesian_online_height_filter.py"
    specification = importlib.util.spec_from_file_location(
        "bayesian_online_height_filter", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def normalize_2021_camera(value: str) -> str:
    prefix, number = value.split("_")
    return f"{prefix}_{int(number):03d}"


def match_2021_development(repo_root: Path) -> pd.DataFrame:
    crop = pd.read_csv(
        repo_root / "outputs" / "crop_positions_2021" / "crop_positions.csv"
    )
    pose = pd.read_csv(
        repo_root
        / "outputs"
        / "pose_candidates_annotation_set_2021"
        / "pose_candidates.csv"
    )
    truth = pd.read_csv(repo_root / "data" / "raw" / "heights_compare_2021.csv")
    pose["rowid"] = pose["camera"].map(normalize_2021_camera)
    pose["date_md"] = pose["day"]

    matches: list[dict[str, object]] = []
    for (row_id, date_md), crop_group in crop.groupby(["rowid", "date_md"], sort=True):
        pose_group = pose[(pose["rowid"] == row_id) & (pose["date_md"] == date_md)]
        if pose_group.empty:
            continue
        distances = np.abs(
            crop_group["x_root_full"].to_numpy()[:, None]
            - pose_group["x_root"].to_numpy()[None, :]
        )
        crop_indices, pose_indices = linear_sum_assignment(distances)
        for crop_index, pose_index in zip(crop_indices, pose_indices):
            distance = float(distances[crop_index, pose_index])
            if distance > 80.0:
                continue
            crop_row = crop_group.iloc[crop_index]
            pose_row = pose_group.iloc[pose_index]
            matches.append(
                {
                    "rowid": row_id,
                    "date_md": date_md,
                    "plantid": crop_row["plant"],
                    "source_image": crop_row["source"],
                    "x_root_recovered_px": float(crop_row["x_root_full"]),
                    "x_root_pose_px": float(pose_row["x_root"]),
                    "x_match_distance_px": distance,
                    "pose_height_px": float(pose_row["height_px"]),
                    "pose_confidence": float(pose_row["confidence"]),
                }
            )

    matched = pd.DataFrame(matches).merge(
        truth,
        on=["rowid", "date_md", "plantid"],
        how="inner",
        validate="one_to_one",
    )
    matched["pose_geometry_height_cm_2021"] = (
        matched["pose_height_px"] * PIXEL_SCALE_2021_CM
    )
    if len(matched) != 61 or matched["rowid"].nunique() != 6:
        raise ValueError(
            "Expected 61 coordinate-recovered records in six 2021 camera rows; "
            f"found {len(matched)} records in {matched['rowid'].nunique()} rows."
        )
    return matched.sort_values(
        ["rowid", "plantid", "date"], kind="mergesort"
    ).reset_index(drop=True)


def fit_2021_calibration(
    development: pd.DataFrame,
) -> tuple[np.ndarray, pd.DataFrame, float]:
    predictor = development["pose_geometry_height_cm_2021"].to_numpy()
    outcome = development["height_true"].to_numpy()
    design = np.column_stack([np.ones(len(development)), predictor])
    coefficients = np.linalg.lstsq(design, outcome, rcond=None)[0]

    cross_validated: list[pd.DataFrame] = []
    for held_out_row in sorted(development["rowid"].unique()):
        training = development[development["rowid"] != held_out_row]
        testing = development[development["rowid"] == held_out_row].copy()
        training_design = np.column_stack(
            [
                np.ones(len(training)),
                training["pose_geometry_height_cm_2021"].to_numpy(),
            ]
        )
        fold_coefficients = np.linalg.lstsq(
            training_design,
            training["height_true"].to_numpy(),
            rcond=None,
        )[0]
        testing["held_out_row"] = held_out_row
        testing["cv_prediction_cm"] = (
            fold_coefficients[0]
            + fold_coefficients[1] * testing["pose_geometry_height_cm_2021"]
        )
        testing["cv_error_cm"] = testing["cv_prediction_cm"] - testing["height_true"]
        cross_validated.append(testing)
    cv = pd.concat(cross_validated, ignore_index=True)
    transfer_residual_rmse = float(np.sqrt(np.mean(np.square(cv["cv_error_cm"]))))
    return coefficients, cv, transfer_residual_rmse


def camera_layout_with_status(
    repo_root: Path, image_data: pd.DataFrame
) -> pd.DataFrame:
    layout = pd.read_csv(
        repo_root / "data" / "raw" / "manual_height_2024" / "camera_layout_2024.csv"
    )
    genotype_for_camera: dict[str, str] = {}
    for genotype, group in image_data.groupby("camera_genotype"):
        image_names = group["image"].dropna().astype(str)
        for camera_id in layout["camera_id"]:
            if image_names.str.contains(rf"\.{camera_id}(?:\.|_)", regex=True).any():
                genotype_for_camera[camera_id] = genotype
    layout["camera_genotype"] = layout["camera_id"].map(genotype_for_camera)
    layout["automated_pose_output"] = layout["camera_genotype"].notna()
    layout["global_plant_numbers"] = np.where(
        layout["camera_position"].eq("R"), "1-6", "7-12"
    )
    layout["analysis_status"] = np.where(
        layout["automated_pose_output"],
        "included when a manual date passes image QC",
        "no automated pose output in the analysis archive",
    )
    return layout


def add_fixed_causal_baselines(
    data: pd.DataFrame, transfer_residual_rmse: float
) -> pd.DataFrame:
    """Apply fixed baselines to the complete daily prefix before manual scoring.

    The Gaussian filter receives the same initial growth mean/SD and process
    scales as the particle filter so that its comparison isolates the robust
    likelihood/particle representation rather than a different prior.
    """
    result = data.sort_values(
        ["plant_uid", "capture_datetime"], kind="mergesort"
    ).copy()
    for column in BASELINE_COLUMNS.values():
        if column != "transferred_single_frame_cm":
            result[column] = np.nan

    for _, group in result.groupby("plant_uid", sort=True):
        history: list[float] = []
        ewma: float | None = None
        level: float | None = None
        trend = 0.0
        gaussian_state: np.ndarray | None = None
        gaussian_covariance: np.ndarray | None = None
        previous_date: pd.Timestamp | None = None
        for index, row in group.iterrows():
            measurement = float(row["transferred_single_frame_cm"])
            date = pd.Timestamp(row["capture_datetime"])
            elapsed = (
                0.0
                if previous_date is None
                else max((date - previous_date).total_seconds() / 86400.0, 1e-6)
            )

            ewma = measurement if ewma is None else 0.5 * measurement + 0.5 * ewma
            history.append(measurement)
            running_median = float(np.median(history[-3:]))

            if level is None:
                level = measurement
            else:
                predicted_level = level + trend * elapsed
                updated_level = 0.5 * measurement + 0.5 * predicted_level
                trend = 0.2 * ((updated_level - level) / elapsed) + 0.8 * trend
                level = updated_level

            if gaussian_state is None:
                gaussian_state = np.array([measurement, 3.0])
                gaussian_covariance = np.diag([transfer_residual_rmse**2, 2.0**2])
            else:
                transition = np.array([[1.0, elapsed], [0.0, 1.0]])
                process_covariance = np.diag([8.78**2 * elapsed, 0.35**2 * elapsed])
                gaussian_state = transition @ gaussian_state
                gaussian_covariance = (
                    transition @ gaussian_covariance @ transition.T + process_covariance
                )
                innovation_variance = (
                    gaussian_covariance[0, 0] + transfer_residual_rmse**2
                )
                gain = gaussian_covariance[:, 0] / innovation_variance
                gaussian_state = gaussian_state + gain * (
                    measurement - gaussian_state[0]
                )
                gaussian_covariance = gaussian_covariance - np.outer(
                    gain, gaussian_covariance[0, :]
                )

            result.loc[
                index,
                ["ewma_cm", "running_median3_cm", "holt_cm", "gaussian_kalman_cm"],
            ] = [ewma, running_median, level, gaussian_state[0]]
            previous_date = date
    return result


def run_2024_filter(
    repo_root: Path,
    coefficients: np.ndarray,
    transfer_residual_rmse: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = pd.read_csv(
        repo_root / "data" / "processed" / "online_longitudinal_pole_heights_daily.csv",
        low_memory=False,
    )
    source = source[source["dataset_key"].astype(str).str.startswith("2024")].copy()
    quality = (
        source["provisional_quality_flag"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )
    source = source[quality & source["height_px"].notna()].copy()
    layout = camera_layout_with_status(repo_root, source)
    included = layout[layout["automated_pose_output"]].copy()
    camera_to_row = included.set_index("camera_genotype")["biological_row_id"].to_dict()
    camera_to_side = included.set_index("camera_genotype")["camera_position"].to_dict()
    source = source[source["camera_genotype"].isin(camera_to_row)].copy()

    distance_ratio = CAMERA_DISTANCE_2024_FT / CAMERA_DISTANCE_2021_FT
    source["transferred_single_frame_cm"] = (
        coefficients[0]
        + coefficients[1]
        * source["height_px"].astype(float)
        * PIXEL_SCALE_2021_CM
        * distance_ratio
    )
    source["transferred_measurement_sd_cm"] = transfer_residual_rmse
    source["capture_datetime"] = pd.to_datetime(source["capture_datetime"])

    filter_module = load_filter_module(repo_root)
    filtered_groups: list[pd.DataFrame] = []
    for _, group in source.groupby("plant_uid", sort=True):
        filtered_groups.append(
            filter_module.filter_one_plant(
                group=group,
                plant_col="plant_uid",
                date_col="capture_datetime",
                measurement_col="transferred_single_frame_cm",
                measurement_sd_col="transferred_measurement_sd_cm",
                particles=5000,
                base_seed=FILTER_SEED,
                default_measurement_sd_cm=transfer_residual_rmse,
                measurement_sd_multiplier=1.0,
                initial_growth_mean_cm_day=3.0,
                initial_growth_sd_cm_day=2.0,
                process_height_sd_cm_sqrt_day=8.78,
                process_growth_sd_cm_day_sqrt_day=0.35,
                minimum_growth_cm_day=-4.0,
                maximum_growth_cm_day=15.0,
                outlier_probability=0.08,
                outlier_sd_cm=60.0,
                resample_ess_fraction=0.5,
            )
        )
    filtered = pd.concat(filtered_groups, ignore_index=True)
    filtered = add_fixed_causal_baselines(filtered, transfer_residual_rmse)
    filtered["biological_row_id"] = filtered["camera_genotype"].map(camera_to_row)
    filtered["camera_position"] = filtered["camera_genotype"].map(camera_to_side)
    filtered["plant_global_rtl"] = filtered["plant_id_rtl"].astype(int) + np.where(
        filtered["camera_position"].eq("L"), 6, 0
    )
    filtered["measurement_date"] = pd.to_datetime(
        filtered["observation_date"]
    ).dt.date.astype(str)
    return filtered, layout


def add_transfer_intervals(
    data: pd.DataFrame, transfer_residual_rmse: float, degrees_freedom: int
) -> pd.DataFrame:
    result = data.copy()
    result["transfer_total_sd_cm"] = np.sqrt(
        np.square(result["posterior_sd_cm"]) + transfer_residual_rmse**2
    )
    for level in [50, 80, 90, 95]:
        probability = 0.5 + level / 200.0
        multiplier = float(t.ppf(probability, df=degrees_freedom))
        result[f"transfer_q{(100 - level) // 2:02d}_cm"] = (
            result["posterior_mean_cm"] - multiplier * result["transfer_total_sd_cm"]
        )
        result[f"transfer_q{100 - (100 - level) // 2:02d}_cm"] = (
            result["posterior_mean_cm"] + multiplier * result["transfer_total_sd_cm"]
        )
    return result


def metric_summary(
    data: pd.DataFrame, estimate_column: str, truth_column: str = "manual_height_cm"
) -> dict[str, float | int]:
    estimate = data[estimate_column].to_numpy(dtype=float)
    truth = data[truth_column].to_numpy(dtype=float)
    error = estimate - truth
    correlation = float(np.corrcoef(estimate, truth)[0, 1])
    return {
        "n": len(data),
        "bias_cm": float(np.mean(error)),
        "mae_cm": float(np.mean(np.abs(error))),
        "rmse_cm": float(np.sqrt(np.mean(np.square(error)))),
        "pearson_r": correlation,
    }


def interval_summary(data: pd.DataFrame, level: int) -> dict[str, float | int]:
    lower = f"transfer_q{(100 - level) // 2:02d}_cm"
    upper = f"transfer_q{100 - (100 - level) // 2:02d}_cm"
    covered = (data["manual_height_cm"] >= data[lower]) & (
        data["manual_height_cm"] <= data[upper]
    )
    return {
        "level_percent": level,
        "covered": int(covered.sum()),
        "n": len(data),
        "coverage_percent": float(100.0 * covered.mean()),
        "mean_width_cm": float((data[upper] - data[lower]).mean()),
    }


def cluster_bootstrap(data: pd.DataFrame) -> pd.DataFrame:
    rows = sorted(data["biological_row_id"].unique())
    summaries: list[dict[str, float]] = []
    for row in rows:
        group = data[data["biological_row_id"] == row]
        bayes_error = group["posterior_mean_cm"] - group["manual_height_cm"]
        summary: dict[str, float] = {
            "n": float(len(group)),
            "bayesian_abs_error_sum": float(np.abs(bayes_error).sum()),
        }
        for name, column in BASELINE_COLUMNS.items():
            error = group[column] - group["manual_height_cm"]
            summary[f"{name}_abs_error_sum"] = float(np.abs(error).sum())
        for level in [80, 95]:
            lower = f"transfer_q{(100 - level) // 2:02d}_cm"
            upper = f"transfer_q{100 - (100 - level) // 2:02d}_cm"
            covered = (group["manual_height_cm"] >= group[lower]) & (
                group["manual_height_cm"] <= group[upper]
            )
            summary[f"covered_{level}_sum"] = float(covered.sum())
            summary[f"width_{level}_sum"] = float((group[upper] - group[lower]).sum())
        summaries.append(summary)

    row_summary = pd.DataFrame(summaries)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = rng.integers(0, len(rows), size=(BOOTSTRAP_REPLICATES, len(rows)))
    denominator = row_summary["n"].to_numpy()[sampled].sum(axis=1)

    def sampled_mean(column: str) -> np.ndarray:
        return row_summary[column].to_numpy()[sampled].sum(axis=1) / denominator

    bayesian_mae = sampled_mean("bayesian_abs_error_sum")
    result = pd.DataFrame(
        {
            "replicate": np.arange(1, BOOTSTRAP_REPLICATES + 1),
            "single_frame_mae_cm": sampled_mean("single_frame_abs_error_sum"),
            "bayesian_mae_cm": bayesian_mae,
        }
    )
    result["mae_gain_cm"] = result["single_frame_mae_cm"] - result["bayesian_mae_cm"]
    for name in BASELINE_COLUMNS:
        result[f"{name}_minus_bayesian_mae_cm"] = (
            sampled_mean(f"{name}_abs_error_sum") - bayesian_mae
        )
    for level in [80, 95]:
        result[f"coverage_{level}_percent"] = 100 * sampled_mean(f"covered_{level}_sum")
        result[f"width_{level}_cm"] = sampled_mean(f"width_{level}_sum")
    return result


def percentile_interval(values: pd.Series) -> list[float]:
    return [float(value) for value in np.quantile(values, [0.025, 0.975])]


def calibration_metadata_audit(
    repo_root: Path, filtered: pd.DataFrame, included_cameras: set[str]
) -> tuple[pd.DataFrame, dict[str, object]]:
    calibration = pd.read_csv(
        repo_root / "data" / "processed" / "automatic_pole_calibrations_daily.csv",
        low_memory=False,
    )
    calibration = calibration[
        calibration["camera_setup_id"].isin(included_cameras)
    ].copy()
    calibration["pole_fit_pass_bool"] = (
        calibration["pole_fit_pass"].astype(str).str.lower().isin(["true", "1", "yes"])
    )
    calibration["inferred_marked_span_ft"] = (
        calibration["max_relative_height_ft"] - calibration["min_relative_height_ft"]
    )
    passed = calibration[calibration["pole_fit_pass_bool"]].copy()
    passed["exceeds_documented_10ft_pole"] = passed["inferred_marked_span_ft"] > 10.0
    camera_audit = (
        passed.groupby("camera_setup_id")
        .agg(
            passing_candidate_images=("image_id", "size"),
            minimum_inferred_span_ft=("inferred_marked_span_ft", "min"),
            median_inferred_span_ft=("inferred_marked_span_ft", "median"),
            maximum_inferred_span_ft=("inferred_marked_span_ft", "max"),
            candidates_exceeding_10ft=(
                "exceeds_documented_10ft_pole",
                "sum",
            ),
        )
        .reset_index()
    )
    selected_span = filtered["reference_n_landmarks"].astype(float) - 1.0
    audit_summary: dict[str, object] = {
        "documented_pole_length_ft": "8-10",
        "documented_mark_spacing_ft": 1.0,
        "passing_candidate_images": len(passed),
        "passing_candidates_exceeding_10ft": int(
            passed["exceeds_documented_10ft_pole"].sum()
        ),
        "passing_candidates_exceeding_10ft_percent": float(
            100.0 * passed["exceeds_documented_10ft_pole"].mean()
        ),
        "filtered_image_records_using_reference_span_over_10ft": int(
            (selected_span > 10.0).sum()
        ),
        "filtered_image_records": len(filtered),
        "filtered_image_records_reference_span_over_10ft_percent": float(
            100.0 * (selected_span > 10.0).mean()
        ),
        "decision": (
            "The 2024 manual-height transfer analysis does not use the "
            "automatic red-component scale because the inferred number of "
            "one-foot intervals conflicts with the recorded 8-10-ft pole "
            "length. It uses the 2021 development calibration and recorded "
            "camera-distance ratio instead."
        ),
    }
    return camera_audit, audit_summary


def plot_validation(
    development: pd.DataFrame,
    validation: pd.DataFrame,
    coefficients: np.ndarray,
    output_dir: Path,
) -> None:
    colors = {
        "M-0006": "#0072B2",
        "M-0013": "#009E73",
        "W-0010": "#D55E00",
        "W-0015": "#CC79A7",
    }
    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8.5))

    ax = axes[0, 0]
    for row_id, group in development.groupby("rowid"):
        ax.scatter(
            group["pose_geometry_height_cm_2021"],
            group["height_true"],
            s=24,
            alpha=0.72,
            label=row_id.replace("_", "-"),
        )
    limits = [25, 210]
    grid = np.linspace(*limits, 200)
    ax.plot(grid, grid, linestyle="--", color="0.55", linewidth=1)
    ax.plot(
        grid,
        coefficients[0] + coefficients[1] * grid,
        color="black",
        linewidth=1.8,
    )
    ax.set(
        xlim=limits,
        ylim=limits,
        xlabel="2021 pose extent after geometry (cm)",
        ylabel="Manual height (cm)",
    )
    ax.set_title("a  Development calibration (2021)", loc="left", fontweight="bold")
    ax.legend(ncol=2, fontsize=7, frameon=False)

    for panel, column, title in [
        (axes[0, 1], "transferred_single_frame_cm", "b  Single-frame transfer (2024)"),
        (axes[1, 0], "posterior_mean_cm", "c  Bayesian longitudinal transfer (2024)"),
    ]:
        for row_id, group in validation.groupby("biological_row_id"):
            panel.scatter(
                group["manual_height_cm"],
                group[column],
                s=25,
                alpha=0.72,
                color=colors[row_id],
                label=row_id,
            )
        lim = [15, 225]
        panel.plot(lim, lim, linestyle="--", color="0.45", linewidth=1)
        summary = metric_summary(validation, column)
        panel.text(
            0.04,
            0.95,
            f"MAE {summary['mae_cm']:.1f} cm\n$r$ = {summary['pearson_r']:.3f}",
            transform=panel.transAxes,
            va="top",
            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
        )
        panel.set(
            xlim=lim,
            ylim=lim,
            xlabel="Manual height (cm)",
            ylabel="Image-derived height (cm)",
        )
        panel.set_title(title, loc="left", fontweight="bold")

    ax = axes[1, 1]
    aggregated = (
        validation.groupby(["biological_row_id", "measurement_date"])
        .agg(
            manual_height_cm=("manual_height_cm", "mean"),
            posterior_mean_cm=("posterior_mean_cm", "mean"),
        )
        .reset_index()
    )
    aggregated["measurement_date"] = pd.to_datetime(aggregated["measurement_date"])
    for row_id, group in aggregated.groupby("biological_row_id"):
        group = group.sort_values("measurement_date")
        ax.plot(
            group["measurement_date"],
            group["posterior_mean_cm"],
            color=colors[row_id],
            linewidth=1.8,
            label=f"{row_id} image",
        )
        ax.scatter(
            group["measurement_date"],
            group["manual_height_cm"],
            facecolor="white",
            edgecolor=colors[row_id],
            linewidth=1.4,
            s=38,
            zorder=3,
            label=f"{row_id} manual",
        )
    ax.set_ylabel("Camera-date mean height (cm)")
    ax.set_xlabel("2024 measurement date")
    ax.set_title(
        "d  Later-year longitudinal trajectories", loc="left", fontweight="bold"
    )
    ax.tick_params(axis="x", rotation=30)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, ncol=2, fontsize=7, frameon=False)

    for ax in axes.ravel():
        ax.grid(color="0.9", linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(output_dir / "manual_height_transfer_2024.pdf", bbox_inches="tight")
    figure.savefig(
        output_dir / "manual_height_transfer_2024.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)


def tex_command(name: str, value: object) -> str:
    return rf"\newcommand{{\{name}}}{{{value}}}"


def write_numbers(
    output_dir: Path,
    development: pd.DataFrame,
    cv: pd.DataFrame,
    validation: pd.DataFrame,
    coefficients: np.ndarray,
    bootstrap: pd.DataFrame,
    audit: dict[str, object],
) -> None:
    single = metric_summary(validation, "transferred_single_frame_cm")
    bayes = metric_summary(validation, "posterior_mean_cm")
    ewma = metric_summary(validation, "ewma_cm")
    running_median = metric_summary(validation, "running_median3_cm")
    holt = metric_summary(validation, "holt_cm")
    gaussian = metric_summary(validation, "gaussian_kalman_cm")
    cv_error = cv["cv_error_cm"]
    gain = single["mae_cm"] - bayes["mae_cm"]
    interval80 = interval_summary(validation, 80)
    interval95 = interval_summary(validation, 95)
    values = [
        ("TransferDevN", len(development)),
        ("TransferDevRows", development["rowid"].nunique()),
        ("TransferCalibrationIntercept", f"{coefficients[0]:.2f}"),
        ("TransferCalibrationSlope", f"{coefficients[1]:.3f}"),
        ("TransferDevCVMAE", f"{np.abs(cv_error).mean():.2f}"),
        ("TransferDevCVRMSE", f"{np.sqrt(np.mean(np.square(cv_error))):.2f}"),
        ("TransferValidationN", len(validation)),
        (
            "TransferValidationPlants",
            validation[["biological_row_id", "plant_global_rtl"]]
            .drop_duplicates()
            .shape[0],
        ),
        ("TransferValidationRows", validation["biological_row_id"].nunique()),
        ("TransferValidationCameras", validation["camera_genotype"].nunique()),
        ("TransferValidationDates", validation["measurement_date"].nunique()),
        ("TransferSingleBias", f"{single['bias_cm']:.2f}"),
        ("TransferSingleMAE", f"{single['mae_cm']:.2f}"),
        ("TransferSingleRMSE", f"{single['rmse_cm']:.2f}"),
        ("TransferSingleCorrelation", f"{single['pearson_r']:.3f}"),
        ("TransferBayesBias", f"{bayes['bias_cm']:.2f}"),
        ("TransferBayesMAE", f"{bayes['mae_cm']:.2f}"),
        ("TransferBayesRMSE", f"{bayes['rmse_cm']:.2f}"),
        ("TransferBayesCorrelation", f"{bayes['pearson_r']:.3f}"),
        ("TransferEWMABias", f"{ewma['bias_cm']:.2f}"),
        ("TransferEWMAMAE", f"{ewma['mae_cm']:.2f}"),
        ("TransferEWMARMSE", f"{ewma['rmse_cm']:.2f}"),
        ("TransferEWMACorrelation", f"{ewma['pearson_r']:.3f}"),
        ("TransferMedianBias", f"{running_median['bias_cm']:.2f}"),
        ("TransferMedianMAE", f"{running_median['mae_cm']:.2f}"),
        ("TransferMedianRMSE", f"{running_median['rmse_cm']:.2f}"),
        ("TransferMedianCorrelation", f"{running_median['pearson_r']:.3f}"),
        ("TransferHoltBias", f"{holt['bias_cm']:.2f}"),
        ("TransferHoltMAE", f"{holt['mae_cm']:.2f}"),
        ("TransferHoltRMSE", f"{holt['rmse_cm']:.2f}"),
        ("TransferHoltCorrelation", f"{holt['pearson_r']:.3f}"),
        ("TransferGaussianBias", f"{gaussian['bias_cm']:.2f}"),
        ("TransferGaussianMAE", f"{gaussian['mae_cm']:.2f}"),
        ("TransferGaussianRMSE", f"{gaussian['rmse_cm']:.2f}"),
        ("TransferGaussianCorrelation", f"{gaussian['pearson_r']:.3f}"),
        ("TransferMAEGain", f"{gain:.2f}"),
        (
            "TransferMAEGainLo",
            f"{percentile_interval(bootstrap['mae_gain_cm'])[0]:.2f}",
        ),
        (
            "TransferMAEGainHi",
            f"{percentile_interval(bootstrap['mae_gain_cm'])[1]:.2f}",
        ),
        (
            "TransferEWMAGain",
            f"{ewma['mae_cm'] - bayes['mae_cm']:.2f}",
        ),
        (
            "TransferEWMAGainLo",
            f"{bootstrap['ewma_minus_bayesian_mae_cm'].quantile(0.025):.2f}",
        ),
        (
            "TransferEWMAGainHi",
            f"{bootstrap['ewma_minus_bayesian_mae_cm'].quantile(0.975):.2f}",
        ),
        (
            "TransferMedianGain",
            f"{running_median['mae_cm'] - bayes['mae_cm']:.2f}",
        ),
        (
            "TransferMedianGainLo",
            f"{bootstrap['running_median3_minus_bayesian_mae_cm'].quantile(0.025):.2f}",
        ),
        (
            "TransferMedianGainHi",
            f"{bootstrap['running_median3_minus_bayesian_mae_cm'].quantile(0.975):.2f}",
        ),
        (
            "TransferHoltGain",
            f"{holt['mae_cm'] - bayes['mae_cm']:.2f}",
        ),
        (
            "TransferHoltGainLo",
            f"{bootstrap['holt_minus_bayesian_mae_cm'].quantile(0.025):.2f}",
        ),
        (
            "TransferHoltGainHi",
            f"{bootstrap['holt_minus_bayesian_mae_cm'].quantile(0.975):.2f}",
        ),
        (
            "TransferGaussianGain",
            f"{gaussian['mae_cm'] - bayes['mae_cm']:.2f}",
        ),
        (
            "TransferGaussianGainLo",
            f"{bootstrap['gaussian_kalman_minus_bayesian_mae_cm'].quantile(0.025):.2f}",
        ),
        (
            "TransferGaussianGainHi",
            f"{bootstrap['gaussian_kalman_minus_bayesian_mae_cm'].quantile(0.975):.2f}",
        ),
        ("TransferCoverageEighty", f"{interval80['coverage_percent']:.1f}"),
        ("TransferWidthEighty", f"{interval80['mean_width_cm']:.1f}"),
        ("TransferCoverageNinetyFive", f"{interval95['coverage_percent']:.1f}"),
        ("TransferWidthNinetyFive", f"{interval95['mean_width_cm']:.1f}"),
        (
            "TransferPoleCandidatesOverTen",
            audit["passing_candidates_exceeding_10ft"],
        ),
        ("TransferPoleCandidates", audit["passing_candidate_images"]),
    ]
    (output_dir / "numbers_2024.tex").write_text(
        "\n".join(tex_command(name, value) for name, value in values) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else repo_root / args.output_dir
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    development = match_2021_development(repo_root)
    coefficients, cross_validated, transfer_residual_rmse = fit_2021_calibration(
        development
    )
    filtered, camera_layout = run_2024_filter(
        repo_root, coefficients, transfer_residual_rmse
    )
    manual = pd.read_csv(
        repo_root
        / "data"
        / "raw"
        / "manual_height_2024"
        / "manual_height_2024_long.csv"
    )
    validation = filtered.merge(
        manual,
        on=["biological_row_id", "plant_global_rtl", "measurement_date"],
        how="inner",
        validate="one_to_one",
    )
    if (
        len(validation) != 166
        or validation["biological_row_id"].nunique() != 4
        or validation["camera_genotype"].nunique() != 6
    ):
        raise ValueError(
            "Expected 166 matched records from four rows and six cameras; "
            f"found {len(validation)}, "
            f"{validation['biological_row_id'].nunique()}, and "
            f"{validation['camera_genotype'].nunique()}."
        )
    validation = add_transfer_intervals(
        validation,
        transfer_residual_rmse,
        degrees_freedom=development["rowid"].nunique() - 1,
    )
    validation["single_frame_abs_error_cm"] = np.abs(
        validation["transferred_single_frame_cm"] - validation["manual_height_cm"]
    )
    validation["bayesian_abs_error_cm"] = np.abs(
        validation["posterior_mean_cm"] - validation["manual_height_cm"]
    )
    validation["bayesian_mae_gain_cm"] = (
        validation["single_frame_abs_error_cm"] - validation["bayesian_abs_error_cm"]
    )

    bootstrap = cluster_bootstrap(validation)
    camera_audit, audit_summary = calibration_metadata_audit(
        repo_root,
        filtered,
        set(
            camera_layout.loc[camera_layout["automated_pose_output"], "camera_genotype"]
        ),
    )

    single = metric_summary(validation, "transferred_single_frame_cm")
    bayes = metric_summary(validation, "posterior_mean_cm")
    baseline_metrics = {
        name: metric_summary(validation, column)
        for name, column in BASELINE_COLUMNS.items()
    }
    interval_results = {
        str(level): interval_summary(validation, level) for level in [50, 80, 90, 95]
    }
    summary: dict[str, object] = {
        "design": {
            "development_year": 2021,
            "validation_year": 2024,
            "source_code_commit_locked_before_workbook_review": LOCKED_SOURCE_COMMIT,
            "manual_2024_outcomes_used_for_fitting_or_tuning": False,
            "camera_distance_transfer_ratio": (
                CAMERA_DISTANCE_2024_FT / CAMERA_DISTANCE_2021_FT
            ),
            "resampling_unit": "biological row containing a left/right camera pair",
            "interpretation": (
                "Later-year, subject-disjoint, label-held-out validation. "
                "The 2024 image tracks were previously used in unlabeled "
                "pipeline development, so this is not a fully external site "
                "validation."
            ),
        },
        "development_calibration": {
            "records": len(development),
            "camera_rows": int(development["rowid"].nunique()),
            "intercept_cm": float(coefficients[0]),
            "slope": float(coefficients[1]),
            "leave_one_row_out_mae_cm": float(
                np.abs(cross_validated["cv_error_cm"]).mean()
            ),
            "leave_one_row_out_rmse_cm": transfer_residual_rmse,
        },
        "validation_counts": {
            "manual_workbook_records": len(manual),
            "manual_workbook_plants": int(
                manual[["biological_row_id", "plant_global_rtl"]]
                .drop_duplicates()
                .shape[0]
            ),
            "matched_records": len(validation),
            "matched_plants": int(
                validation[["biological_row_id", "plant_global_rtl"]]
                .drop_duplicates()
                .shape[0]
            ),
            "biological_rows": int(validation["biological_row_id"].nunique()),
            "camera_views": int(validation["camera_genotype"].nunique()),
            "unique_calendar_dates": int(validation["measurement_date"].nunique()),
            "manual_records_without_qc_eligible_image_output": int(
                len(manual) - len(validation)
            ),
        },
        "single_frame": single,
        "fixed_causal_baselines": baseline_metrics,
        "bayesian_longitudinal": bayes,
        "paired_mae_gain_cm": float(single["mae_cm"] - bayes["mae_cm"]),
        "paired_mae_gain_95pct_row_cluster_interval_cm": percentile_interval(
            bootstrap["mae_gain_cm"]
        ),
        "transfer_aware_intervals": interval_results,
        "red_band_metadata_audit": audit_summary,
    }

    development.to_csv(output_dir / "development_matches_2021.csv", index=False)
    cross_validated.to_csv(
        output_dir / "development_leave_one_row_out_2021.csv", index=False
    )
    filtered.to_csv(output_dir / "filtered_2024_all_daily.csv", index=False)
    validation.to_csv(output_dir / "matched_manual_validation_2024.csv", index=False)
    camera_layout.to_csv(output_dir / "camera_pair_accounting_2024.csv", index=False)
    camera_audit.to_csv(output_dir / "red_band_metadata_audit_2024.csv", index=False)
    bootstrap.to_csv(output_dir / "row_cluster_bootstrap_2024.csv", index=False)
    baseline_rows: list[dict[str, object]] = []
    for name, column in BASELINE_COLUMNS.items():
        metric = metric_summary(validation, column)
        draws = bootstrap[f"{name}_minus_bayesian_mae_cm"]
        baseline_rows.append(
            {
                "estimator": name,
                **metric,
                "baseline_minus_bayesian_mae_cm": float(
                    metric["mae_cm"] - bayes["mae_cm"]
                ),
                "gain_interval_low_cm": float(draws.quantile(0.025)),
                "gain_interval_high_cm": float(draws.quantile(0.975)),
            }
        )
    baseline_rows.append(
        {
            "estimator": "bayesian_longitudinal",
            **bayes,
            "baseline_minus_bayesian_mae_cm": 0.0,
            "gain_interval_low_cm": 0.0,
            "gain_interval_high_cm": 0.0,
        }
    )
    pd.DataFrame(baseline_rows).to_csv(
        output_dir / "fixed_causal_baseline_comparison_2024.csv", index=False
    )
    validation.groupby("biological_row_id").agg(
        records=("manual_height_cm", "size"),
        plants=("plant_global_rtl", "nunique"),
        single_frame_mae_cm=("single_frame_abs_error_cm", "mean"),
        bayesian_mae_cm=("bayesian_abs_error_cm", "mean"),
        bayesian_mae_gain_cm=("bayesian_mae_gain_cm", "mean"),
    ).reset_index().to_csv(output_dir / "by_biological_row_2024.csv", index=False)
    (output_dir / "validation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (output_dir / "README.md").write_text(
        "# 2024 later-year manual-height validation\n\n"
        "The affine pose-to-height calibration is fit only on 2021 records "
        "with recovered source coordinates. Its physical scale is transferred "
        "to 2024 by the recorded 8.5/10.25 camera-distance ratio. The 2024 "
        "manual outcomes enter only after all daily image updates have been "
        "computed. Left and right camera views are paired within biological "
        "row, and bootstrap resampling uses the four biological rows.\n\n"
        "The transfer-aware intervals retain the row-held-out 2021 calibration "
        "RMSE as a non-shrinking uncertainty component and use a Student-t "
        "multiplier with five degrees of freedom, reflecting the six 2021 "
        "development rows.\n\n"
        "Fixed prefix-causal comparators are evaluated on the same daily image "
        "prefixes before manual outcomes are joined. The Gaussian local-linear "
        "filter receives the same initial growth prior and process scales as the "
        "particle filter.\n\n"
        "The red-band metadata audit is diagnostic. Automated candidates can "
        "encode more one-foot intervals than the recorded 8-10-ft pole can "
        "contain; therefore that scale is not used for the manual-height "
        "transfer result.\n",
        encoding="utf-8",
    )
    plot_validation(development, validation, coefficients, output_dir)
    write_numbers(
        output_dir,
        development,
        cross_validated,
        validation,
        coefficients,
        bootstrap,
        audit_summary,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
