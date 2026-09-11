"""End-to-end image-to-height engine for the plant-scientist application.

The engine keeps the published ordering of operations: images are processed in
time order within camera, the preceding position and height states participate
in current-image candidate selection, physical calibration converts selected
keypoints to centimetres, and a robust particle filter emits an as-of posterior.
No result at time t uses an image dated after t.
"""

from __future__ import annotations

import json
import math
import platform
import re
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import ExifTags, Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment
from scipy.special import logsumexp

APP_VERSION = "1.0.0"
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
PUBLISHED_2021_CM_PER_PIXEL = 0.415886


@dataclass(frozen=True)
class AnalysisConfig:
    """User-visible settings plus the locked published-filter defaults."""

    calibration_mode: str = "published_2021"
    cm_per_pixel: float = PUBLISHED_2021_CM_PER_PIXEL
    red_band_interval_cm: float = 30.48
    pole_to_plant_depth_factor: float = 0.85
    expected_plants: int = 6
    numbering_direction: str = "left_to_right"
    image_size: int = 640
    confidence_threshold: float = 0.05
    iou_threshold: float = 0.50
    maximum_detections: int = 50
    minimum_height_px: float = 20.0
    minimum_root_y_fraction: float = 0.35
    maximum_track_distance_fraction: float = 0.16
    position_sd_fraction: float = 0.05
    position_gain: float = 0.50
    innovation_gate_z: float = 3.0
    base_measurement_sd_cm: float = 12.0
    extrapolation_sd_cm_per_band: float = 1.5
    particles: int = 5000
    seed: int = 20260724
    initial_growth_mean_cm_day: float = 0.0
    initial_growth_sd_cm_day: float = 8.0
    process_height_sd_cm_sqrt_day: float = 8.78
    process_growth_sd_cm_day_sqrt_day: float = 0.35
    minimum_growth_cm_day: float = -4.0
    maximum_growth_cm_day: float = 15.0
    outlier_probability: float = 0.065
    outlier_sd_cm: float = 59.04
    resample_ess_fraction: float = 0.50

    def validate(self) -> None:
        if self.calibration_mode not in {
            "published_2021",
            "known_scale",
            "red_band",
        }:
            raise ValueError(f"Unknown calibration mode: {self.calibration_mode}")
        if self.cm_per_pixel <= 0:
            raise ValueError("The image scale must be greater than zero.")
        if self.red_band_interval_cm <= 0:
            raise ValueError("The red-band interval must be greater than zero.")
        if self.pole_to_plant_depth_factor <= 0:
            raise ValueError(
                "The pole-to-plant depth factor must be greater than zero."
            )
        if self.expected_plants < 1 or self.expected_plants > 100:
            raise ValueError("Expected plants must be between 1 and 100.")
        if self.numbering_direction not in {"left_to_right", "right_to_left"}:
            raise ValueError(
                "Numbering direction must be left_to_right or right_to_left."
            )
        if not 0 < self.position_gain <= 1:
            raise ValueError("Position gain must be in (0, 1].")
        if not 0 < self.maximum_track_distance_fraction <= 1:
            raise ValueError("Maximum tracking distance must be in (0, 1].")
        if self.particles < 200:
            raise ValueError("At least 200 particles are required.")
        if self.position_sd_fraction <= 0:
            raise ValueError("Position uncertainty must be greater than zero.")
        if self.base_measurement_sd_cm <= 0 or self.outlier_sd_cm <= 0:
            raise ValueError(
                "Measurement uncertainty values must be greater than zero."
            )
        if not 0 < self.outlier_probability < 1:
            raise ValueError("Outlier probability must be between zero and one.")


@dataclass
class AnalysisArtifacts:
    height_estimates: pd.DataFrame
    image_summary: pd.DataFrame
    candidates: pd.DataFrame
    calibrations: pd.DataFrame
    annotated_images: dict[str, bytes]
    run_metadata: dict[str, object]
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Track:
    plant_number: int
    plant_uid: str
    x_fraction: float
    root_y: float
    height_filter: RobustHeightFilter | None = None


def _stable_seed(label: object, base_seed: int) -> int:
    digest = sha256(f"{base_seed}|{label}".encode()).digest()
    return int.from_bytes(digest[:8], "little") % (2**32 - 1)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def infer_capture_datetime(
    filename: str, image_bytes: bytes | None = None
) -> pd.Timestamp | None:
    """Infer an acquisition time from a filename, then from EXIF metadata."""

    name = Path(filename).name
    patterns = [
        (
            r"(?P<y>20\d{2})[-_](?P<m>\d{2})[-_](?P<d>\d{2})"
            r"(?:[-_](?P<h>\d{2})[-_](?P<minute>\d{2})(?:[-_](?P<s>\d{2}))?)?"
        ),
        r"(?<!\d)(?P<y>20\d{2})(?P<m>\d{2})(?P<d>\d{2})(?!\d)",
    ]
    for pattern in patterns:
        match = re.search(pattern, name)
        if not match:
            continue
        values = match.groupdict()
        try:
            return pd.Timestamp(
                year=int(values["y"]),
                month=int(values["m"]),
                day=int(values["d"]),
                hour=int(values.get("h") or 12),
                minute=int(values.get("minute") or 0),
                second=int(values.get("s") or 0),
            )
        except ValueError:
            pass

    if image_bytes is not None:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                exif = image.getexif()
                labels = {
                    ExifTags.TAGS.get(key, key): value for key, value in exif.items()
                }
                value = labels.get("DateTimeOriginal") or labels.get("DateTime")
                if value:
                    return pd.to_datetime(str(value), format="%Y:%m:%d %H:%M:%S")
        except (OSError, TypeError, ValueError):
            pass
    return None


def default_metadata(
    filenames: Iterable[str],
    image_bytes: Mapping[str, bytes] | None = None,
    camera_id: str = "camera_1",
) -> pd.DataFrame:
    rows = []
    payload = image_bytes or {}
    for filename in filenames:
        inferred = infer_capture_datetime(filename, payload.get(filename))
        rows.append(
            {
                "filename": Path(filename).name,
                "capture_datetime": ""
                if inferred is None
                else inferred.isoformat(sep=" "),
                "camera_id": camera_id,
            }
        )
    return pd.DataFrame(rows)


