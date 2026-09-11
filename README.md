# Bayesian longitudinal maize height from fixed cameras

This repository accompanies the Methods and Techniques manuscript prepared for submission to *The Plant Phenome Journal*, **“Prior-guided image analysis for Bayesian longitudinal maize height phenotyping with fixed cameras.”** It releases the manuscript, analysis code, canonical derived data, 61 curated 2021 field images, 12 human-annotated support-pole XML files, a pose checkpoint, and cached predictions.

The methodological distinction is where the longitudinal information acts. A conventional two-stage workflow chooses a measurement from each image and only then links those measurements in a longitudinal model. Here the predictive state is returned to current-image analysis: running position guides plant association and base refinement, while the stronger candidate branch lets the predicted height distribution score competing plant-top candidates before the measurement is finalized.

The workflow treats “online” as an as-of analysis. When an image arrives, it is added to the available pool and the algorithm returns a measurement and height-growth distribution using that image and earlier images. Later images trigger later updates and do not revise earlier outputs.

## Principal results

- The primary independent physical-height validation retained all 132 manual measurements from 33 plants across 12 stationary-camera rows and five dates in 2021. Its plant subjects and reference outcomes were separate from the 2024–2025 longitudinal-model development data. Manual height was reserved for evaluation and excluded from model and comparator tuning. Mean absolute error was 12.03 cm for the single-frame image extent and 10.97 cm for the robust Bayesian particle filter. The within-record reduction was 1.06 cm (95% camera-row-cluster bootstrap interval, -0.16 to 2.39 cm). Across the 99 observations after a plant's first image, the reduction was 1.44 cm (-0.21 to 3.26 cm). Median absolute error decreased from 8.74 to 7.30 cm (whole-row bootstrap reduction, 1.43 cm; 0.29–3.70 cm), and the mean-error gain stayed positive under all 12 leave-one-camera-row-out omissions (0.61–1.42 cm).
- The particle filter had the lowest point-estimate error among the fixed causal comparisons. The Gaussian local-linear Kalman filter reached 11.62 cm MAE; its within-record difference from the particle filter was 0.66 cm (-0.43 to 1.79 cm). Improvements over EWMA, the running median, and Holt were 4.01, 7.80, and 3.08 cm, and all three whole-row bootstrap intervals excluded zero.
- Central 80% and 95% latent-height posterior intervals covered 87.1% and 94.7% of the held-out 2021 manual heights, with mean widths of 47.9 and 75.4 cm. Their whole-row bootstrap coverage intervals were 79.3–93.6% and 89.4–98.6%, respectively.
- In a secondary temporal uncertainty check, settings estimated from 36 plant tracks in 2024 achieved 94.9% coverage with a 97.8 cm mean 95% predictive width on 372 forecasts from 11 evaluated plant tracks at two cameras in 2025. Annual replanting makes this a temporally later, subject-disjoint cohort with no plant subject shared across years. This result supports transfer for those installations rather than broad camera generalization.
- In the controlled ambiguity simulation, root mean squared error was 10.48 cm for single-frame selection, 8.61 cm for filtering after selection, and 6.01 cm when the predicted height distribution participated in candidate scoring.
- In the matched 2021 real-image audit, the two temporal candidate rules selected the same candidate on all 63 evaluated plant-dates. This is a negative control: those natural candidate sets contained no conflict under the fixed gates.
- The 172 usable support-pole annotations formed 39 repeated row–pole series across all 12 camera rows. Median within-series pixel-length coefficient of variation was 1.24% (95% whole-row bootstrap interval, 0.78–1.99%); 38 of 39 series were below 5%.

These estimates describe a pilot study. The field advantage over the strongest comparators is uncertain. The primary independent manual-reference validation spans 12 stationary-camera rows, while the secondary subject-disjoint 2025 predictive evaluation has only two cameras. The manual reference series and newly annotated pole images are from 2021; the final manual reference was recorded at the end of that season. The external 2024–2025 growth field used no 2021 manual labels. Forecasts repeat within plant tracks and cameras and are not treated as independent biological subjects. Human evidence includes 150 plant masks, 132 manual field-height records, and Haoming Wang's 199 physical-reference traces across 61 images.

