# Plant Phenomics submission package v1.1.3

This release freezes the materials underlying the manuscript **“Bayesian Longitudinal Maize Height Estimation with Prior-Guided Image Analysis.”**

## Included

- Plant Phenomics LaTeX source, compiled main manuscript, and compiled supplement.
- Canonical analysis scripts, derived data, reported summaries, and figures.
- The pinned maize pose checkpoint with SHA-256 digest `d813f7176890fd04f478868f8834ceae0b6f05c9c88ddfc8910c8c695745a572`.
- Sixty-one unique 2021 pole-calibration images and 12 row-level CVAT XML files containing Haoming Wang's completed human physical-reference audit: 199 traces, including 172 marked usable and 27 marked unusable. `C-039_2021-07-30.JPG` is retained and the confirmed duplicate spelling is omitted.
- A fast reproduction entry point and an automated integrity check.
- Explicit documentation that annual replanting makes the 2024 development and 2025 test cohorts temporally ordered and subject-disjoint, with repeated forecasts still nested within plant tracks and cameras.
- Evidence hierarchy clarified: the 2021 manual measurements across 12 stationary-camera rows are the primary physical-height validation; the two-camera 2025 analysis is a secondary temporal predictive-interval transfer check, and the separate locked calibration test uses three cameras.
- Validation terminology clarified: the subject-disjoint 2021 study is an independent validation because its plant subjects and manual reference outcomes were separate from longitudinal-model development, and the true manual heights were excluded from fitting and tuning. The manual reference series ends with an end-of-season 2021 measurement, and the newly completed pole annotations describe 2021 images. Ambiguous pairing language has been replaced by the precise concept of manual reference outcomes used only to score evaluated predictions.

## Validation

Running `python reproduce_core.py` recalculates the core field comparison, causal baselines, real-image candidate audit, multi-level uncertainty summaries, and LaTeX numbers before executing `verify_release.py`. The frozen release passed this workflow on 10 September 2026.

## Scope disclosures

The larger 2024–2025 raw-image archive is not redistributed; the measurement-level derived table needed for the reported uncertainty analysis is included. The exact training manifest and random seed for the released checkpoint were not recoverable from the project archive and are documented in the model card. The MIT License applies to code; no separate reuse license has been confirmed for non-code materials.