def validate_metadata(
    metadata: pd.DataFrame, image_paths: Mapping[str, Path]
) -> pd.DataFrame:
    required = {"filename", "capture_datetime", "camera_id"}
    missing = sorted(required - set(metadata.columns))
    if missing:
        raise ValueError("The date table is missing: " + ", ".join(missing))
    result = metadata[["filename", "capture_datetime", "camera_id"]].copy()
    result["filename"] = result["filename"].map(lambda value: Path(str(value)).name)
    if result["filename"].duplicated().any():
        duplicated = result.loc[result["filename"].duplicated(), "filename"].tolist()
        raise ValueError(
            "Each image filename must occur once: " + ", ".join(duplicated[:5])
        )
    expected = set(image_paths)
    supplied = set(result["filename"])
    missing_rows = sorted(expected - supplied)
    extra_rows = sorted(supplied - expected)
    if missing_rows:
        raise ValueError("Dates are missing for: " + ", ".join(missing_rows[:8]))
    if extra_rows:
        raise ValueError(
            "The date table names files that were not uploaded: "
            + ", ".join(extra_rows[:8])
        )
    result["capture_datetime"] = pd.to_datetime(
        result["capture_datetime"], errors="coerce"
    )
    if result["capture_datetime"].isna().any():
        bad = result.loc[result["capture_datetime"].isna(), "filename"].tolist()
        raise ValueError(
            "Enter a valid date for every image. Check: " + ", ".join(bad[:8])
        )
    result["camera_id"] = result["camera_id"].astype(str).str.strip()
    if result["camera_id"].eq("").any():
        raise ValueError("Every image needs a camera or plot identifier.")
    result["image_path"] = result["filename"].map(image_paths)
    result["image_sha256"] = result["image_path"].map(_file_sha256)
    return result.sort_values(
        ["camera_id", "capture_datetime", "filename"], kind="mergesort"
    ).reset_index(drop=True)


def _load_font(size: int = 18) -> ImageFont.ImageFont:
    for name in (
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "Arial.ttf",
        "arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def run_pose_inference(
    metadata: pd.DataFrame,
    model_path: Path,
    config: AnalysisConfig,
    model: object | None = None,
    progress: Callable[[str, int, int, str], None] | None = None,
) -> pd.DataFrame:
    """Run the released two-keypoint pose model on every image."""

    if model is None:
        from ultralytics import YOLO

        model = YOLO(str(model_path))
    rows: list[dict[str, object]] = []
    total = len(metadata)
    for image_number, record in enumerate(metadata.itertuples(index=False), start=1):
        if progress:
            progress(
                "pose", image_number, total, f"Finding plants in {record.filename}"
            )
        result = model.predict(
            source=str(record.image_path),
            imgsz=config.image_size,
            conf=config.confidence_threshold,
            iou=config.iou_threshold,
            max_det=config.maximum_detections,
            device="cpu",
            save=False,
            verbose=False,
        )[0]
        if result.boxes is None or result.keypoints is None or len(result.boxes) == 0:
            continue
        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        keypoints = result.keypoints.xy.cpu().numpy()
        image_height, image_width = result.orig_shape
        for candidate_index in range(len(boxes)):
            x1, y1, x2, y2 = boxes[candidate_index]
            top_x, top_y = keypoints[candidate_index, 0]
            root_x, root_y = keypoints[candidate_index, 1]
            values = np.asarray([x1, y1, x2, y2, top_x, top_y, root_x, root_y])
            if not np.isfinite(values).all():
                continue
            x1 = float(np.clip(x1, 0, image_width - 1))
            x2 = float(np.clip(x2, 0, image_width - 1))
            y1 = float(np.clip(y1, 0, image_height - 1))
            y2 = float(np.clip(y2, 0, image_height - 1))
            if x2 <= x1 or y2 <= y1:
                continue
            top_x = float(np.clip(top_x, x1, x2))
            root_x = float(np.clip(root_x, x1, x2))
            top_y = float(np.clip(top_y, y1, y2))
            root_y = float(np.clip(root_y, y1, y2))
            height_px = max(root_y - top_y, 0.0)
            box_width = x2 - x1
            aspect_ratio = (y2 - y1) / max(box_width, 1.0)
            if height_px < config.minimum_height_px:
                continue
            if root_y < config.minimum_root_y_fraction * image_height:
                continue
            if box_width < 5 or not 0.4 <= aspect_ratio <= 25:
                continue
            rows.append(
                {
                    "filename": record.filename,
                    "camera_id": record.camera_id,
                    "capture_datetime": record.capture_datetime,
                    "candidate_index": int(candidate_index),
                    "confidence": float(confidences[candidate_index]),
                    "x_top": top_x,
                    "y_top": top_y,
                    "x_root": root_x,
                    "y_root": root_y,
                    "x_root_fraction": root_x / image_width,
                    "height_px": height_px,
                    "box_x1": x1,
                    "box_y1": y1,
                    "box_x2": x2,
                    "box_y2": y2,
                    "image_width": int(image_width),
                    "image_height": int(image_height),
                    "selected": False,
                    "selected_plant_uid": pd.NA,
                }
            )
    columns = [
        "filename",
        "camera_id",
        "capture_datetime",
        "candidate_index",
        "confidence",
        "x_top",
        "y_top",
        "x_root",
        "y_root",
        "x_root_fraction",
        "height_px",
        "box_x1",
        "box_y1",
        "box_x2",
        "box_y2",
        "image_width",
        "image_height",
        "selected",
        "selected_plant_uid",
    ]
    return pd.DataFrame(rows, columns=columns)


def _red_components(image_bgr: np.ndarray) -> list[dict[str, float]]:
    blue, green, red = cv2.split(image_bgr.astype(np.int16))
    mask = ((red >= 60) & (red - green >= 4) & (red - blue >= 4) & (red <= 248)).astype(
        np.uint8
    ) * 255
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask)
    height, width = mask.shape
    candidates: list[dict[str, float]] = []
    for index in range(1, count):
        x, y, component_width, component_height, area = stats[index]
        center_x, center_y = centroids[index]
        if not 5 <= area <= 500:
            continue
        if not (2 <= component_width <= 45 and 2 <= component_height <= 30):
            continue
        if component_width / max(component_height, 1) < 0.75:
            continue
        if (
            center_y > 0.82 * height
            or center_x < 0.03 * width
            or center_x > 0.97 * width
        ):
            continue
        margin_x = max(8, round(1.5 * component_width))
        margin_y = max(12, round(3.0 * component_height))
        local = hsv[
            max(0, y - margin_y) : min(height, y + component_height + margin_y),
            max(0, x - margin_x) : min(width, x + component_width + margin_x),
        ]
        white_fraction = float(np.mean((local[:, :, 1] < 70) & (local[:, :, 2] > 115)))
        if white_fraction < 0.06:
            continue
        region = image_bgr[y : y + component_height, x : x + component_width].astype(
            float
        )
        mean_blue, mean_green, mean_red = region.reshape(-1, 3).mean(axis=0)
        color_strength = float(mean_red - max(mean_green, mean_blue))
        aspect = component_width / max(component_height, 1)
        score = (
            12 * white_fraction
            + color_strength / 15
            + math.log1p(area)
            - abs(math.log(max(aspect, 0.01) / 1.5))
        )
        candidates.append(
            {
                "x": float(center_x),
                "y": float(center_y),
                "area": float(area),
                "component_score": score,
            }
        )
    return sorted(candidates, key=lambda item: item["component_score"], reverse=True)[
        :250
    ]


