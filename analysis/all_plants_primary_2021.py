#!/usr/bin/env python
"""Summarize the prespecified all-plant 2021 comparison with row bootstrap CIs."""

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
        "--output",
        type=Path,
        default=Path("outputs/filter_height_sam_2021/all_plants_primary.json"),
    )
    parser.add_argument("--replicates", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260908)
    return parser.parse_args()


def metrics(data: pd.DataFrame, column: str) -> dict[str, float | int]:
    error = data[column] - data["height_true"]
    return {
        "n": int(len(data)),
        "plants": int(data["plant_uid"].nunique()),
        "rows": int(data["rowid"].nunique()),
        "bias_cm": float(error.mean()),
        "mae_cm": float(error.abs().mean()),
        "rmse_cm": float(np.sqrt((error**2).mean())),
    }


def bootstrap_improvement(
    data: pd.DataFrame, replicates: int, seed: int
) -> dict[str, object]:
    clusters = sorted(data["rowid"].unique())
    groups = {cluster: data[data["rowid"] == cluster] for cluster in clusters}
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates)
    for index in range(replicates):
        chosen = rng.choice(clusters, size=len(clusters), replace=True)
        sampled = pd.concat([groups[cluster] for cluster in chosen], ignore_index=True)
        image_error = (sampled["height_sam"] - sampled["height_true"]).abs().mean()
        filter_error = (
            sampled["posterior_mean_cm"] - sampled["height_true"]
        ).abs().mean()
        draws[index] = image_error - filter_error
    observed = (
        (data["height_sam"] - data["height_true"]).abs().mean()
        - (data["posterior_mean_cm"] - data["height_true"]).abs().mean()
    )
    return {
        "cluster": "rowid",
        "clusters": len(clusters),
        "replicates": replicates,
        "seed": seed,
        "mae_improvement_cm": float(observed),
        "ci95_cm": [float(value) for value in np.quantile(draws, [0.025, 0.975])],
    }


def summarize(data: pd.DataFrame, replicates: int, seed: int) -> dict[str, object]:
    return {
        "single_frame": metrics(data, "height_sam"),
        "online_filter": metrics(data, "posterior_mean_cm"),
        "paired_row_cluster_bootstrap": bootstrap_improvement(data, replicates, seed),
    }


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input)
    result = {
        "configuration": (
            "height_sam geometric scale; phi=1.0; growth field learned from the "
            "2024-2025 pole stream; no 2021 field height used for fitting"
        ),
        "whole_season_all_plants": summarize(data, args.replicates, args.seed),
        "endpoint_all_plants": summarize(
            data.sort_values("date").groupby("plant_uid", as_index=False).tail(1),
            args.replicates,
            args.seed + 1,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
