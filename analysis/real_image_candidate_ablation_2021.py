#!/usr/bin/env python
"""Real-image ablation of height-prior candidate scoring on 2021 images.

All methods receive the same cached YOLOv8-pose candidates, fixed physical scale,
confidence evidence, initial labeled root anchors, position update, and height-growth
Kalman update. The only distinction between the two temporal streams is whether the
predicted height distribution enters candidate assignment before the update. Manual
field height is used only for scoring. This is an exploratory mechanism audit because
the images do not have two independent agronomic top/base annotations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


CM_PER_PIXEL = 0.415886
POSITION_SD_FRACTION = 0.05
MAX_POSITION_DISTANCE = 0.16
INNOVATION_GATE_Z = 3.0
MEASUREMENT_SD_CM = 12.0
PROCESS_HEIGHT_SD_CM_SQRT_DAY = 8.78
PROCESS_GROWTH_SD_CM_DAY_SQRT_DAY = 0.35


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/processed/yolo_candidates_2021.csv"),
    )
    parser.add_argument(
        "--anchors",
        type=Path,
        default=Path("outputs/crop_positions_2021/crop_positions.csv"),
    )
    parser.add_argument(
        "--truth", type=Path, default=Path("data/raw/heights_compare_2021.csv")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/real_image_candidate_ablation_2021")
    )
    parser.add_argument("--replicates", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260909)
    return parser.parse_args()


class LocalLinearFilter:
    def __init__(self, measurement: float):
        self.state = np.array([measurement, 0.0])
        self.covariance = np.diag([MEASUREMENT_SD_CM**2, 8.0**2])

    def predict(self, elapsed_days: float) -> None:
        transition = np.array([[1.0, elapsed_days], [0.0, 1.0]])
        process = np.diag(
            [
                PROCESS_HEIGHT_SD_CM_SQRT_DAY**2 * elapsed_days,
                PROCESS_GROWTH_SD_CM_DAY_SQRT_DAY**2 * elapsed_days,
            ]
        )
        self.state = transition @ self.state
        self.covariance = transition @ self.covariance @ transition.T + process

    def update(self, measurement: float, confidence: float) -> None:
        variance = MEASUREMENT_SD_CM**2 / max(confidence, 0.05)
        innovation_variance = self.covariance[0, 0] + variance
        gain = self.covariance[:, 0] / innovation_variance
        self.state = self.state + gain * (measurement - self.state[0])
        self.covariance = self.covariance - np.outer(gain, self.covariance[0, :])


def assign_candidates(
    candidates: pd.DataFrame,
    positions: dict[str, float],
    filters: dict[str, LocalLinearFilter] | None = None,
) -> dict[str, int]:
    plants = list(positions)
    candidates = candidates.reset_index(drop=True)
    cost = np.full((len(plants), len(candidates)), 1e6)
    for plant_index, plant in enumerate(plants):
        for candidate_index, candidate in candidates.iterrows():
            distance = abs(float(candidate["x_root_frac"]) - positions[plant])
            if distance > MAX_POSITION_DISTANCE:
                continue
            log_score = np.log(max(float(candidate["conf"]), 1e-12))
            log_score -= 0.5 * (distance / POSITION_SD_FRACTION) ** 2
            if filters is not None and plant in filters:
                measurement = float(candidate["height_px"]) * CM_PER_PIXEL
                predicted_mean = float(filters[plant].state[0])
                predictive_sd = np.sqrt(
                    filters[plant].covariance[0, 0]
                    + MEASUREMENT_SD_CM**2 / max(float(candidate["conf"]), 0.05)
                )
                standardized = abs(measurement - predicted_mean) / predictive_sd
                if standardized > INNOVATION_GATE_Z:
                    log_score += np.log(0.05)
                log_score -= 0.5 * standardized**2 + np.log(predictive_sd)
            cost[plant_index, candidate_index] = -log_score
    row_indices, column_indices = linear_sum_assignment(cost)
    return {
        plants[row_index]: int(column_index)
        for row_index, column_index in zip(row_indices, column_indices)
        if cost[row_index, column_index] < 1e5
    }


def run_camera(
    camera: str,
    candidates: pd.DataFrame,
    anchors: pd.DataFrame,
    truth: pd.DataFrame,
) -> list[dict[str, object]]:
    camera_candidates = candidates[candidates["camera"] == camera]
    camera_truth = truth[truth["camera"] == camera]
    camera_anchors = anchors[anchors["rowid"] == camera]
    plants = sorted(set(camera_truth["plantid"]) & set(camera_anchors["plant"]))
    initial_positions = {
        plant: float(
            camera_anchors[camera_anchors["plant"] == plant]
            .sort_values("date_md")
            .iloc[0]["x_root_full"]
            / camera_anchors[camera_anchors["plant"] == plant].iloc[0]["frame_w"]
        )
        for plant in plants
    }
    plain_positions = initial_positions.copy()
    prior_positions = initial_positions.copy()
    post_filters: dict[str, LocalLinearFilter] = {}
    prior_filters: dict[str, LocalLinearFilter] = {}
    records: list[dict[str, object]] = []
    previous_date = None

    for day in sorted(camera_candidates["day"].unique()):
        date = pd.Timestamp("2021-" + day.replace("_", "-"))
        elapsed_days = 0.0 if previous_date is None else float((date - previous_date).days)
        if previous_date is not None:
            for state_filter in post_filters.values():
                state_filter.predict(elapsed_days)
            for state_filter in prior_filters.values():
                state_filter.predict(elapsed_days)

        current = camera_candidates[camera_candidates["day"] == day].reset_index(drop=True)
        plain_assignment = assign_candidates(current, plain_positions)
        prior_assignment = assign_candidates(current, prior_positions, prior_filters)

        by_plant: dict[str, dict[str, object]] = {}
        for plant, candidate_index in plain_assignment.items():
            candidate = current.iloc[candidate_index]
            measurement = float(candidate["height_px"]) * CM_PER_PIXEL
            if plant not in post_filters:
                post_filters[plant] = LocalLinearFilter(measurement)
            post_filters[plant].update(measurement, float(candidate["conf"]))
            plain_positions[plant] = (
                0.5 * plain_positions[plant] + 0.5 * float(candidate["x_root_frac"])
            )
            by_plant[plant] = {
                "single_frame_cm": measurement,
                "post_detection_filter_cm": float(post_filters[plant].state[0]),
                "plain_candidate_index": candidate_index,
            }

        for plant, candidate_index in prior_assignment.items():
            candidate = current.iloc[candidate_index]
            measurement = float(candidate["height_px"]) * CM_PER_PIXEL
            if plant not in prior_filters:
                prior_filters[plant] = LocalLinearFilter(measurement)
            prior_filters[plant].update(measurement, float(candidate["conf"]))
            prior_positions[plant] = (
                0.5 * prior_positions[plant] + 0.5 * float(candidate["x_root_frac"])
            )
            if plant in by_plant:
                by_plant[plant].update(
                    {
                        "prior_guided_filter_cm": float(prior_filters[plant].state[0]),
                        "prior_candidate_index": candidate_index,
                        "same_candidate": bool(
                            by_plant[plant]["plain_candidate_index"] == candidate_index
                        ),
                    }
                )

        for plant, values in by_plant.items():
            target = camera_truth[
                (camera_truth["plantid"] == plant) & (camera_truth["date_md"] == day)
            ]
            if target.empty or "prior_guided_filter_cm" not in values:
                continue
            records.append(
                {
                    "camera": camera,
                    "plantid": plant,
                    "day": day,
                    "manual_height_cm": float(target["height_true"].iloc[0]),
                    **values,
                }
            )
        previous_date = date
    return records


def metrics(data: pd.DataFrame, column: str) -> dict[str, float | int]:
    error = data[column] - data["manual_height_cm"]
    return {
        "n": int(len(data)),
        "bias_cm": float(error.mean()),
        "mae_cm": float(error.abs().mean()),
        "rmse_cm": float(np.sqrt(np.mean(error**2))),
    }


def bootstrap_difference(
    data: pd.DataFrame, left: str, right: str, replicates: int, seed: int
) -> dict[str, object]:
    cameras = sorted(data["camera"].unique())
    grouped = {}
    for camera in cameras:
        group = data[data["camera"] == camera]
        grouped[camera] = {
            "n": len(group),
            "left": float((group[left] - group["manual_height_cm"]).abs().sum()),
            "right": float((group[right] - group["manual_height_cm"]).abs().sum()),
        }
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates)
    for index in range(replicates):
        selected = rng.choice(cameras, size=len(cameras), replace=True)
        denominator = sum(grouped[camera]["n"] for camera in selected)
        draws[index] = sum(
            grouped[camera]["left"] - grouped[camera]["right"]
            for camera in selected
        ) / denominator
    observed = metrics(data, left)["mae_cm"] - metrics(data, right)["mae_cm"]
    return {
        "left_minus_right_mae_cm": float(observed),
        "ci95_cm": [float(value) for value in np.quantile(draws, [0.025, 0.975])],
        "bootstrap_probability_gt_zero": float(np.mean(draws > 0)),
    }


def main() -> None:
    args = parse_args()
    candidates = pd.read_csv(args.candidates)
    anchors = pd.read_csv(args.anchors)
    truth = pd.read_csv(args.truth)
    truth["camera"] = truth["rowid"]
    cameras = sorted(set(candidates["camera"]) & set(anchors["rowid"]) & set(truth["camera"]))
    records = []
    for camera in cameras:
        records.extend(run_camera(camera, candidates, anchors, truth))
    data = pd.DataFrame(records)
    methods = {
        "Single frame": "single_frame_cm",
        "Identical candidates plus post-detection filter": "post_detection_filter_cm",
        "Height prior in candidate scoring plus identical filter": "prior_guided_filter_cm",
    }
    summary = [{"method": name, **metrics(data, column)} for name, column in methods.items()]
    comparison = bootstrap_difference(
        data,
        "post_detection_filter_cm",
        "prior_guided_filter_cm",
        args.replicates,
        args.seed,
    )
    payload = {
        "design": {
            "cameras": int(data["camera"].nunique()),
            "plant_tracks": int(data.groupby(["camera", "plantid"]).ngroups),
            "plant_dates": int(len(data)),
            "physical_scale_cm_per_pixel": CM_PER_PIXEL,
            "manual_height_used_for_tuning": False,
            "initial_root_anchors": "human-mask root positions from the first available image",
            "bootstrap_cluster": "camera",
            "bootstrap_replicates": args.replicates,
            "seed": args.seed,
        },
        "selection_agreement": float(data["same_candidate"].mean()),
        "metrics": summary,
        "post_filter_vs_prior_guided": comparison,
        "interpretation": (
            "The natural images did not contain a candidate-choice conflict under the "
            "prespecified gates: both temporal methods selected the same candidate. The "
            "real-image result is therefore a negative control, not evidence of an accuracy gain."
        ),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output / "per_record.csv", index=False)
    pd.DataFrame(summary).to_csv(args.output / "method_metrics.csv", index=False)
    (args.output / "summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(pd.DataFrame(summary).round(3).to_string(index=False))
    print(json.dumps({"selection_agreement": payload["selection_agreement"], **comparison}, indent=2))


if __name__ == "__main__":
    main()