def _collapse_close_y(points: list[dict[str, float]]) -> list[dict[str, float]]:
    if not points:
        return []
    ordered = sorted(points, key=lambda item: item["y"])
    groups: list[list[dict[str, float]]] = [[ordered[0]]]
    for point in ordered[1:]:
        if point["y"] - groups[-1][-1]["y"] <= 8:
            groups[-1].append(point)
        else:
            groups.append([point])
    collapsed = []
    for group in groups:
        weights = np.asarray([item["area"] for item in group])
        collapsed.append(
            {
                "x": float(np.average([item["x"] for item in group], weights=weights)),
                "y": float(np.average([item["y"] for item in group], weights=weights)),
                "area": float(sum(item["area"] for item in group)),
                "component_score": float(
                    max(item["component_score"] for item in group)
                ),
            }
        )
    return collapsed


def _estimate_base_gap(gaps: np.ndarray) -> float | None:
    useful = gaps[(gaps >= 18) & (gaps <= 110)]
    if len(useful) < 3:
        return None
    best: tuple[int, float, float] | None = None
    for candidate in np.linspace(18, 110, 185):
        relative_error = np.abs(useful / candidate - 1)
        matched = relative_error <= 0.22
        count = int(matched.sum())
        if count < 2:
            continue
        score = (count, -float(np.median(relative_error[matched])), float(candidate))
        if best is None or score > best:
            best = score
    if best is None:
        return None
    candidate = best[2]
    values = useful[np.abs(useful / candidate - 1) <= 0.22]
    return float(np.median(values))


def _best_contiguous_run(
    points: list[dict[str, float]], base_gap: float
) -> list[dict[str, float]]:
    ordered = sorted(points, key=lambda item: item["y"])
    gaps = np.diff([item["y"] for item in ordered])
    good = (gaps / base_gap >= 0.68) & (gaps / base_gap <= 1.36)
    runs: list[list[dict[str, float]]] = []
    start = 0
    for index, is_good in enumerate(good):
        if not is_good:
            runs.append(ordered[start : index + 1])
            start = index + 1
    runs.append(ordered[start:])
    return max(
        runs,
        key=lambda run: (
            len(run),
            sum(item["component_score"] for item in run),
            run[-1]["y"] - run[0]["y"] if len(run) > 1 else 0,
        ),
    )


def _sequence_metrics(points: list[dict[str, float]]) -> dict[str, float] | None:
    points = _collapse_close_y(points)
    if len(points) < 4:
        return None
    y = np.asarray([item["y"] for item in points])
    x = np.asarray([item["x"] for item in points])
    gaps = np.diff(y)
    base_gap = _estimate_base_gap(gaps)
    if base_gap is None:
        return None
    gap_residual = np.abs(gaps / base_gap - 1)
    x_fit = np.polyval(np.polyfit(y, x, 1), y)
    line_rmse = float(np.sqrt(np.mean((x - x_fit) ** 2)))
    regularity = float(np.median(gap_residual))
    span = float(y.max() - y.min())
    if line_rmse > 8 or regularity > 0.32 or span < 90:
        return None
    return {
        "base_gap_px": base_gap,
        "gap_regularity": regularity,
        "line_rmse_px": line_rmse,
        "span_px": span,
    }


def _find_pole_sequence(
    candidates: list[dict[str, float]], min_bands: int = 5
) -> tuple[list[dict[str, float]], dict[str, float]] | None:
    if len(candidates) < min_bands:
        return None
    best: tuple[float, list[dict[str, float]], dict[str, float]] | None = None
    for first_index in range(len(candidates)):
        for second_index in range(first_index + 1, len(candidates)):
            first = candidates[first_index]
            second = candidates[second_index]
            delta_y = second["y"] - first["y"]
            if abs(delta_y) < 70:
                continue
            slope = (second["x"] - first["x"]) / delta_y
            if abs(slope) > 0.35:
                continue
            intercept = first["x"] - slope * first["y"]
            aligned = [
                item
                for item in candidates
                if abs(item["x"] - (slope * item["y"] + intercept)) <= 7
            ]
            aligned = _collapse_close_y(aligned)
            if len(aligned) >= min_bands:
                initial_gap = _estimate_base_gap(
                    np.diff([item["y"] for item in aligned])
                )
                if initial_gap is not None:
                    aligned = _best_contiguous_run(aligned, initial_gap)
            metrics = _sequence_metrics(aligned)
            if metrics is None or len(aligned) < min_bands:
                continue
            mean_area = float(np.mean([item["area"] for item in aligned]))
            score = (
                25 * len(aligned)
                + 0.08 * metrics["span_px"]
                + 0.05 * mean_area
                - 8 * metrics["line_rmse_px"]
                - 35 * metrics["gap_regularity"]
            )
            if best is None or score > best[0]:
                best = (score, aligned, metrics)
    return None if best is None else (best[1], best[2])


def fit_projective_calibration(
    y_px: Iterable[float], relative_height_cm: Iterable[float]
) -> dict[str, float]:
    y = np.asarray(list(y_px), dtype=float)
    height = np.asarray(list(relative_height_cm), dtype=float)
    if len(y) < 4 or len(np.unique(height)) < 4:
        raise ValueError("At least four distinct pole landmarks are required.")
    y_center = float(y.mean())
    y_scale = float(y.std(ddof=0))
    if y_scale <= 0:
        raise ValueError("Pole landmark rows have zero spread.")
    normalized = (y - y_center) / y_scale
    design = np.column_stack(
        [normalized, np.ones_like(normalized), -height * normalized]
    )
    a, b, c = np.linalg.lstsq(design, height, rcond=None)[0]
    denominator = c * normalized + 1
    if np.min(np.abs(denominator)) < 0.1:
        raise ValueError("The pole calibration is numerically unstable.")
    fitted = (a * normalized + b) / denominator
    if a - b * c >= 0:
        raise ValueError("Pole landmarks are not vertically ordered.")
    residual = height - fitted
    return {
        "a": float(a),
        "b": float(b),
        "c": float(c),
        "y_center": y_center,
        "y_scale": y_scale,
        "pole_fit_rmse_cm": float(np.sqrt(np.mean(residual**2))),
        "pole_fit_max_abs_error_cm": float(np.max(np.abs(residual))),
        "min_landmark_y_px": float(y.min()),
        "max_landmark_y_px": float(y.max()),
    }