Source-frame matching recovered coordinates for 87 archived plant crops across seven camera rows. Sixty-three of these map to the primary validation across six rows; the other 69 primary records preserve the derived segmentation extent without a reconstructable raw-image-to-extent chain. The released crop-position table records the recoverable coordinates and match scores.

## Repository map

- `manuscript/`: final LaTeX source, editable figures, main PDF, and supplementary PDF.
- The main source follows the official June 2026 *The Plant Phenome Journal* submission template in standard LaTeX: 12-point Times-family type, US-letter paper, 1-inch margins, double spacing, continuous line numbers, the journal's front-matter order, full postal affiliations, and APA author–year references. The journal supplies a Word template rather than a LaTeX class, so the source uses the journal's official LaTeX submission route.
- `analysis/`: canonical scripts used for the reported calculations and physical-reference import.
- `data/raw/pole_calibration_images/`: 61 curated 2021 images. `C-039_2021-07-30.JPG` is retained; the confirmed duplicate spelling is omitted.
- `data/manual_annotations/poles_2021/`: Haoming Wang's support-pole annotations, one XML file per camera row.
- `data/processed/`: public derived measurements and candidate tables with workstation paths and server links removed.
- `outputs/`: canonical summaries, bootstrap results, prediction tables, and audit figures.
- `outputs/manual_height_uncertainty_2021/`: manual-reference posterior coverage and width at 80% and 95%, with per-date and whole-row bootstrap summaries.
- `outputs/pole_repeatability_2021/`: temporal repeatability of all usable repeated support-pole series.
- `models/`: released pose checkpoint and its model card.

## Reproduce the core tables

Python 3.12 or 3.13 is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-core.txt
python reproduce_core.py
```

This fast path recalculates the all-plant summary, fixed field baselines, manual-height interval audit, support-pole repeatability, matched real-image audit, multi-level uncertainty summary, and generated LaTeX numbers from the released prediction tables. It also runs integrity checks.

To rerun the two 5,000-particle daily filters from the released depth-corrected measurement table:

```bash
python reproduce_core.py --full-filter
```

To rerun pose inference on all 61 curated images, install `requirements.txt` and run:

```bash
python analysis/cache_pose_candidates_annotation_set.py
```

The larger 2024–2025 raw-image archive is not included. The released derived table is sufficient to rerun the uncertainty analysis from its measurement-level input. The checkpoint's embedded training seed, deterministic setting, software version, training arguments, and summary metrics are preserved in `models/checkpoint_metadata.json`. The referenced dataset file, exact original training-image manifest, original training masks, source commit, and full cross-fitting image set were not recoverable from the project archive; see `models/MODEL_CARD.md`.

## Physical and annotation definitions

Haoming Wang manually traced 199 physical references across the 61 curated 2021 images; 172 traces are marked usable and 27 unusable in the XML audit. The labels `pole1` through `pole4` identify different visible camera-support poles. Each annotated segment runs from ground contact to the nominal camera mounting or optical-center height: 5 ft (152.4 cm). Across repeated usable row–pole series, the median temporal coefficient of variation in projected length is 1.24%. This supports temporal stability of the fixed-camera annotations and does not by itself establish absolute scale accuracy. Four 35 in intervals describe horizontal field layout, totaling 140 in between adjacent rows; they are not vertical pole marks. The 2024–2025 reference is a separate 8–10 ft pole whose adjacent red-band edges are 1 ft (30.48 cm) apart.

The primary 2021 manual field-height column comes from `_ft(cm)` measurement 1: ground to the topmost plant point that touches a meter stick before tasseling, and ground to the flag leaves after tasseling, excluding the tassel.

## Rights and citation

Code is released under the MIT License. No separate reuse license has been confirmed for the data, images, annotations, model weights, figures, or manuscript materials; see `DATA_RIGHTS.md`. Please cite the accompanying manuscript and repository metadata in `CITATION.cff`.
