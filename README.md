# Bayesian longitudinal maize height from fixed cameras

This repository accompanies the Plant Phenomics manuscript **“Bayesian Longitudinal Maize Height Estimation with Prior-Guided Image Analysis.”** It releases the final manuscript, analysis code, canonical derived data, 61 curated 2021 field images, 12 human-annotated support-pole XML files, a pose checkpoint, and cached predictions.

The methodological distinction is where the longitudinal information acts. A conventional two-stage workflow chooses a measurement from each image and only then links those measurements in a longitudinal model. Here the predictive state is returned to current-image analysis: running position guides plant association and base refinement, while the stronger candidate branch lets the predicted height distribution score competing plant-top candidates before the measurement is finalized.

The workflow treats “online” as an as-of analysis. When an image arrives, it is added to the available pool and the algorithm returns a measurement and height-growth distribution using that image and earlier images. Later images trigger later updates and do not revise earlier outputs.

## Principal results

- All 132 manual plant-height records from 33 plants in 12 field rows were retained. Mean absolute error was 12.03 cm for the single-frame image extent and 10.97 cm for the robust Bayesian particle filter. The paired reduction was 1.06 cm (95% row-cluster bootstrap interval, -0.16 to 2.39 cm).
- The particle filter had the lowest point-estimate error among the fixed causal comparisons. The Gaussian local-linear Kalman filter reached 11.62 cm MAE; its paired difference from the particle filter was 0.66 cm (-0.43 to 1.79 cm).
- With every noise scale expressed after the same 0.85 depth conversion, settings estimated from 2024 achieved 94.9% coverage with a 97.8 cm mean 95% predictive width on 372 held-out 2025 forecasts from two cameras. Lower nominal levels remained conservative.
- In the controlled ambiguity simulation, root mean squared error was 10.48 cm for single-frame selection, 8.61 cm for filtering after selection, and 6.01 cm when the predicted height distribution participated in candidate scoring.
- In the matched 2021 real-image audit, the two temporal candidate rules selected the same candidate on all 63 evaluated plant-dates. This is a negative control: those natural candidate sets contained no conflict under the fixed gates.

These estimates describe a pilot study. The field advantage over the strongest comparators is uncertain, and the 2025 predictive evaluation has two sequential cameras. Human evidence includes 150 plant masks, 132 manual field-height records, and Haoming Wang's 199 physical-reference traces across 61 images.

## Repository map

- `manuscript/`: final LaTeX source, editable figures, main PDF, and supplementary PDF.
- `analysis/`: canonical scripts used for the reported calculations and physical-reference import.
- `data/raw/pole_calibration_images/`: 61 curated 2021 images. `C-039_2021-07-30.JPG` is retained; the confirmed duplicate spelling is omitted.
- `data/manual_annotations/poles_2021/`: Haoming Wang's support-pole annotations, one XML file per camera row.
- `data/processed/`: public derived measurements and candidate tables with workstation paths and server links removed.
- `outputs/`: canonical summaries, bootstrap results, prediction tables, and audit figures.
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

This fast path recalculates the all-plant summary, fixed field baselines, matched real-image audit, multi-level uncertainty summary, and generated LaTeX numbers from the released prediction tables. It also runs integrity checks.

To rerun the two 5,000-particle daily filters from the released depth-corrected measurement table:

```bash
python reproduce_core.py --full-filter
```

To rerun pose inference on all 61 curated images, install `requirements.txt` and run:

```bash
python analysis/cache_pose_candidates_annotation_set.py
```

The larger 2024–2025 raw-image archive is not included. The released derived table is sufficient to rerun the uncertainty analysis from its measurement-level input. The exact original training manifest, random seed, and full cross-fitting image set for the checkpoint were not recoverable from the project archive; see `models/MODEL_CARD.md`.

## Physical and annotation definitions

Haoming Wang manually traced 199 physical references across the 61 curated 2021 images; 172 traces are marked usable and 27 unusable in the XML audit. The labels `pole1` through `pole4` identify different visible camera-support poles. Each annotated segment runs from ground contact to the nominal camera mounting or optical-center height: 5 ft (152.4 cm). Four 35 in intervals describe horizontal field layout, totaling 140 in between adjacent rows; they are not vertical pole marks. The 2024–2025 reference is a separate 8–10 ft pole whose adjacent red-band edges are 1 ft (30.48 cm) apart.

The primary 2021 manual field-height column comes from `_ft(cm)` measurement 1: ground to the topmost plant point that touches a meter stick before tasseling, and ground to the flag leaves after tasseling, excluding the tassel.

## Rights and citation

Code is released under the MIT License. No separate reuse license has been confirmed for the data, images, annotations, model weights, figures, or manuscript materials; see `DATA_RIGHTS.md`. Please cite the accompanying manuscript and repository metadata in `CITATION.cff`.