def _transform_y(y_px: float, calibration: Mapping[str, object]) -> float:
    normalized = (float(y_px) - float(calibration["y_center"])) / float(
        calibration["y_scale"]
    )
    denominator = float(calibration["c"]) * normalized + 1
    return (
        float(calibration["a"]) * normalized + float(calibration["b"])
    ) / denominator


def detect_red_band_calibrations(
    metadata: pd.DataFrame,
    config: AnalysisConfig,
    progress: Callable[[str, int, int, str], None] | None = None,
) -> tuple[pd.DataFrame, dict[str, list[dict[str, float]]]]:
    rows: list[dict[str, object]] = []
    points_by_image: dict[str, list[dict[str, float]]] = {}
    total = len(metadata)
    for image_number, record in enumerate(metadata.itertuples(index=False), start=1):
        if progress:
            progress(
                "calibration",
                image_number,
                total,
                f"Finding pole bands in {record.filename}",
            )
        image = cv2.imread(str(record.image_path))
        if image is None:
            raise FileNotFoundError(record.image_path)
        candidates = _red_components(image)
        found = _find_pole_sequence(candidates, min_bands=5)
        row: dict[str, object] = {
            "filename": record.filename,
            "camera_id": record.camera_id,
            "capture_datetime": record.capture_datetime,
            "red_component_candidates": len(candidates),
            "pole_detected": found is not None,
            "pole_fit_pass": False,
            "n_landmarks": 0,
        }
        if found is not None:
            points, metrics = found
            points = sorted(points, key=lambda item: item["y"])
            gaps = np.diff([point["y"] for point in points])
            increments = np.maximum(1, np.rint(gaps / metrics["base_gap_px"])).astype(
                int
            )
            levels_from_top = np.concatenate([[0], np.cumsum(increments)])
            maximum = int(levels_from_top[-1])
            assigned = []
            for point, level in zip(points, levels_from_top):
                assigned.append(
                    {
                        **point,
                        "relative_height_cm": float(maximum - level)
                        * config.red_band_interval_cm,
                    }
                )
            fit = fit_projective_calibration(
                [point["y"] for point in assigned],
                [point["relative_height_cm"] for point in assigned],
            )
            row.update(metrics)
            row.update(fit)
            row["n_landmarks"] = len(assigned)
            row["pole_fit_pass"] = bool(
                fit["pole_fit_rmse_cm"] <= 2.54
                and metrics["gap_regularity"] <= 0.22
                and len(assigned) >= 5
            )
            row["landmark_rows_px"] = json.dumps(
                [round(point["y"], 3) for point in assigned]
            )
            points_by_image[record.filename] = assigned
        rows.append(row)
    return pd.DataFrame(rows), points_by_image


def _select_causal_calibration(
    calibrations: pd.DataFrame, camera_id: str, capture_datetime: pd.Timestamp
) -> dict[str, object] | None:
    if calibrations.empty:
        return None
    eligible = calibrations[
        calibrations["camera_id"].eq(camera_id)
        & calibrations["pole_fit_pass"].fillna(False)
        & (pd.to_datetime(calibrations["capture_datetime"]) <= capture_datetime)
    ].copy()
    if eligible.empty:
        return None
    capped = eligible[eligible["pole_fit_rmse_cm"] <= 1.27]
    if not capped.empty:
        eligible = capped
    eligible = eligible.sort_values(
        [
            "n_landmarks",
            "span_px",
            "pole_fit_rmse_cm",
            "capture_datetime",
            "filename",
        ],
        ascending=[False, False, True, True, True],
        kind="mergesort",
    )
    return eligible.iloc[0].to_dict()


def _weighted_quantile(
    values: np.ndarray, weights: np.ndarray, probabilities: list[float]
) -> np.ndarray:
    order = np.argsort(values)
    sorted_values = values[order]
    cumulative = np.cumsum(weights[order])
    cumulative /= cumulative[-1]
    return np.interp(probabilities, cumulative, sorted_values)


