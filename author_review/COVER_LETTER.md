10 September 2026

Dear Editor-in-Chief and Editors of *The Plant Phenome Journal*:

Please consider our manuscript, “Prior-guided image analysis for Bayesian longitudinal maize height phenotyping with fixed cameras,” for publication as a **Methods and Techniques** article.

Fixed-camera phenotyping produces a sequence of related images, yet common pipelines finalize a measurement from each image before a longitudinal model is applied. Our method closes that separation: the Bayesian predictive state from earlier images guides association and can rank competing height candidates while the current image is being analyzed. An in-scene physical reference converts image extent to centimeters, and a robust particle filter updates plant height, growth, and uncertainty using only the images available at that time.

The paper combines method development with crop-relevant validation. The primary independent study contains 132 manual height records from 33 maize plants across 12 stationary-camera rows in 2021. Those plants are separate from the 2024–2025 development cohorts, and no manual height was used to fit or tune the image measurement, longitudinal model, noise parameters, or comparators. The particle filter had the lowest mean absolute error among six causal estimators. Camera-row bootstrap intervals support improvements over EWMA, running median, and Holt; the smaller improvements over single-frame and Gaussian filtering remain explicitly uncertain. A controlled ambiguity experiment establishes the prior-in-image candidate-selection mechanism, while a matched real-image audit is reported as a negative control because its candidate sets contained no conflict.

The manuscript fits the journal’s transdisciplinary scope by joining plant phenotyping, image analysis, physical calibration, sequential statistical modeling, and transparent uncertainty. It also provides practical transfer conditions and candidly separates evidence for physical-height accuracy, calibration, detector agreement, candidate choice, and year-forward uncertainty. The public versioned release includes analysis code, 61 curated images, 12 human-annotated pole XML files, a pose checkpoint, candidate outputs, derived validation data, figures, and a SHA-256 manifest.

This work has not been published and is not under consideration elsewhere. All authors approved the manuscript and its submission. The authors declare no conflict of interest.

Thank you for your consideration.

Sincerely,

Peng Liu, Ph.D.
Department of Statistics
Iowa State University
Ames, Iowa, USA
pliu@iastate.edu
On behalf of all authors
