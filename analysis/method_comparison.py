#!/usr/bin/env python
"""Baseline comparison and ablation study on simulated data with known truth.

The one-step-ahead comparison in the real-data analysis can only measure
agreement with the next noisy image, not recovery of the true trajectory.
Here we regenerate the same simulated trajectories used in the simulation
study (identical seeds), where the latent height is known, and compare the
proposed filter against baselines and against ablated versions of itself,
scoring every method by height RMSE and 95%-interval coverage of the true
latent height, clustered by plant.

Methods
-------
Proposed (full)         : deployed monotone particle filter.
Ablations (same filter, one component disabled):
  no monotonicity       : growth rate allowed strongly negative.
  no outlier mixture    : outlier probability set to zero.
  no growth-rate state  : slope pinned at zero (pure random walk on height).
Baselines (separate estimators):
  last obs. carried fwd : causal, no model.
  local linear trend KF : unconstrained Gaussian state-space (statsmodels).
  exponential smoothing : Holt's linear trend, causal.
  isotonic (retrospective) : noncausal monotone least squares; an upper
                          bound that uses future data, labeled as such.

All causal methods see only observations up to the current time. The
retrospective isotonic fit is explicitly noncausal and included only as a
reference ceiling. Interval coverage is reported where a method produces a
predictive/posterior interval; point-only methods report RMSE alone.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from bayesian_online_height_filter import filter_one_plant  # noqa: E402
from simulation_study import DEPLOYED, simulate_plant  # noqa: E402

warnings.filterwarnings("ignore")


SCENARIOS = [
    "gradual_linear",
    "rapid_then_plateau",
    "plateau_early",
    "irregular_times",
    "missing_images",
    "heavy_outliers",
    "depth_uncertainty",
    "localization_error",
]


def regenerate_sim(plants_per_scenario: int, base_seed: int) -> pd.DataFrame:
    """Reproduce the simulation-study inputs exactly (same per-scenario seeds)."""
    # Mirror the seed scheme in simulation_study.main: scenarios list there
    # begins with 'well_specified' at index 0, so the misspecified scenarios
    # start at index 1. We reproduce that indexing to get identical data.
    full_scenarios = ["well_specified"] + SCENARIOS
    frames = []
    for s_idx, scenario in enumerate(full_scenarios):
        if scenario == "well_specified":
            continue
        rng = np.random.default_rng(base_seed + 1000 * s_idx)
        for i in range(plants_per_scenario):
            frames.append(simulate_plant(scenario, i, rng))
    return pd.concat(frames, ignore_index=True)


def run_particle_variant(sim: pd.DataFrame, **overrides) -> pd.DataFrame:
    kwargs = dict(DEPLOYED)
    kwargs.update(overrides)
    frames = []
    for _, group in sim.groupby("plant_uid", sort=True):
        frames.append(filter_one_plant(group.reset_index(drop=True), **kwargs))
    return pd.concat(frames, ignore_index=True)


def score_particle(result: pd.DataFrame) -> dict:
    r = result.copy()
    r["h_err"] = r["posterior_mean_cm"] - r["true_h_cm"]
    r["covered"] = (r["true_h_cm"] >= r["posterior_q025_cm"]) & (
        r["true_h_cm"] <= r["posterior_q975_cm"]
    )
    per_plant = r.groupby("plant_uid").agg(
        rmse=("h_err", lambda s: np.sqrt((s**2).mean())),
        cover=("covered", "mean"),
    )
    return {
        "height_rmse_cm": round(float(per_plant["rmse"].mean()), 2),
        "coverage_95": round(float(per_plant["cover"].mean()), 3),
    }


# ---- Baselines producing (estimate, lo, hi) per observation ----------------


def baseline_locf(g: pd.DataFrame) -> pd.DataFrame:
    est = g["y_cm"].shift(1)
    est.iloc[0] = g["y_cm"].iloc[0]
    return pd.DataFrame({"est": est.to_numpy(), "lo": np.nan, "hi": np.nan}, index=g.index)


def baseline_kalman_llt(g: pd.DataFrame) -> pd.DataFrame:
    """Unconstrained local-linear-trend Kalman filter, filtered (causal) states."""
    from statsmodels.tsa.statespace.structural import UnobservedComponents

    y = g["y_cm"].to_numpy(float)
    if len(y) < 4:
        return pd.DataFrame({"est": y, "lo": np.nan, "hi": np.nan}, index=g.index)
    model = UnobservedComponents(y, level="local linear trend")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = model.fit(disp=False, maxiter=50)
    # Filtered (one-sided) level; predicted state std for intervals.
    fs = res.filtered_state[0]
    fs_cov = res.filtered_state_cov[0, 0]
    sd = np.sqrt(np.clip(fs_cov, 0, None))
    return pd.DataFrame(
        {"est": fs, "lo": fs - 1.96 * sd, "hi": fs + 1.96 * sd}, index=g.index
    )


def baseline_holt(g: pd.DataFrame) -> pd.DataFrame:
    """Holt's linear-trend exponential smoothing, one-step filtered fits."""
    from statsmodels.tsa.holtwinters import Holt

    y = g["y_cm"].to_numpy(float)
    if len(y) < 4:
        return pd.DataFrame({"est": y, "lo": np.nan, "hi": np.nan}, index=g.index)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = Holt(y, initialization_method="estimated").fit()
    return pd.DataFrame(
        {"est": res.fittedvalues, "lo": np.nan, "hi": np.nan}, index=g.index
    )


