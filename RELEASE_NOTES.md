# Plant-scientist application release v1.3.0

This repository release adds Bayesian Plant Height application v1.0.0, a complete
local browser application for turning dated, fixed-camera maize images into
longitudinal plant-height estimates.

## Image-to-height application

- Added a Streamlit interface that accepts multiple images, infers dates from
  filenames or EXIF metadata, and provides an editable date/camera table.
- Added one-click Windows startup plus macOS/Linux startup scripts. The first run
  creates an isolated environment; subsequent runs reuse it.
- Retained the released YOLOv8-pose checkpoint for top/root detection and the exact
  robust particle-filter state update used by the reproducibility analysis.
- Added prior-guided candidate assignment: the running plant-position state and
  predicted height distribution score current-image candidates before measurement.
- Added three physical-calibration routes: the published 2021 scale, a user-supplied
  centimetres-per-pixel scale, and automatic regularly spaced red-band detection with
  a pole-to-plant depth correction.
- Added stable within-camera plant IDs, prior-updated root positions, explicit quality
  flags, and prediction-only output when a plant is missed after its track is initialized.
- Added downloadable CSV output, 80% and 95% posterior intervals, growth-rate estimates,
  annotated images, calibration diagnostics, model/input hashes, settings, and software
  versions in one result ZIP.
- Added a command-line batch interface using the same analysis engine.

## Validation

- Seven focused tests cover date parsing, physical calibration, height-prior candidate
  selection, prediction-only behavior, exact agreement with the released particle-filter
  implementation, and prefix causality when future images are appended.
- A full image-to-height run on five released C-004 dates detected six tracks and emitted
  30 plant-image rows. Twenty-nine rows used current-image measurements and the one missed
  detection correctly produced a prediction-only row.
- The browser application loads without exceptions and exposes both image and date-table
  upload controls.
- Python compilation and Ruff source checks pass.

## Manuscript package

The journal-ready *The Plant Phenome Journal* manuscript, supplement, submission files,
analysis code, curated images, annotations, derived data, and model provenance from v1.2.1
remain included unchanged.

## Scope and rights

The pose checkpoint is intended for field maize imagery resembling the released data.
Annotated-image review remains part of the application workflow. The MIT License applies
to repository code; the model card records the Ultralytics dependency and the available
checkpoint provenance.
