# ScholarOne metadata for The Plant Phenome Journal

## Article type

Methods and Techniques

## Title

Prior-Guided Image Analysis for Bayesian Longitudinal Maize Height Phenotyping with Fixed Cameras

## Running title

Prior-Guided Longitudinal Maize Phenotyping

## Authors and affiliations

1. Haoming Wang — Department of Statistics, Iowa State University, Ames, Iowa, USA
2. Chong Wang — Department of Statistics; Department of Veterinary Diagnostic and Production Animal Medicine, Iowa State University, Ames, Iowa, USA
3. Yawei Li — Plant Sciences Institute; Interdepartmental Genetics and Genomics Graduate Program; Department of Agronomy, Iowa State University, Ames, Iowa, USA
4. Cheng-Ting Yeh — Plant Sciences Institute; Department of Agronomy, Iowa State University, Ames, Iowa, USA
5. Patrick S. Schnable — Plant Sciences Institute; Interdepartmental Genetics and Genomics Graduate Program; Department of Agronomy, Iowa State University, Ames, Iowa, USA
6. Peng Liu — Department of Statistics, Iowa State University, Ames, Iowa, USA

Corresponding author: Peng Liu, pliu@iastate.edu

## Abstract

Fixed cameras could make repeated field phenotyping more accessible, but occlusion and uncertain pixel-to-length calibration can corrupt individual-image measurements. We developed a Bayesian longitudinal maize (Zea mays L.) height method in which predictions from earlier images guide current-image association and candidate selection before a measurement is finalized. Physical references convert image extents to centimeters, and a robust particle filter updates height, growth, and uncertainty using only images available through each time point. Independent 2021 validation comprised 132 manual heights from 33 plants in 12 camera rows; manual heights were excluded from fitting and tuning. Among six causal estimators, the particle filter gave the lowest mean absolute error (10.97 cm) and improved on EWMA, running median, and Holt by 4.01, 7.80, and 3.08 cm, with row-cluster intervals above zero. Improvements over single-frame and Gaussian filtering were 1.06 and 0.66 cm and were uncertain. Posterior 95% intervals covered 94.7% of manual heights. In simulated candidate ambiguity, using the prior during image analysis reduced latent-height RMSE from 10.5 to 6.0 cm; a matched real-image audit contained no candidate conflict. The method provides an open, physically calibrated workflow for longitudinal maize phenotyping and shows how temporal predictions can inform image analysis before measurement extraction.

Character count, including spaces: 1,425. Word count: 200.

## Plain Language Summary

Measuring the same plants by hand throughout a field season is slow. Fixed cameras can reduce repeated field visits and plant disturbance, but leaves can overlap and an image must be converted from pixels to centimeters. We developed a method that uses what earlier images suggest about a plant's position and height while analyzing each new image. It then updates the plant's estimated height, growth, and uncertainty. Tests against 132 manual measurements from 33 maize plants found the lowest average error among six methods. Clear advantages were seen over three simple time-series methods, while differences from single-image and Gaussian-filter methods were small and uncertain. All code, curated images, annotations, and derived validation data are public. The approach offers a transparent route to repeated field measurements from fixed cameras and reports when the data do not distinguish competing methods.

Character count, including spaces: 917.

## Core Ideas

- Predictive Bayesian states guide current-image analysis before height measurement.
- Fixed cameras and physical references support longitudinal maize height phenotyping.
- Held-out 2021 manual heights independently validate the causal pipeline.
- Particle filtering improves simple longitudinal baselines; gains over stronger comparators remain uncertain.

Each Core Idea is within the journal's 115-character limit.

## Keywords

Bayesian longitudinal model; prior-guided image analysis; maize height; particle filter; stationary camera; uncertainty calibration

## Subject and methods terms

Plant phenotyping; image analysis; longitudinal data; state-space model; physical calibration; maize; uncertainty quantification; fixed camera

## Declarations

- Conflict of interest: None declared.
- Funding: Plant Sciences Institute at Iowa State University; Laurence H. Baker Center for Bioinformatics and Biological Statistics.
- Data availability: https://github.com/ChongWangStat/Bayesian-Longitudinal-Maize-Height/releases/tag/v1.2.0
- Prior publication: None.
- Concurrent consideration: None.
- Author approval: All authors approved the final manuscript and submission.

## Preferred reviewers

The journal requests at least two. These candidates cover computer vision, fixed-camera or time-series phenotyping, and field sensing. Verify recent coauthorship, grants, institutional ties, and other conflicts in ScholarOne immediately before submission.

1. Amy Tabb, USDA Agricultural Research Service — Amy.Tabb@usda.gov — computer vision, camera calibration, and structural plant phenotyping.
2. David Rousseau, Université d’Angers — david.rousseau@univ-angers.fr — plant image analysis, temporal phenotyping, and affordable imaging systems.
3. Sindhuja Sankaran, Washington State University — sindhuja.sankaran@wsu.edu — proximal sensing, automation, and field crop phenotyping.
4. Sruti Das Choudhury, University of Nebraska–Lincoln — s.d.choudhury@unl.edu — temporal image analysis and computer-vision plant phenotyping.

## Suggested editor-facing significance statement

This work shows how a longitudinal Bayesian prediction can enter analysis of the next plant image before measurement extraction, while physical references preserve centimeter-scale interpretation and posterior intervals expose uncertainty. Independent manual-height validation and public intermediate outputs distinguish supported field findings from controlled mechanism evidence.
