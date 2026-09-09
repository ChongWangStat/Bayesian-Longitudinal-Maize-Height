#!/usr/bin/env python3
"""Draw the publication workflow for the as-of Bayesian height update.

The figure separates the solid field-data path from the stronger, dashed
height-candidate-selection branch that is evaluated in simulation.  It uses
only matplotlib so the vector PDF remains directly editable in illustration
software and the PNG can be regenerated without source images.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PNG = PROJECT_ROOT / "manuscript" / "figures" / "online_bayesian_workflow.png"
DEFAULT_PDF = PROJECT_ROOT / "manuscript" / "figures" / "online_bayesian_workflow.pdf"


# Colorblind-conscious palette with dark text and high-contrast borders.
NAVY = "#1F4E79"
BLUE_FILL = "#EAF3F8"
TEAL = "#006D66"
TEAL_FILL = "#E6F4F1"
PURPLE = "#62459A"
PURPLE_FILL = "#F0ECF8"
GREEN = "#4F772D"
GREEN_FILL = "#F1F7E8"
AMBER = "#C46A10"
AMBER_FILL = "#FFF2D8"
GRAY = "#4B5563"
LIGHT_GRAY = "#F5F6F8"
DARK = "#17202A"


def add_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    *,
    face: str,
    edge: str,
    linestyle: str = "solid",
    linewidth: float = 1.8,
    tag: str | None = None,
    tag_face: str | None = None,
) -> None:
    """Add a rounded workflow box with consistent typography."""
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.025,rounding_size=0.12",
        facecolor=face,
        edgecolor=edge,
        linewidth=linewidth,
        linestyle=linestyle,
        zorder=3,
    )
    ax.add_patch(patch)

    if tag:
        tag_w = min(0.78, 0.12 * len(tag) + 0.18)
        tag_h = 0.25
        tag_patch = FancyBboxPatch(
            (x + w - tag_w - 0.12, y + h - tag_h - 0.10),
            tag_w,
            tag_h,
            boxstyle="round,pad=0.015,rounding_size=0.07",
            facecolor=tag_face or edge,
            edgecolor="none",
            zorder=5,
        )
        ax.add_patch(tag_patch)
        ax.text(
            x + w - tag_w / 2 - 0.12,
            y + h - tag_h / 2 - 0.10,
            tag,
            ha="center",
            va="center",
            fontsize=7.2,
            fontweight="bold",
            color="white",
            zorder=6,
        )

    ax.text(
        x + w / 2,
        y + h * 0.68,
        title,
        ha="center",
        va="center",
        fontsize=10.5,
        fontweight="bold",
        color=edge,
        linespacing=1.08,
        zorder=6,
    )
    ax.text(
        x + w / 2,
        y + h * 0.27,
        body,
        ha="center",
        va="center",
        fontsize=8.8,
        color=DARK,
        linespacing=1.12,
        zorder=6,
    )


def arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = NAVY,
    linestyle: str = "solid",
    linewidth: float = 1.8,
    mutation_scale: float = 13,
    connectionstyle: str = "arc3",
    zorder: int = 2,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=mutation_scale,
            linewidth=linewidth,
            linestyle=linestyle,
            color=color,
            connectionstyle=connectionstyle,
            shrinkA=1.5,
            shrinkB=1.5,
            zorder=zorder,
        )
    )


def elbow_arrow(
    ax: plt.Axes,
    points: list[tuple[float, float]],
    *,
    color: str,
    linestyle: str = "solid",
    linewidth: float = 1.7,
    mutation_scale: float = 13,
) -> None:
    """Draw a polyline whose final segment carries an arrowhead."""
    for p0, p1 in zip(points[:-2], points[1:-1]):
        ax.plot(
            [p0[0], p1[0]],
            [p0[1], p1[1]],
            color=color,
            linewidth=linewidth,
            linestyle=linestyle,
            solid_capstyle="round",
            dash_capstyle="round",
            zorder=1,
        )
    arrow(
        ax,
        points[-2],
        points[-1],
        color=color,
        linestyle=linestyle,
        linewidth=linewidth,
        mutation_scale=mutation_scale,
        zorder=2,
    )


def draw_workflow() -> plt.Figure:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.unicode_minus": False,
        }
    )

    fig, ax = plt.subplots(figsize=(16, 8.4), constrained_layout=False)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8.4)
    ax.axis("off")

    ax.text(
        0.45,
        8.02,
        "Longitudinal Bayesian image analysis with physical calibration",
        fontsize=18,
        fontweight="bold",
        color=DARK,
        ha="left",
        va="center",
    )
    ax.text(
        0.45,
        7.60,
        r"As-of update at acquisition $t$: the result uses $I_{\leq t}$; $I_{t+1}$ does not yet exist.",
        fontsize=10.8,
        color=GRAY,
        ha="left",
        va="center",
    )

    # Legend / implementation distinction.
    ax.plot([0.50, 1.15], [7.12, 7.12], color=NAVY, linewidth=2.3)
    arrow(ax, (0.82, 7.12), (1.15, 7.12), color=NAVY, linewidth=2.3, mutation_scale=11)
    ax.text(1.28, 7.12, "Executed on field data", ha="left", va="center", fontsize=9.5, color=DARK)
    ax.plot([3.40, 4.05], [7.12, 7.12], color=AMBER, linewidth=2.0, linestyle=(0, (5, 3)))
    arrow(
        ax,
        (3.72, 7.12),
        (4.05, 7.12),
        color=AMBER,
        linestyle=(0, (5, 3)),
        linewidth=2.0,
        mutation_scale=11,
    )
    ax.text(
        4.18,
        7.12,
        "Stronger height-candidate selection evaluated in simulation",
        ha="left",
        va="center",
        fontsize=9.5,
        color=DARK,
    )
    ax.add_patch(
        FancyBboxPatch(
            (9.44, 6.99),
            0.28,
            0.26,
            boxstyle="round,pad=0.01,rounding_size=0.04",
            facecolor=GREEN_FILL,
            edgecolor=GREEN,
            linewidth=1.5,
        )
    )
    ax.text(9.84, 7.12, "Recorded physical reference", ha="left", va="center", fontsize=9.5, color=DARK)

    # Main, field-executed path.
    y_main, h_main = 4.95, 1.75
    boxes = [
        (0.45, 2.25, "1  Accumulated\nimages", "$I_{\\leq t}$\nnew image appended"),
        (3.05, 2.45, "2  Current-image\nanalysis", "detector candidates\ntop/base keypoints + scores"),
        (5.90, 2.85, "3  Prior-guided\nassociation", "match plant + update\nbase keypoint from the\nprevious position posterior"),
        (9.20, 2.55, "4  Physical\nconversion", "in-scene pole +\nrecorded geometry\npixels to centimeters"),
        (12.20, 3.05, "5  Robust Bayesian\nupdate", "particle filter with\ninlier/outlier-mixture likelihood"),
    ]
    for x, w, title, body in boxes:
        add_box(
            ax,
            x,
            y_main,
            w,
            h_main,
            title,
            body,
            face=BLUE_FILL if x < 9 else TEAL_FILL,
            edge=NAVY if x < 9 else TEAL,
        )

    centers_y = y_main + h_main / 2
    arrow(ax, (2.70, centers_y), (3.05, centers_y))
    arrow(ax, (5.50, centers_y), (5.90, centers_y))
    arrow(ax, (8.75, centers_y), (9.20, centers_y))
    arrow(ax, (11.75, centers_y), (12.20, centers_y), color=TEAL)

    # Previous posterior and physical metadata enter the field path.
    add_box(
        ax,
        6.00,
        3.35,
        2.65,
        1.05,
        "Previous plant-specific\nposterior",
        r"$p(\mathbf{s}_{t-1}\mid I_{\leq t-1})$",
        face=LIGHT_GRAY,
        edge=NAVY,
    )
    arrow(ax, (7.325, 4.40), (7.325, 4.95), color=NAVY)

    add_box(
        ax,
        9.25,
        3.35,
        2.45,
        1.05,
        "Recorded physical\nreference",
        "pole definition, band spacing,\ncamera/row distances",
        face=GREEN_FILL,
        edge=GREEN,
    )
    arrow(ax, (10.475, 4.40), (10.475, 4.95), color=GREEN)

    # Immediate as-of output.
    add_box(
        ax,
        12.25,
        3.10,
        2.95,
        1.35,
        "6  Immediate as-of\nresult",
        "$p(h_t,r_t\\mid I_{\\leq t})$\nheight estimate + interval",
        face=PURPLE_FILL,
        edge=PURPLE,
    )
    arrow(ax, (13.725, 4.95), (13.725, 4.45), color=PURPLE)

    # The stronger height-candidate branch is deliberately dashed and separate.
    add_box(
        ax,
        2.45,
        1.40,
        6.30,
        1.55,
        "Simulation-tested extension\nPrior-guided top-candidate selection",
        "height prior re-ranks competing top-keypoint candidates under ambiguity\n(stronger than the field position-association/base update above)",
        face=AMBER_FILL,
        edge=AMBER,
        linestyle=(0, (5, 3)),
        linewidth=2.0,
    )
    arrow(
        ax,
        (4.275, 4.95),
        (4.275, 2.95),
        color=AMBER,
        linestyle=(0, (5, 3)),
        linewidth=1.8,
    )
    arrow(
        ax,
        (7.325, 3.35),
        (7.325, 2.95),
        color=AMBER,
        linestyle=(0, (5, 3)),
        linewidth=1.8,
    )
    elbow_arrow(
        ax,
        [(8.75, 2.18), (8.95, 2.18), (8.95, 5.825), (9.20, 5.825)],
        color=AMBER,
        linestyle=(0, (5, 3)),
        linewidth=1.8,
    )

    # Carry the posterior forward and append the next image on the next cycle.
    elbow_arrow(
        ax,
        [(12.25, 3.74), (11.95, 3.74), (11.95, 3.07), (7.325, 3.07), (7.325, 3.35)],
        color=PURPLE,
        linewidth=1.55,
    )
    ax.text(
        10.05,
        3.11,
        "posterior carried forward",
        ha="center",
        va="bottom",
        fontsize=8.4,
        color=PURPLE,
    )

    elbow_arrow(
        ax,
        [(14.85, 3.10), (14.85, 0.62), (1.575, 0.62), (1.575, 4.95)],
        color=NAVY,
        linewidth=1.65,
    )
    ax.text(
        7.65,
        0.30,
        r"At $t+1$: append the next image to the pool and repeat; earlier outputs remain fixed.",
        ha="center",
        va="center",
        fontsize=9.6,
        color=NAVY,
        fontweight="bold",
    )

    # Short interpretation cue, useful when the figure is viewed outside the text.
    ax.text(
        13.55,
        2.15,
        "Future images are added later;\nthey are not used in the result at time t.",
        ha="right",
        va="center",
        fontsize=8.6,
        color=GRAY,
        style="italic",
    )

    return fig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG, help="PNG output path")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF, help="PDF output path")
    parser.add_argument("--dpi", type=int, default=400, help="PNG resolution (default: 400)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.png.parent.mkdir(parents=True, exist_ok=True)
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    fig = draw_workflow()
    fig.savefig(args.png, dpi=args.dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(args.pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {args.png}")
    print(f"Wrote {args.pdf}")


if __name__ == "__main__":
    main()
