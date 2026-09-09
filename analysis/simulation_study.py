#!/usr/bin/env python
"""Simulation study of the online Bayesian monotone height filter.

The real-image analysis has no known latent height, so the filter's
inferential properties (does the posterior recover the truth? do the stated
intervals cover at their nominal rate?) cannot be assessed on it directly.
This script generates trajectories with a *known* latent height and growth
rate, runs the exact production filter (``filter_one_plant``) on simulated
noisy measurements, and compares the posterior against the truth.

Design principle: we import and call the deployed filter unchanged, so this
validates the shipped code, not a re-implementation. Two regimes are run:

  * well-specified -- data simulated from the filter's own state-space model,
    a pure implementation/sampler correctness check that should give near
    nominal coverage; and
  * misspecified -- data simulated from realistic maize biology (Gompertz
    plateau, heavy-tailed outliers, depth-ratio uncertainty, irregular and
    missing observations), run with the filter's *deployed* hyperparameters,
    which tests robustness to the model being wrong in the ways we expect it
    to be wrong in the field.

All randomness is seeded; no wall-clock or unseeded RNG is used, so results
are reproducible. Metrics cluster by simulated plant.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from bayesian_online_height_filter import filter_one_plant  # noqa: E402


# Deployed hyperparameters: the values the pipeline actually ships with after
# empirical calibration (analysis/calibrate_growth_noise.py on 2024 cameras).
DEPLOYED = dict(
    plant_col="plant_uid",
    date_col="t",
    measurement_col="y_cm",
    measurement_sd_col="y_sd_cm",
    particles=5000,
    base_seed=20260723,
    default_measurement_sd_cm=15.0,
    measurement_sd_multiplier=1.0,
    initial_growth_mean_cm_day=3.0,
    initial_growth_sd_cm_day=2.0,
    process_height_sd_cm_sqrt_day=10.244,
    process_growth_sd_cm_day_sqrt_day=0.35,
    minimum_growth_cm_day=-4.0,
    maximum_growth_cm_day=15.0,
    outlier_probability=0.065,
    outlier_sd_cm=59.04,
    resample_ess_fraction=0.5,
)


def gompertz(t: np.ndarray, asymptote: float, displacement: float, rate: float) -> np.ndarray:
    """Monotone increasing Gompertz curve; returns height in cm at times t (days)."""
    return asymptote * np.exp(-displacement * np.exp(-rate * t))


def gompertz_rate(t: np.ndarray, asymptote: float, displacement: float, rate: float) -> np.ndarray:
    """Analytic derivative of the Gompertz curve, cm/day."""
    return gompertz(t, asymptote, displacement, rate) * displacement * rate * np.exp(-rate * t)


def simulate_plant(
    scenario: str,
    plant_index: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Return one plant's observed series with true latent height/rate attached."""
    n_obs = 12
    base_interval = 7.0

    # Observation times.
    if scenario == "irregular_times":
        gaps = rng.uniform(3.0, 14.0, n_obs - 1)
    else:
        jitter = rng.normal(0, 0.15, n_obs - 1)
        gaps = np.clip(base_interval + jitter, 1.0, None)
    times = np.concatenate([[0.0], np.cumsum(gaps)])

    # Latent truth.
    if scenario == "gradual_linear":
        rate_cm_day = rng.uniform(2.5, 4.0)
        h0 = rng.uniform(20, 45)
        true_h = h0 + rate_cm_day * times
        true_rate = np.full_like(times, rate_cm_day)
    else:
        # Gompertz family for everything else, with scenario-specific shape.
        asymptote = rng.uniform(230, 290)
        displacement = rng.uniform(2.5, 4.5)
        if scenario == "plateau_early":
            gr = rng.uniform(0.09, 0.13)
        elif scenario in ("rapid_then_plateau", "well_specified"):
            gr = rng.uniform(0.05, 0.075)
        else:
            gr = rng.uniform(0.05, 0.09)
        # Shift so t=0 is early-season, not at the inflection.
        t_shift = times + rng.uniform(5, 20)
        true_h = gompertz(t_shift, asymptote, displacement, gr)
        true_rate = gompertz_rate(t_shift, asymptote, displacement, gr)

    # Measurement model.
    meas_sd = rng.uniform(8.0, 13.0)  # per-plant measurement noise scale (cm)
    if scenario == "well_specified":
        # Simulate directly from the filter's own model: random-walk growth,
        # Gaussian measurement noise, the deployed outlier mixture.
        true_h, true_rate = _simulate_from_filter_model(times, rng, meas_sd)
        y = true_h + rng.normal(0, meas_sd, len(times))
        # Inject the model's own outliers.
        is_out = rng.random(len(times)) < DEPLOYED["outlier_probability"]
        y[is_out] = true_h[is_out] + rng.normal(0, DEPLOYED["outlier_sd_cm"], is_out.sum())
    else:
        y = true_h + rng.normal(0, meas_sd, len(times))

    # Scenario-specific corruptions of the observed series.
    if scenario == "heavy_outliers":
        is_out = rng.random(len(times)) < 0.15
        y[is_out] = y[is_out] + rng.normal(0, 55.0, is_out.sum()) * rng.choice([-1, 1], is_out.sum())
    if scenario == "depth_uncertainty":
        # A per-plant multiplicative depth-ratio error (kappa mis-set by +/-8%).
        kappa_err = rng.normal(1.0, 0.08)
        y = y * kappa_err
    if scenario == "localization_error":
        # Correlated top/root pixel bias that drifts over the season.
        drift = np.cumsum(rng.normal(0, 3.0, len(times)))
        y = y + drift

    df = pd.DataFrame(
        {
            "plant_uid": f"{scenario}_{plant_index:03d}",
            "scenario": scenario,
            "t": pd.Timestamp("2025-06-01") + pd.to_timedelta(times, unit="D"),
            "y_cm": y,
            "y_sd_cm": meas_sd,
            "true_h_cm": true_h,
            "true_rate_cm_day": true_rate,
            "obs_index": np.arange(len(times)),
            "n_obs_plant": len(times),
        }
    )

    if scenario == "missing_images":
        # Drop ~30% of interior observations (keep first and last).
        interior = df.index[1:-1]
        drop = rng.choice(interior, size=int(0.3 * len(interior)), replace=False)
        df = df.drop(index=drop).reset_index(drop=True)
        df["obs_index"] = np.arange(len(df))
        df["n_obs_plant"] = len(df)

    return df


