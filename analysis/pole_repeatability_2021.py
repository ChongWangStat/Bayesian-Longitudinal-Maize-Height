#!/usr/bin/env python
"""Summarize temporal repeatability of usable 2021 support-pole traces.

Each row/pole-label series refers to the same stationary physical reference over
multiple dates. The within-series coefficient of variation (CV) therefore
measures repeatability of the projected annotated length. It does not establish
the absolute accuracy of the nominal 5-ft physical length.
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
            "data/processed/manual_poles_2021/manual_pole_annotations_2021.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/pole_repeatability_2021"),
    )
    parser.add_argument("--replicates", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260910)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input)
    usable = data[data["annotation_status"].eq("usable")].copy()
    series = (
        usable.groupby(["row_id", "pole_label"], as_index=False)
        .agg(
            images=("image_name", "nunique"),
            mean_length_px=("polyline_length_px", "mean"),
            sd_length_px=("polyline_length_px", "std"),
            minimum_length_px=("polyline_length_px", "min"),
            maximum_length_px=("polyline_length_px", "max"),
        )
    )
    series = series[series["images"] >= 2].copy()
    series["cv_percent"] = 100 * series["sd_length_px"] / series["mean_length_px"]
    series["relative_range_percent"] = (
        100
        * (series["maximum_length_px"] - series["minimum_length_px"])
        / series["mean_length_px"]
    )
    series = series.sort_values(["row_id", "pole_label"], kind="mergesort")

    clusters = sorted(series["row_id"].unique())
    grouped = {
        cluster: series.loc[series["row_id"].eq(cluster), "cv_percent"].to_numpy()
        for cluster in clusters
    }
    rng = np.random.default_rng(args.seed)
    draws = np.empty((args.replicates, 3))
    for index in range(args.replicates):
        selected = rng.choice(clusters, size=len(clusters), replace=True)
        values = np.concatenate([grouped[cluster] for cluster in selected])
        draws[index] = (
            np.median(values),
            np.quantile(values, 0.90),
            np.mean(values < 5.0),
        )

    payload = {
        "design": {
            "usable_annotations": int(len(usable)),
            "repeated_row_pole_series": int(len(series)),
            "stationary_camera_rows": int(series["row_id"].nunique()),
            "minimum_images_per_series": 2,
            "bootstrap_cluster": "row_id",
            "bootstrap_replicates": args.replicates,
            "seed": args.seed,
        },
        "median_cv_percent": float(series["cv_percent"].median()),
        "median_cv_row_cluster_ci95_percent": [
            float(value) for value in np.quantile(draws[:, 0], [0.025, 0.975])
        ],
        "p90_cv_percent": float(series["cv_percent"].quantile(0.90)),
        "p90_cv_row_cluster_ci95_percent": [
            float(value) for value in np.quantile(draws[:, 1], [0.025, 0.975])
        ],
        "series_below_5_percent_cv": int((series["cv_percent"] < 5.0).sum()),
        "proportion_below_5_percent_cv": float(
            (series["cv_percent"] < 5.0).mean()
        ),
        "proportion_below_5_percent_cv_row_cluster_ci95": [
            float(value) for value in np.quantile(draws[:, 2], [0.025, 0.975])
        ],
        "maximum_cv_percent": float(series["cv_percent"].max()),
        "interpretation": (
            "Within-series CV measures temporal repeatability of annotated projected "
            "pole length for a fixed camera and pole identity. It does not validate "
            "absolute physical length or transfer scale between depths."
        ),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    series.to_csv(args.output / "per_series.csv", index=False)
    (args.output / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
