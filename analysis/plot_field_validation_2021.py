#!/usr/bin/env python
"""Plot the prespecified all-plant 2021 field validation without exclusions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "outputs"
    / "filter_height_sam_2021"
    / "filtered_height_sam__phi1.0_plus_pole_growth_field.csv"
)
DEFAULT_SUMMARY = (
    PROJECT_ROOT / "outputs" / "filter_height_sam_2021" / "all_plants_primary.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument(
        "--output-dir", type=Path,
        default=PROJECT_ROOT / "manuscript" / "figures",
    )
    return parser.parse_args()


def select_quantile_examples(per_plant: pd.DataFrame) -> list[dict]:
    """Select fixed benefit quantiles from plants with at least four observations."""
    eligible = per_plant.loc[per_plant["n"] >= 4].copy()
    chosen: list[dict] = []
    used: set[str] = set()
    for quantile, label in [(0.10, "10th percentile"), (0.50, "median"), (0.90, "90th percentile")]:
        target = float(eligible["benefit_cm"].quantile(quantile))
        candidates = eligible.loc[~eligible["plant_uid"].isin(used)].copy()
        candidates["distance"] = (candidates["benefit_cm"] - target).abs()
        row = candidates.sort_values(["distance", "plant_uid"]).iloc[0]
        used.add(str(row["plant_uid"]))
        chosen.append(
            {
                "quantile": quantile,
                "quantile_label": label,
                "target_benefit_cm": target,
                "plant_uid": str(row["plant_uid"]),
                "n": int(row["n"]),
                "single_frame_mae_cm": float(row["single_frame_mae_cm"]),
                "online_bayesian_mae_cm": float(row["online_bayesian_mae_cm"]),
                "benefit_cm": float(row["benefit_cm"]),
            }
        )
    return chosen


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.16, 1.06, label, transform=ax.transAxes, ha="left", va="top",
        fontsize=10, fontweight="bold",
    )


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input, parse_dates=["date"])
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    required = {
        "plant_uid", "rowid", "date", "height_true", "height_sam",
        "posterior_mean_cm", "posterior_q025_cm", "posterior_q975_cm",
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    data["single_frame_abs_error_cm"] = (data["height_sam"] - data["height_true"]).abs()
    data["online_bayesian_abs_error_cm"] = (
        data["posterior_mean_cm"] - data["height_true"]
    ).abs()
    per_plant = (
        data.groupby("plant_uid", as_index=False)
        .agg(
            n=("height_true", "size"),
            single_frame_mae_cm=("single_frame_abs_error_cm", "mean"),
            online_bayesian_mae_cm=("online_bayesian_abs_error_cm", "mean"),
        )
    )
    per_plant["benefit_cm"] = (
        per_plant["single_frame_mae_cm"] - per_plant["online_bayesian_mae_cm"]
    )
    examples = select_quantile_examples(per_plant)

    whole = summary["whole_season_all_plants"]
    single = whole["single_frame"]
    bayes = whole["online_filter"]
    comparison = whole["paired_row_cluster_bootstrap"]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8.5,
            "axes.linewidth": 0.7,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    blue = "#0072B2"
    orange = "#D55E00"
    gray = "#4D4D4D"
    light_gray = "#D0D0D0"

    fig = plt.figure(figsize=(7.2, 6.7), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=[1.0, 1.1])
    top_axes = [fig.add_subplot(grid[0, index]) for index in range(3)]
    bottom_axes = [fig.add_subplot(grid[1, index]) for index in range(3)]

    combined = np.concatenate(
        [data["height_true"], data["height_sam"], data["posterior_mean_cm"]]
    )
    lower = 25 * np.floor((combined.min() - 5) / 25)
    upper = 25 * np.ceil((combined.max() + 5) / 25)
    identity = [lower, upper]

    ax = top_axes[0]
    ax.scatter(
        data["height_true"], data["height_sam"], s=18,
        facecolor=orange, edgecolor="white", linewidth=0.3, alpha=0.72,
    )
    ax.plot(identity, identity, color=gray, lw=1.0, ls="--")
    ax.set(xlim=identity, ylim=identity, xlabel="Manual height (cm)", ylabel="Estimated height (cm)")
    ax.set_title("Single-frame image estimate")
    ax.text(
        0.04, 0.96,
        f"MAE {single['mae_cm']:.2f} cm\nBias {single['bias_cm']:+.2f} cm",
        transform=ax.transAxes, ha="left", va="top",
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": light_gray, "alpha": 0.9},
    )
    panel_label(ax, "A")

    ax = top_axes[1]
    ax.scatter(
        data["height_true"], data["posterior_mean_cm"], s=18,
        facecolor=blue, edgecolor="white", linewidth=0.3, alpha=0.72,
    )
    ax.plot(identity, identity, color=gray, lw=1.0, ls="--")
    ax.set(xlim=identity, ylim=identity, xlabel="Manual height (cm)", ylabel="Estimated height (cm)")
    ax.set_title("Online Bayesian posterior mean")
    ax.text(
        0.04, 0.96,
        f"MAE {bayes['mae_cm']:.2f} cm\nBias {bayes['bias_cm']:+.2f} cm",
        transform=ax.transAxes, ha="left", va="top",
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": light_gray, "alpha": 0.9},
    )
    panel_label(ax, "B")

    ax = top_axes[2]
    ranked = per_plant.sort_values(["single_frame_mae_cm", "plant_uid"]).reset_index(drop=True)
    x_rank = np.arange(1, len(ranked) + 1)
    delta = -ranked["benefit_cm"].to_numpy()  # Bayesian minus single-frame MAE.
    colors = np.where(delta < 0, blue, orange)
    ax.vlines(x_rank, 0, delta, color=colors, lw=0.9, alpha=0.7)
    ax.scatter(x_rank, delta, c=colors, s=18, edgecolor="white", linewidth=0.3, zorder=3)
    ax.axhline(0, color=gray, lw=0.8)
    ax.set(
        xlabel="Plants ordered by single-frame MAE",
        ylabel="Change in plant MAE\n(Bayesian - single-frame, cm)",
        xlim=(0, len(ranked) + 1),
    )
    ax.set_title("Within-plant paired MAE")
    ci_low, ci_high = comparison["ci95_cm"]
    ax.text(
        0.97, 0.96,
        f"20/33 plants improved\nOverall benefit {comparison['mae_improvement_cm']:.2f} cm\n"
        f"Row-bootstrap 95% CI\n{ci_low:.2f} to {ci_high:.2f} cm",
        transform=ax.transAxes, ha="right", va="top", fontsize=7,
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": light_gray, "alpha": 0.92},
    )
    panel_label(ax, "C")

    selected_data = data[data["plant_uid"].isin([item["plant_uid"] for item in examples])]
    y_min = min(0.0, float(selected_data["posterior_q025_cm"].min()))
    y_max = float(selected_data["posterior_q975_cm"].max())
    y_min = 25 * np.floor(y_min / 25)
    y_max = 25 * np.ceil(y_max / 25)

    legend_handles = None
    for index, (ax, example) in enumerate(zip(bottom_axes, examples)):
        subset = data.loc[data["plant_uid"] == example["plant_uid"]].sort_values("date")
        ax.fill_between(
            subset["date"].to_numpy(),
            subset["posterior_q025_cm"].to_numpy(dtype=float),
            subset["posterior_q975_cm"].to_numpy(dtype=float),
            color=blue, alpha=0.13, linewidth=0,
        )
        manual_line, = ax.plot(
            subset["date"], subset["height_true"], color="black", marker="o",
            ms=4.0, lw=1.4, label="Manual reference", zorder=4,
        )
        frame_line, = ax.plot(
            subset["date"], subset["height_sam"], color=orange, marker="s",
            markerfacecolor="white", markeredgewidth=1.0, ms=4.0, lw=1.0,
            ls="--", label="Single-frame estimate", zorder=3,
        )
        bayes_line, = ax.plot(
            subset["date"], subset["posterior_mean_cm"], color=blue, marker="o",
            ms=3.8, lw=1.4, label="Online Bayesian mean", zorder=5,
        )
        if legend_handles is None:
            legend_handles = [manual_line, frame_line, bayes_line]
        ax.set_ylim(y_min, y_max)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.tick_params(axis="x", labelrotation=30)
        if index == 0:
            ax.set_ylabel("Plant height (cm)")
        ax.set_xlabel("2021 measurement date")
        direction = "benefit" if example["benefit_cm"] >= 0 else "harm"
        ax.set_title(
            f"{example['quantile_label']}: {example['plant_uid']}\n"
            f"Bayesian {direction} = {abs(example['benefit_cm']):.2f} cm"
        )
        panel_label(ax, chr(ord("D") + index))

    legend_handles.append(Patch(facecolor=blue, alpha=0.13, edgecolor="none"))
    fig.legend(
        handles=legend_handles,
        labels=[
            "Manual reference", "Single-frame estimate", "Online Bayesian mean",
            "95% posterior interval",
        ],
        loc="outside lower center", ncol=4, frameon=False,
    )

    for ax in top_axes + bottom_axes:
        ax.grid(color="#E5E5E5", linewidth=0.5, alpha=0.8)
        ax.set_axisbelow(True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    png_path = args.output_dir / "field_validation_2021.png"
    pdf_path = args.output_dir / "field_validation_2021.pdf"
    fig.savefig(png_path, dpi=450, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    figure_notes = {
        "figure": "field_validation_2021",
        "source_csv": str(args.input),
        "scope": {
            "records": int(len(data)),
            "plants": int(data["plant_uid"].nunique()),
            "rows": int(data["rowid"].nunique()),
            "exclusions": "None; all available 2021 manually measured plants are included.",
        },
        "primary_metrics": whole,
        "plants_with_lower_bayesian_mae": int((per_plant["benefit_cm"] > 0).sum()),
        "representative_selection_rule": (
            "Among plants with at least four dates, select the plant nearest the "
            "10th, 50th, and 90th percentiles of per-plant MAE benefit, defined as "
            "single-frame MAE minus online-Bayesian MAE; ties are broken by plant UID."
        ),
        "representative_plants": examples,
    }
    (args.output_dir / "field_validation_2021.figure_notes.json").write_text(
        json.dumps(figure_notes, indent=2), encoding="utf-8"
    )
    caption = (
        "All-plant 2021 field validation. (A, B) Agreement of manual plant-height "
        "measurements with the single-frame image estimate and the online Bayesian "
        "posterior mean for all 132 observations from 33 plants in 12 rows; dashed "
        "lines denote equality. (C) Within-plant change in mean absolute error "
        "(Bayesian minus single-frame) for every plant, ordered by single-frame MAE; "
        "blue values below zero favor the online analysis. The observation-weighted "
        "MAE benefit was 1.06 cm (95% row-cluster bootstrap CI, -0.16 to 2.39 cm), "
        "and 20 of 33 plants had lower Bayesian MAE. (D-F) Longitudinal examples "
        "selected by a fixed rule as the plants nearest the 10th, 50th, and 90th "
        "percentiles of per-plant MAE benefit among plants with at least four dates. "
        "Blue shading denotes the 95% posterior interval. No plant was excluded from "
        "the primary analysis."
    )
    (args.output_dir / "field_validation_2021.caption.txt").write_text(
        caption + "\n", encoding="utf-8"
    )
    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")
    print(json.dumps(figure_notes["representative_plants"], indent=2))


if __name__ == "__main__":
    main()
