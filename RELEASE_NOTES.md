# Plant Phenomics special-issue submission v2.0.0

This release adds the strongest supportable Plant Phenomics manuscript and a
reproducible later-year manual-height validation.

## 2024 temporal validation

- Imported 247 manual field heights from 45 plants without imputation or correction.
- Parsed the Camera layout sheet as four biological rows, each covered by a paired
  left/right camera layout. The biological row is the independent resampling unit.
- Locked the existing code before outcome review and used no 2024 manual height for
  fitting, tuning, candidate selection, or calibration.
- Matched 166 records from 34 plants, four biological rows, six contributing camera
  views, and seven dates after explicit exclusion accounting.
- Added fixed causal comparisons: single frame, EWMA, running median, Holt
  level-trend, and a Gaussian local-linear model with the same prior and process
  scales as the particle method.
- Obtained 17.36 cm MAE, 22.41 cm RMSE, and correlation 0.847 for the Bayesian
  longitudinal estimate. The matched Gaussian model was practically tied at 17.35
  cm MAE and 22.42 cm RMSE.
- Estimated a 0.74 cm MAE gain over single frames with a four-row 95% cluster
  interval of -0.44 to 1.30 cm.
- Reported transfer-aware 80%, 90%, and 95% coverage of 78.9%, 90.4%, and 97.0%,
  together with mean widths of 56.0, 76.4, and 97.5 cm.
- Audited the 8–10 ft red-marked pole and excluded automatic band enumeration from
  absolute 2024 calibration because inferred spans conflicted with the recorded
  physical length.

## Manuscript and journal package

- Reframed the contribution around prior-guided image analysis within Bayesian
  longitudinal phenotyping.
- Added the 2024 design, camera-pair map, complete record accounting, causal
  comparators, cluster uncertainty, limitations, and data provenance throughout the
  title, abstract, introduction, methods, results, discussion, supplement, and cover
  letter.
- Built separate double-anonymized manuscript and supplement files plus an identified
  title page using the official Elsevier `elsarticle` class v3.5.
- Added a five-page audited manual-height and camera-pair protocol in Word and PDF.
- Added deterministic package generation with an anonymized code/data archive,
  source archives, separate figures, upload instructions, and SHA-256 manifests.

## Validation

- The full 2024 analysis reproduces from the anonymous review archive.
- Both anonymous and identified LaTeX source archives compile independently.
- The main manuscript is 19 pages with a 225-word abstract, four figures, four
  tables, and 19 cited references.
- The anonymous text audit found no author names, institutional identifiers,
  workstation paths, or public repository links.
- Package and anonymous-archive SHA-256 manifests verify without mismatch.
