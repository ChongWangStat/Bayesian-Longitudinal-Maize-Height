# The Plant Phenome Journal submission package v1.2.0

This release freezes the materials underlying **“Prior-Guided Image Analysis for Bayesian Longitudinal Maize Height Phenotyping with Fixed Cameras.”** The manuscript is positioned as a Methods and Techniques article for *The Plant Phenome Journal*.

## Journal-focused revision

- Added the required Plain Language Summary, Core Ideas, alphabetical abbreviations, continuous line numbers, double spacing, and author–year references.
- Reframed the paper around a clear crop-phenomics problem: the Bayesian longitudinal state guides current-image association and candidate choice before measurement extraction.
- Added explicit affordable-phenomics context while stating that equipment cost, installation labor, maintenance cost, and processing time were not recorded consistently.
- Added a claim-to-evidence design table, practical deployment and transfer requirements, a concise Conclusions section, and CRediT-form author contributions.
- Preserved the strongest defensible evidence: 132 manual-height records from 33 independent 2021 plants across 12 camera rows, with all manual outcomes excluded from fitting and tuning.
- Kept comparative claims calibrated: row-cluster intervals support improvements over EWMA, running median, and Holt; gains over the single-frame and Gaussian-filter comparators remain uncertain.
- Kept mechanism evidence separate: simulation shows the benefit of prior-guided candidate choice under ambiguity, while the matched real-image subset contains no candidate conflict.
- Clarified that annual replanting makes year cohorts subject-disjoint and that the 2021 manual-height series ends with an end-of-season measurement.

## Included evidence and reproducibility

- LaTeX source, compiled main manuscript, compiled supplement, editable figure sources, and generated numerical macros.
- Canonical analysis scripts, fixed seeds, derived data, reported summaries, and figures.
- Sixty-one unique 2021 pole-calibration images and 12 row-level CVAT XML files containing Haoming Wang's 199 physical-reference traces: 172 usable and 27 unusable.
- The released maize pose checkpoint with SHA-256 digest `d813f7176890fd04f478868f8834ceae0b6f05c9c88ddfc8910c8c695745a572`, recovered training settings, and a complete candidate cache for the 61 curated images.
- Partial source-frame recovery for 87 archived plant crops; 63 map to the primary validation, while 69 primary records retain the derived segmentation extent without a reconstructable raw-image chain.
- A fast reproduction entry point and automated integrity check.

## Validation snapshot

The robust particle filter has the lowest mean absolute error among six causal estimators (10.97 cm). Its improvements over EWMA, running median, and Holt are 4.01, 7.80, and 3.08 cm with whole-row intervals above zero; its 1.06- and 0.66-cm improvements over single-frame and Gaussian filtering are uncertain. Posterior 95% intervals cover 94.7% of the 132 held-out manual heights, with a 75.4-cm mean width. In controlled candidate ambiguity, prior-guided image analysis reduces latent-height RMSE from 10.5 to 6.0 cm.

Running `python reproduce_core.py` recalculates the core field comparison, fixed baselines, after-first-image analysis, manual-height interval calibration, support-pole repeatability, matched real-image audit, uncertainty summaries, and LaTeX numbers before running `verify_release.py`.

## Scope and rights

The larger 2024–2025 raw-image archive is not redistributed; checksum-identified measurement-level data needed for the reported uncertainty analysis are included. The checkpoint's complete original training manifest, original masks, dataset file, and source commit were not recoverable and are documented in the model card. The MIT License applies to code. No separate reuse license has been confirmed for non-code materials.
