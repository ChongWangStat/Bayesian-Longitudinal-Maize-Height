#!/usr/bin/env python
"""Schematic of the imaging geometry and pole-to-plant depth correction.

Two panels: (a) a scale side-view of the field geometry (camera height,
camera-to-row and camera-to-pole distances, the depth gap that the
correction addresses), and (b) the image-plane view showing the pole's
evenly spaced bands as the metric reference and the plant top/root points
whose pixel separation is converted to height. Distances are read from the
pole-camera registry so the diagram stays consistent with the analysis.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", type=Path, default=Path("data/reference/pole_camera_registry.csv"))
    p.add_argument("--output", required=True, type=Path)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    reg = pd.read_csv(args.registry).iloc[0]
    H = float(reg["camera_height_ft"])
    d_row = float(reg["camera_to_row_ft"])
    d_pole = float(reg["camera_to_pole_ft"])
    kappa = float(reg["depth_correction_factor"])

    fig, (axg, axi) = plt.subplots(1, 2, figsize=(13, 5.2))

    # ---- Panel (a): side-view field geometry (to scale) ----
    axg.set_title("(a) Field geometry (side view, to scale)")
    # Ground line.
    axg.plot([-0.5, d_pole + 1.5], [0, 0], color="#8c6d4f", lw=2)
    axg.fill_between([-0.5, d_pole + 1.5], -0.6, 0, color="#e8dcc8")
    # Camera mast at x=0.
    axg.plot([0, 0], [0, H], color="#555", lw=3)
    axg.plot([0], [H], marker="s", markersize=13, color="#2166ac")
    axg.annotate("camera", (0, H), textcoords="offset points", xytext=(6, 6), fontsize=9)
    # Camera height brace.
    axg.annotate(
        "", xy=(-0.35, 0), xytext=(-0.35, H),
        arrowprops=dict(arrowstyle="<->", color="#555"),
    )
    axg.text(-0.75, H / 2, f"H = {H:.1f} ft", rotation=90, va="center", fontsize=9)
    # Target plant row.
    plant_h = 2.6
    for dx in (-0.12, 0.0, 0.12):
        axg.plot([d_row + dx, d_row + dx], [0, plant_h * (1 - abs(dx))], color="#3a8f3a", lw=2)
    axg.plot([d_row], [plant_h], marker="^", markersize=10, color="#3a8f3a")
    axg.annotate("target\nplant row", (d_row, 0), textcoords="offset points",
                 xytext=(-30, 22), ha="center", fontsize=9, color="#2a662a")
    # Pole behind row.
    axg.plot([d_pole, d_pole], [0, 3.2], color="#b2182b", lw=3)
    for zft in range(0, 4):
        axg.plot([d_pole], [zft], marker="_", markersize=14, color="#b2182b", mew=3)
    axg.annotate("reference pole", (d_pole, 1.4), textcoords="offset points",
                 xytext=(10, 0), fontsize=9, color="#8f1420", va="center")
    # Sight lines from camera.
    axg.plot([0, d_row], [H, plant_h], color="#2166ac", ls=":", lw=1)
    axg.plot([0, d_pole], [H, 3.2], color="#b2182b", ls=":", lw=1)
    # Distance braces along ground.
    axg.annotate("", xy=(0, -0.35), xytext=(d_row, -0.35),
                 arrowprops=dict(arrowstyle="<->", color="#2166ac"))
    axg.text(d_row / 2, -0.6, f"$D_{{tgt}}$ = {d_row:.1f} ft", ha="center", fontsize=9, color="#2166ac")
    axg.annotate("", xy=(0, 0.28), xytext=(d_pole, 0.28),
                 arrowprops=dict(arrowstyle="<->", color="#b2182b"))
    axg.text(d_pole / 2, 0.42, f"$D_{{ref}}$ = {d_pole:.1f} ft", ha="center", fontsize=9, color="#b2182b")
    # Gap callout, placed high to avoid the pole and labels.
    axg.annotate(
        f"depth gap {d_pole - d_row:.1f} ft\n"
        rf"$\kappa=D_{{tgt}}/D_{{ref}}={kappa:.2f}$",
        xy=(d_row / 2, H + 0.3), fontsize=8.5, ha="center",
        bbox=dict(boxstyle="round", fc="#fff4e6", ec="#d59b4c"),
    )
    axg.set_xlim(-1.2, d_pole + 2.6)
    axg.set_ylim(-0.85, H + 1.2)
    axg.set_aspect("equal")
    axg.axis("off")

    # ---- Panel (b): image-plane view ----
    axi.set_title("(b) Image plane: reference bands and plant endpoints")
    # Perspective: bands closer together toward the top (higher up the pole).
    # Draw pole at right, plant at left.
    band_x = 0.72
    n_bands = 9
    # y positions with mild foreshortening (projective compression upward).
    ys = np.linspace(0.12, 0.88, n_bands)
    gaps = np.diff(ys)
    # Compress upper gaps slightly for a perspective feel.
    ys = 0.12 + np.cumsum(np.concatenate([[0], gaps * np.linspace(1.15, 0.8, n_bands - 1)]))
    ys = ys / ys.max() * 0.88
    axi.plot([band_x, band_x], [ys.min(), ys.max()], color="#b2182b", lw=2)
    for i, y in enumerate(ys):
        axi.plot([band_x - 0.02, band_x + 0.02], [y, y], color="#b2182b", lw=4)
    axi.annotate("bands 30.48 cm apart\n(known physical spacing)", (band_x, ys.max()),
                 textcoords="offset points", xytext=(-2, 10), ha="center", fontsize=8.5, color="#8f1420")

    # Plant with root and top points.
    plant_x = 0.30
    root_y, top_y = 0.14, 0.70
    axi.plot([plant_x, plant_x], [root_y, top_y], color="#3a8f3a", lw=2.5)
    # A few leaves.
    for yy, sgn in [(0.34, 1), (0.46, -1), (0.58, 1)]:
        axi.plot([plant_x, plant_x + sgn * 0.10], [yy, yy + 0.04], color="#3a8f3a", lw=1.5)
    axi.plot([plant_x], [top_y], marker="v", markersize=11, color="#1b5e20")
    axi.plot([plant_x], [root_y], marker="o", markersize=9, color="#8c6d4f")
    axi.annotate("plant top (detected pixel)", (plant_x, top_y),
                 textcoords="offset points", xytext=(8, 4), fontsize=8.5)
    axi.annotate("plant base / root (detected pixel)", (plant_x, root_y),
                 textcoords="offset points", xytext=(8, -10), fontsize=8.5)
    axi.annotate(
        "height = pixel-to-cm( top )\n            $-$ pixel-to-cm( base ),\n"
        "            then $\\times\\,\\kappa$ (depth)",
        xy=(0.02, 0.9), fontsize=8.5, va="top",
        bbox=dict(boxstyle="round", fc="#eef4fb", ec="#7aa6d0"),
    )
    axi.set_xlim(0, 1)
    axi.set_ylim(0, 1)
    axi.axis("off")
    axi.add_patch(mpatches.Rectangle((0, 0), 1, 1, fill=False, ec="#bbb"))

    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
