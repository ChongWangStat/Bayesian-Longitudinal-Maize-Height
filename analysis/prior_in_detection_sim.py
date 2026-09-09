#!/usr/bin/env python
"""Does putting the Bayesian prior INSIDE the image analysis (detection) win?

Mechanism demonstration on simulated sequences with KNOWN truth. A detector emits,
per frame, candidate keypoint-heights: a correct candidate (true height + small
noise) and, with some probability, a spurious high-confidence candidate (tassel =
too tall, or occlusion = too short) -- the real failure mode where a per-image
detector latches onto the wrong point confidently. We compare three ways of using
(or not using) the temporal prior:

  1. Single-frame (cross-sectional): take the highest-confidence candidate. No prior.
  2. Post-hoc filter ("our side"): single-frame stream -> online particle filter.
     The prior acts only AFTER detection (can down-weight, cannot re-pick).
  3. Prior-in-detection (proposed): the filter's one-step predictive distribution is
     the prior; at each frame we SELECT the candidate maximizing confidence x prior
     likelihood, then update. The prior is inside the image analysis.

All three share the SAME online filter dynamics (height + growth + outlier mixture);
only the measurement the filter receives differs, isolating the effect of moving the
prior into detection. Scored by per-plant RMSE and 95% interval coverage of the true
latent height. Fully seeded/reproducible.

Output: outputs/candidate_ambiguity_simulation/ (CSV and summary files).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from method_comparison import regenerate_sim  # noqa: E402

OUT = ROOT / "outputs/candidate_ambiguity_simulation"
SEED = 20260724
N_PARTICLES = 3000
SIGMA_OK = 3.0          # px/cm noise on the correct candidate
P_SPURIOUS = 0.30       # chance of an extra spurious candidate
PROC_H, PROC_G = 6.0, 0.35
OUT_PROB, OUT_SD = 0.10, 40.0


def make_candidates(true_h: float, rng: np.random.Generator):
    """Return list of (location, confidence). One correct; sometimes a spurious one."""
    cands = [(true_h + rng.normal(0, SIGMA_OK), float(rng.uniform(0.60, 0.95)))]
    if rng.random() < P_SPURIOUS:
        sign = 1.0 if rng.random() < 0.5 else -1.0        # tassel(+) or occlusion(-)
        cands.append((true_h + sign * rng.uniform(25.0, 60.0),
                      float(rng.uniform(0.40, 0.90))))     # can out-score the correct one
    rng.shuffle(cands)
    return cands


class HeightFilter:
    """Compact online particle filter: latent height + nonneg-ish growth + outlier mix."""

    def __init__(self, y0: float, rng: np.random.Generator):
        self.rng = rng
        self.h = np.clip(rng.normal(y0, 8.0, N_PARTICLES), 0, 450)
        self.g = np.clip(rng.normal(3.0, 2.0, N_PARTICLES), -4.0, 15.0)
        self.w = np.full(N_PARTICLES, 1.0 / N_PARTICLES)

    def predict(self, dt: float):
        rt = np.sqrt(max(dt, 1e-6))
        self.h = np.clip(self.h + self.g * dt + self.rng.normal(0, PROC_H * rt, N_PARTICLES), 0, 450)
        self.g = np.clip(self.g + self.rng.normal(0, PROC_G * rt, N_PARTICLES), -4.0, 15.0)

    def predictive(self):
        m = float(np.sum(self.w * self.h))
        v = float(np.sum(self.w * (self.h - m) ** 2))
        return m, v

    def update(self, y: float):
        core = (1 - OUT_PROB) * _npdf(y, self.h, SIGMA_OK)
        out = OUT_PROB * _npdf(y, self.h, OUT_SD)
        self.w *= (core + out)
        s = self.w.sum()
        self.w = np.full(N_PARTICLES, 1.0 / N_PARTICLES) if s <= 0 else self.w / s
        if 1.0 / np.sum(self.w ** 2) < 0.5 * N_PARTICLES:      # systematic resample
            idx = _systematic(self.w, self.rng)
            self.h, self.g = self.h[idx], self.g[idx]
            self.w = np.full(N_PARTICLES, 1.0 / N_PARTICLES)

    def summary(self):
        m = float(np.sum(self.w * self.h))
        lo, hi = _wquantile(self.h, self.w, [0.025, 0.975])
        return m, lo, hi


def _npdf(x, mu, sd):
    return np.exp(-0.5 * ((x - mu) / sd) ** 2) / (sd * np.sqrt(2 * np.pi))


def _systematic(w, rng):
    n = len(w); pos = (rng.random() + np.arange(n)) / n
    return np.searchsorted(np.cumsum(w), pos)


def _wquantile(x, w, qs):
    o = np.argsort(x); xs, ws = x[o], w[o]; cw = np.cumsum(ws)
    return [float(xs[np.searchsorted(cw, q)]) if q <= cw[-1] else float(xs[-1]) for q in qs]


def run_plant(g: pd.DataFrame, seed: int):
    rng = np.random.default_rng(seed)
    g = g.sort_values("t").reset_index(drop=True)
    t = pd.to_datetime(g["t"]); dt = t.diff().dt.total_seconds().to_numpy() / 86400.0
    truth = g["true_h_cm"].to_numpy(float)
    cand_sets = [make_candidates(th, rng) for th in truth]

    # 1) single-frame: highest-confidence candidate
    sf = np.array([max(cs, key=lambda c: c[1])[0] for cs in cand_sets])

    # 2) post-hoc filter on the single-frame stream (prior only after detection)
    ph = _filter_stream(sf, dt, seed + 1)

    # 3) prior-in-detection: filter predictive is the prior for candidate selection
    pid_est, pid_lo, pid_hi, correct = _prior_in_detection(cand_sets, truth, dt, seed + 2)

    return dict(truth=truth, single=sf, posthoc=ph, pid=pid_est,
                pid_lo=pid_lo, pid_hi=pid_hi, pid_correct=correct)


def _filter_stream(y, dt, seed):
    rng = np.random.default_rng(seed)
    f = HeightFilter(y[0], rng)
    est, lo, hi = [], [], []
    for i, yi in enumerate(y):
        if i > 0:
            f.predict(dt[i])
        f.update(yi)
        m, l, h = f.summary(); est.append(m); lo.append(l); hi.append(h)
    return np.array(est), np.array(lo), np.array(hi)


def _prior_in_detection(cand_sets, truth, dt, seed):
    rng = np.random.default_rng(seed)
    f = HeightFilter(max(cand_sets[0], key=lambda c: c[1])[0], rng)
    est, lo, hi, correct = [], [], [], []
    for i, cs in enumerate(cand_sets):
        if i > 0:
            f.predict(dt[i])
        pm, pv = f.predictive()
        psd = np.sqrt(pv + SIGMA_OK ** 2)
        # posterior score of each candidate = detector confidence x prior likelihood
        chosen = max(cs, key=lambda c: c[1] * _npdf(c[0], pm, psd))[0]
        f.update(chosen)
        m, l, h = f.summary(); est.append(m); lo.append(l); hi.append(h)
        # did we pick the candidate closest to truth?
        correct.append(abs(chosen - truth[i]) == min(abs(c[0] - truth[i]) for c in cs))
    return np.array(est), np.array(lo), np.array(hi), np.array(correct)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sim = regenerate_sim(60, SEED)
    rows, per_plant = [], []
    for k, (uid, g) in enumerate(sim.groupby("plant_uid", sort=True)):
        r = run_plant(g, SEED + k)
        per_plant.append((uid, r))

    def rmse(a, b):
        return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))

    # aggregate per plant then average (clustered)
    def agg(key, lo=None, hi=None):
        rm = np.mean([rmse(r[key], r["truth"]) for _, r in per_plant])
        cov = None
        if lo:
            cov = np.mean([np.mean((r["truth"] >= r[lo]) & (r["truth"] <= r[hi])) for _, r in per_plant])
        return round(rm, 2), (round(float(cov), 3) if cov is not None else None)

    sf_rmse, _ = agg("single")
    ph_rmse, ph_cov = agg("posthoc_est") if False else (None, None)
    # posthoc returns tuple; unpack per plant
    ph_rmse = round(np.mean([rmse(r["posthoc"][0], r["truth"]) for _, r in per_plant]), 2)
    ph_cov = round(float(np.mean([np.mean((r["truth"] >= r["posthoc"][1]) & (r["truth"] <= r["posthoc"][2])) for _, r in per_plant])), 3)
    pid_rmse, pid_cov = agg("pid", "pid_lo", "pid_hi")
    det_acc = round(float(np.mean([np.mean(r["pid_correct"]) for _, r in per_plant])), 3)
    # single-frame detection accuracy (how often max-confidence == closest to truth)
    sf_det = []
    for _, r in per_plant:
        pass

    table = pd.DataFrame([
        {"method": "Single-frame (cross-sectional, no prior)", "prior": "none",
         "height_rmse_cm": sf_rmse, "coverage_95": None},
        {"method": "Post-hoc filter (prior after detection)", "prior": "on output",
         "height_rmse_cm": ph_rmse, "coverage_95": ph_cov},
        {"method": "Prior-in-detection (prior inside analysis)", "prior": "in detection",
         "height_rmse_cm": pid_rmse, "coverage_95": pid_cov},
    ])
    table.to_csv(OUT / "prior_in_detection_sim.csv", index=False)

    per_rows = []
    for uid, r in per_plant:
        per_rows.append(
            {
                "plant_uid": uid,
                "scenario": str(uid).rsplit("_", 1)[0],
                "single_frame_rmse_cm": rmse(r["single"], r["truth"]),
                "post_hoc_rmse_cm": rmse(r["posthoc"][0], r["truth"]),
                "prior_in_detection_rmse_cm": rmse(r["pid"], r["truth"]),
                "post_hoc_coverage_95": float(
                    np.mean((r["truth"] >= r["posthoc"][1]) & (r["truth"] <= r["posthoc"][2]))
                ),
                "prior_in_detection_coverage_95": float(
                    np.mean((r["truth"] >= r["pid_lo"]) & (r["truth"] <= r["pid_hi"]))
                ),
                "prior_in_detection_truth_closest_rate": float(np.mean(r["pid_correct"])),
            }
        )
    per_table = pd.DataFrame(per_rows)
    per_table.to_csv(OUT / "prior_in_detection_sim_per_plant.csv", index=False)

    rng_boot = np.random.default_rng(SEED + 99)
    indices = rng_boot.integers(0, len(per_table), size=(20000, len(per_table)))
    boot = {}
    for column in [
        "single_frame_rmse_cm",
        "post_hoc_rmse_cm",
        "prior_in_detection_rmse_cm",
    ]:
        values = per_table[column].to_numpy(float)
        means = values[indices].mean(axis=1)
        boot[column] = {
            "mean": float(values.mean()),
            "ci95": [float(x) for x in np.quantile(means, [0.025, 0.975])],
        }
    for name, left, right in [
        (
            "single_minus_prior_in_detection_rmse_cm",
            "single_frame_rmse_cm",
            "prior_in_detection_rmse_cm",
        ),
        (
            "post_hoc_minus_prior_in_detection_rmse_cm",
            "post_hoc_rmse_cm",
            "prior_in_detection_rmse_cm",
        ),
    ]:
        values = per_table[left].to_numpy(float) - per_table[right].to_numpy(float)
        means = values[indices].mean(axis=1)
        boot[name] = {
            "mean": float(values.mean()),
            "ci95": [float(x) for x in np.quantile(means, [0.025, 0.975])],
        }
    summary = {
        "seed": SEED,
        "bootstrap_seed": SEED + 99,
        "bootstrap_replicates": 20000,
        "plants": int(len(per_table)),
        "scenarios": int(per_table["scenario"].nunique()),
        "spurious_candidate_probability": P_SPURIOUS,
        "truth_closest_selection_rate": float(
            per_table["prior_in_detection_truth_closest_rate"].mean()
        ),
        "plant_cluster_bootstrap": boot,
    }
    (OUT / "prior_in_detection_sim_summary.json").write_text(
        __import__("json").dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(table.to_string(index=False))
    print(f"\nprior-in-detection picked the truth-closest candidate {det_acc:.1%} of the time")

    markdown_table = (
        "| Method | Prior acts | RMSE (cm) | 95% coverage |\n"
        "|---|---|---:|---:|\n"
        + "\n".join(
            f"| {row.method} | {row.prior} | {row.height_rmse_cm:.2f} | "
            + ("--" if pd.isna(row.coverage_95) else f"{row.coverage_95:.3f}")
            + " |"
            for row in table.itertuples()
        )
    )
    (OUT / "README.md").write_text(
        "# Prior-in-detection vs post-hoc vs single-frame (SIMULATION, known truth)\n\n"
        f"Seed {SEED}; 60 plants/scenario over the 8 misspecified scenarios; clustered by "
        "plant. A detector emits candidate keypoint-heights (one correct; with "
        f"p={P_SPURIOUS} a spurious tassel/occlusion candidate that can out-score it). "
        "All methods share the same online filter; only where the prior acts differs.\n\n"
        + markdown_table + "\n\n"
        f"- Prior-in-detection selected the truth-closest candidate {det_acc:.1%} of the time.\n"
        "- Single-frame has no interval. Post-hoc can down-weight a bad measurement but "
        "cannot re-pick the correct candidate; prior-in-detection avoids the wrong "
        "candidate at the source.\n"
        "- The mechanism experiment is distinct from the field configuration and is "
        "reported as controlled evidence under candidate ambiguity.\n",
        encoding="utf-8",
    )
    print(f"[wrote] {OUT/'prior_in_detection_sim.csv'} and README.md")


if __name__ == "__main__":
    main()