def baseline_isotonic(g: pd.DataFrame) -> pd.DataFrame:
    """Retrospective (noncausal) isotonic regression -- uses the whole series."""
    from sklearn.isotonic import IsotonicRegression

    y = g["y_cm"].to_numpy(float)
    x = np.arange(len(y))
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
    est = iso.fit_transform(x, y)
    return pd.DataFrame({"est": est, "lo": np.nan, "hi": np.nan}, index=g.index)


def score_baseline(sim: pd.DataFrame, fn) -> dict:
    parts = []
    for _, g in sim.groupby("plant_uid", sort=True):
        g = g.reset_index(drop=True)
        out = fn(g)
        out = out.reset_index(drop=True)
        d = pd.DataFrame(
            {
                "plant_uid": g["plant_uid"],
                "true": g["true_h_cm"].to_numpy(float),
                "est": out["est"].to_numpy(float),
                "lo": out["lo"].to_numpy(float),
                "hi": out["hi"].to_numpy(float),
            }
        )
        parts.append(d)
    r = pd.concat(parts, ignore_index=True).dropna(subset=["est"])
    r["h_err"] = r["est"] - r["true"]
    per_plant_rmse = r.groupby("plant_uid")["h_err"].apply(
        lambda s: np.sqrt((s**2).mean())
    )
    result = {"height_rmse_cm": round(float(per_plant_rmse.mean()), 2)}
    if r["lo"].notna().any():
        r_cov = r.dropna(subset=["lo", "hi"])
        r_cov = r_cov.assign(cov=(r_cov["true"] >= r_cov["lo"]) & (r_cov["true"] <= r_cov["hi"]))
        result["coverage_95"] = round(float(r_cov.groupby("plant_uid")["cov"].mean().mean()), 3)
    else:
        result["coverage_95"] = None
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--plants-per-scenario", type=int, default=60)
    p.add_argument("--seed", type=int, default=20260724)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sim = regenerate_sim(args.plants_per_scenario, args.seed)

    rows = []

    # --- Proposed full model + ablations (all particle-filter variants) ---
    full = run_particle_variant(sim)
    rows.append({"method": "Proposed monotone filter (full)", "kind": "proposed", "causal": "yes", **score_particle(full)})

    abl_nomono = run_particle_variant(sim, minimum_growth_cm_day=-60.0)
    rows.append({"method": "Ablation: no monotonicity", "kind": "ablation", "causal": "yes", **score_particle(abl_nomono)})

    abl_noout = run_particle_variant(sim, outlier_probability=0.0)
    rows.append({"method": "Ablation: no outlier mixture", "kind": "ablation", "causal": "yes", **score_particle(abl_noout)})

    abl_noslope = run_particle_variant(
        sim,
        initial_growth_mean_cm_day=0.0,
        initial_growth_sd_cm_day=1e-6,
        process_growth_sd_cm_day_sqrt_day=0.0,
    )
    rows.append({"method": "Ablation: no growth-rate state", "kind": "ablation", "causal": "yes", **score_particle(abl_noslope)})

    # --- External baselines ---
    rows.append({"method": "Last observation carried forward", "kind": "baseline", "causal": "yes", **score_baseline(sim, baseline_locf)})
    rows.append({"method": "Local linear trend Kalman filter", "kind": "baseline", "causal": "yes", **score_baseline(sim, baseline_kalman_llt)})
    rows.append({"method": "Holt exponential smoothing", "kind": "baseline", "causal": "yes", **score_baseline(sim, baseline_holt)})
    rows.append({"method": "Isotonic regression (retrospective)", "kind": "baseline", "causal": "no", **score_baseline(sim, baseline_isotonic)})

    df = pd.DataFrame(rows)[["method", "kind", "causal", "height_rmse_cm", "coverage_95"]]
    df.to_csv(args.output / "method_comparison.csv", index=False)
    print(df.to_string(index=False))
    print(f"\nWrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
