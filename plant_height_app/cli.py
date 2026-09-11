"""Command-line batch interface to the same engine used by the web app."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

try:
    from .engine import (
        SUPPORTED_IMAGE_SUFFIXES,
        AnalysisConfig,
        analyze_images,
        default_metadata,
        write_artifacts,
    )
except ImportError:
    from engine import (  # type: ignore[no-redef]
        SUPPORTED_IMAGE_SUFFIXES,
        AnalysisConfig,
        analyze_images,
        default_metadata,
        write_artifacts,
    )


ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate longitudinal maize height from dated fixed-camera images."
    )
    parser.add_argument("--images", required=True, type=Path, help="Image folder")
    parser.add_argument(
        "--metadata",
        type=Path,
        help="CSV with filename, capture_datetime, and camera_id; dates are inferred when omitted",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "models" / "maize_pose_2021_best.pt",
    )
    parser.add_argument(
        "--calibration-mode",
        choices=["published_2021", "known_scale", "red_band"],
        default="published_2021",
    )
    parser.add_argument("--cm-per-pixel", type=float, default=0.415886)
    parser.add_argument("--red-band-interval-cm", type=float, default=30.48)
    parser.add_argument("--pole-to-plant-depth-factor", type=float, default=0.85)
    parser.add_argument("--expected-plants", type=int, default=6)
    parser.add_argument(
        "--numbering-direction",
        choices=["left_to_right", "right_to_left"],
        default="left_to_right",
    )
    parser.add_argument("--particles", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    images = sorted(
        path
        for path in args.images.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    )
    if not images:
        raise FileNotFoundError(f"No supported images found under {args.images}")
    names = [path.name for path in images]
    if len(names) != len(set(names)):
        raise ValueError("Image basenames must be unique across the input folder.")
    image_paths = {path.name: path for path in images}
    metadata = pd.read_csv(args.metadata) if args.metadata else default_metadata(names)
    config = AnalysisConfig(
        calibration_mode=args.calibration_mode,
        cm_per_pixel=args.cm_per_pixel,
        red_band_interval_cm=args.red_band_interval_cm,
        pole_to_plant_depth_factor=args.pole_to_plant_depth_factor,
        expected_plants=args.expected_plants,
        numbering_direction=args.numbering_direction,
        particles=args.particles,
    )

    def progress(stage: str, current: int, total: int, message: str) -> None:
        print(f"[{stage} {current}/{total}] {message}", flush=True)

    artifacts = analyze_images(
        image_paths,
        metadata,
        args.model,
        config,
        progress=progress,
    )
    write_artifacts(artifacts, args.output)
    print(
        f"Wrote {len(artifacts.height_estimates)} plant-image rows to "
        f"{args.output.resolve()}"
    )
    for warning in artifacts.warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
