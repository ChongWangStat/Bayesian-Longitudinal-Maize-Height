# Plant Phenomics submission package v1.0.0

This release freezes the materials underlying the manuscript **“Prior-Guided Bayesian Image Analysis for Physically Calibrated Longitudinal Maize Height.”**

## Included

- Plant Phenomics LaTeX source, compiled main manuscript, and compiled supplement.
- Canonical analysis scripts, derived data, reported summaries, and figures.
- The pinned maize pose checkpoint with SHA-256 digest `d813f7176890fd04f478868f8834ceae0b6f05c9c88ddfc8910c8c695745a572`.
- Sixty-one unique 2021 pole-calibration images and 12 row-level CVAT XML files. `C-039_2021-07-30.JPG` is retained and the confirmed duplicate spelling is omitted.
- A prospective, blinded two-reader plant-landmark packet and an agreement scorer.
- A fast reproduction entry point and an automated integrity check.

## Validation

Running `python reproduce_core.py` recalculates the core field comparison, causal baselines, real-image candidate audit, multi-level uncertainty summaries, and LaTeX numbers before executing `verify_release.py`. The frozen release passed this workflow on 9 September 2026.

## Scope disclosures

The released A/B plant-landmark sheets are intentionally blank and still require two independent human annotation passes. The larger 2024–2025 raw-image archive is not redistributed; the measurement-level derived table needed for the reported uncertainty analysis is included. The exact training manifest and random seed for the released checkpoint were not recoverable from the project archive and are documented in the model card.
