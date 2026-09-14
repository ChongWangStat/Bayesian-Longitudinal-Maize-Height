# Examples

The app includes two longitudinal fixed-camera examples:

- `longitudinal_C-024` is the default clean demonstration: four images, four plants,
  16 current-image measurements, and no warnings.
- `longitudinal_C-004` is a harder five-image demonstration: six plants, 29
  current-image measurements, and one prediction-only update after a missed detection.

Each folder contains the date table, expected height table, image-quality summary,
and height-versus-day plot generated with the default 5,000-particle analysis. The
source images remain in `data/raw/pole_calibration_images/` and are copied into the
standalone collaborator package.

`image_dates_template.csv` is a blank-format example for users preparing their own
images. The preferred prospective schedule is one image per camera per day at a
similar time, although the app also accepts irregular intervals.
