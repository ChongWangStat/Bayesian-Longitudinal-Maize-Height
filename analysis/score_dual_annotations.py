#!/usr/bin/env python3
"""Validate and compare two independently completed plant-annotation sheets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


KEY = ["image", "plant_slot_right_to_left"]
COORDS = [
    "highest_visible_x_px", "highest_visible_y_px",
    "top_visible_collar_x_px", "top_visible_collar_y_px",
    "flag_leaf_tip_x_px", "flag_leaf_tip_y_px",
    "ground_contact_x_px", "ground_contact_y_px",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotator-a", type=Path, default=Path("annotation/annotator_A.csv"))
    parser.add_argument("--annotator-b", type=Path, default=Path("annotation/annotator_B.csv"))
    parser.add_argument("--output", type=Path, default=Path("outputs/dual_annotation_agreement"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    a = pd.read_csv(args.annotator_a, keep_default_na=False)
    b = pd.read_csv(args.annotator_b, keep_default_na=False)
    for label, frame in (("A", a), ("B", b)):
        missing = set(KEY + ["plant_present", "image_usable"] + COORDS) - set(frame.columns)
        if missing:
            raise ValueError(f"Annotator {label} sheet is missing columns: {sorted(missing)}")
        if frame.duplicated(KEY).any():
            raise ValueError(f"Annotator {label} sheet has duplicate image/slot rows")

    merged = a.merge(b, on=KEY, how="outer", suffixes=("_A", "_B"), indicator=True)
    incomplete_a = int((a["plant_present"].astype(str).str.strip() == "").sum())
    incomplete_b = int((b["plant_present"].astype(str).str.strip() == "").sum())
    summary: dict[str, object] = {
        "status": "incomplete" if incomplete_a or incomplete_b else "complete",
        "rows_A": len(a), "rows_B": len(b),
        "unanswered_plant_present_A": incomplete_a,
        "unanswered_plant_present_B": incomplete_b,
        "unmatched_keys": int((merged["_merge"] != "both").sum()),
    }

    if summary["status"] == "complete" and summary["unmatched_keys"] == 0:
        yes = {"1", "true", "yes", "y"}
        present_a = merged["plant_present_A"].astype(str).str.lower().isin(yes)
        present_b = merged["plant_present_B"].astype(str).str.lower().isin(yes)
        summary["plant_presence_agreement_percent"] = float(100 * (present_a == present_b).mean())
        paired = merged[present_a & present_b].copy()
        for col in COORDS:
            paired[col + "_A"] = pd.to_numeric(paired[col + "_A"], errors="coerce")
            paired[col + "_B"] = pd.to_numeric(paired[col + "_B"], errors="coerce")
        for landmark in ("highest_visible", "top_visible_collar", "flag_leaf_tip", "ground_contact"):
            dx = paired[f"{landmark}_x_px_A"] - paired[f"{landmark}_x_px_B"]
            dy = paired[f"{landmark}_y_px_A"] - paired[f"{landmark}_y_px_B"]
            distance = np.sqrt(dx**2 + dy**2).dropna()
            summary[f"{landmark}_paired_n"] = int(len(distance))
            summary[f"{landmark}_median_distance_px"] = float(distance.median()) if len(distance) else None
            summary[f"{landmark}_mean_distance_px"] = float(distance.mean()) if len(distance) else None
        for top in ("highest_visible", "top_visible_collar", "flag_leaf_tip"):
            extent_a = paired["ground_contact_y_px_A"] - paired[f"{top}_y_px_A"]
            extent_b = paired["ground_contact_y_px_B"] - paired[f"{top}_y_px_B"]
            difference = (extent_a - extent_b).dropna()
            summary[f"{top}_extent_difference_n"] = int(len(difference))
            summary[f"{top}_extent_difference_bias_px"] = float(difference.mean()) if len(difference) else None
            summary[f"{top}_extent_difference_mae_px"] = float(difference.abs().mean()) if len(difference) else None
        paired.to_csv(args.output / "paired_annotations.csv", index=False)

    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