class RobustHeightFilter:
    """Stateful form of the released robust height-growth particle filter."""

    def __init__(self, config: AnalysisConfig, label: str):
        self.config = config
        self.rng = np.random.default_rng(_stable_seed(label, config.seed))
        self.height: np.ndarray | None = None
        self.growth: np.ndarray | None = None
        self.weights: np.ndarray | None = None
        self.current_time: pd.Timestamp | None = None
        self.last_outlier_probability = np.nan
        self.last_effective_sample_size = float(config.particles)
        self.last_predictive_mean = np.nan
        self.last_predictive_sd = np.nan

    @property
    def initialized(self) -> bool:
        return self.height is not None

    def initialize(
        self, measurement_cm: float, measurement_sd_cm: float, when: pd.Timestamp
    ) -> None:
        sd = max(float(measurement_sd_cm), 1.0)
        self.height = np.clip(
            self.rng.normal(measurement_cm, sd, self.config.particles), 0, 450
        )
        self.growth = np.clip(
            self.rng.normal(
                self.config.initial_growth_mean_cm_day,
                self.config.initial_growth_sd_cm_day,
                self.config.particles,
            ),
            self.config.minimum_growth_cm_day,
            self.config.maximum_growth_cm_day,
        )
        self.weights = np.full(self.config.particles, 1 / self.config.particles)
        self.current_time = pd.Timestamp(when)

    def predict_to(self, when: pd.Timestamp) -> None:
        if not self.initialized:
            return
        if self.last_effective_sample_size < self.config.resample_ess_fraction * len(
            self.weights
        ):
            positions = (self.rng.random() + np.arange(len(self.weights))) / len(
                self.weights
            )
            indices = np.searchsorted(np.cumsum(self.weights), positions, side="right")
            self.height = self.height[indices]
            self.growth = self.growth[indices]
            self.weights.fill(1 / len(self.weights))
            self.last_effective_sample_size = float(len(self.weights))
        when = pd.Timestamp(when)
        elapsed = (when - self.current_time).total_seconds() / 86400
        if elapsed < -1e-9:
            raise ValueError("Images must be processed in chronological order.")
        if elapsed <= 0:
            mean, variance = self.predictive_moments(0)
            self.last_predictive_mean = mean
            self.last_predictive_sd = math.sqrt(variance)
            return
        root_elapsed = math.sqrt(elapsed)
        self.height = np.clip(
            self.height
            + self.growth * elapsed
            + self.rng.normal(
                0,
                self.config.process_height_sd_cm_sqrt_day * root_elapsed,
                self.config.particles,
            ),
            0,
            450,
        )
        self.growth = np.clip(
            self.growth
            + self.rng.normal(
                0,
                self.config.process_growth_sd_cm_day_sqrt_day * root_elapsed,
                self.config.particles,
            ),
            self.config.minimum_growth_cm_day,
            self.config.maximum_growth_cm_day,
        )
        self.current_time = when
        mean, variance = self.predictive_moments(0)
        self.last_predictive_mean = mean
        self.last_predictive_sd = math.sqrt(variance)

    def predictive_moments(self, measurement_sd_cm: float) -> tuple[float, float]:
        if not self.initialized:
            return np.nan, np.nan
        mean = float(np.sum(self.weights * self.height))
        latent_variance = float(np.sum(self.weights * (self.height - mean) ** 2))
        return mean, latent_variance + float(measurement_sd_cm) ** 2

    def candidate_log_score(
        self, measurement_cm: float, measurement_sd_cm: float
    ) -> float:
        mean, variance = self.predictive_moments(measurement_sd_cm)
        predictive_sd = math.sqrt(max(variance, 1e-9))
        standardized = abs(measurement_cm - mean) / predictive_sd
        score = -0.5 * standardized**2 - math.log(predictive_sd)
        if standardized > self.config.innovation_gate_z:
            score += math.log(0.05)
        return score

    def update(self, measurement_cm: float, measurement_sd_cm: float) -> None:
        measurement_sd_cm = max(float(measurement_sd_cm), 1.0)
        log_inlier = (
            math.log1p(-self.config.outlier_probability)
            - 0.5 * ((measurement_cm - self.height) / measurement_sd_cm) ** 2
            - math.log(measurement_sd_cm)
            - 0.5 * math.log(2 * math.pi)
        )
        log_outlier = (
            math.log(self.config.outlier_probability)
            - 0.5 * ((measurement_cm - self.height) / self.config.outlier_sd_cm) ** 2
            - math.log(self.config.outlier_sd_cm)
            - 0.5 * math.log(2 * math.pi)
        )
        component = np.logaddexp(log_inlier, log_outlier)
        log_weights = np.log(self.weights) + component
        log_weights -= logsumexp(log_weights)
        self.weights = np.exp(log_weights)
        responsibility = np.exp(log_outlier - component)
        self.last_outlier_probability = float(np.sum(self.weights * responsibility))
        self.last_effective_sample_size = float(1 / np.sum(self.weights**2))

    def summary(self) -> dict[str, float]:
        if not self.initialized:
            return {
                "bayesian_height_cm": np.nan,
                "height_95_low_cm": np.nan,
                "height_80_low_cm": np.nan,
                "height_median_cm": np.nan,
                "height_80_high_cm": np.nan,
                "height_95_high_cm": np.nan,
                "posterior_sd_cm": np.nan,
                "growth_cm_day": np.nan,
                "growth_sd_cm_day": np.nan,
            }
        mean = float(np.sum(self.weights * self.height))
        height_sd = float(np.sqrt(np.sum(self.weights * (self.height - mean) ** 2)))
        growth_mean = float(np.sum(self.weights * self.growth))
        growth_sd = float(
            np.sqrt(np.sum(self.weights * (self.growth - growth_mean) ** 2))
        )
        q025, q10, q50, q90, q975 = _weighted_quantile(
            self.height, self.weights, [0.025, 0.10, 0.50, 0.90, 0.975]
        )
        return {
            "bayesian_height_cm": mean,
            "height_95_low_cm": float(q025),
            "height_80_low_cm": float(q10),
            "height_median_cm": float(q50),
            "height_80_high_cm": float(q90),
            "height_95_high_cm": float(q975),
            "posterior_sd_cm": height_sd,
            "growth_cm_day": growth_mean,
            "growth_sd_cm_day": growth_sd,
        }


def _measurement_for_candidate(
    candidate: Mapping[str, object],
    proposed_root_y: float,
    calibration: Mapping[str, object] | None,
    config: AnalysisConfig,
) -> dict[str, object]:
    confidence = max(float(candidate["confidence"]), 0.05)
    pose_sd = config.base_measurement_sd_cm / math.sqrt(confidence)
    if config.calibration_mode in {"published_2021", "known_scale"}:
        height_cm = (
            max(proposed_root_y - float(candidate["y_top"]), 0) * config.cm_per_pixel
        )
        return {
            "measurement_cm": height_cm,
            "measurement_sd_cm": pose_sd,
            "measurement_qc": "pass" if 0 < height_cm <= 450 else "height_out_of_range",
            "calibration_reference_image": "fixed_scale",
            "vertical_extrapolation_band_units": 0.0,
        }
    if calibration is None:
        return {
            "measurement_cm": np.nan,
            "measurement_sd_cm": np.nan,
            "measurement_qc": "no_past_passing_pole_calibration",
            "calibration_reference_image": pd.NA,
            "vertical_extrapolation_band_units": np.nan,
        }
    top_cm = _transform_y(float(candidate["y_top"]), calibration)
    root_cm = _transform_y(proposed_root_y, calibration)
    height_cm = (top_cm - root_cm) * config.pole_to_plant_depth_factor
    low = float(calibration["min_landmark_y_px"])
    high = float(calibration["max_landmark_y_px"])
    extrapolation_px = max(
        low - float(candidate["y_top"]),
        float(candidate["y_top"]) - high,
        low - proposed_root_y,
        proposed_root_y - high,
        0.0,
    )
    extrapolation_bands = extrapolation_px / float(calibration["base_gap_px"])
    fit_sd = (
        math.sqrt(2)
        * float(calibration["pole_fit_rmse_cm"])
        * config.pole_to_plant_depth_factor
    )
    extrapolation_sd = extrapolation_bands * config.extrapolation_sd_cm_per_band
    regularity_sd = abs(height_cm) * float(calibration["gap_regularity"])
    measurement_sd = math.sqrt(
        pose_sd**2 + fit_sd**2 + extrapolation_sd**2 + regularity_sd**2
    )
    if not 0 < height_cm <= 450:
        qc = "height_out_of_range"
    elif extrapolation_bands > 3:
        qc = "pole_extrapolation_over_three_bands"
    else:
        qc = "pass"
    return {
        "measurement_cm": height_cm,
        "measurement_sd_cm": measurement_sd,
        "measurement_qc": qc,
        "calibration_reference_image": calibration["filename"],
        "vertical_extrapolation_band_units": extrapolation_bands,
    }


