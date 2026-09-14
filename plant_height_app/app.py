"""Streamlit interface for image-to-height analysis."""

from __future__ import annotations

import tempfile
import zipfile
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from .engine import (
        APP_VERSION,
        AnalysisConfig,
        analyze_images,
        default_metadata,
        package_results,
    )
except ImportError:
    from engine import (  # type: ignore[no-redef]
        APP_VERSION,
        AnalysisConfig,
        analyze_images,
        default_metadata,
        package_results,
    )


ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "maize_pose_2021_best.pt"
EXAMPLE_IMAGE_DIRECTORY = ROOT / "data" / "raw" / "pole_calibration_images"
EXAMPLE_DIRECTORY = Path(__file__).resolve().parent / "examples"
EXAMPLES = {
    "C-024 · clean four-date series": {
        "camera_id": "C-024",
        "expected_plants": 4,
        "filenames": [
            "C-024_2021-07-02.JPG",
            "C-024_2021-07-11.JPG",
            "C-024_2021-07-18.JPG",
            "C-024_2021-07-30.JPG",
        ],
        "metadata": EXAMPLE_DIRECTORY / "longitudinal_C-024" / "image_dates.csv",
        "description": "four dates, four plants, and all 16 image measurements used",
    },
    "C-004 · five-date missed-detection recovery": {
        "camera_id": "C-004",
        "expected_plants": 6,
        "filenames": [
            "C-004_2021-07-02.JPG",
            "C-004_2021-07-11.JPG",
            "C-004_2021-07-18.JPG",
            "C-004_2021-07-30.JPG",
            "C-004_2021-08-06.JPG",
        ],
        "metadata": EXAMPLE_DIRECTORY / "longitudinal_C-004" / "image_dates.csv",
        "description": "five dates, six plants, and one prediction-only recovery",
    },
}


class _MemoryUpload:
    """Small UploadedFile-compatible wrapper for the included example."""

    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


def _included_example(
    example_name: str,
) -> tuple[list[_MemoryUpload], _MemoryUpload, bytes]:
    definition = EXAMPLES[example_name]
    filenames = list(definition["filenames"])
    metadata_path = Path(definition["metadata"])
    missing = [
        name for name in filenames if not (EXAMPLE_IMAGE_DIRECTORY / name).is_file()
    ]
    if missing or not metadata_path.is_file():
        raise FileNotFoundError(
            "The included example is incomplete: "
            + ", ".join(missing or [str(metadata_path)])
        )
    images = [
        _MemoryUpload(name, (EXAMPLE_IMAGE_DIRECTORY / name).read_bytes())
        for name in filenames
    ]
    metadata_bytes = metadata_path.read_bytes()
    metadata_upload = _MemoryUpload(metadata_path.name, metadata_bytes)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("image_dates.csv", metadata_bytes)
        for upload in images:
            archive.writestr(f"images/{upload.name}", upload.getvalue())
    return images, metadata_upload, buffer.getvalue()


