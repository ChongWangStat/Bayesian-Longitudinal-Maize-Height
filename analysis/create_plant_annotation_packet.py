#!/usr/bin/env python3
"""Create blinded, duplicate annotation sheets for the curated 2021 images."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import cv2
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def camera_from_name(name: str) -> str:
    match = re.search(r"C[-_](\d{3})", name, flags=re.IGNORECASE)
    return f"C-{match.group(1)}" if match else ""


def date_from_name(name: str) -> str:
    match = re.search(r"(2021-\d{2}-\d{2})", name)
    return match.group(1) if match else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=Path("data/raw/pole_calibration_images"))
    parser.add_argument("--output", type=Path, default=Path("annotation"))
    parser.add_argument("--slots", type=int, default=6)
    args = parser.parse_args()

    images = sorted(p for p in args.images.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    args.output.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    sheet_rows: list[dict[str, object]] = []
    for image in images:
        frame = cv2.imread(str(image))
        if frame is None:
            raise RuntimeError(f"Could not read {image}")
        height, width = frame.shape[:2]
        camera = camera_from_name(image.name)
        date = date_from_name(image.name)
        manifest_rows.append(
            {
                "image": image.name,
                "camera": camera,
                "date": date,
                "width_px": width,
                "height_px": height,
                "sha256": sha256(image),
            }
        )
        for slot in range(1, args.slots + 1):
            sheet_rows.append(
                {
                    "image": image.name,
                    "camera": camera,
                    "date": date,
                    "plant_slot_right_to_left": slot,
                    "plant_present": "",
                    "image_usable": "",
                    "growth_stage": "",
                    "highest_visible_x_px": "",
                    "highest_visible_y_px": "",
                    "top_visible_collar_x_px": "",
                    "top_visible_collar_y_px": "",
                    "flag_leaf_tip_x_px": "",
                    "flag_leaf_tip_y_px": "",
                    "ground_contact_x_px": "",
                    "ground_contact_y_px": "",
                    "top_occlusion": "",
                    "base_occlusion": "",
                    "confidence": "",
                    "notes": "",
                }
            )

    pd.DataFrame(manifest_rows).to_csv(args.output / "image_manifest.csv", index=False)
    sheet = pd.DataFrame(sheet_rows)
    sheet.to_csv(args.output / "annotator_A.csv", index=False)
    sheet.to_csv(args.output / "annotator_B.csv", index=False)
    print(f"Created two blinded sheets with {len(sheet):,} rows for {len(images)} images.")


if __name__ == "__main__":
    main()
