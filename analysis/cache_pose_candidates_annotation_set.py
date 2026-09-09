#!/usr/bin/env python
"""Run the released pose checkpoint on the curated 61-image annotation set.

The low confidence threshold retains alternative instances for downstream candidate
audits. Predictions are cached so statistical analyses do not depend on repeated neural
network inference. The output metadata records the checkpoint hash, package version,
and inference settings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images",
        type=Path,
        default=Path("data/raw/pole_calibration_images"),
    )
    parser.add_argument(
        "--model", type=Path, default=Path("models/maize_pose_2021_best.pt")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/pose_candidates_annotation_set_2021"),
    )
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--iou", type=float, default=0.50)
    parser.add_argument("--max-det", type=int, default=50)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_keys(path: Path) -> tuple[str | None, str | None, str]:
    camera_match = re.search(r"C-(\d{3})", path.name, flags=re.IGNORECASE)
    date_match = re.search(r"(2021)-(\d{2})-(\d{2})", path.name)
    camera = f"C_{camera_match.group(1)}" if camera_match else None
    day = f"{date_match.group(2)}_{date_match.group(3)}" if date_match else None
    image_role = "field_date_image" if re.match(r"^C-\d{3}_", path.name) else "installation_reference"
    return camera, day, image_role


def main() -> None:
    args = parse_args()
    from ultralytics import YOLO, __version__ as ultralytics_version

    images = sorted(
        path for path in args.images.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not images:
        raise RuntimeError(f"No images found in {args.images}.")
    model = YOLO(str(args.model))
    rows: list[dict[str, object]] = []
    image_rows: list[dict[str, object]] = []
    for image_path in images:
        camera, day, role = image_keys(image_path)
        result = model.predict(
            str(image_path),
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            max_det=args.max_det,
            device=args.device,
            verbose=False,
        )[0]
        count = 0
        if result.keypoints is not None and len(result.keypoints):
            keypoints = result.keypoints.xy.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()
            boxes = result.boxes.xyxy.cpu().numpy()
            height, width = result.orig_shape
            for candidate_index in range(keypoints.shape[0]):
                top_x, top_y = keypoints[candidate_index, 0]
                root_x, root_y = keypoints[candidate_index, 1]
                x1, y1, x2, y2 = boxes[candidate_index]
                rows.append(
                    {
                        "camera": camera,
                        "day": day,
                        "image": image_path.name,
                        "image_role": role,
                        "candidate_index": candidate_index,
                        "x_top": float(top_x),
                        "y_top": float(top_y),
                        "x_root": float(root_x),
                        "y_root": float(root_y),
                        "x_root_fraction": float(root_x / width),
                        "height_px": float(max(root_y - top_y, 0.0)),
                        "confidence": float(confidences[candidate_index]),
                        "box_x1": float(x1),
                        "box_y1": float(y1),
                        "box_x2": float(x2),
                        "box_y2": float(y2),
                        "image_width": int(width),
                        "image_height": int(height),
                    }
                )
                count += 1
        image_rows.append(
            {
                "camera": camera,
                "day": day,
                "image": image_path.name,
                "image_role": role,
                "candidates": count,
                "sha256": sha256(image_path),
            }
        )

    args.output.mkdir(parents=True, exist_ok=True)
    candidates = pd.DataFrame(rows)
    manifest = pd.DataFrame(image_rows)
    candidates.to_csv(args.output / "pose_candidates.csv", index=False)
    manifest.to_csv(args.output / "image_inference_manifest.csv", index=False)
    metadata = {
        "images": len(images),
        "images_with_candidates": int((manifest["candidates"] > 0).sum()),
        "candidates": int(len(candidates)),
        "cameras": int(manifest["camera"].nunique()),
        "model": str(args.model),
        "model_sha256": sha256(args.model),
        "ultralytics_version": ultralytics_version,
        "imgsz": args.imgsz,
        "confidence_threshold": args.conf,
        "iou_threshold": args.iou,
        "max_detections": args.max_det,
        "device": args.device,
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