st.set_page_config(
    page_title="Bayesian Plant Height",
    page_icon="🌽",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
      .block-container {max-width: 1220px; padding-top: 2rem;}
      .hero {padding: 1.25rem 1.5rem; border-radius: 16px;
             background: linear-gradient(120deg,#173d2c,#296347); color: white;
             margin-bottom: 1.2rem;}
      .hero h1 {margin:0; font-size:2.05rem; color:white;}
      .hero p {margin:.45rem 0 0; color:#e7f3eb; font-size:1.03rem;}
      .step {font-weight:700; color:#173d2c; margin-top:.3rem;}
      div[data-testid="stMetric"] {background:#f4f8f4; border:1px solid #d8e6dc;
                                  border-radius:12px; padding:.6rem 1rem;}
    </style>
    <div class="hero">
      <h1>Bayesian longitudinal plant height</h1>
      <p>Upload fixed-camera maize images, confirm their dates, and download plant-level height estimates with uncertainty.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def load_model(model_path: str):
    from ultralytics import YOLO

    return YOLO(model_path)


def _normalize_date_upload(uploaded_file, base: pd.DataFrame) -> pd.DataFrame:
    if uploaded_file is None:
        return base
    supplied = pd.read_csv(BytesIO(uploaded_file.getvalue()))
    aliases = {
        "image": "filename",
        "file": "filename",
        "date": "capture_datetime",
        "datetime": "capture_datetime",
        "camera": "camera_id",
        "plot": "camera_id",
    }
    supplied = supplied.rename(
        columns={
            column: aliases.get(column.strip().lower(), column)
            for column in supplied.columns
        }
    )
    needed = {"filename", "capture_datetime"}
    if not needed.issubset(supplied.columns):
        raise ValueError("The date CSV needs filename and capture_datetime columns.")
    if "camera_id" not in supplied:
        supplied["camera_id"] = "camera_1"
    supplied = supplied[["filename", "capture_datetime", "camera_id"]].copy()
    supplied["filename"] = supplied["filename"].map(lambda value: Path(str(value)).name)
    merged = base[["filename"]].merge(supplied, on="filename", how="left")
    merged["camera_id"] = merged["camera_id"].fillna("camera_1")
    merged["capture_datetime"] = merged["capture_datetime"].fillna("")
    return merged


def _display_results(payload: dict[str, object]) -> None:
    artifacts = payload["artifacts"]
    estimates = artifacts.height_estimates
    st.divider()
    st.subheader("Results")
    if artifacts.warnings:
        for warning in artifacts.warnings:
            st.warning(warning)
    if estimates.empty:
        st.error(
            "No plant tracks were initialized. Check the annotated images, then lower "
            "the expected plant count or confirm that an early image shows every plant."
        )
        st.download_button(
            "Download diagnostic package",
            payload["result_zip"],
            file_name="plant_height_results.zip",
            mime="application/zip",
        )
        return

    columns = st.columns(4)
    columns[0].metric("Images", int(artifacts.image_summary.shape[0]))
    columns[1].metric("Tracked plants", int(estimates["plant_uid"].nunique()))
    columns[2].metric("Measured rows", int(estimates["measurement_used"].sum()))
    columns[3].metric(
        "Prediction-only rows", int((~estimates["measurement_used"]).sum())
    )

    selected_camera = str(estimates["camera_id"].iloc[0])
    chart_data = estimates.dropna(subset=["bayesian_height_cm"]).copy()
    if not chart_data.empty:
        chart_left, chart_right = st.columns([2, 3])
        camera_ids = sorted(chart_data["camera_id"].astype(str).unique())
        selected_camera = chart_left.selectbox(
            "Camera or plot shown",
            camera_ids,
            key="result_chart_camera",
        )
        time_axis = chart_right.radio(
            "Horizontal axis",
            ["Days after first image", "Calendar date"],
            horizontal=True,
            key="result_chart_axis",
        )
        chart_data = chart_data[chart_data["camera_id"].astype(str).eq(selected_camera)]
        chart_data["series"] = chart_data["plant_id"]
        x_column = (
            "days_after_first_image"
            if time_axis == "Days after first image"
            else "capture_datetime"
        )
        chart = chart_data.pivot_table(
            index=x_column,
            columns="series",
            values="bayesian_height_cm",
            aggfunc="last",
        )
        st.line_chart(
            chart,
            height=390,
            x_label=(
                "Days after first image (day 0 = first uploaded image)"
                if time_axis == "Days after first image"
                else "Image date"
            ),
            y_label="Height (cm)",
        )
        st.caption(
            "The downloadable PNG adds the 95% uncertainty bands and marks the "
            "current-image measurements with × symbols."
        )

    display_columns = [
        "camera_id",
        "plant_id",
        "date",
        "days_after_first_image",
        "bayesian_height_cm",
        "height_95_low_cm",
        "height_95_high_cm",
        "image_measurement_cm",
        "growth_cm_day",
        "status",
        "filename",
    ]
    display = estimates[display_columns].copy()
    numeric = display.select_dtypes(include="number").columns
    display[numeric] = display[numeric].round(2)
    st.dataframe(display, width="stretch", hide_index=True)

    left, middle, right = st.columns(3)
    left.download_button(
        "Download height table (CSV)",
        estimates.to_csv(index=False).encode("utf-8"),
        file_name="height_estimates.csv",
        mime="text/csv",
        width="stretch",
    )
    safe_camera = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in selected_camera
    ).strip("._")
    plot_name = f"{safe_camera or 'camera'}_height_by_day.png"
    if plot_name in artifacts.trajectory_plots:
        middle.download_button(
            "Download height-versus-day plot (PNG)",
            artifacts.trajectory_plots[plot_name],
            file_name=plot_name,
            mime="image/png",
            width="stretch",
        )
    right.download_button(
        "Download complete results and annotated images (ZIP)",
        payload["result_zip"],
        file_name="plant_height_results.zip",
        mime="application/zip",
        width="stretch",
    )

    st.subheader("Image review")
    annotated_names = list(artifacts.annotated_images)
    selected_image = st.selectbox("Annotated image", annotated_names)
    st.image(
        artifacts.annotated_images[selected_image],
        caption="Red point: detected top. Blue point: prior-updated root. Yellow points: detected pole bands.",
        width="stretch",
    )
    with st.expander("Quality-control details"):
        st.dataframe(artifacts.image_summary, width="stretch", hide_index=True)
        if not artifacts.calibrations.empty:
            st.markdown("**Automatic red-band calibration fits**")
            st.dataframe(artifacts.calibrations, width="stretch", hide_index=True)


analyze_tab, guide_tab = st.tabs(["Analyze images", "How to use the app"])

with guide_tab:
    st.subheader("What to prepare")
    st.markdown(
        """
        1. Use images from a **stationary camera**. Give images from different cameras different camera IDs.
        2. For a new study, prefer **one image per camera per day**, taken at a similar time. Wider and irregular intervals are accepted.
        3. Include at least one early image in which all tracked plants are visible.
        4. Put the capture date in each filename (`YYYY-MM-DD`) or enter it in the table.
        5. Enter the number of visible plants separately for each camera or plot.
        6. Choose the correct physical calibration:
           - **Published 2021 setup** for the camera geometry used in the paper.
           - **Known scale** when you already know centimetres per vertical pixel.
           - **Automatic red-band pole** when the images contain the 1-ft-style reference pole.
        7. Inspect the annotated images before using the downloaded values in a biological analysis.

        Select **Try the included longitudinal example** to run either a clean C-024
        sequence or a harder C-004 sequence without preparing any files.
        """
    )
    st.subheader("What the output means")
    st.markdown(
        """
        `bayesian_height_cm` is the main estimate. `days_after_first_image` starts at
        day 0 separately for each camera and supplies the horizontal axis of the exported
        trajectory plot. The 80% and 95% columns describe posterior uncertainty. A
        `measured` row used that image's detected and calibrated plant extent. A
        `prediction_only` row reports the as-of model estimate when a usable detection was
        unavailable. No estimate uses an image dated later than the row.

        Plant IDs describe horizontal position in each camera view. They are stable only
        while the camera remains fixed and the same plants remain in view. The model was
        developed for field maize images resembling the released data; lighting, occlusion,
        tassels, unusual camera angles, and changed optics can affect performance.
        """
    )
    st.caption(f"Application version {APP_VERSION}")

with analyze_tab:
    st.markdown(
        '<div class="step">1 · Upload images and dates</div>', unsafe_allow_html=True
    )
    input_source = st.radio(
        "Choose input",
        ["Upload my images", "Try the included longitudinal example"],
        horizontal=True,
    )
    example_expected_plants: dict[str, int] = {}
    if input_source == "Try the included longitudinal example":
        example_name = st.selectbox("Included example", list(EXAMPLES))
        example_definition = EXAMPLES[example_name]
        try:
            uploads, dates_upload, example_zip = _included_example(example_name)
            example_camera = str(example_definition["camera_id"])
            example_expected_plants[example_camera] = int(
                example_definition["expected_plants"]
            )
            st.success(
                f"Loaded {example_name}: {example_definition['description']}. "
                "Keep the published 2021 calibration for this example."
            )
            st.download_button(
                "Download the example images and date table",
                example_zip,
                file_name=f"{example_camera}_longitudinal_example_inputs.zip",
                mime="application/zip",
            )
        except FileNotFoundError as error:
            st.error(str(error))
            uploads = []
            dates_upload = None
    else:
        uploads = st.file_uploader(
            "Images",
            type=["jpg", "jpeg", "png", "bmp", "tif", "tiff"],
            accept_multiple_files=True,
            help="Upload one or more dated images from each fixed camera.",
        )
        dates_upload = st.file_uploader(
            "Optional date table (CSV)",
            type=["csv"],
            help="Columns: filename, capture_datetime, camera_id. Dates in filenames are filled automatically.",
        )

    if uploads:
        names = [Path(upload.name).name for upload in uploads]
        if len(names) != len(set(names)):
            st.error("Uploaded image filenames must be unique.")
        else:
            image_payload = {
                name: upload.getvalue() for name, upload in zip(names, uploads)
            }
            upload_signature = sha256(
                b"|".join(
                    name.encode("utf-8") + b":" + sha256(image_payload[name]).digest()
                    for name in sorted(names)
                )
            ).hexdigest()
            base = default_metadata(names, image_payload)
            try:
                metadata_default = _normalize_date_upload(dates_upload, base)
            except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as error:
                st.error(str(error))
                metadata_default = base
            st.caption(
                "Confirm every date and use one camera ID for each unchanged camera view."
            )
            edited_metadata = st.data_editor(
                metadata_default,
                hide_index=True,
                width="stretch",
                num_rows="fixed",
                disabled=["filename"],
                column_config={
                    "filename": st.column_config.TextColumn("Image"),
                    "capture_datetime": st.column_config.TextColumn(
                        "Capture date/time",
                        help="Examples: 2026-07-18 or 2026-07-18 11:45",
                    ),
                    "camera_id": st.column_config.TextColumn(
                        "Camera or plot ID",
                        help="Use the same value for the same fixed view.",
                    ),
                },
                key=(
                    "metadata_editor_"
                    + sha256(
                        (
                            upload_signature
                            + (
                                sha256(dates_upload.getvalue()).hexdigest()
                                if dates_upload is not None
                                else ""
                            )
                        ).encode("utf-8")
                    ).hexdigest()[:12]
                ),
            )

            st.markdown(
                '<div class="step">2 · Choose physical calibration</div>',
                unsafe_allow_html=True,
            )
            calibration_label = st.selectbox(
                "Calibration",
                [
                    "Published 2021 fixed-camera setup",
                    "Known centimetres per pixel",
                    "Automatic red-band pole",
                ],
            )
            if calibration_label == "Published 2021 fixed-camera setup":
                calibration_mode = "published_2021"
                cm_per_pixel = 0.415886
                depth_factor = 1.0
                band_interval = 30.48
                st.info(
                    "Uses 0.415886 cm per vertical pixel, derived from the camera geometry "
                    "documented for the 2021 validation images."
                )
            elif calibration_label == "Known centimetres per pixel":
                calibration_mode = "known_scale"
                cm_per_pixel = st.number_input(
                    "Vertical scale (cm per pixel)",
                    min_value=0.000001,
                    value=0.415886,
                    format="%.6f",
                )
                depth_factor = 1.0
                band_interval = 30.48
            else:
                calibration_mode = "red_band"
                cm_per_pixel = 0.415886
                c1, c2 = st.columns(2)
                band_interval = c1.number_input(
                    "Distance between adjacent bands (cm)",
                    min_value=1.0,
                    value=30.48,
                    step=0.01,
                )
                depth_factor = c2.number_input(
                    "Pole-to-plant depth factor",
                    min_value=0.01,
                    value=0.85,
                    step=0.01,
                    help="Camera-to-plant distance divided by camera-to-pole distance.",
                )
                st.info(
                    "A passing pole calibration must be visible at or before the first height "
                    "measurement. Later pole images are never used for earlier estimates."
                )
                st.warning(
                    "Automatic band detection is intentionally conservative. If the QC table "
                    "reports no passing fit, use a clear pole image or an independently known "
                    "centimetres-per-pixel scale."
                )

            st.markdown(
                '<div class="step">3 · Set the plant layout</div>',
                unsafe_allow_html=True,
            )
            camera_ids = sorted(
                edited_metadata["camera_id"].astype(str).str.strip().unique()
            )
            camera_layout = st.data_editor(
                pd.DataFrame(
                    {
                        "camera_id": camera_ids,
                        "expected_plants": [
                            example_expected_plants.get(camera_id, 6)
                            for camera_id in camera_ids
                        ],
                    }
                ),
                hide_index=True,
                width="stretch",
                num_rows="fixed",
                disabled=["camera_id"],
                column_config={
                    "camera_id": st.column_config.TextColumn("Camera or plot ID"),
                    "expected_plants": st.column_config.NumberColumn(
                        "Plants visible",
                        min_value=1,
                        max_value=100,
                        step=1,
                        help="Set this separately for each fixed camera view.",
                    ),
                },
                key=(
                    "camera_layout_"
                    + sha256(
                        (upload_signature + "|".join(camera_ids)).encode("utf-8")
                    ).hexdigest()[:12]
                ),
            )
            layout_counts = pd.to_numeric(
                camera_layout["expected_plants"], errors="coerce"
            ).fillna(6)
            expected_plants_by_camera = dict(
                zip(camera_layout["camera_id"].astype(str), layout_counts.astype(int))
            )
            numbering_label = st.radio(
                "Plant numbering",
                ["Left to right", "Right to left"],
                horizontal=True,
            )

            with st.expander("Advanced analysis settings"):
                advanced_left, advanced_middle, advanced_right = st.columns(3)
                particles = advanced_left.number_input(
                    "Particle count",
                    min_value=500,
                    max_value=20000,
                    value=5000,
                    step=500,
                )
                maximum_track_distance = advanced_middle.number_input(
                    "Maximum tracking distance (image fraction)",
                    min_value=0.01,
                    max_value=0.50,
                    value=0.16,
                    step=0.01,
                )
                position_gain = advanced_right.number_input(
                    "Position update gain",
                    min_value=0.05,
                    max_value=1.0,
                    value=0.50,
                    step=0.05,
                )
                st.caption(
                    "The defaults reproduce the released plant-association and robust-filter settings."
                )

            current_signature = sha256(
                (
                    upload_signature
                    + edited_metadata.to_csv(index=False)
                    + "|".join(
                        map(
                            str,
                            [
                                calibration_mode,
                                cm_per_pixel,
                                band_interval,
                                depth_factor,
                                sorted(expected_plants_by_camera.items()),
                                numbering_label,
                                particles,
                                maximum_track_distance,
                                position_gain,
                            ],
                        )
                    )
                ).encode("utf-8")
            ).hexdigest()
            if st.session_state.get("input_signature") not in {None, current_signature}:
                st.session_state.pop("analysis_payload", None)
            st.session_state["input_signature"] = current_signature

            run = st.button(
                "Run plant-height analysis",
                type="primary",
                width="stretch",
            )
            if run:
                if not MODEL_PATH.exists():
                    st.error(f"The released model file is missing: {MODEL_PATH}")
                else:
                    config = AnalysisConfig(
                        calibration_mode=calibration_mode,
                        cm_per_pixel=float(cm_per_pixel),
                        red_band_interval_cm=float(band_interval),
                        pole_to_plant_depth_factor=float(depth_factor),
                        expected_plants=6,
                        expected_plants_by_camera=expected_plants_by_camera,
                        numbering_direction=(
                            "left_to_right"
                            if numbering_label == "Left to right"
                            else "right_to_left"
                        ),
                        particles=int(particles),
                        maximum_track_distance_fraction=float(maximum_track_distance),
                        position_gain=float(position_gain),
                    )
                    progress_bar = st.progress(0, text="Preparing analysis")

                    def update_progress(
                        stage: str, current: int, total: int, message: str
                    ) -> None:
                        stage_offset = 0.0 if stage == "pose" else 0.65
                        stage_width = 0.65 if stage == "pose" else 0.25
                        value = min(
                            0.92, stage_offset + stage_width * current / max(total, 1)
                        )
                        progress_bar.progress(value, text=message)

                    try:
                        with tempfile.TemporaryDirectory(
                            prefix="plant_height_app_"
                        ) as temporary:
                            temporary_path = Path(temporary)
                            image_paths = {}
                            for name, content in image_payload.items():
                                destination = temporary_path / Path(name).name
                                destination.write_bytes(content)
                                image_paths[name] = destination
                            progress_bar.progress(
                                0.02, text="Loading the maize pose model"
                            )
                            pose_model = load_model(str(MODEL_PATH))
                            artifacts = analyze_images(
                                image_paths,
                                edited_metadata,
                                MODEL_PATH,
                                config,
                                model=pose_model,
                                progress=update_progress,
                            )
                        progress_bar.progress(1.0, text="Analysis complete")
                        st.session_state["analysis_payload"] = {
                            "artifacts": artifacts,
                            "result_zip": package_results(artifacts),
                        }
                    except Exception as error:  # noqa: BLE001 - show analysis failures in the UI
                        progress_bar.empty()
                        st.exception(error)

    if "analysis_payload" in st.session_state:
        _display_results(st.session_state["analysis_payload"])
    elif not uploads:
        st.info(
            "Upload at least one image to begin. Dates will be read from filenames when possible."
        )
