#!/usr/bin/env python
"""Plot the controlled prior-in-detection experiment for the manuscript."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "outputs/candidate_ambiguity_simulation/prior_in_detection_sim_per_plant.csv"
SUMMARY = ROOT / "outputs/candidate_ambiguity_simulation/prior_in_detection_sim_summary.json"
OUT = ROOT / "manuscript/figures"


def main() -> None:
    data = pd.read_csv(DATA)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    boot = summary["plant_cluster_bootstrap"]
    OUT.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.7), constrained_layout=True)
    colors = ["#D55E00", "#0072B2", "#009E73"]

    labels = ["Single\nframe", "Post-detection\nfilter", "Prior in\ndetection"]
    keys = ["single_frame_rmse_cm", "post_hoc_rmse_cm", "prior_in_detection_rmse_cm"]
    means = np.array([boot[key]["mean"] for key in keys])
    intervals = np.array([boot[key]["ci95"] for key in keys])
    yerr = np.vstack([means - intervals[:, 0], intervals[:, 1] - means])
    axes[0].bar(np.arange(3), means, color=colors, width=0.68, edgecolor="black", linewidth=0.6)
    axes[0].errorbar(np.arange(3), means, yerr=yerr, fmt="none", ecolor="black", capsize=4, lw=1)
    axes[0].set_xticks(np.arange(3), labels)
    axes[0].set_ylabel("Plant-level height RMSE (cm)")
    axes[0].set_ylim(0, max(intervals[:, 1]) * 1.18)
    for x, value in enumerate(means):
        axes[0].text(x, value + 0.35, f"{value:.2f}", ha="center", va="bottom", fontsize=9)
    axes[0].text(-0.14, 1.03, "a", transform=axes[0].transAxes, fontsize=14, fontweight="bold")

    scenario_order = (
        data.groupby("scenario")["post_hoc_rmse_cm"].mean()
        .sub(data.groupby("scenario")["prior_in_detection_rmse_cm"].mean())
        .sort_values()
        .index
    )
    gains = data.assign(
        gain=data["post_hoc_rmse_cm"] - data["prior_in_detection_rmse_cm"]
    ).groupby("scenario")["gain"].agg(["mean", "sem"]).loc[scenario_order]
    ypos = np.arange(len(gains))
    axes[1].axvline(0, color="0.45", lw=0.8)
    axes[1].errorbar(
        gains["mean"], ypos, xerr=1.96 * gains["sem"], fmt="o", color="#0072B2",
        ecolor="#0072B2", capsize=2, markersize=5,
    )
    axes[1].set_yticks(ypos, [name.replace("_", " ") for name in gains.index])
    axes[1].set_xlabel("RMSE reduction vs post-detection filter (cm)")
    axes[1].text(-0.14, 1.03, "b", transform=axes[1].transAxes, fontsize=14, fontweight="bold")

    selection = (
        data.groupby("scenario")["prior_in_detection_truth_closest_rate"].mean().loc[scenario_order]
    )
    axes[2].barh(ypos, 100 * selection, color="#009E73", edgecolor="black", linewidth=0.5)
    axes[2].set_yticks(ypos, [])
    axes[2].set_xlabel("Truth-closest candidate selected (%)")
    axes[2].set_xlim(80, 100)
    axes[2].axvline(100 * selection.mean(), color="black", ls="--", lw=0.9)
    axes[2].text(
        0.97, 0.04, f"Overall {100 * selection.mean():.1f}%", transform=axes[2].transAxes,
        ha="right", va="bottom", fontsize=9,
    )
    axes[2].text(-0.14, 1.03, "c", transform=axes[2].transAxes, fontsize=14, fontweight="bold")

    for ax in axes:
        ax.tick_params(direction="out")

    png = OUT / "prior_in_detection_sim.png"
    pdf = OUT / "prior_in_detection_sim.pdf"
    fig.savefig(png, dpi=350, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    notes = {
        "input": str(DATA.relative_to(ROOT)),
        "plants": int(summary["plants"]),
        "scenarios": int(summary["scenarios"]),
        "spurious_candidate_probability": summary["spurious_candidate_probability"],
        "uncertainty": "Panel a: 95% plant-cluster bootstrap intervals; panel b: normal 95% intervals across 60 plants within each scenario",
        "seed": summary["seed"],
    }
    (OUT / "prior_in_detection_sim.json").write_text(
        json.dumps(notes, indent=2) + "\n", encoding="utf-8"
    )
    print(png)
    print(pdf)


if __name__ == "__main__":
    main()
