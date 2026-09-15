# Prior-guided image analysis for Bayesian longitudinal maize height phenotyping

This repository accompanies a Methods Article prepared for *Plant Phenomics* and
the special issue **Plant Modeling, Big Data Analytics, and High-Throughput
Phenotyping for Smart Agriculture**. The title is **“Prior-guided image analysis
for Bayesian longitudinal maize height phenotyping with fixed cameras.”**

The methodological contribution is the location of the longitudinal prior. A
usual two-stage workflow selects a height independently from each image and then
links the measurements in a longitudinal model. Here the predictive state from
earlier images is returned to analysis of the newly added image: it guides plant
association and can score competing top candidates before a height is committed.
Each reported value is prefix-causal and uses only the image available at that
date and earlier images.

## Later-year manual-height validation

The primary temporal validation develops the transfer on 61 matched 2021 records
from six camera rows and evaluates it against 166 matched 2024 manual field heights
from 34 newly grown plants. No 2024 manual outcome was used for fitting or tuning.

The 2024 workbook contains four biological rows. Each biological row is covered
by a paired left/right camera layout, so the two camera views are kept together
and are not counted as independent biological samples. All uncertainty resampling
uses the four biological rows as clusters.

| Estimator | Bias (cm) | MAE (cm) | RMSE (cm) | Pearson r |
|---|---:|---:|---:|---:|
| Single frame | -13.49 | 18.10 | 23.54 | 0.813 |
| EWMA | -16.46 | 19.70 | 24.44 | 0.847 |
| Running median, 3 images | -16.26 | 19.94 | 24.66 | 0.835 |
| Holt level-trend | -13.65 | 17.60 | 22.63 | 0.843 |
| Gaussian local-linear | -13.22 | 17.35 | 22.42 | 0.846 |
| Bayesian longitudinal particle method | -13.24 | 17.36 | 22.41 | 0.847 |

The Bayesian estimate reduced MAE by 0.74 cm relative to single-frame estimates;
the 95% biological-row cluster interval was -0.44 to 1.30 cm. The particle and
matched Gaussian filters were practically tied. This comparison focuses the paper
on prior-guided image association, causal longitudinal measurement, physical
calibration, and transparent uncertainty rather than on a claim that particle
computation is universally superior.

Transfer-aware interval coverage was 78.9%, 90.4%, and 97.0% for nominal 80%,
90%, and 95% intervals, with mean widths of 56.0, 76.4, and 97.5 cm. The broad
upper-level intervals retain the 2021 leave-one-camera-row-out transfer error.

The imported workbook has 247 nonmissing values from 45 plants. Fifty-four values
belong to two unavailable camera halves, and 27 more lack a same-date QC-eligible
automated output, leaving 166 matches. Manual and image times differ by a median
2.78 hours and a maximum 6.90 hours. The workbook does not encode which of the two
documented pre-tasseling endpoints was used, so the outcome is described as
“manual field height.”

Field notes document an 8–10 ft 2024 calibration pole with 1 ft red-mark spacing.
The automatic red-component sequence often implied more than the documented pole
length and is therefore retained as a diagnostic rather than used for absolute
2024 calibration. The validation uses the 2021 development calibration and the
recorded 8.5/10.25 camera-distance ratio.

## Plant-scientist application

The local browser application accepts dated fixed-camera images, detects plant
tops and roots, maintains plant identity through time, applies physical
calibration, and returns height as a function of study day or calendar date.
Outputs include 80% and 95% intervals, growth estimates, quality flags, annotated
images, tables, and downloadable trajectory plots.

On Windows, double-click `START_PLANT_HEIGHT_APP.bat`. Instructions and batch
usage are in `plant_height_app/README.md`. The built-in C-024 and C-004 examples
provide four- and five-date longitudinal demonstrations; the application also
supports different visible-plant counts for different cameras. One image per
camera per day at a similar time is the preferred prospective schedule, while
wider and irregular intervals remain supported.

## Journal files

The journal-specific source is in
`journal_submissions/plant_phenomics_special_issue_2026/submission_source/`.
It uses the official Elsevier `elsarticle` class version 3.5 dated 9 January 2026
and contains separate anonymous manuscript, title page, anonymous supplement,
cover letter, highlights, portal metadata, and compiled PDFs. The complete upload
package is built with:

```bash
python analysis/build_plant_phenomics_special_issue.py
python analysis/package_plant_phenomics_submission.py
```

The audited field protocol is available in both Word and PDF under `protocols/`.

## Reproduce the 2024 validation

Python 3.12 or 3.13 is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-core.txt
python analysis/validate_manual_height_transfer_2024.py
```

The canonical inputs are in `data/raw/manual_height_2024/`,
`data/raw/heights_compare_2021.csv`, `data/processed/`, and the two supporting
2021 output directories used by the validation script. The generated results,
row-cluster bootstrap replicates, comparator table, accounting table, figure, and
numerical LaTeX macros are in `outputs/manual_height_transfer_2024/`.

For the earlier released analyses, run `python reproduce_core.py`. To rerun pose
inference on the 61 curated 2021 images, install `requirements.txt` and run
`python analysis/cache_pose_candidates_annotation_set.py`.

## Repository map

- `analysis/`: analysis, validation, figure, manuscript-build, and package scripts.
- `data/raw/manual_height_2024/`: imported manual heights, camera-pair map, and source hashes.
- `data/raw/pole_calibration_images/`: 61 curated 2021 images; the duplicate spelling of `C-039_2021-07-30.JPG` is omitted.
- `data/manual_annotations/poles_2021/`: 12 CVAT XML files containing the support-pole annotations.
- `data/processed/`: released derived image measurements and calibration records.
- `outputs/manual_height_transfer_2024/`: primary later-year validation outputs.
- `plant_height_app/`: browser and command-line application, examples, and tests.
- `models/`: pose checkpoint and available provenance.
- `protocols/`: audited 2024 manual-height and paired-camera protocol.

## Scope and rights

The 2024 result is later-year, subject-disjoint, label-held-out temporal field
validation. The image tracks had previously been used without their manual labels
during pipeline development, so it is not a fully external-site validation. Its
four biological rows limit precision, and the point-estimate advantage over the
strongest matched comparator is negligible.

Code is released under the MIT License. No separate reuse license has been
confirmed for data, images, annotations, model weights, figures, or manuscript
materials; see `DATA_RIGHTS.md` and `models/MODEL_CARD.md`.
