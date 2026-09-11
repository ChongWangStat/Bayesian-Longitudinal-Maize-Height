# ScholarOne metadata for The Plant Phenome Journal

## Article type

Methods and Techniques

## Title

Prior-guided image analysis for Bayesian longitudinal maize height phenotyping with fixed cameras

## Running title

Prior-guided longitudinal maize phenotyping

## Authors and affiliations

1. Haoming Wang — Department of Statistics, Iowa State University, 2438 Osborn Drive, Ames, IA 50011-1090, USA
2. Chong Wang — Department of Statistics, Iowa State University, 2438 Osborn Drive, Ames, IA 50011-1090, USA; Department of Veterinary Diagnostic and Production Animal Medicine, Iowa State University, 1809 South Riverside Drive, Ames, IA 50011-1134, USA
3. Yawei Li — Plant Sciences Institute, Iowa State University, 1111 WOI Road, Ames, IA 50011-1085, USA; Interdepartmental Genetics and Genomics Graduate Program, Iowa State University, 2014 Molecular Biology Building, 2437 Pammel Drive, Ames, IA 50011-1079, USA; Department of Agronomy, Iowa State University, Agronomy Hall, 716 Farm House Lane, Ames, IA 50011-1051, USA
4. Cheng-Ting Yeh — Plant Sciences Institute, Iowa State University, 1111 WOI Road, Ames, IA 50011-1085, USA; Department of Agronomy, Iowa State University, Agronomy Hall, 716 Farm House Lane, Ames, IA 50011-1051, USA
5. Patrick S. Schnable — Plant Sciences Institute, Iowa State University, 1111 WOI Road, Ames, IA 50011-1085, USA; Interdepartmental Genetics and Genomics Graduate Program, Iowa State University, 2014 Molecular Biology Building, 2437 Pammel Drive, Ames, IA 50011-1079, USA; Department of Agronomy, Iowa State University, Agronomy Hall, 716 Farm House Lane, Ames, IA 50011-1051, USA
6. Peng Liu — Department of Statistics, Iowa State University, 2438 Osborn Drive, Ames, IA 50011-1090, USA

Corresponding author: Peng Liu, 2117 Snedecor Hall, 2438 Osborn Drive, Ames, IA 50011-1090, USA; pliu@iastate.edu; ORCID 0000-0002-2093-8018

## Abstract

Fixed cameras could make repeated field phenotyping more accessible, but occlusion and uncertain pixel-to-length calibration can corrupt individual-image measurements. We developed a Bayesian longitudinal maize (Zea mays L.) height method in which predictions from earlier images guide current-image association and candidate selection before a measurement is finalized. Physical references convert image extents to centimeters, and a robust particle filter updates height, growth, and uncertainty using only images available through each time point. Independent 2021 validation comprised 132 manual heights from 33 plants in 12 camera rows; manual heights were excluded from fitting and tuning. Among six causal estimators, the particle filter gave the lowest mean absolute error (10.97 cm) and improved on exponentially weighted moving average, running median, and Holt by 4.01, 7.80, and 3.08 cm, with row-cluster intervals above zero. Improvements over single-frame and Gaussian filtering were 1.06 and 0.66 cm and were uncertain. Posterior 95% intervals covered 94.7% of manual heights. In simulated candidate ambiguity, using the prior during image analysis reduced latent-height root mean squared error from 10.5 to 6.0 cm; a matched real-image audit contained no candidate conflict. The method provides an open, physically calibrated workflow for longitudinal maize phenotyping and shows how temporal predictions can inform image analysis before measurement extraction.

Character count, including spaces: 1,477. Word count: 206.

## Plain Language Summary

Measuring the same plants by hand throughout a field season is slow. Fixed cameras can reduce repeated field visits and plant disturbance, but leaves can overlap and an image must be converted from pixels to centimeters. We developed a method that uses what earlier images suggest about a plant's position and height while analyzing each new image. It then updates the plant's estimated height, growth, and uncertainty. Tests against 132 manual measurements from 33 maize plants found the lowest average error among six methods. Clear advantages were seen over three simple time-series methods, while differences from the two strongest comparison methods were small and uncertain. All code, curated images, annotations, and derived validation data are public. The approach offers a transparent route to repeated field measurements from fixed cameras and reports when the data do not distinguish competing methods.

Character count, including spaces: 913.

## Keywords

Bayesian longitudinal model; prior-guided image analysis; maize height; particle filter; stationary camera; uncertainty calibration

## Subject and methods terms

Plant phenotyping; image analysis; longitudinal data; state-space model; physical calibration; maize; uncertainty quantification; fixed camera

## Declarations

- Conflict of interest: None declared.
- Funding: Plant Sciences Institute at Iowa State University; Laurence H. Baker Center for Bioinformatics and Biological Statistics.
- Data availability: https://github.com/ChongWangStat/Bayesian-Longitudinal-Maize-Height/releases/tag/v1.2.1
- Supplemental material: A separate 25-page Supplementary Materials PDF contains three figures, six tables, detailed methods, calibration derivations, uncertainty analyses, candidate-selection audits, and provenance documentation.
- AI declaration: During preparation of this work, the authors used Claude (Anthropic) and Codex (OpenAI) to assist with data exploration, code review, figure and manuscript preparation, and language editing. The authors reviewed and edited all assisted content, verified the reported results against the included analysis code, and take full responsibility for the content of the manuscript.
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