def _initial_candidates(frame: pd.DataFrame, expected_plants: int) -> list[int]:
    if frame.empty:
        return []
    ranked = frame.sort_values(
        ["confidence", "height_px", "candidate_index"],
        ascending=[False, False, True],
        kind="mergesort",
    )
    chosen: list[int] = []
    chosen_positions: list[float] = []
    minimum_separation = 0.035
    for index, row in ranked.iterrows():
        x = float(row["x_root_fraction"])
        if all(
            abs(x - existing) >= minimum_separation for existing in chosen_positions
        ):
            chosen.append(index)
            chosen_positions.append(x)
        if len(chosen) == expected_plants:
            return chosen
    return []


def analyze_candidate_table(
    metadata: pd.DataFrame,
    candidates: pd.DataFrame,
    calibrations: pd.DataFrame,
    config: AnalysisConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Track candidates and update height filters in strict camera-time order."""

    config.validate()
    candidate_work = candidates.copy()
    if not candidate_work.empty:
        candidate_work["capture_datetime"] = pd.to_datetime(
            candidate_work["capture_datetime"]
        )
    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    for camera_id, camera_images in metadata.groupby("camera_id", sort=True):
        tracks: list[_Track] | None = None
        camera_images = camera_images.sort_values(
            ["capture_datetime", "filename"], kind="mergesort"
        )
        for image_record in camera_images.itertuples(index=False):
            when = pd.Timestamp(image_record.capture_datetime)
            frame = candidate_work[
                candidate_work["filename"].eq(image_record.filename)
            ].copy()
            calibration = (
                _select_causal_calibration(calibrations, camera_id, when)
                if config.calibration_mode == "red_band"
                else None
            )
            if tracks is None:
                initial_indices = _initial_candidates(frame, config.expected_plants)
                if len(initial_indices) != config.expected_plants:
                    continue
                initial = frame.loc[initial_indices].copy()
                initial = initial.sort_values(
                    "x_root_fraction",
                    ascending=config.numbering_direction == "left_to_right",
                )
                tracks = []
                for plant_number, (candidate_row_index, candidate) in enumerate(
                    initial.iterrows(), start=1
                ):
                    plant_uid = f"{camera_id}_P{plant_number}"
                    track = _Track(
                        plant_number=plant_number,
                        plant_uid=plant_uid,
                        x_fraction=float(candidate["x_root_fraction"]),
                        root_y=float(candidate["y_root"]),
                    )
                    measurement = _measurement_for_candidate(
                        candidate, track.root_y, calibration, config
                    )
                    used = measurement["measurement_qc"] == "pass"
                    if used:
                        track.height_filter = RobustHeightFilter(config, plant_uid)
                        track.height_filter.initialize(
                            float(measurement["measurement_cm"]),
                            float(measurement["measurement_sd_cm"]),
                            when,
                        )
                    tracks.append(track)
                    candidate_work.at[candidate_row_index, "selected"] = True
                    candidate_work.at[candidate_row_index, "selected_plant_uid"] = (
                        plant_uid
                    )
                    rows.append(
                        _result_row(
                            image_record,
                            track,
                            candidate,
                            measurement,
                            used,
                            "measured" if used else "calibration_unavailable",
                        )
                    )
                continue

            for track in tracks:
                if track.height_filter is not None:
                    track.height_filter.predict_to(when)

            assignments: dict[int, int] = {}
            proposed_measurements: dict[tuple[int, int], dict[str, object]] = {}
            if not frame.empty:
                frame_indices = list(frame.index)
                cost = np.full((len(tracks), len(frame_indices)), 1e9)
                for track_index, track in enumerate(tracks):
                    for local_index, candidate_row_index in enumerate(frame_indices):
                        candidate = frame.loc[candidate_row_index]
                        distance = abs(
                            float(candidate["x_root_fraction"]) - track.x_fraction
                        )
                        if distance > config.maximum_track_distance_fraction:
                            continue
                        proposed_root_y = track.root_y + config.position_gain * (
                            float(candidate["y_root"]) - track.root_y
                        )
                        measurement = _measurement_for_candidate(
                            candidate, proposed_root_y, calibration, config
                        )
                        proposed_measurements[(track_index, local_index)] = measurement
                        log_score = math.log(max(float(candidate["confidence"]), 1e-12))
                        log_score -= 0.5 * (distance / config.position_sd_fraction) ** 2
                        if (
                            track.height_filter is not None
                            and measurement["measurement_qc"] == "pass"
                        ):
                            log_score += track.height_filter.candidate_log_score(
                                float(measurement["measurement_cm"]),
                                float(measurement["measurement_sd_cm"]),
                            )
                        cost[track_index, local_index] = -log_score
                track_indices, local_indices = linear_sum_assignment(cost)
                assignments = {
                    int(track_index): int(local_index)
                    for track_index, local_index in zip(track_indices, local_indices)
                    if cost[track_index, local_index] < 1e8
                }

            for track_index, track in enumerate(tracks):
                if track_index not in assignments:
                    rows.append(
                        _result_row(
                            image_record,
                            track,
                            None,
                            None,
                            False,
                            "prediction_only_no_matched_detection"
                            if track.height_filter is not None
                            else "waiting_for_first_measurement",
                        )
                    )
                    continue
                local_index = assignments[track_index]
                candidate_row_index = list(frame.index)[local_index]
                candidate = frame.loc[candidate_row_index]
                track.x_fraction += config.position_gain * (
                    float(candidate["x_root_fraction"]) - track.x_fraction
                )
                track.root_y += config.position_gain * (
                    float(candidate["y_root"]) - track.root_y
                )
                measurement = proposed_measurements[(track_index, local_index)]
                used = measurement["measurement_qc"] == "pass"
                if used and track.height_filter is None:
                    track.height_filter = RobustHeightFilter(config, track.plant_uid)
                    track.height_filter.initialize(
                        float(measurement["measurement_cm"]),
                        float(measurement["measurement_sd_cm"]),
                        when,
                    )
                elif used:
                    track.height_filter.update(
                        float(measurement["measurement_cm"]),
                        float(measurement["measurement_sd_cm"]),
                    )
                candidate_work.at[candidate_row_index, "selected"] = True
                candidate_work.at[candidate_row_index, "selected_plant_uid"] = (
                    track.plant_uid
                )
                if used:
                    status = "measured"
                elif track.height_filter is not None:
                    status = "prediction_only_measurement_failed_qc"
                else:
                    status = "calibration_unavailable"
                rows.append(
                    _result_row(
                        image_record,
                        track,
                        candidate,
                        measurement,
                        used,
                        status,
                    )
                )

        if tracks is None:
            warnings.append(
                f"{camera_id}: no image contained {config.expected_plants} distinct "
                "plant detections, so tracking could not start."
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["camera_id", "plant_number", "capture_datetime", "filename"],
            kind="mergesort",
        ).reset_index(drop=True)
    return result, candidate_work, warnings


def _result_row(
    image_record: object,
    track: _Track,
    candidate: pd.Series | None,
    measurement: Mapping[str, object] | None,
    measurement_used: bool,
    status: str,
) -> dict[str, object]:
    summary = (
        track.height_filter.summary()
        if track.height_filter is not None
        else _empty_filter_summary()
    )
    height_filter = track.height_filter
    return {
        "camera_id": image_record.camera_id,
        "plant_number": track.plant_number,
        "plant_id": f"P{track.plant_number}",
        "plant_uid": track.plant_uid,
        "capture_datetime": pd.Timestamp(image_record.capture_datetime),
        "date": pd.Timestamp(image_record.capture_datetime).date().isoformat(),
        "filename": image_record.filename,
        "status": status,
        "measurement_used": bool(measurement_used),
        "image_measurement_cm": (
            float(measurement["measurement_cm"])
            if measurement is not None and np.isfinite(measurement["measurement_cm"])
            else np.nan
        ),
        "measurement_sd_cm": (
            float(measurement["measurement_sd_cm"])
            if measurement is not None and np.isfinite(measurement["measurement_sd_cm"])
            else np.nan
        ),
        "measurement_qc": (
            measurement["measurement_qc"] if measurement is not None else "no_detection"
        ),
        **summary,
        "predictive_mean_before_image_cm": (
            height_filter.last_predictive_mean if height_filter is not None else np.nan
        ),
        "predictive_sd_before_image_cm": (
            height_filter.last_predictive_sd if height_filter is not None else np.nan
        ),
        "outlier_posterior_probability": (
            height_filter.last_outlier_probability
            if height_filter is not None
            else np.nan
        ),
        "effective_sample_size": (
            height_filter.last_effective_sample_size
            if height_filter is not None
            else np.nan
        ),
        "detection_confidence": (
            float(candidate["confidence"]) if candidate is not None else np.nan
        ),
        "candidate_index": (
            int(candidate["candidate_index"]) if candidate is not None else pd.NA
        ),
        "x_top_px": float(candidate["x_top"]) if candidate is not None else np.nan,
        "y_top_px": float(candidate["y_top"]) if candidate is not None else np.nan,
        "x_root_px": float(candidate["x_root"]) if candidate is not None else np.nan,
        "raw_y_root_px": float(candidate["y_root"])
        if candidate is not None
        else np.nan,
        "prior_updated_y_root_px": track.root_y if candidate is not None else np.nan,
        "calibration_reference_image": (
            measurement["calibration_reference_image"]
            if measurement is not None
            else pd.NA
        ),
        "vertical_extrapolation_band_units": (
            measurement["vertical_extrapolation_band_units"]
            if measurement is not None
            else np.nan
        ),
    }


def _empty_filter_summary() -> dict[str, float]:
    return {
        "bayesian_height_cm": np.nan,
        "height_95_low_cm": np.nan,
        "height_80_low_cm": np.nan,
        "height_median_cm": np.nan,
        "height_80_high_cm": np.nan,
        "height_95_high_cm": np.nan,
        "posterior_sd_cm": np.nan,
        "growth_cm_day": np.nan,
        "growth_sd_cm_day": np.nan,
    }


def _image_summary(
    metadata: pd.DataFrame,
    candidates: pd.DataFrame,
    estimates: pd.DataFrame,
    calibrations: pd.DataFrame,
    config: AnalysisConfig,
) -> pd.DataFrame:
    rows = []
    for record in metadata.itertuples(index=False):
        frame_candidates = candidates[candidates["filename"].eq(record.filename)]
        frame_estimates = (
            estimates[estimates["filename"].eq(record.filename)]
            if not estimates.empty
            else estimates
        )
        calibration_row = (
            calibrations[calibrations["filename"].eq(record.filename)]
            if not calibrations.empty
            else calibrations
        )
        rows.append(
            {
                "camera_id": record.camera_id,
                "capture_datetime": record.capture_datetime,
                "date": pd.Timestamp(record.capture_datetime).date().isoformat(),
                "filename": record.filename,
                "plant_candidates": len(frame_candidates),
                "assigned_tracks": int(
                    frame_candidates["selected"].fillna(False).sum()
                ),
                "measurements_used": int(
                    frame_estimates["measurement_used"].sum()
                    if not frame_estimates.empty
                    else 0
                ),
                "prediction_only": int(
                    (~frame_estimates["measurement_used"]).sum()
                    if not frame_estimates.empty
                    else 0
                ),
                "red_bands_detected": int(
                    calibration_row["n_landmarks"].iloc[0]
                    if not calibration_row.empty
                    else 0
                ),
                "pole_calibration_pass": bool(
                    calibration_row["pole_fit_pass"].iloc[0]
                    if not calibration_row.empty
                    else config.calibration_mode != "red_band"
                ),
            }
        )
    return pd.DataFrame(rows)


def _annotate_images(
    metadata: pd.DataFrame,
    candidates: pd.DataFrame,
    estimates: pd.DataFrame,
    calibration_points: Mapping[str, list[dict[str, float]]],
) -> dict[str, bytes]:
    colors = [
        (33, 102, 172),
        (178, 24, 43),
        (35, 139, 69),
        (117, 107, 177),
        (230, 85, 13),
        (0, 140, 140),
        (166, 54, 3),
        (106, 61, 154),
    ]
    font = _load_font(18)
    small_font = _load_font(14)
    outputs: dict[str, bytes] = {}
    for record in metadata.itertuples(index=False):
        with Image.open(record.image_path) as source:
            image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        for point in calibration_points.get(record.filename, []):
            x, y = float(point["x"]), float(point["y"])
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(255, 215, 0), width=3)
        selected = candidates[
            candidates["filename"].eq(record.filename)
            & candidates["selected"].fillna(False)
        ]
        frame_estimates = (
            estimates[estimates["filename"].eq(record.filename)]
            if not estimates.empty
            else estimates
        )
        for candidate in selected.itertuples(index=False):
            match = frame_estimates[
                frame_estimates["plant_uid"].eq(str(candidate.selected_plant_uid))
            ]
            if match.empty:
                continue
            result = match.iloc[0]
            plant_number = int(str(result["plant_id"])[1:])
            color = colors[(plant_number - 1) % len(colors)]
            draw.rectangle(
                (
                    candidate.box_x1,
                    candidate.box_y1,
                    candidate.box_x2,
                    candidate.box_y2,
                ),
                outline=color,
                width=3,
            )
            root_y = float(result["prior_updated_y_root_px"])
            draw.line(
                (candidate.x_top, candidate.y_top, candidate.x_root, root_y),
                fill=color,
                width=4,
            )
            radius = 5
            draw.ellipse(
                (
                    candidate.x_top - radius,
                    candidate.y_top - radius,
                    candidate.x_top + radius,
                    candidate.y_top + radius,
                ),
                fill=(220, 35, 35),
            )
            draw.ellipse(
                (
                    candidate.x_root - radius,
                    root_y - radius,
                    candidate.x_root + radius,
                    root_y + radius,
                ),
                fill=(30, 110, 220),
            )
            height = result["bayesian_height_cm"]
            label = result["plant_id"]
            if pd.notna(height):
                label += f"  {float(height):.1f} cm"
            else:
                label += "  no calibrated height"
            text_x = max(2, int(candidate.box_x1))
            text_y = max(2, int(candidate.box_y1) - 24)
            box = draw.textbbox((text_x, text_y), label, font=font)
            draw.rectangle(box, fill=(255, 255, 255))
            draw.text((text_x, text_y), label, fill=color, font=font)
        banner = (
            f"{record.camera_id} | {pd.Timestamp(record.capture_datetime):%Y-%m-%d %H:%M} | "
            f"{len(selected)} assigned"
        )
        banner_box = draw.textbbox((8, 8), banner, font=small_font)
        draw.rectangle(
            (
                banner_box[0] - 4,
                banner_box[1] - 3,
                banner_box[2] + 4,
                banner_box[3] + 3,
            ),
            fill=(255, 255, 255),
        )
        draw.text((8, 8), banner, fill=(20, 20, 20), font=small_font)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=92)
        outputs[f"{Path(record.filename).stem}_annotated.jpg"] = buffer.getvalue()
    return outputs


def analyze_images(
    image_paths: Mapping[str, Path],
    metadata: pd.DataFrame,
    model_path: Path,
    config: AnalysisConfig,
    model: object | None = None,
    progress: Callable[[str, int, int, str], None] | None = None,
) -> AnalysisArtifacts:
    config.validate()
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Pose model not found: {model_path}")
    clean_metadata = validate_metadata(metadata, image_paths)
    candidates = run_pose_inference(
        clean_metadata, model_path, config, model=model, progress=progress
    )
    if config.calibration_mode == "red_band":
        calibrations, calibration_points = detect_red_band_calibrations(
            clean_metadata, config, progress=progress
        )
    else:
        calibrations = pd.DataFrame()
        calibration_points = {}
    estimates, candidates, warnings = analyze_candidate_table(
        clean_metadata, candidates, calibrations, config
    )
    image_summary = _image_summary(
        clean_metadata, candidates, estimates, calibrations, config
    )
    annotated = _annotate_images(
        clean_metadata, candidates, estimates, calibration_points
    )
    try:
        import torch
        import ultralytics

        dependency_versions = {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "ultralytics": ultralytics.__version__,
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        }
    except ImportError:
        dependency_versions = {"python": platform.python_version()}
    run_metadata = {
        "application": "Bayesian Longitudinal Plant Height",
        "application_version": APP_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "method": (
            "causal prior-guided plant association and candidate scoring, physical "
            "calibration, and robust Bayesian height-growth particle filtering"
        ),
        "future_images_used": False,
        "height_definition": "model top keypoint to prior-updated root keypoint",
        "measurement_uncertainty_model": (
            "12-cm base pose SD divided by the square root of detector confidence, "
            "with pole-fit, extrapolation, and band-regularity terms when applicable"
        ),
        "plant_numbering": config.numbering_direction,
        "model_file": model_path.name,
        "model_sha256": _file_sha256(model_path),
        "config": asdict(config),
        "software": dependency_versions,
        "images": clean_metadata[
            ["filename", "camera_id", "capture_datetime", "image_sha256"]
        ]
        .assign(
            capture_datetime=lambda data: data["capture_datetime"].map(
                lambda value: pd.Timestamp(value).isoformat()
            )
        )
        .to_dict(orient="records"),
        "warnings": warnings,
    }
    return AnalysisArtifacts(
        height_estimates=estimates,
        image_summary=image_summary,
        candidates=candidates,
        calibrations=calibrations,
        annotated_images=annotated,
        run_metadata=run_metadata,
        warnings=warnings,
    )


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    export = frame.copy()
    for column in export.columns:
        if pd.api.types.is_datetime64_any_dtype(export[column]):
            export[column] = export[column].map(
                lambda value: pd.Timestamp(value).isoformat()
            )
    return export.to_csv(index=False).encode("utf-8")


def package_results(artifacts: AnalysisArtifacts) -> bytes:
    """Create the scientist-facing result bundle without copying source images."""

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("height_estimates.csv", _csv_bytes(artifacts.height_estimates))
        archive.writestr(
            "image_quality_summary.csv", _csv_bytes(artifacts.image_summary)
        )
        archive.writestr("all_pose_candidates.csv", _csv_bytes(artifacts.candidates))
        if not artifacts.calibrations.empty:
            archive.writestr(
                "red_band_calibrations.csv", _csv_bytes(artifacts.calibrations)
            )
        archive.writestr(
            "run_metadata.json",
            json.dumps(artifacts.run_metadata, indent=2, default=str).encode("utf-8"),
        )
        archive.writestr(
            "README_RESULTS.txt",
            (
                "Use bayesian_height_cm as the estimated plant height. The 80% and 95% "
                "columns report posterior uncertainty. measurement_used indicates whether "
                "that image contributed a detected, calibrated measurement; prediction-only "
                "rows use preceding images. Review the annotated images and QC columns before "
                "biological analysis. No estimate at a date uses a later image.\n"
            ),
        )
        for name, payload in artifacts.annotated_images.items():
            archive.writestr(f"annotated_images/{name}", payload)
    return buffer.getvalue()


def write_artifacts(artifacts: AnalysisArtifacts, output_directory: Path) -> None:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    artifacts.height_estimates.to_csv(
        output_directory / "height_estimates.csv", index=False
    )
    artifacts.image_summary.to_csv(
        output_directory / "image_quality_summary.csv", index=False
    )
    artifacts.candidates.to_csv(
        output_directory / "all_pose_candidates.csv", index=False
    )
    if not artifacts.calibrations.empty:
        artifacts.calibrations.to_csv(
            output_directory / "red_band_calibrations.csv", index=False
        )
    (output_directory / "run_metadata.json").write_text(
        json.dumps(artifacts.run_metadata, indent=2, default=str), encoding="utf-8"
    )
    annotated_directory = output_directory / "annotated_images"
    annotated_directory.mkdir(exist_ok=True)
    for name, payload in artifacts.annotated_images.items():
        (annotated_directory / name).write_bytes(payload)
