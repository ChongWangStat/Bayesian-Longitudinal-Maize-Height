# Collaborator-ready plant-height application v1.4.0

This repository release adds Bayesian Plant Height application v1.1.0, prepared for
sharing with plant scientists who want to turn dated fixed-camera maize images into
longitudinal height estimates without writing code.

## Collaborator workflow

- Added two built-in longitudinal examples that run directly in the browser app.
  C-024 is a clean four-date series with 16 of 16 current-image measurements used.
  C-004 is a harder five-date series with 29 measurements and one prediction-only
  recovery after a missed detection.
- Bundled the nine source images, date tables, expected output tables, image-quality
  summaries, and example height-versus-day plots in the standalone package.
- Added `days_after_first_image` to every height row, starting at day 0 separately
  for each camera.
- Added an interactive choice of study day or calendar date for the horizontal axis.
- Added downloadable height-versus-day PNGs with Bayesian trajectories, 95% uncertainty
  bands, and current-image measurements, both individually and in the complete result ZIP.
- Added separate visible-plant counts for each camera or plot in the browser and batch
  interfaces.
- Documented one image per camera per day, taken at a similar time, as the preferred
  prospective schedule while retaining support for wider and irregular intervals.
- Replaced obsolete Streamlit width settings so the current interface runs without
  deprecation warnings.

## Expanded validation

- Ran fresh pose inference on all 49 released longitudinal field images from 12 camera
  series, yielding 253 geometrically valid candidates.
- Replayed every series under its true irregular dates and under daily, three-day,
  seven-day, and 30-day schedules. Every schedule completed with 248 finite height rows:
  241 current-image updates and seven prediction-only rows.
- Confirmed that the independently supplied 0.415886 cm-per-pixel route exactly matches
  the published 2021 calibration route.
- Tested the automatic red-band route on all 49 field images. It completed without error
  and conservatively withheld calibration when a pole fit failed; only four field frames
  passed. The included examples therefore use the validated published 2021 scale.
- Twelve focused tests pass, including exact released-filter equivalence, prefix
  causality, daily/three-day/seven-day timing, per-camera plant counts, plot generation,
  and result-ZIP contents.
- Both built-in examples complete through the actual Streamlit interface with zero
  application exceptions.

## Manuscript package

The journal-ready *The Plant Phenome Journal* manuscript, supplement, submission files,
analysis code, curated annotations, derived data, and model provenance remain included.

## Scope and rights

The pose checkpoint is intended for field maize imagery resembling the released data.
Annotated-image and calibration-QC review remain part of the workflow. The MIT License
applies to repository code; the model card records the Ultralytics dependency and the
available checkpoint provenance.
