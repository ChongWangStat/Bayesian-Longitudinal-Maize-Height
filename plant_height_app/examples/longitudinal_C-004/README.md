# Included longitudinal example

This example uses five released images from stationary camera row C-004 on 2 July,
11 July, 18 July, 30 July, and 6 August 2021. The source images are in
`data/raw/pole_calibration_images/` and are loaded automatically by the app.

Select **Try the included longitudinal example**, retain the **Published 2021
fixed-camera setup** calibration and six visible plants, then click **Run
plant-height analysis**. The results include a row for each plant and image day,
an interactive height trajectory, a downloadable height-versus-day PNG, annotated
images, and CSV files.

The original dates are intentionally irregular. The validation suite also replays
the same image sequences at daily, three-day, and seven-day intervals to check the
time-update logic. Those replay dates test software behavior and do not replace the
images' true acquisition dates.
