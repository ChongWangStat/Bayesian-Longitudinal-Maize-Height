from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from analysis.bayesian_online_height_filter import filter_one_plant
from plant_height_app.engine import (
    AnalysisConfig,
    RobustHeightFilter,
    analyze_candidate_table,
    detect_red_band_calibrations,
    fit_projective_calibration,
    infer_capture_datetime,
)


def _metadata(dates: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "filename": [f"camera_2021-{date}.jpg" for date in dates],
            "capture_datetime": pd.to_datetime([f"2021-{date}" for date in dates]),
            "camera_id": "camera_1",
        }
    )


def _candidate(filename: str, index: int, height_px: float, confidence: float = 0.8):
    root_y = 800.0
    return {
        "filename": filename,
        "camera_id": "camera_1",
        "capture_datetime": pd.Timestamp(filename[7:17]),
        "candidate_index": index,
        "confidence": confidence,
        "x_top": 400.0,
        "y_top": root_y - height_px,
        "x_root": 400.0,
        "y_root": root_y,
        "x_root_fraction": 0.5,
        "height_px": height_px,
        "box_x1": 350.0,
        "box_y1": root_y - height_px,
        "box_x2": 450.0,
        "box_y2": 820.0,
        "image_width": 800,
        "image_height": 1000,
        "selected": False,
        "selected_plant_uid": pd.NA,
    }


def test_date_inference_handles_date_and_time() -> None:
    value = infer_capture_datetime("plot-A_2026-07-18-11-45_camera.jpg")
    assert value == pd.Timestamp("2026-07-18 11:45:00")


def test_projective_calibration_recovers_linear_landmarks() -> None:
    fit = fit_projective_calibration(
        [100, 200, 300, 400, 500],
        [120, 90, 60, 30, 0],
    )
    assert fit["pole_fit_rmse_cm"] < 1e-8
    assert fit["min_landmark_y_px"] == 100
    assert fit["max_landmark_y_px"] == 500


def test_height_prior_selects_plausible_candidate() -> None:
    metadata = _metadata(["07-01", "07-02"])
    first_name, second_name = metadata["filename"].tolist()
    candidates = pd.DataFrame(
        [
            _candidate(first_name, 0, 120, 0.90),
            _candidate(second_name, 0, 130, 0.60),
            _candidate(second_name, 1, 350, 0.95),
        ]
    )
    config = AnalysisConfig(expected_plants=1, particles=1000)
    estimates, selected, warnings = analyze_candidate_table(
        metadata, candidates, pd.DataFrame(), config
    )
    assert not warnings
    chosen = selected[selected["filename"].eq(second_name) & selected["selected"]]
    assert chosen["candidate_index"].tolist() == [0]
    assert estimates["measurement_used"].all()


def test_prefix_results_do_not_change_when_future_image_is_added() -> None:
    metadata = _metadata(["07-01", "07-03", "07-06"])
    candidates = pd.DataFrame(
        [
            _candidate(filename, 0, height, confidence)
            for filename, height, confidence in zip(
                metadata["filename"], [120, 170, 250], [0.90, 0.85, 0.88]
            )
        ]
    )
    config = AnalysisConfig(expected_plants=1, particles=1000)
    full, _, _ = analyze_candidate_table(metadata, candidates, pd.DataFrame(), config)
    prefix_names = set(metadata["filename"].iloc[:2])
    prefix, _, _ = analyze_candidate_table(
        metadata.iloc[:2],
        candidates[candidates["filename"].isin(prefix_names)],
        pd.DataFrame(),
        config,
    )
    columns = [
        "filename",
        "bayesian_height_cm",
        "height_95_low_cm",
        "height_95_high_cm",
        "image_measurement_cm",
    ]
    pd.testing.assert_frame_equal(
        full[full["filename"].isin(prefix_names)][columns].reset_index(drop=True),
        prefix[columns].reset_index(drop=True),
        check_exact=True,
    )


def test_prediction_only_row_is_emitted_for_missed_detection() -> None:
    metadata = _metadata(["07-01", "07-02"])
    candidates = pd.DataFrame([_candidate(metadata["filename"].iloc[0], 0, 120)])
    config = AnalysisConfig(expected_plants=1, particles=1000)
    estimates, _, _ = analyze_candidate_table(
        metadata, candidates, pd.DataFrame(), config
    )
    second = estimates.iloc[1]
    assert second["status"] == "prediction_only_no_matched_detection"
    assert not bool(second["measurement_used"])
    assert np.isfinite(second["bayesian_height_cm"])


def test_automatic_red_band_calibration_on_clean_reference(tmp_path: Path) -> None:
    image_path = tmp_path / "pole_2026-06-15.jpg"
    image = Image.new("RGB", (800, 1000), "white")
    draw = ImageDraw.Draw(image)
    for y in [150, 200, 250, 300, 350, 400, 450]:
        draw.rectangle((380, y - 4, 410, y + 4), fill=(200, 55, 55))
    image.save(image_path, quality=100)
    metadata = pd.DataFrame(
        {
            "filename": [image_path.name],
            "capture_datetime": [pd.Timestamp("2026-06-15 12:00")],
            "camera_id": ["camera_1"],
            "image_path": [image_path],
        }
    )
    calibrations, points = detect_red_band_calibrations(
        metadata, AnalysisConfig(calibration_mode="red_band")
    )
    assert bool(calibrations.loc[0, "pole_fit_pass"])
    assert calibrations.loc[0, "n_landmarks"] == 7
    assert len(points[image_path.name]) == 7


def test_stateful_filter_matches_released_filter() -> None:
    data = pd.DataFrame(
        {
            "plant_uid": ["camera_1_P1"] * 4,
            "date": pd.to_datetime(
                ["2021-07-01", "2021-07-03", "2021-07-07", "2021-07-08"]
            ),
            "height": [50.0, 72.0, 118.0, 125.0],
            "sd": [14.0, 15.0, 18.0, 13.0],
        }
    )
    config = AnalysisConfig(expected_plants=1, particles=1000)
    released = filter_one_plant(
        data,
        "plant_uid",
        "date",
        "height",
        "sd",
        config.particles,
        config.seed,
        15.0,
        1.0,
        config.initial_growth_mean_cm_day,
        config.initial_growth_sd_cm_day,
        config.process_height_sd_cm_sqrt_day,
        config.process_growth_sd_cm_day_sqrt_day,
        config.minimum_growth_cm_day,
        config.maximum_growth_cm_day,
        config.outlier_probability,
        config.outlier_sd_cm,
        config.resample_ess_fraction,
    )
    stateful = RobustHeightFilter(config, "camera_1_P1")
    summaries = []
    for index, row in data.iterrows():
        if index == 0:
            stateful.initialize(row["height"], row["sd"], row["date"])
        else:
            stateful.predict_to(row["date"])
            stateful.update(row["height"], row["sd"])
        summaries.append(stateful.summary())
    assert np.allclose(
        released["posterior_mean_cm"],
        [row["bayesian_height_cm"] for row in summaries],
        rtol=0,
        atol=1e-12,
    )
    assert np.allclose(
        released["posterior_q025_cm"],
        [row["height_95_low_cm"] for row in summaries],
        rtol=0,
        atol=1e-12,
    )