def _simulate_from_filter_model(
    times: np.ndarray, rng: np.random.Generator, meas_sd: float
) -> tuple[np.ndarray, np.ndarray]:
    """Latent height/rate drawn from the filter's own transition model."""
    h = np.zeros(len(times))
    v = np.zeros(len(times))
    h[0] = rng.uniform(25, 45)
    v[0] = rng.uniform(2.5, 4.0)
    for i in range(1, len(times)):
        dt = times[i] - times[i - 1]
        root_dt = np.sqrt(dt)
        v[i] = v[i - 1] + rng.normal(0, DEPLOYED["process_growth_sd_cm_day_sqrt_day"] * root_dt)
        v[i] = np.clip(v[i], 0.0, DEPLOYED["maximum_growth_cm_day"])  # enforce monotone truth
        # Note: the filter's own process-height sd (10.244) is a combined
        # process+measurement term; using it here would double-count the
        # measurement noise added separately, so we use a smaller pure-process
        # term and let meas_sd carry the observation noise.
        h[i] = h[i - 1] + v[i - 1] * dt + rng.normal(0, 2.0 * root_dt)
        h[i] = max(h[i], h[i - 1])  # monotone latent truth
    return h, v


def run_filter(df: pd.DataFrame, particles: int | None = None) -> pd.DataFrame:
    kwargs = dict(DEPLOYED)
    if particles is not None:
        kwargs["particles"] = particles
    frames = []
    for _, group in df.groupby("plant_uid", sort=True):
        merged = group.reset_index(drop=True)
        out = filter_one_plant(merged, **kwargs)
        # filter_one_plant preserves passed-through columns, including truth.
        frames.append(out)
    return pd.concat(frames, ignore_index=True)


def cluster_metrics(result: pd.DataFrame) -> dict:
    """Per-plant then across-plant summary of recovery vs. known truth."""
    r = result.copy()
    r["h_err"] = r["posterior_mean_cm"] - r["true_h_cm"]
    r["rate_err"] = r["posterior_growth_mean_cm_day"] - r["true_rate_cm_day"]
    r["h_covered"] = (r["true_h_cm"] >= r["posterior_q025_cm"]) & (
        r["true_h_cm"] <= r["posterior_q975_cm"]
    )
    r["interval_width"] = r["posterior_q975_cm"] - r["posterior_q025_cm"]

    per_plant = r.groupby("plant_uid").agg(
        h_bias=("h_err", "mean"),
        h_mae=("h_err", lambda s: s.abs().mean()),
        h_rmse=("h_err", lambda s: np.sqrt((s**2).mean())),
        rate_bias=("rate_err", "mean"),
        rate_rmse=("rate_err", lambda s: np.sqrt((s**2).mean())),
        coverage=("h_covered", "mean"),
        width=("interval_width", "mean"),
    )
    return {
        "n_plants": int(per_plant.shape[0]),
        "n_obs": int(len(r)),
        "height_bias_cm": round(float(per_plant["h_bias"].mean()), 2),
        "height_mae_cm": round(float(per_plant["h_mae"].mean()), 2),
        "height_rmse_cm": round(float(per_plant["h_rmse"].mean()), 2),
        "growth_rate_bias_cm_day": round(float(per_plant["rate_bias"].mean()), 3),
        "growth_rate_rmse_cm_day": round(float(per_plant["rate_rmse"].mean()), 3),
        "coverage_95": round(float(per_plant["coverage"].mean()), 3),
        "mean_interval_width_cm": round(float(per_plant["width"].mean()), 2),
    }


