# Bayesian Plant Height application

This local browser application converts dated fixed-camera maize images into
plant-level height estimates. It uses the released maize top/root pose model,
feeds earlier position and height states into analysis of the current image,
converts the selected image extent to centimetres, and applies the robust
Bayesian height-growth particle filter from the accompanying manuscript.

## Fastest start on Windows

1. Install 64-bit Python 3.12 or 3.13 from Python.org if it is not already installed.
2. Double-click `START_APP.bat` in this folder.
3. The first start installs the application components and can take several minutes.
4. When the browser opens, upload images, confirm dates and camera IDs, choose the
   calibration, enter the number of plants, and click **Run plant-height analysis**.
5. Inspect the annotated images and download the complete result ZIP.

To test the installation first, select **Try the included longitudinal example**.
Choose the clean four-date C-024 series or the harder five-date C-004 series, which
demonstrates a prediction-only update after one missed detection. The app loads the
released images, their original dates, and the published 2021 calibration. No file
preparation is required.

The application runs locally. Uploaded images are processed on the computer running
the app and are not sent to an external image-analysis service.

On macOS or Linux, run:

```bash
chmod +x plant_height_app/start_app.sh
./plant_height_app/start_app.sh
```

## Inputs

Upload one or more JPG, PNG, BMP, or TIFF images. Images from one `camera_id` must
come from an unchanged fixed-camera view. Images from different cameras or plots
can be analyzed together when their camera IDs differ. The app accepts a different
visible-plant count for every camera.

For a new experiment, the preferred acquisition schedule is **one image per camera
per day**, taken at a similar time. Daily input produces one updated estimate per
plant per day. The model also accepts wider or irregular intervals and scales its
process uncertainty by the elapsed time.

The app recognizes dates such as `2026-07-18` in filenames. Dates can be corrected
in the on-screen table or supplied as a CSV with these columns:

| Column | Meaning |
|---|---|
| `filename` | Exact image filename, including extension |
| `capture_datetime` | Date or date and time, such as `2026-07-18 11:45` |
| `camera_id` | Stable identifier for one unchanged camera view |

An editable example is in `examples/image_dates_template.csv`.

At least one early image per camera must contain the expected number of distinct
plants. That image initializes stable horizontal plant IDs. If tracking cannot
start, inspect the diagnostic images and lower the expected count only when it
matches the actual plants intended for measurement.

## Physical calibration choices

**Published 2021 fixed-camera setup** uses the documented 0.415886 cm per vertical
pixel scale. Select it only for images made with that same camera geometry and image
processing.

**Known centimetres per pixel** accepts a scale established independently for the
current camera setup.

**Automatic red-band pole** detects a vertical reference pole with regularly spaced
red bands. Enter the physical distance between adjacent bands and the depth factor:

```text
depth factor = camera-to-plant distance / camera-to-pole distance
```

The default band interval is 30.48 cm and the default depth factor is 0.85, matching
the study setup. A passing calibration must be available at or before a plant image.
The app never uses a later pole image to calibrate an earlier plant image.

## Outputs

`height_estimates.csv` contains one row per tracked plant at every uploaded image
date after tracking starts. The main fields are:

| Field | Meaning |
|---|---|
| `bayesian_height_cm` | Main plant-height estimate |
| `days_after_first_image` | Elapsed study day, starting at day 0 for each camera |
| `height_80_low_cm`, `height_80_high_cm` | Central 80% posterior interval |
| `height_95_low_cm`, `height_95_high_cm` | Central 95% posterior interval |
| `image_measurement_cm` | Calibrated measurement extracted from the current image |
| `growth_cm_day` | Current posterior mean growth rate |
| `measurement_used` | Whether the current image updated the height filter |
| `status` | Measured, prediction-only, or unresolved reason |

Prediction-only rows use images available before or at that date. Later images do
not revise earlier outputs. The complete ZIP also contains all pose candidates,
calibration diagnostics, annotated images, height-versus-day PNG plots, input hashes,
model hash, settings, and software versions. Each PNG shows the Bayesian trajectory,
95% uncertainty band, and current-image measurements.

Because the click-based workflow does not require weather measurements, its image
uncertainty starts from the released 12-cm pose term and increases it when detector
confidence is low. The automatic-pole route also adds pole-fit, extrapolation, and
band-regularity terms. The exact formula and every setting are recorded in the
downloaded `run_metadata.json`.

## Scripted batch use

The same engine can run without the browser:

```bash
python plant_height_app/cli.py \
  --images path/to/images \
  --metadata path/to/image_dates.csv \
  --output plant_height_results \
  --calibration-mode known_scale \
  --cm-per-pixel 0.415886 \
  --expected-plants 6
```

For multiple cameras with different plant counts, repeat `--camera-plants`, for
example `--camera-plants C-004=6 --camera-plants C-021=4`.

Use `--calibration-mode red_band`, `--red-band-interval-cm`, and
`--pole-to-plant-depth-factor` for the red-band workflow. Run
`python plant_height_app/cli.py --help` for all options.

## Interpretation boundary

The pose checkpoint was developed for field maize imagery resembling the released
data. Changed optics, camera movement, unusual angles, lighting, wind, occlusion,
and tassels can change accuracy. The annotated-image review is part of the workflow;
exclude or reprocess images with visibly incorrect top, root, plant identity, or pole
calibration before downstream biological analysis.

The application code is covered by the repository MIT license. The bundled
Ultralytics software and checkpoint retain the dependency and provenance information
recorded in `models/MODEL_CARD.md` and `models/checkpoint_metadata.json`.
