#!/usr/bin/env python
"""Evaluate 2021 latent-height posterior intervals against held-out manual heights.

The posterior interval is formed after the current image is incorporated. Manual
field height is used only as an external reference outcome and never enters the
filter, its settings, or interval construction. Whole stationary-camera rows are
resampled so repeated observations within a row remain together.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


INTERVALS = (
    (0.80, "posterior_q10_cm", "posterior_q90_cm"),
    (0.95, "posterior_q025_cm", "posterior_q975_cm"),
)


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
        "--output",
        type=Path,
        default=Path("outputs/manual_height_uncertainty_2021"),
    )
    parser.add_argument("--replicates", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260910)
    return parser.parse_args()


def summarize_interval(
    data: pd.DataFrame,
    nominal: float,
    lower: str,
    upper: str,
    replicates: int,
    seed: int,
) -> dict[str, object]:
    covered = data["height_true"].between(data[lower], data[upper]).to_numpy(int)
    widths = (data[upper] - data[lower]).to_numpy(float)
    below = (data["height_true"] < data[lower]).to_numpy(int)
    above = (data["height_true"] > data[upper]).to_numpy(int)

    clusters = sorted(data["rowid"].unique())
    by_cluster = []
    for cluster in clusters:
        keep = data["rowid"].eq(cluster).to_numpy()
        by_cluster.append(
            (
                int(keep.sum()),
                int(covered[keep].sum()),
                float(widths[keep].sum()),
            )
        )
    cluster_stats = np.asarray(by_cluster, dtype=float)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(clusters), size=(replicates, len(clusters)))
    sampled_n = cluster_stats[sampled, 0].sum(axis=1)
    sampled_coverage = cluster_stats[sampled, 1].sum(axis=1) / sampled_n
    sampled_width = cluster_stats[sampled, 2].sum(axis=1) / sampled_n

    return {
        "nominal_coverage": nominal,
        "n": int(len(data)),
        "covered": int(covered.sum()),
        "empirical_coverage": float(covered.mean()),
        "coverage_row_cluster_ci95": [
            float(value)
            for value in np.quantile(sampled_coverage, [0.025, 0.975])
        ],
        "mean_width_cm": float(widths.mean()),
        "mean_width_row_cluster_ci95_cm": [
            float(value) for value in np.quantile(sampled_width, [0.025, 0.975])
        ],
        "median_width_cm": float(np.median(widths)),
        "below_interval": int(below.sum()),
        "above_interval": int(above.sum()),
        "lower_column": lower,
        "upper_column": upper,
    }


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input)
    required = {
        "rowid",
        "plant_uid",
        "date",
        "height_true",
        *(column for _, lower, upper in INTERVALS for column in (lower, upper)),
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    interval_rows = [
        summarize_interval(
            data,
            nominal,
            lower,
            upper,
            args.replicates,
            args.seed + index,
        )
        for index, (nominal, lower, upper) in enumerate(INTERVALS)
    ]

    by_date_rows: list[dict[str, object]] = []
    for nominal, lower, upper in INTERVALS:
        for date, group in data.groupby("date", sort=True):
            covered = group["height_true"].between(group[lower], group[upper])
            width = group[upper] - group[lower]
            by_date_rows.append(
                {
                    "date": date,
                    "nominal_coverage": nominal,
                    "n": int(len(group)),
                    "covered": int(covered.sum()),
                    "empirical_coverage": float(covered.mean()),
                    "mean_width_cm": float(width.mean()),
                }
            )

    payload = {
        "design": {
            "records": int(len(data)),
            "plants": int(data["plant_uid"].nunique()),
            "stationary_camera_rows": int(data["rowid"].nunique()),
            "dates": int(data["date"].nunique()),
            "target": "latent plant height after incorporating the current image",
            "reference": "manual field height",
            "manual_height_used_for_fitting_or_tuning": False,
            "bootstrap_cluster": "rowid",
            "bootstrap_replicates": args.replicates,
            "seed": args.seed,
        },
        "intervals": interval_rows,
        "interpretation": (
            "Coverage uses manual field height as a held-out physical reference proxy. "
            "It evaluates posterior agreement after the current image update, not "
            "one-step prediction before the image and not manual-measurement error."
        ),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(interval_rows).to_csv(
        args.output / "interval_calibration.csv", index=False
    )
    pd.DataFrame(by_date_rows).to_csv(args.output / "by_date.csv", index=False)
    (args.output / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
