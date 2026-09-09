#!/usr/bin/env python
"""Signed calibration error when extrapolating BELOW the fitted band range (the root's regime).

Uses POLE truth only (bands are 1 ft apart by construction) -- no manual height involved.
For each image we drop the lowest k bands, fit the projective calibration on the REMAINING
(upper) bands, then predict the dropped bands' known heights. That places the test points
exactly where the plant root sits: a known distance BELOW the fitted range. We record the
SIGNED error as a function of that distance, so the question "does downward extrapolation
systematically place a point too low (inflating height = z(top) - z(root))?" gets a direct,
truth-based answer, and -- if the sign is consistent -- a correction curve.

Sign convention: error = predicted_ft - true_ft. NEGATIVE error => the point is placed LOWER
than it truly is. For the ROOT that inflates (top - root) => OVERestimates plant height,
which is the direction of the manual-field discrepancy.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from calibrate_from_poles import fit_projective_calibration, transform_y  # noqa: E402

OUT = ROOT / "outputs/pole_downward_bias"
MIN_CALIB = 4


def per_image(group: pd.DataFrame, image_id, max_k: int = 3) -> list[dict]:
    g = group.dropna(subset=["y_px", "relative_height_ft"]).sort_values("relative_height_ft")
    g = g[g["relative_height_ft"] == g["relative_height_ft"].round()]
    n = len(g)
    recs: list[dict] = []
    if n < MIN_CALIB + 1:
        return recs
    for k in range(1, min(max_k, n - MIN_CALIB) + 1):
        calib, test = g.iloc[k:], g.iloc[:k]
        if len(calib) < MIN_CALIB or len(test) == 0:
            continue
        try:
            fit = fit_projective_calibration(calib.assign(image_id=image_id))
        except ValueError:
            continue
        lo_fit = float(calib["relative_height_ft"].min())      # bottom of fitted range
        pred = transform_y(test["y_px"].to_numpy(), fit)
        for p, t in zip(pred, test["relative_height_ft"].to_numpy()):
            recs.append(dict(k_dropped=k, true_ft=float(t), pred_ft=float(p),
                             below_ft=lo_fit - float(t),            # distance below fit range
                             error_ft=float(p) - float(t),
                             error_cm=(float(p) - float(t)) * 30.48,
                             image_id=image_id,
                             camera=group["camera_setup_id"].iloc[0]
                             if "camera_setup_id" in group else "na"))
    return recs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--landmarks", type=Path,
                    default=ROOT / "data/processed/automatic_pole_calibrations_daily_landmarks.csv")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lm = pd.read_csv(args.landmarks)
    recs: list[dict] = []
    for img, grp in lm.groupby("image_id"):
        recs.extend(per_image(grp, img))
    d = pd.DataFrame(recs)
    if d.empty:
        print("no records"); return
    d.to_csv(OUT / "downward_extrapolation_errors.csv", index=False)

    print(f"n test-band predictions = {len(d)}  (images {d['image_id'].nunique()})")
    print("\n=== SIGNED error vs distance BELOW the fitted band range ===")
    print("(negative error_cm => point placed too LOW => inflates measured plant height)")
    agg = d.groupby("below_ft")["error_cm"].agg(["count", "mean", "median", "std"]).round(2)
    print(agg.to_string())
    print("\n=== by number of bands dropped ===")
    print(d.groupby("k_dropped")["error_cm"].agg(["count", "mean", "median", "std"]).round(2).to_string())
    print("\n=== per-camera mean signed error (cm), 1 band dropped ===")
    print(d[d["k_dropped"] == 1].groupby("camera")["error_cm"].agg(["count", "mean"]).round(2).to_string())
    # linear trend of signed error on distance below range -> extrapolatable correction
    sub = d.dropna(subset=["below_ft", "error_cm"])
    if sub["below_ft"].nunique() > 1:
        b, a = np.polyfit(sub["below_ft"], sub["error_cm"], 1)
        print(f"\nfit: error_cm = {a:+.2f} {b:+.2f} * below_ft   "
              f"(corr={np.corrcoef(sub['below_ft'], sub['error_cm'])[0,1]:+.2f})")
        for dd in [1.0, 1.44, 2.0, 3.0]:
            print(f"   implied signed error at {dd:.2f} band-units below range: {a + b*dd:+.2f} cm")


if __name__ == "__main__":
    main()
