#!/usr/bin/env python
"""Cluster-bootstrap confidence intervals for the held-out validation metrics.

Because bands from one camera are not independent, point estimates alone
overstate precision -- especially for the 2025 locked-test set, which has
few cameras. We resample whole cameras with replacement (a cluster
bootstrap), recompute the camera-mean-of-means metric on each resample, and
report percentile CIs. Wide test-set intervals are the honest consequence of
few test cameras and are reported as such rather than hidden behind a point
estimate.

Seeded via a fixed integer sequence (no wall-clock RNG) for reproducibility.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--band", type=Path,
        default=Path("outputs/pole_holdout_validation_daily/band_holdout_errors.csv"),
    )
    p.add_argument(
        "--registry", type=Path, default=Path("data/reference/pole_camera_registry.csv"),
    )
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260724)
    return p.parse_args()


def camera_mean_of_means(df: pd.DataFrame, error_col: str) -> float:
    """MAE averaged within camera, then across cameras (the reported statistic)."""
    per_cam = df.groupby("camera_setup_id")[error_col].apply(lambda s: s.abs().mean())
    return float(per_cam.mean())


def cluster_bootstrap_ci(
    df: pd.DataFrame, error_col: str, n_boot: int, rng: np.random.Generator
) -> tuple[float, float, float]:
    cameras = df["camera_setup_id"].unique()
    # Pre-split for speed.
    groups = {c: df[df["camera_setup_id"] == c] for c in cameras}
    point = camera_mean_of_means(df, error_col)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        drawn = rng.choice(cameras, size=len(cameras), replace=True)
        # Average each drawn camera's within-camera MAE (a camera may repeat).
        vals = [groups[c][error_col].abs().mean() for c in drawn]
        boots[b] = float(np.mean(vals))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, float(lo), float(hi)


def main() -> None:
    args = parse_args()
    band = pd.read_csv(args.band)
    reg = pd.read_csv(args.registry)[["camera_genotype", "pole_reference_year"]].rename(
        columns={"camera_genotype": "camera_setup_id"}
    )
    band = band.drop(columns=["pole_reference_year"], errors="ignore").merge(
        reg, on="camera_setup_id", how="left"
    )

    rng = np.random.default_rng(args.seed)
    out = {}
    for year, label in [(2024, "development"), (2025, "locked_test")]:
        for split in ["interpolation_alternating", "extrapolation_lower_to_upper"]:
            sub = band[(band["pole_reference_year"] == year) & (band["split"] == split)]
            if sub.empty:
                continue
            point, lo, hi = cluster_bootstrap_ci(sub, "error_in", args.n_boot, rng)
            key = f"{label}_{split}"
            out[key] = {
                "n_cameras": int(sub["camera_setup_id"].nunique()),
                "n_obs": int(len(sub)),
                "mae_in": round(point, 3),
                "ci95_lo_in": round(lo, 3),
                "ci95_hi_in": round(hi, 3),
            }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
