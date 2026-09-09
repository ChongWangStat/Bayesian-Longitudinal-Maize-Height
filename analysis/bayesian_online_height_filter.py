#!/usr/bin/env python
"""Sequential Bayesian plant-height inference with a robust particle filter.

The filter emits a posterior after each image and never revises an earlier
result using a later image. Hyperparameters are supplied on the command line
and written to the output, making prior/sensitivity choices auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import logsumexp, ndtr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--plant-col",
        default="plant_uid",
        help=(
            "Plant identifier column, or comma-separated columns that jointly "
            "identify a plant (for example rowid,plantid)."
        ),
    )
    parser.add_argument("--date-col", default="capture_datetime")
    parser.add_argument(
        "--measurement-col", default="pole_calibrated_height_cm"
    )
    parser.add_argument("--measurement-sd-col", default="measurement_sd_cm")
    parser.add_argument("--truth-col")
    parser.add_argument(
        "--quality-col",
        default="provisional_quality_flag",
        help="Boolean eligibility column; pass an empty string to use all rows.",
    )
    parser.add_argument("--particles", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--default-measurement-sd-cm", type=float, default=15.0)
    parser.add_argument("--measurement-sd-multiplier", type=float, default=1.0)
    parser.add_argument("--initial-growth-mean-cm-day", type=float, default=3.0)
    parser.add_argument("--initial-growth-sd-cm-day", type=float, default=2.0)
    parser.add_argument("--process-height-sd-cm-sqrt-day", type=float, default=1.5)
    parser.add_argument(
        "--process-growth-sd-cm-day-sqrt-day", type=float, default=0.35
    )
    parser.add_argument("--minimum-growth-cm-day", type=float, default=-4.0)
    parser.add_argument("--maximum-growth-cm-day", type=float, default=15.0)
    parser.add_argument("--outlier-probability", type=float, default=0.08)
    parser.add_argument("--outlier-sd-cm", type=float, default=60.0)
    parser.add_argument("--resample-ess-fraction", type=float, default=0.5)
    parser.add_argument(
        "--outlier-probability-col",
        help="Optional per-observation outlier-probability column (e.g. environment-driven).",
    )
    parser.add_argument(
        "--initial-growth-mean-col",
        help="Optional per-plant initial growth-rate prior mean column (e.g. genotype/GDD BLUP).",
    )
    parser.add_argument(
        "--initial-growth-sd-col",
        help="Optional per-plant initial growth-rate prior SD column.",
    )
    parser.add_argument(
        "--growth-reversion",
        type=float,
        default=1.0,
        help=(
            "Per-day geometric decay of the growth rate toward zero "
            "(1.0 = random walk, unchanged; <1 encodes plateauing growth)."
        ),
    )
    return parser.parse_args()


def stable_seed(label: object, base_seed: int) -> int:
    digest = hashlib.sha256(f"{base_seed}|{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little") % (2**32 - 1)


def weighted_quantile(
    values: np.ndarray, quantiles: list[float], weights: np.ndarray
) -> np.ndarray:
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    cumulative /= cumulative[-1]
    return np.interp(quantiles, cumulative, sorted_values)


def systematic_resample(
    rng: np.random.Generator, weights: np.ndarray
) -> np.ndarray:
    positions = (rng.random() + np.arange(len(weights))) / len(weights)
    cumulative = np.cumsum(weights)
    return np.searchsorted(cumulative, positions, side="right")


def normal_logpdf(value: float, mean: np.ndarray, sd: float) -> np.ndarray:
    return -0.5 * ((value - mean) / sd) ** 2 - np.log(sd) - 0.5 * np.log(
        2 * np.pi
    )


def predictive_mixture_cdf(
    value: float,
    height_particles: np.ndarray,
    weights: np.ndarray,
    measurement_sd: float,
    outlier_probability: float,
    outlier_sd_cm: float,
) -> float:
    """CDF of the one-step observation law represented by the particles."""
    inlier = ndtr((value - height_particles) / measurement_sd)
    outlier = ndtr((value - height_particles) / outlier_sd_cm)
    component_cdf = (
        (1.0 - outlier_probability) * inlier
        + outlier_probability * outlier
    )
    return float(np.sum(weights * component_cdf))


def predictive_mixture_quantile(
    probability: float,
    height_particles: np.ndarray,
    weights: np.ndarray,
    measurement_sd: float,
    outlier_probability: float,
    outlier_sd_cm: float,
) -> float:
    """Numerically invert the weighted inlier/outlier particle-mixture CDF."""
    tail_sd = max(measurement_sd, outlier_sd_cm)
    lower = float(np.min(height_particles) - 10.0 * tail_sd)
    upper = float(np.max(height_particles) + 10.0 * tail_sd)

    def objective(value: float) -> float:
        return predictive_mixture_cdf(
            value,
            height_particles,
            weights,
            measurement_sd,
            outlier_probability,
            outlier_sd_cm,
        ) - probability

    return float(brentq(objective, lower, upper, xtol=1e-6, rtol=1e-10))


def filter_one_plant(
    group: pd.DataFrame,
    plant_col: str,
    date_col: str,
    measurement_col: str,
    measurement_sd_col: str | None,
    particles: int,
    base_seed: int,
    default_measurement_sd_cm: float,
    measurement_sd_multiplier: float,
    initial_growth_mean_cm_day: float,
    initial_growth_sd_cm_day: float,
    process_height_sd_cm_sqrt_day: float,
    process_growth_sd_cm_day_sqrt_day: float,
    minimum_growth_cm_day: float,
    maximum_growth_cm_day: float,
    outlier_probability: float,
    outlier_sd_cm: float,
    resample_ess_fraction: float,
    outlier_probability_col: str | None = None,
    initial_growth_mean_col: str | None = None,
    initial_growth_sd_col: str | None = None,
    growth_reversion: float = 1.0,
    growth_field: tuple[np.ndarray, np.ndarray] | None = None,
    growth_field_retention: float = 0.0,
) -> pd.DataFrame:
    group = group.sort_values(date_col, kind="mergesort").copy()
    label = group[plant_col].iloc[0]
    rng = np.random.default_rng(stable_seed(label, base_seed))
    first_measurement = float(group[measurement_col].iloc[0])
    if measurement_sd_col and measurement_sd_col in group:
        first_sd = float(group[measurement_sd_col].iloc[0])
    else:
        first_sd = default_measurement_sd_cm
    if not np.isfinite(first_sd) or first_sd <= 0:
        first_sd = default_measurement_sd_cm
    first_sd = max(1.0, first_sd * measurement_sd_multiplier)

    # Optional per-plant informative growth prior (e.g. genotype/GDD BLUP).
    # Absent or non-finite -> fall back to the global scalar, so behavior is
    # identical to a run without auxiliary information.
    plant_growth_mean = initial_growth_mean_cm_day
    if initial_growth_mean_col and initial_growth_mean_col in group:
        candidate = float(group[initial_growth_mean_col].iloc[0])
        if np.isfinite(candidate):
            plant_growth_mean = candidate
    plant_growth_sd = initial_growth_sd_cm_day
    if initial_growth_sd_col and initial_growth_sd_col in group:
        candidate = float(group[initial_growth_sd_col].iloc[0])
        if np.isfinite(candidate) and candidate > 0:
            plant_growth_sd = candidate

    height_particles = rng.normal(first_measurement, first_sd, particles)
    height_particles = np.clip(height_particles, 0, 450)
    growth_particles = rng.normal(
        plant_growth_mean,
        plant_growth_sd,
        particles,
    )
    growth_particles = np.clip(
        growth_particles, minimum_growth_cm_day, maximum_growth_cm_day
    )
    weights = np.full(particles, 1 / particles)

    previous_date: pd.Timestamp | None = None
    raw_history: list[tuple[pd.Timestamp, float]] = []
    output_rows: list[dict[str, object]] = []
    for sequence_number, row in enumerate(group.itertuples(index=False), start=1):
        row_data = row._asdict()
        current_date = pd.Timestamp(row_data[date_col])
        measurement = float(row_data[measurement_col])
        measurement_sd = (
            float(row_data[measurement_sd_col])
            if measurement_sd_col
            and measurement_sd_col in row_data
            and pd.notna(row_data[measurement_sd_col])
            else default_measurement_sd_cm
        )
        measurement_sd = max(1.0, measurement_sd * measurement_sd_multiplier)

        # Optional per-observation outlier probability (e.g. driven by that
        # camera-date's wind/lighting). Absent or non-finite -> global scalar,
        # so behavior is identical to a run without auxiliary information.
        step_outlier_probability = outlier_probability
        if (
            outlier_probability_col
            and outlier_probability_col in row_data
            and pd.notna(row_data[outlier_probability_col])
        ):
            candidate = float(row_data[outlier_probability_col])
            if 0.0 <= candidate < 1.0:
                step_outlier_probability = candidate

        if previous_date is None:
            elapsed_days = 0.0
            predictive_mean = np.nan
            predictive_sd = np.nan
            predictive_median = np.nan
            predictive_q025 = np.nan
            predictive_q05 = np.nan
            predictive_q10 = np.nan
            predictive_q25 = np.nan
            predictive_q75 = np.nan
            predictive_q90 = np.nan
            predictive_q95 = np.nan
            predictive_q975 = np.nan
            predictive_log_score = np.nan
            predictive_pit = np.nan
            outlier_posterior = np.nan
            ess = float(particles)
        else:
            elapsed_days = (current_date - previous_date).total_seconds() / 86400
            elapsed_days = max(elapsed_days, 1e-6)
            root_dt = np.sqrt(elapsed_days)
            height_particles = (
                height_particles
                + growth_particles * elapsed_days
                + rng.normal(
                    0,
                    process_height_sd_cm_sqrt_day * root_dt,
                    particles,
                )
            )
            height_particles = np.clip(height_particles, 0, 450)
            # Growth-rate transition. With growth_reversion < 1 the rate decays
            # geometrically toward zero each elapsed day (a mean-zero AR(1)
            # process), encoding biological deceleration toward a plateau;
            # growth_reversion == 1 (default) is the plain random walk and
            # leaves earlier behavior unchanged.
            # A GROWTH FIELD generalizes this. growth_reversion pulls the rate toward
            # ZERO, which is a pre-specified parametric decay whose one constant has to
            # be fitted. Given an empirical rate-vs-height field r_hat(h) -- estimated
            # elsewhere, e.g. from a densely observed reference stream -- we instead pull
            # the rate toward r_hat(h) at the particle's current height. Nothing is
            # fitted here: the field is supplied. growth_field_retention is the per-day
            # fraction of the deviation from the field that persists (0 = adopt the field
            # each step, 1 = ignore it), and defaults to full adoption.
            if growth_field is not None:
                field_h, field_r = growth_field
                target = np.interp(height_particles, field_h, field_r)
                if growth_field_retention <= 0.0:
                    growth_particles = target
                else:
                    keep = growth_field_retention**elapsed_days
                    growth_particles = target + (growth_particles - target) * keep
            elif growth_reversion != 1.0:
                growth_particles = growth_particles * (growth_reversion**elapsed_days)
            growth_particles = growth_particles + rng.normal(
                0,
                process_growth_sd_cm_day_sqrt_day * root_dt,
                particles,
            )
            growth_particles = np.clip(
                growth_particles,
                minimum_growth_cm_day,
                maximum_growth_cm_day,
            )

            predictive_mean = float(np.sum(weights * height_particles))
            latent_variance = float(
                np.sum(weights * (height_particles - predictive_mean) ** 2)
            )
            observation_variance = (
                (1.0 - step_outlier_probability) * measurement_sd**2
                + step_outlier_probability * outlier_sd_cm**2
            )
            predictive_variance = latent_variance + observation_variance
            predictive_sd = float(np.sqrt(predictive_variance))
            predictive_quantiles = {
                probability: predictive_mixture_quantile(
                    probability,
                    height_particles,
                    weights,
                    measurement_sd,
                    step_outlier_probability,
                    outlier_sd_cm,
                )
                for probability in (0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975)
            }
            predictive_q025 = predictive_quantiles[0.025]
            predictive_q05 = predictive_quantiles[0.05]
            predictive_q10 = predictive_quantiles[0.10]
            predictive_q25 = predictive_quantiles[0.25]
            predictive_median = predictive_quantiles[0.50]
            predictive_q75 = predictive_quantiles[0.75]
            predictive_q90 = predictive_quantiles[0.90]
            predictive_q95 = predictive_quantiles[0.95]
            predictive_q975 = predictive_quantiles[0.975]
            predictive_pit = predictive_mixture_cdf(
                measurement,
                height_particles,
                weights,
                measurement_sd,
                step_outlier_probability,
                outlier_sd_cm,
            )

            log_inlier = (
                np.log1p(-step_outlier_probability)
                + normal_logpdf(
                    measurement, height_particles, measurement_sd
                )
            )
            log_outlier = np.log(step_outlier_probability) + normal_logpdf(
                measurement, height_particles, outlier_sd_cm
            )
            component_log_likelihood = np.logaddexp(log_inlier, log_outlier)
            predictive_log_score = float(
                logsumexp(np.log(weights) + component_log_likelihood)
            )
            log_weights = np.log(weights) + component_log_likelihood
            log_weights -= logsumexp(log_weights)
            weights = np.exp(log_weights)
            outlier_responsibility = np.exp(
                log_outlier - component_log_likelihood
            )
            outlier_posterior = float(
                np.sum(weights * outlier_responsibility)
            )
            ess = float(1 / np.sum(weights**2))

        posterior_mean = float(np.sum(weights * height_particles))
        posterior_sd = float(
            np.sqrt(
                np.sum(weights * (height_particles - posterior_mean) ** 2)
            )
        )
        posterior_quantiles = weighted_quantile(
            height_particles,
            [0.025, 0.10, 0.50, 0.90, 0.975],
            weights,
        )
        growth_mean = float(np.sum(weights * growth_particles))
        growth_sd = float(
            np.sqrt(
                np.sum(weights * (growth_particles - growth_mean) ** 2)
            )
        )

        last_observation_prediction = (
            raw_history[-1][1] if raw_history else np.nan
        )
        if len(raw_history) >= 2:
            previous_time, previous_value = raw_history[-1]
            older_time, older_value = raw_history[-2]
            raw_elapsed = (previous_time - older_time).total_seconds() / 86400
            raw_slope = (
                (previous_value - older_value) / raw_elapsed
                if raw_elapsed > 0
                else 0.0
            )
            raw_slope = float(
                np.clip(
                    raw_slope,
                    minimum_growth_cm_day,
                    maximum_growth_cm_day,
                )
            )
            linear_prediction = previous_value + raw_slope * elapsed_days
        else:
            linear_prediction = last_observation_prediction

        output_row = dict(row_data)
        output_row.update(
            {
                "online_sequence_number": sequence_number,
                "elapsed_days": elapsed_days,
                "predictive_mean_cm": predictive_mean,
                "predictive_sd_cm": predictive_sd,
                "predictive_q025_cm": predictive_q025,
                "predictive_q05_cm": predictive_q05,
                "predictive_q10_cm": predictive_q10,
                "predictive_q25_cm": predictive_q25,
                "predictive_median_cm": predictive_median,
                "predictive_q75_cm": predictive_q75,
                "predictive_q90_cm": predictive_q90,
                "predictive_q95_cm": predictive_q95,
                "predictive_q975_cm": predictive_q975,
                "predictive_log_score": predictive_log_score,
                "predictive_pit": predictive_pit,
                "last_observation_prediction_cm": last_observation_prediction,
                "linear_extrapolation_prediction_cm": linear_prediction,
                "posterior_mean_cm": posterior_mean,
                "posterior_sd_cm": posterior_sd,
                "posterior_q025_cm": posterior_quantiles[0],
                "posterior_q10_cm": posterior_quantiles[1],
                "posterior_median_cm": posterior_quantiles[2],
                "posterior_q90_cm": posterior_quantiles[3],
                "posterior_q975_cm": posterior_quantiles[4],
                "posterior_growth_mean_cm_day": growth_mean,
                "posterior_growth_sd_cm_day": growth_sd,
                "outlier_posterior_probability": outlier_posterior,
                "effective_sample_size": ess,
            }
        )
        output_rows.append(output_row)

        if ess < resample_ess_fraction * particles:
            indices = systematic_resample(rng, weights)
            height_particles = height_particles[indices]
            growth_particles = growth_particles[indices]
            weights.fill(1 / particles)
        previous_date = current_date
        raw_history.append((current_date, measurement))

    return pd.DataFrame(output_rows)


def error_metrics(
    observed: pd.Series, estimated: pd.Series, label: str
) -> dict[str, object]:
    keep = observed.notna() & estimated.notna()
    error = estimated[keep] - observed[keep]
    return {
        "estimator": label,
        "n": int(keep.sum()),
        "bias_cm": float(error.mean()) if len(error) else None,
        "mae_cm": float(error.abs().mean()) if len(error) else None,
        "rmse_cm": (
            float(np.sqrt(np.mean(error**2))) if len(error) else None
        ),
    }


def summarize_results(
    results: pd.DataFrame,
    measurement_col: str,
    truth_col: str | None,
) -> dict[str, object]:
    later = results[results["online_sequence_number"] > 1]
    interval_columns = {
        "50": ("predictive_q25_cm", "predictive_q75_cm", 0.50),
        "80": ("predictive_q10_cm", "predictive_q90_cm", 0.20),
        "90": ("predictive_q05_cm", "predictive_q95_cm", 0.10),
        "95": ("predictive_q025_cm", "predictive_q975_cm", 0.05),
    }
    interval_diagnostics: dict[str, dict[str, float | int]] = {}
    observed = later[measurement_col]
    for label, (lower_col, upper_col, alpha) in interval_columns.items():
        valid = observed.notna() & later[lower_col].notna() & later[upper_col].notna()
        lower = later.loc[valid, lower_col]
        upper = later.loc[valid, upper_col]
        truth = observed.loc[valid]
        interval_diagnostics[label] = {
            "nominal_coverage": 1.0 - alpha,
            "n": int(valid.sum()),
            "empirical_coverage": float(((truth >= lower) & (truth <= upper)).mean()),
            "mean_width_cm": float((upper - lower).mean()),
            "median_width_cm": float((upper - lower).median()),
        }

    # Weighted interval score over four central intervals. Lower is better.
    valid_wis = observed.notna() & later["predictive_median_cm"].notna()
    wis_numerator = 0.5 * (
        observed.loc[valid_wis] - later.loc[valid_wis, "predictive_median_cm"]
    ).abs()
    for lower_col, upper_col, alpha in interval_columns.values():
        lower = later.loc[valid_wis, lower_col]
        upper = later.loc[valid_wis, upper_col]
        truth = observed.loc[valid_wis]
        interval_score = (
            (upper - lower)
            + (2.0 / alpha) * (lower - truth).clip(lower=0)
            + (2.0 / alpha) * (truth - upper).clip(lower=0)
        )
        wis_numerator = wis_numerator + (alpha / 2.0) * interval_score
    mean_wis = float((wis_numerator / 4.5).mean()) if valid_wis.any() else None

    summary: dict[str, object] = {
        "forecast_target": (
            "the next image-derived measurement; this is a consistency test, "
            "not validation against physical plant height"
        ),
        "forecast_metrics": [
            error_metrics(
                later[measurement_col],
                later["predictive_mean_cm"],
                "bayesian_one_step_predictive_mean",
            ),
            error_metrics(
                later[measurement_col],
                later["last_observation_prediction_cm"],
                "last_observation_carried_forward",
            ),
            error_metrics(
                later[measurement_col],
                later["linear_extrapolation_prediction_cm"],
                "two_point_linear_extrapolation",
            ),
        ],
        "predictive_interval_diagnostics": interval_diagnostics,
        "predictive_95_interval_coverage_of_image_measurement": (
            interval_diagnostics["95"]["empirical_coverage"] if len(later) else None
        ),
        "mean_predictive_log_score": (
            float(later["predictive_log_score"].mean()) if len(later) else None
        ),
        "mean_weighted_interval_score_cm": mean_wis,
    }
    if truth_col and truth_col in results:
        summary["truth_target"] = truth_col
        summary["truth_metrics"] = [
            error_metrics(
                results[truth_col],
                results[measurement_col],
                "raw_image_measurement",
            ),
            error_metrics(
                results[truth_col],
                results["posterior_mean_cm"],
                "bayesian_filtered_posterior_mean",
            ),
        ]
        truth_keep = results[truth_col].notna()
        summary["posterior_95_interval_coverage_of_truth"] = float(
            (
                (
                    results.loc[truth_keep, truth_col]
                    >= results.loc[truth_keep, "posterior_q025_cm"]
                )
                & (
                    results.loc[truth_keep, truth_col]
                    <= results.loc[truth_keep, "posterior_q975_cm"]
                )
            ).mean()
        )
    return summary


def plot_results(
    results: pd.DataFrame,
    output: Path,
    plant_col: str,
    date_col: str,
    measurement_col: str,
) -> None:
    plants = sorted(results[plant_col].dropna().unique())
    selected = plants[: min(12, len(plants))]
    columns = 3
    rows = int(np.ceil(len(selected) / columns))
    fig, axes = plt.subplots(
        rows, columns, figsize=(14, 3.5 * rows), squeeze=False
    )
    for axis, plant in zip(axes.ravel(), selected):
        data = results[results[plant_col] == plant].sort_values(date_col)
        dates = pd.to_datetime(data[date_col])
        axis.fill_between(
            dates,
            data["posterior_q025_cm"].to_numpy(float),
            data["posterior_q975_cm"].to_numpy(float),
            color="#92c5de",
            alpha=0.45,
            label="95% posterior interval",
        )
        axis.plot(
            dates,
            data["posterior_mean_cm"],
            color="#2166ac",
            linewidth=2,
            label="posterior mean",
        )
        axis.scatter(
            dates,
            data[measurement_col],
            color="#b2182b",
            s=22,
            zorder=3,
            label="image measurement",
        )
        axis.set_title(str(plant), fontsize=9)
        axis.tick_params(axis="x", rotation=30)
        axis.grid(alpha=0.2)
    for axis in axes.ravel()[len(selected) :]:
        axis.axis("off")
    if selected:
        handles, labels = axes.ravel()[0].get_legend_handles_labels()
        axes.ravel()[0].legend(handles, labels, fontsize=8, frameon=False)
    fig.suptitle("Strictly online Bayesian height updates (selected plants)")
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input)
    plant_columns = [
        column.strip() for column in args.plant_col.split(",") if column.strip()
    ]
    if len(plant_columns) == 1:
        plant_col = plant_columns[0]
    else:
        missing_plant_columns = [
            column for column in plant_columns if column not in data
        ]
        if missing_plant_columns:
            raise ValueError(
                f"Missing plant identifier columns: {missing_plant_columns}"
            )
        plant_col = "analysis_plant_uid"
        data[plant_col] = data[plant_columns].astype(str).agg("::".join, axis=1)
    data[args.date_col] = pd.to_datetime(data[args.date_col], errors="raise")
    data[args.measurement_col] = pd.to_numeric(
        data[args.measurement_col], errors="coerce"
    )
    if args.measurement_sd_col in data:
        data[args.measurement_sd_col] = pd.to_numeric(
            data[args.measurement_sd_col], errors="coerce"
        )
        measurement_sd_col: str | None = args.measurement_sd_col
    else:
        measurement_sd_col = None
    if args.truth_col and args.truth_col in data:
        data[args.truth_col] = pd.to_numeric(data[args.truth_col], errors="coerce")

    eligible = data[
        data[plant_col].notna() & data[args.measurement_col].notna()
    ].copy()
    if args.quality_col and args.quality_col in eligible:
        quality = eligible[args.quality_col]
        if quality.dtype != bool:
            quality = (
                quality.astype(str)
                .str.strip()
                .str.lower()
                .isin(["true", "1", "yes"])
            )
        eligible = eligible[quality].copy()
    if eligible.empty:
        raise RuntimeError("No eligible longitudinal observations.")

    frames = [
        filter_one_plant(
            group,
            plant_col,
            args.date_col,
            args.measurement_col,
            measurement_sd_col,
            args.particles,
            args.seed,
            args.default_measurement_sd_cm,
            args.measurement_sd_multiplier,
            args.initial_growth_mean_cm_day,
            args.initial_growth_sd_cm_day,
            args.process_height_sd_cm_sqrt_day,
            args.process_growth_sd_cm_day_sqrt_day,
            args.minimum_growth_cm_day,
            args.maximum_growth_cm_day,
            args.outlier_probability,
            args.outlier_sd_cm,
            args.resample_ess_fraction,
            args.outlier_probability_col,
            args.initial_growth_mean_col,
            args.initial_growth_sd_col,
            args.growth_reversion,
        )
        for _, group in eligible.groupby(plant_col, sort=True)
    ]
    results = pd.concat(frames, ignore_index=True)
    results = results.sort_values(
        [plant_col, args.date_col], kind="mergesort"
    ).reset_index(drop=True)

    args.output.mkdir(parents=True, exist_ok=True)
    export = results.copy()
    export[args.date_col] = export[args.date_col].map(
        lambda value: pd.Timestamp(value).isoformat()
    )
    export.to_csv(args.output / "online_bayesian_height_posteriors.csv", index=False)
    summary = summarize_results(
        results, args.measurement_col, args.truth_col
    )
    hyperparameters = {
        "model": "robust sequential Monte Carlo local-linear-trend state model",
        "causal_update": True,
        "particles": args.particles,
        "seed": args.seed,
        "default_measurement_sd_cm": args.default_measurement_sd_cm,
        "measurement_sd_multiplier": args.measurement_sd_multiplier,
        "initial_growth_mean_cm_day": args.initial_growth_mean_cm_day,
        "initial_growth_sd_cm_day": args.initial_growth_sd_cm_day,
        "process_height_sd_cm_sqrt_day": args.process_height_sd_cm_sqrt_day,
        "process_growth_sd_cm_day_sqrt_day": (
            args.process_growth_sd_cm_day_sqrt_day
        ),
        "minimum_growth_cm_day": args.minimum_growth_cm_day,
        "maximum_growth_cm_day": args.maximum_growth_cm_day,
        "outlier_probability": args.outlier_probability,
        "outlier_sd_cm": args.outlier_sd_cm,
        "resample_ess_fraction": args.resample_ess_fraction,
        "measurement_equation": (
            "y_t is a prespecified inlier/outlier Gaussian mixture around "
            "latent height h_t"
        ),
        "predictive_interval": (
            "weighted particle-mixture quantiles, including both inlier and "
            "outlier observation components"
        ),
        "transition_equation": (
            "h_t = h_(t-1) + dt*v_(t-1) + process noise; "
            "v_t = v_(t-1) + process noise"
        ),
    }
    (args.output / "model_hyperparameters.json").write_text(
        json.dumps(hyperparameters, indent=2), encoding="utf-8"
    )
    (args.output / "evaluation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    plot_results(
        results,
        args.output / "online_bayesian_trajectories.png",
        plant_col,
        args.date_col,
        args.measurement_col,
    )
    print(
        f"Filtered {len(results)} observations from "
        f"{results[plant_col].nunique()} plants into "
        f"{args.output.resolve()}"
    )


if __name__ == "__main__":
    main()
