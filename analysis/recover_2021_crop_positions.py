#!/usr/bin/env python
"""Recover each 2021 per-plant crop's position in its full source frame.

The legacy 2021 pipeline stored one masked RGBA crop per plant per date (p1.png, p3.png, ...),
which preserves the plant's pixel HEIGHT but discards where the plant sat in the frame. A
position-dependent (projective) calibration needs that position back. Each crop is a masked
region of the source JPG, so we locate it by masked template matching (TM_CCORR_NORMED with the
alpha channel as the mask) and record the absolute top/bottom rows.

Output: outputs/crop_positions_2021/crop_positions.csv with, per (camera, date, plant):
  y_top_full, y_root_full   absolute rows in the 1030-px frame
  match_score               matching confidence (1.0 = perfect); low values flag failures
  height_px                 bottom-top, which must reproduce the legacy height_px
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "data/raw/plant_height_image_2021",
        help="Directory containing C_XXX_MM_DD folders with source images and RGBA crops.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/crop_positions_2021/crop_positions.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for folder in sorted(p for p in args.source.iterdir() if p.is_dir()):
        m = re.match(r"^(C_\d+)_(\d{2})_(\d{2})$", folder.name)
        if not m:
            continue
        cam, mm, dd = m.groups()
        jpgs = list(folder.glob("*.JPG"))
        if not jpgs:
            continue
        full = cv2.imread(str(jpgs[0]))
        if full is None:
            continue
        for crop_path in sorted(folder.glob("p*.png")):
            if crop_path.name.startswith("binary"):
                continue
            plant = crop_path.stem
            crop = cv2.imread(str(crop_path), cv2.IMREAD_UNCHANGED)
            if crop is None or crop.ndim != 3 or crop.shape[2] != 4:
                continue
            tmpl = crop[..., :3]
            alpha = crop[..., 3]
            mask = (alpha > 0).astype(np.uint8) * 255
            if mask.sum() == 0 or tmpl.shape[0] >= full.shape[0] or tmpl.shape[1] >= full.shape[1]:
                continue
            try:
                res = cv2.matchTemplate(full, tmpl, cv2.TM_CCORR_NORMED,
                                        mask=cv2.merge([mask] * 3))
            except cv2.error:
                continue
            res = np.nan_to_num(res, nan=-1.0, posinf=-1.0, neginf=-1.0)
            _, score, _, loc = cv2.minMaxLoc(res)
            x0, y0 = loc
            h = tmpl.shape[0]
            # within the crop, the plant's own top/bottom rows come from the mask
            ys = np.where(mask.max(axis=1) > 0)[0]
            if len(ys) == 0:
                continue
            y_root_crop = int(ys.max())
            x_at_root = np.where(mask[y_root_crop] > 0)[0]
            x_root_crop = int(np.median(x_at_root)) if len(x_at_root) else int(mask.shape[1] / 2)
            rows.append(dict(rowid=cam, date_md=f"{mm}_{dd}", plant=plant,
                             match_score=round(float(score), 4),
                             crop_h=h, crop_w=tmpl.shape[1],
                             x_root_full=int(x0 + x_root_crop),
                             y_top_full=int(y0 + ys.min()),
                             y_root_full=int(y0 + ys.max()),
                             height_px=int(ys.max() - ys.min()),
                             frame_h=full.shape[0], frame_w=full.shape[1],
                             source=jpgs[0].name))
    d = pd.DataFrame(rows)
    d.to_csv(args.output, index=False)
    print(f"recovered {len(d)} crops across {d['rowid'].nunique() if len(d) else 0} cameras")
    if len(d):
        print("\nmatch score: min %.3f  median %.3f  frac>0.9: %.2f"
              % (d["match_score"].min(), d["match_score"].median(),
                 (d["match_score"] > 0.9).mean()))
        print("\nrecovered rows: y_top %d-%d   y_root %d-%d  (frame is %d px tall)"
              % (d["y_top_full"].min(), d["y_top_full"].max(),
                 d["y_root_full"].min(), d["y_root_full"].max(), d["frame_h"].iloc[0]))
        print("\nsample:")
        print(d.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