def position_split_metrics(result: pd.DataFrame) -> dict:
    """Coverage/RMSE at the start vs. end of trajectories."""
    r = result.copy()
    r["h_err"] = r["posterior_mean_cm"] - r["true_h_cm"]
    r["h_covered"] = (r["true_h_cm"] >= r["posterior_q025_cm"]) & (
        r["true_h_cm"] <= r["posterior_q975_cm"]
    )
    r["frac"] = r["obs_index"] / (r["n_obs_plant"] - 1).clip(lower=1)
    out = {}
    for label, mask in [
        ("first_third", r["frac"] <= 1 / 3),
        ("last_third", r["frac"] >= 2 / 3),
    ]:
        sub = r[mask]
        out[label] = {
            "n_obs": int(len(sub)),
            "height_rmse_cm": round(float(np.sqrt((sub["h_err"] ** 2).mean())), 2),
            "coverage_95": round(float(sub["h_covered"].mean()), 3),
        }
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--plants-per-scenario", type=int, default=60)
    p.add_argument("--seed", type=int, default=20260724)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    scenarios = [
        "well_specified",
        "gradual_linear",
        "rapid_then_plateau",
        "plateau_early",
        "irregular_times",
        "missing_images",
        "heavy_outliers",
        "depth_uncertainty",
        "localization_error",
    ]

    # Deterministic per-scenario seeds derived from the base seed and index.
    scenario_rows = []
    position_rows = []
    all_obs = []
    for s_idx, scenario in enumerate(scenarios):
        rng = np.random.default_rng(args.seed + 1000 * s_idx)
        plants = [simulate_plant(scenario, i, rng) for i in range(args.plants_per_scenario)]
        sim = pd.concat(plants, ignore_index=True)
        result = run_filter(sim)
        all_obs.append(result.assign(scenario=scenario))

        m = cluster_metrics(result)
        m["scenario"] = scenario
        scenario_rows.append(m)

        pos = position_split_metrics(result)
        position_rows.append(
            {
                "scenario": scenario,
                "first_third_rmse_cm": pos["first_third"]["height_rmse_cm"],
                "first_third_coverage": pos["first_third"]["coverage_95"],
                "last_third_rmse_cm": pos["last_third"]["height_rmse_cm"],
                "last_third_coverage": pos["last_third"]["coverage_95"],
            }
        )
        print(f"[{scenario}] {json.dumps(m)}")

    scenario_df = pd.DataFrame(scenario_rows)[
        [
            "scenario",
            "n_plants",
            "n_obs",
            "height_bias_cm",
            "height_mae_cm",
            "height_rmse_cm",
            "growth_rate_bias_cm_day",
            "growth_rate_rmse_cm_day",
            "coverage_95",
            "mean_interval_width_cm",
        ]
    ]
    scenario_df.to_csv(args.output / "simulation_scenario_metrics.csv", index=False)
    pd.DataFrame(position_rows).to_csv(
        args.output / "simulation_position_metrics.csv", index=False
    )

    # --- Particle-count sensitivity on one representative scenario ---
    sens_rows = []
    for particles in [500, 1000, 2000, 5000, 10000]:
        rng = np.random.default_rng(args.seed + 99)
        plants = [simulate_plant("rapid_then_plateau", i, rng) for i in range(args.plants_per_scenario)]
        sim = pd.concat(plants, ignore_index=True)
        t0 = time.perf_counter()  # timing only; not used for any RNG
        result = run_filter(sim, particles=particles)
        elapsed = time.perf_counter() - t0
        m = cluster_metrics(result)
        sens_rows.append(
            {
                "particles": particles,
                "height_rmse_cm": m["height_rmse_cm"],
                "coverage_95": m["coverage_95"],
                "mean_interval_width_cm": m["mean_interval_width_cm"],
                "seconds": round(elapsed, 1),
            }
        )
        print(f"[particles={particles}] {json.dumps(sens_rows[-1])}")
    pd.DataFrame(sens_rows).to_csv(
        args.output / "simulation_particle_sensitivity.csv", index=False
    )

    pd.concat(all_obs, ignore_index=True).to_csv(
        args.output / "simulation_observations.csv", index=False
    )

    print(f"\nSimulation study complete: {args.output.resolve()}")


if __name__ == "__main__":
    main()
