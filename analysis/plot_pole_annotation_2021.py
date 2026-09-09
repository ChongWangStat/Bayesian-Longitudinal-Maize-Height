#!/usr/bin/env python
"""Plot a representative 2021 support-pole annotation from the CVAT XML."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XML_DIR = PROJECT_ROOT / "data" / "manual_annotations" / "poles_2021"
DEFAULT_IMAGE_DIR = PROJECT_ROOT / "data" / "raw" / "pole_calibration_images"
RETAINED_IMAGE = "C-039_2021-07-30.JPG"
EXCLUDED_DUPLICATE = "C-039_2021-07-30JPG.JPG"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xml-dir", type=Path, default=DEFAULT_XML_DIR,
        help="Directory containing C-039.xml.",
    )
    parser.add_argument(
        "--image-dir", type=Path, default=DEFAULT_IMAGE_DIR,
        help="Directory containing the curated support-pole images.",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=PROJECT_ROOT / "manuscript" / "figures",
    )
    return parser.parse_args()


def load_annotation(xml_path: Path, image_name: str) -> tuple[dict, list[dict]]:
    root = ET.parse(xml_path).getroot()
    image_node = next(
        node for node in root.findall("image") if node.attrib["name"] == image_name
    )
    annotations: list[dict] = []
    for polyline in image_node.findall("polyline"):
        status_node = polyline.find("attribute[@name='status']")
        status = status_node.text.strip().lower() if status_node is not None else "unknown"
        points = [
            tuple(float(value) for value in point.split(","))
            for point in polyline.attrib["points"].split(";")
        ]
        annotations.append(
            {
                "label": polyline.attrib["label"],
                "status": status,
                "points": points,
            }
        )
    metadata = {
        "name": image_node.attrib["name"],
        "width_px": int(image_node.attrib["width"]),
        "height_px": int(image_node.attrib["height"]),
    }
    return metadata, annotations


def main() -> None:
    args = parse_args()
    xml_path = args.xml_dir / "C-039.xml"
    image_path = args.image_dir / RETAINED_IMAGE
    if not xml_path.exists() or not image_path.exists():
        raise FileNotFoundError(f"Missing {xml_path} or {image_path}")

    metadata, annotations = load_annotation(xml_path, RETAINED_IMAGE)
    image = Image.open(image_path).convert("RGB")
    if image.size != (metadata["width_px"], metadata["height_px"]):
        raise ValueError(f"Image size {image.size} disagrees with XML metadata {metadata}")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.linewidth": 0.7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    usable_color = "#0072B2"
    unusable_color = "#D55E00"
    status_styles = {
        "usable": (usable_color, "-"),
        "unusable": (unusable_color, (0, (5, 2))),
    }

    fig, ax = plt.subplots(figsize=(7.2, 4.35), constrained_layout=True)
    ax.imshow(image)
    crop_top, crop_bottom = 560, 980
    ax.set_xlim(0, metadata["width_px"])
    ax.set_ylim(crop_bottom, crop_top)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    label_offsets = {
        "pole1": (12, 4),
        "pole2": (20, -4),
        "pole3": (-72, -8),
        "pole4": (18, 9),
    }
    for ann in annotations:
        color, linestyle = status_styles.get(ann["status"], ("white", ":"))
        x = [point[0] for point in ann["points"]]
        y = [point[1] for point in ann["points"]]
        ax.plot(
            x, y, color="black", linewidth=5.0, alpha=0.72,
            solid_capstyle="round", zorder=3,
        )
        ax.plot(
            x, y, color=color, linewidth=2.8, linestyle=linestyle,
            solid_capstyle="round", zorder=4,
        )
        # XML polylines run from the camera mounting/optical-center endpoint
        # toward the ground-contact endpoint in these images.
        ax.scatter(
            x[0], y[0], marker="^", s=46, facecolor=color,
            edgecolor="white", linewidth=0.9, zorder=5,
        )
        ax.scatter(
            x[-1], y[-1], marker="o", s=38, facecolor=color,
            edgecolor="white", linewidth=0.9, zorder=5,
        )
        midpoint = ((x[0] + x[-1]) / 2, (y[0] + y[-1]) / 2)
        offset = label_offsets.get(ann["label"], (8, 6))
        ax.annotate(
            f"{ann['label']}\n{ann['status']}",
            xy=midpoint,
            xytext=offset,
            textcoords="offset points",
            color="white",
            fontsize=8,
            fontweight="bold",
            ha="left",
            va="center",
            bbox={"boxstyle": "round,pad=0.22", "fc": color, "ec": "white", "lw": 0.7, "alpha": 0.92},
            arrowprops={"arrowstyle": "-", "color": "white", "lw": 0.8},
            zorder=6,
        )

    ax.text(
        0.012, 0.975, "a", transform=ax.transAxes, ha="left", va="top",
        fontsize=11, fontweight="bold", color="black",
        bbox={"boxstyle": "square,pad=0.18", "fc": "white", "ec": "none", "alpha": 0.85},
        zorder=8,
    )

    inset = ax.inset_axes([0.79, 0.43, 0.19, 0.54])
    inset.imshow(image)
    inset.add_patch(
        Rectangle(
            (0, crop_top), metadata["width_px"], crop_bottom - crop_top,
            fill=False, edgecolor="#CC79A7", linewidth=1.6,
        )
    )
    inset.set_xticks([])
    inset.set_yticks([])
    for spine in inset.spines.values():
        spine.set_color("white")
        spine.set_linewidth(0.8)
    inset.text(
        0.04, 0.96, "b", transform=inset.transAxes, ha="left", va="top",
        fontsize=9, fontweight="bold", color="black",
        bbox={"boxstyle": "square,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.85},
    )

    legend_handles = [
        Line2D([0], [0], color=usable_color, lw=2.8, label="Usable pole trace"),
        Line2D([0], [0], color=unusable_color, lw=2.8, ls=(0, (5, 2)), label="Unusable pole trace"),
        Line2D([0], [0], marker="^", color="none", markerfacecolor="#666666", markeredgecolor="white", markersize=7, label="Camera mount / optical center"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#666666", markeredgecolor="white", markersize=7, label="Ground contact"),
    ]
    ax.legend(
        handles=legend_handles, loc="lower right", bbox_to_anchor=(0.985, 0.025),
        frameon=True, facecolor="white", edgecolor="#666666", framealpha=0.92,
        fontsize=7.5, handlelength=2.5, ncol=2, columnspacing=1.0,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    png_path = args.output_dir / "pole_annotation_2021.png"
    pdf_path = args.output_dir / "pole_annotation_2021.pdf"
    fig.savefig(png_path, dpi=450, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    counts = {
        status: sum(ann["status"] == status for ann in annotations)
        for status in sorted({ann["status"] for ann in annotations})
    }
    notes = {
        "figure": "pole_annotation_2021",
        "source_xml": str(xml_path),
        "source_image": str(image_path),
        "retained_filename": RETAINED_IMAGE,
        "excluded_duplicate_filename": EXCLUDED_DUPLICATE,
        "annotation_counts": counts,
        "pole_definition": (
            "Each pole1-pole4 polyline traces one distinct 2021 stationary-camera "
            "support pole from the camera mounting/optical-center endpoint to the "
            "ground-contact endpoint. All four support poles had a nominal physical "
            "height of 5 ft (152.4 cm). Pole numbers identify poles within the view "
            "and do not encode depth."
        ),
        "field_geometry": {
            "camera_support_pole_height_ft": 5.0,
            "camera_support_pole_height_cm": 152.4,
            "camera_to_target_row_ft": 10.25,
            "marked_ground_interval_in": 35.0,
            "four_intervals_adjacent_row_spacing_in": 140.0,
            "adjacent_row_spacing_ft": 11.67,
            "target_row_to_next_row_remainder_ft": 1.42,
            "clarification": (
                "The 35-in intervals are horizontal field-layout marks, not tick "
                "marks on the vertical support poles."
            ),
        },
        "crop_pixels": {"x_min": 0, "x_max": 773, "y_min": crop_top, "y_max": crop_bottom},
    }
    (args.output_dir / "pole_annotation_2021.figure_notes.json").write_text(
        json.dumps(notes, indent=2), encoding="utf-8"
    )
    caption = (
        "Representative manual annotation of 2021 camera support poles. "
        "(a) Enlarged lower-field crop from C-039 on 30 July 2021. Solid blue "
        "polylines passed annotation quality control; the dashed orange pole4 "
        "trace was marked unusable. Triangles and circles denote the camera "
        "mounting/optical-center and ground-contact endpoints, respectively. "
        "Each labeled pole was a distinct nominal 5-ft (152.4-cm) camera support "
        "pole; pole numbers are within-view identities and do not encode depth. "
        "(b) Full frame with the displayed crop outlined."
    )
    (args.output_dir / "pole_annotation_2021.caption.txt").write_text(
        caption + "\n", encoding="utf-8"
    )
    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
