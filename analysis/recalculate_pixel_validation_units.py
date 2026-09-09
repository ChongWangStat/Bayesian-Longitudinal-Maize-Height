#!/usr/bin/env python
"""Recalculate detector-validation centimeter metrics from the recorded optics.

The saved out-of-fold predictions are already in pixels.  Earlier centimeter
columns used a regression slope fitted to field heights.  This script replaces
that conversion with the prespecified 2021 camera-geometry scale D/f and a zero
intercept, without retraining or changing any pixel prediction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


F_PX_2021 = 4.5 / 6.17 * 5152 * (1030 / 5152)
D_FT_2021 = 10.25
CM_PER_PX = D_FT_2021 / F_PX_2021 * 30.48


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path("outputs/pixel_validation_2021"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    per_path = args.directory / "per_instance.csv"
    summary_path = args.directory / "summary.json"
    data = pd.read_csv(per_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    data["gt_h_cm"] = data["gt_h_px"] * CM_PER_PX
    data["pred_h_cm"] = data["pred_h_px"] * CM_PER_PX
    error_px = data["pred_h_px"] - data["gt_h_px"]
    error_cm = error_px * CM_PER_PX

    summary.update(
        {
            "height_mae_px": float(error_px.abs().mean()),
            "height_bias_px": float(error_px.mean()),
            "height_rmse_px": float(np.sqrt((error_px**2).mean())),
            "height_corr": float(data[["gt_h_px", "pred_h_px"]].corr().iloc[0, 1]),
            "height_mae_cm": float(error_cm.abs().mean()),
            "height_bias_cm": float(error_cm.mean()),
            "height_rmse_cm": float(np.sqrt((error_cm**2).mean())),
            "cm_per_px": float(CM_PER_PX),
            "cm_conversion": (
                "recorded 2021 camera geometry: D/f with D=10.25 ft, "
                "4.5 mm focal length, 6.17 mm sensor width, and 1030-px "
                "stored field of view; zero intercept"
            ),
        }
    )

    data.to_csv(per_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
