#!/usr/bin/env python
"""Compare fixed, prefix-causal baselines on all 2021 field-height records.

Every estimator receives the same physically scaled per-image extent. Baseline settings
are fixed without consulting manual height: EWMA alpha=0.5, a three-image running median,
Holt level/trend alpha=0.5 and beta=0.2, and a Gaussian local-linear Kalman filter whose
height-process scale is estimated robustly from image increments. The proposed robust
particle estimate is read from the canonical leakage-free run. Paired uncertainty resamples
the 12 field rows and retains all observations and plants inside each sampled row.
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
        "--input",
        type=Path,
        default=Path(
            "outputs/filter_height_sam_2021/"
            "filtered_height_sam__phi1.0_plus_pole_growth_field.csv"
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/field_baselines_2021")
    )
    parser.add_argument("--replicates", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260909)
    return parser.parse_args()


def robust_process_scale(data: pd.DataFrame) -> float:
    increments: list[float] = []
    for _, group in data.groupby("plant_uid", sort=True):
        group = group.sort_values("date")
        values = group["height_sam"].to_numpy(float)
        dates = group["date"].to_numpy(dtype="datetime64[ns]")
        if len(group) < 2:
            continue
        dt = np.diff(dates).astype("timedelta64[s]").astype(float) / 86400.0
        keep = dt > 0
        increments.extend((np.diff(values)[keep] / np.sqrt(dt[keep])).tolist())
    values = np.asarray(increments, float)
    median = np.median(values)
    return float(1.4826 * np.median(np.abs(values - median)))


def add_baselines(data: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    data = data.sort_values(["plant_uid", "date"], kind="mergesort").copy()
    for column in ("ewma_cm", "running_median3_cm", "holt_cm", "gaussian_kalman_cm"):
        data[column] = np.nan
    process_height_sd = robust_process_scale(data)

    for _, group in data.groupby("plant_uid", sort=True):
        history: list[float] = []
        ewma = None
        level = None
        trend = 0.0
        state = None
        covariance = None
        previous_date = None
        for index, row in group.iterrows():
            measurement = float(row["height_sam"])
            date = pd.Timestamp(row["date"])
            elapsed = 0.0 if previous_date is None else max(
                (date - previous_date).total_seconds() / 86400.0, 1e-6
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

            measurement_sd = float(row["measurement_sd_cm"])
            if state is None:
                state = np.array([measurement, 0.0])
                covariance = np.diag([measurement_sd**2, 8.0**2])
            else:
                transition = np.array([[1.0, elapsed], [0.0, 1.0]])
                process_covariance = np.diag(
                    [process_height_sd**2 * elapsed, 0.35**2 * elapsed]
                )
                state = transition @ state
                covariance = transition @ covariance @ transition.T + process_covariance
                innovation_variance = covariance[0, 0] + measurement_sd**2
                gain = covariance[:, 0] / innovation_variance
                state = state + gain * (measurement - state[0])
                covariance = covariance - np.outer(gain, covariance[0, :])

            data.loc[index, [
                "ewma_cm",
                "running_median3_cm",
                "holt_cm",
                "gaussian_kalman_cm",
            ]] = [ewma, running_median, level, state[0]]
            previous_date = date
    return data, process_height_sd


def metric(data: pd.DataFrame, column: str) -> dict[str, float | int]:
    error = data[column] - data["height_true"]
    return {
        "n": int(len(data)),
        "bias_cm": float(error.mean()),
        "mae_cm": float(error.abs().mean()),
        "rmse_cm": float(np.sqrt(np.mean(error**2))),
    }


def cluster_bootstrap(
    data: pd.DataFrame,
    columns: dict[str, str],
    proposed_column: str,
    replicates: int,
    seed: int,
) -> dict[str, dict[str, object]]:
    row_ids = sorted(data["rowid"].unique())
    by_row = {}
    proposed_error = (data[proposed_column] - data["height_true"]).abs()
    for row_id in row_ids:
        keep = data["rowid"].eq(row_id)
        by_row[row_id] = {
            "n": int(keep.sum()),
            "proposed": float(proposed_error[keep].sum()),
            **{
                name: float((data.loc[keep, column] - data.loc[keep, "height_true"]).abs().sum())
                for name, column in columns.items()
            },
        }
    rng = np.random.default_rng(seed)
    result: dict[str, dict[str, object]] = {}
    for name, column in columns.items():
        observed = metric(data, column)["mae_cm"] - metric(data, proposed_column)["mae_cm"]
        draws = np.empty(replicates)
        for index in range(replicates):
            selected = rng.choice(row_ids, size=len(row_ids), replace=True)
            denominator = sum(by_row[row_id]["n"] for row_id in selected)
            numerator = sum(
                by_row[row_id][name] - by_row[row_id]["proposed"]
                for row_id in selected
            )
            draws[index] = numerator / denominator
        result[name] = {
            "baseline_minus_proposed_mae_cm": float(observed),
            "ci95_cm": [float(value) for value in np.quantile(draws, [0.025, 0.975])],
            "bootstrap_probability_gain_gt_zero": float(np.mean(draws > 0)),
        }
    return result


def distributional_sensitivity(
    data: pd.DataFrame,
    methods: dict[str, str],
    replicates: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Report complete error quantiles and influence checks for the primary sample."""
    quantile_levels = (0.25, 0.50, 0.75, 0.90, 0.95)
    quantile_rows = []
    for name, column in methods.items():
        absolute_error = (data[column] - data["height_true"]).abs()
        values = absolute_error.quantile(quantile_levels)
        quantile_rows.append(
            {
                "estimator": name,
                **{
                    f"absolute_error_q{int(100 * level):02d}_cm": float(values[level])
                    for level in quantile_levels
                },
            }
        )
    quantiles = pd.DataFrame(quantile_rows)

    single_error = (data["height_sam"] - data["height_true"]).abs().to_numpy()
    proposed_error = (
        data["posterior_mean_cm"] - data["height_true"]
    ).abs().to_numpy()
    row_ids = sorted(data["rowid"].unique())
    indices_by_row = {
        row_id: np.flatnonzero(data["rowid"].eq(row_id).to_numpy())
        for row_id in row_ids
    }
    leave_one_out_rows = []
    for omitted_row in row_ids:
        keep = ~data["rowid"].eq(omitted_row).to_numpy()
        single_mae = float(single_error[keep].mean())
        proposed_mae = float(proposed_error[keep].mean())
        leave_one_out_rows.append(
            {
                "omitted_row": omitted_row,
                "records_retained": int(keep.sum()),
                "single_frame_mae_cm": single_mae,
                "particle_filter_mae_cm": proposed_mae,
                "mae_improvement_cm": single_mae - proposed_mae,
            }
        )
    leave_one_out = pd.DataFrame(leave_one_out_rows)

    rng = np.random.default_rng(seed)
    median_draws = np.empty(replicates)
    for index in range(replicates):
        selected = rng.choice(row_ids, size=len(row_ids), replace=True)
        sampled_indices = np.concatenate(
            [indices_by_row[row_id] for row_id in selected]
        )
        median_draws[index] = np.median(single_error[sampled_indices]) - np.median(
            proposed_error[sampled_indices]
        )

    median_single = float(np.median(single_error))
    median_proposed = float(np.median(proposed_error))
    min_index = leave_one_out["mae_improvement_cm"].idxmin()
    max_index = leave_one_out["mae_improvement_cm"].idxmax()
    summary = {
        "absolute_error_quantiles": list(quantile_levels),
        "median_absolute_error": {
            "single_frame_cm": median_single,
            "particle_filter_cm": median_proposed,
            "reduction_cm": median_single - median_proposed,
            "row_cluster_bootstrap_ci95_cm": [
                float(value)
                for value in np.quantile(median_draws, [0.025, 0.975])
            ],
            "bootstrap_replicates": replicates,
            "bootstrap_cluster": "rowid",
            "seed": seed,
        },
        "leave_one_row_out_mae": {
            "omissions": int(len(leave_one_out)),
            "all_improvements_positive": bool(
                (leave_one_out["mae_improvement_cm"] > 0).all()
            ),
            "minimum_improvement_cm": float(
                leave_one_out.loc[min_index, "mae_improvement_cm"]
            ),
            "minimum_omitted_row": str(
                leave_one_out.loc[min_index, "omitted_row"]
            ),
            "maximum_improvement_cm": float(
                leave_one_out.loc[max_index, "mae_improvement_cm"]
            ),
            "maximum_omitted_row": str(
                leave_one_out.loc[max_index, "omitted_row"]
            ),
        },
    }
    return quantiles, leave_one_out, summary


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(args.input)
    data["date"] = pd.to_datetime(data["date"])
    data, process_height_sd = add_baselines(data)

    methods = {
        "Single-frame image extent": "height_sam",
        "EWMA (alpha=0.5)": "ewma_cm",
        "Running median (three images)": "running_median3_cm",
        "Holt level-trend (alpha=0.5, beta=0.2)": "holt_cm",
        "Gaussian local-linear Kalman filter": "gaussian_kalman_cm",
        "Robust Bayesian particle filter": "posterior_mean_cm",
    }
    rows = [{"estimator": name, **metric(data, column)} for name, column in methods.items()]
    comparison = pd.DataFrame(rows)
    baseline_columns = {
        name: column for name, column in methods.items() if column != "posterior_mean_cm"
    }
    bootstrap = cluster_bootstrap(
        data,
        baseline_columns,
        "posterior_mean_cm",
        args.replicates,
        args.seed,
    )
    for row in rows:
        if row["estimator"] in bootstrap:
            row.update(bootstrap[row["estimator"]])
    comparison = pd.DataFrame(rows)
    comparison.to_csv(args.output / "field_baseline_comparison.csv", index=False)
    data.to_csv(args.output / "field_baseline_per_record.csv", index=False)
    quantiles, leave_one_out, sensitivity = distributional_sensitivity(
        data,
        methods,
        args.replicates,
        args.seed + 1,
    )
    quantiles.to_csv(args.output / "absolute_error_quantiles.csv", index=False)
    leave_one_out.to_csv(args.output / "leave_one_row_out.csv", index=False)
    payload = {
        "design": {
            "records": int(len(data)),
            "plants": int(data["plant_uid"].nunique()),
            "rows": int(data["rowid"].nunique()),
            "dates": int(data["date"].nunique()),
            "process_height_sd_cm_sqrt_day": process_height_sd,
            "manual_height_used_for_tuning": False,
            "bootstrap_replicates": args.replicates,
            "bootstrap_cluster": "rowid",
            "seed": args.seed,
        },
        "metrics": rows,
        "distributional_sensitivity": sensitivity,
    }
    (args.output / "summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(comparison.round(3).to_string(index=False))
    print(json.dumps(sensitivity, indent=2))


if __name__ == "__main__":
    main()
