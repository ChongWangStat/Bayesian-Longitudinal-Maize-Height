#!/usr/bin/env python
"""Import the manually annotated 2021 camera-support poles.

The CVAT XML files use ``pole1`` through ``pole4`` for distinct visible
camera-support poles.  Every polyline runs from the nominal camera mounting
height to the ground contact of that pole.  The 2021 installation record gives
a nominal support-pole/camera height of 5 ft (152.4 cm).  The label number is an
within-image identity only; it is not interpreted as a distance class.

The field-layout record separately gives four marked intervals of 35 in
between adjacent camera rows (140 in total).  Those are horizontal layout
intervals, not tick marks along the vertical support poles.

``C-039_2021-07-30JPG.JPG`` duplicates the July 30 C-039 scene.  Per the
project lead's decision on 2026-09-08, this importer retains
``C-039_2021-07-30.JPG`` and excludes the former name.
"""

from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd


POLE_LENGTH_FT = 5.0
POLE_LENGTH_CM = 152.4
FIELD_MARK_INTERVAL_IN = 35.0
FIELD_MARK_INTERVALS_PER_ROW = 4
ROW_SPACING_IN = 140.0
CAMERA_TO_TARGET_ROW_FT = 10.25
TARGET_TO_NEXT_ROW_FT = 1.42
DUPLICATE_IMAGE = "C-039_2021-07-30JPG.JPG"
RETAINED_IMAGE = "C-039_2021-07-30.JPG"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xml-dir",
        type=Path,
        default=Path("data/manual_annotations/poles_2021"),
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        help="Optional local image directory used only to verify file presence.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/manual_poles_2021"),
    )
    return parser.parse_args()


def status_of(polyline: ET.Element) -> str:
    for attribute in polyline.findall("attribute"):
        if attribute.get("name") == "status":
            return (attribute.text or "").strip().lower()
    return ""


def parse_points(value: str) -> list[tuple[float, float]]:
    return [tuple(map(float, item.split(","))) for item in value.split(";")]


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    excluded: list[dict[str, str]] = []
    missing_images: list[str] = []

    for xml_path in sorted(args.xml_dir.glob("C-*.xml")):
        root = ET.parse(xml_path).getroot()
        for image in root.findall("image"):
            image_name = str(image.get("name"))
            if image_name == DUPLICATE_IMAGE:
                excluded.append(
                    {
                        "excluded_image": image_name,
                        "retained_image": RETAINED_IMAGE,
                        "reason": "duplicate scene; project decision 2026-09-08",
                    }
                )
                continue
            if args.image_dir and not (args.image_dir / image_name).is_file():
                missing_images.append(image_name)

            for polyline in image.findall("polyline"):
                points = parse_points(str(polyline.get("points")))
                if len(points) < 2:
                    continue
                pixel_length = sum(
                    math.hypot(x2 - x1, y2 - y1)
                    for (x1, y1), (x2, y2) in zip(points, points[1:])
                )
                top_x, top_y = min(points, key=lambda point: point[1])
                ground_x, ground_y = max(points, key=lambda point: point[1])
                rows.append(
                    {
                        "row_id": xml_path.stem,
                        "source_xml": xml_path.name,
                        "image_name": image_name,
                        "pole_label": polyline.get("label"),
                        "annotation_status": status_of(polyline),
                        "top_x_px": top_x,
                        "top_y_px": top_y,
                        "ground_x_px": ground_x,
                        "ground_y_px": ground_y,
                        "polyline_length_px": pixel_length,
                        "physical_length_ft": POLE_LENGTH_FT,
                        "physical_length_cm": POLE_LENGTH_CM,
                        "physical_definition": (
                            "nominal vertical extent from pole ground contact to "
                            "camera mounting/optical-center height"
                        ),
                        "label_definition": (
                            "distinct visible 2021 camera-support pole; numeric label "
                            "does not by itself encode depth"
                        ),
                    }
                )

    annotations = pd.DataFrame(rows).sort_values(
        ["row_id", "image_name", "pole_label"], kind="mergesort"
    )
    annotations.to_csv(args.output_dir / "manual_pole_annotations_2021.csv", index=False)

    definitions = pd.DataFrame(
        [
            {
                "labels": "pole1-pole4",
                "object": "stationary-camera support pole",
                "physical_length_ft": POLE_LENGTH_FT,
                "physical_length_cm": POLE_LENGTH_CM,
                "vertical_endpoint_definition": (
                    "ground contact to nominal camera mounting/optical-center height"
                ),
                "field_mark_interval_in": FIELD_MARK_INTERVAL_IN,
                "field_mark_intervals_per_row": FIELD_MARK_INTERVALS_PER_ROW,
                "adjacent_row_spacing_in": ROW_SPACING_IN,
                "camera_to_target_row_ft": CAMERA_TO_TARGET_ROW_FT,
                "target_to_next_row_ft": TARGET_TO_NEXT_ROW_FT,
                "source": (
                    "Feedback for stationary camera project questions_yawei.docx; "
                    "2020 to 2025 Stationary camera settings .xlsx"
                ),
                "interpretation_note": (
                    "The 35-in marks describe horizontal field layout. They are "
                    "not the 1-ft red-band markings on the separate 2024-2025 "
                    "calibration poles."
                ),
            }
        ]
    )
    definitions.to_csv(args.output_dir / "pole_definitions_2021.csv", index=False)

    summary = {
        "xml_files": int(len(list(args.xml_dir.glob("C-*.xml")))),
        "retained_unique_images": int(annotations["image_name"].nunique()),
        "annotations": int(len(annotations)),
        "usable_annotations": int((annotations["annotation_status"] == "usable").sum()),
        "unusable_annotations": int((annotations["annotation_status"] == "unusable").sum()),
        "labels": sorted(annotations["pole_label"].dropna().unique().tolist()),
        "excluded_duplicates": excluded,
        "missing_referenced_images": sorted(set(missing_images)),
        "physical_length_ft": POLE_LENGTH_FT,
        "physical_length_cm": POLE_LENGTH_CM,
        "field_mark_interval_in": FIELD_MARK_INTERVAL_IN,
        "field_mark_intervals_per_row": FIELD_MARK_INTERVALS_PER_ROW,
        "adjacent_row_spacing_in": ROW_SPACING_IN,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
