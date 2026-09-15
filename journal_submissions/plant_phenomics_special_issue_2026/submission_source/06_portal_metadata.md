# Portal metadata

- **Journal:** Plant Phenomics
- **Article type:** Methods Article
- **Special issue category:** VSI: PMBDA2025
- **Special issue:** Plant Modeling, Big Data Analytics, and High-Throughput Phenotyping for Smart Agriculture
- **Title:** Prior-guided image analysis for Bayesian longitudinal maize height phenotyping with fixed cameras
- **Corresponding author:** Peng Liu, pliu@iastate.edu
- **Authors in order:** Haoming Wang; Chong Wang; Yawei Li; Cheng-Ting Yeh; Patrick S. Schnable; Peng Liu
- **Keywords:** affordable phenotyping; Bayesian longitudinal analysis; fixed camera; maize height; prior-guided image analysis; temporal validation; uncertainty calibration
- **Conflict of interest:** None declared
- **Funding:** Plant Sciences Institute at Iowa State University; Laurence H. Baker Center for Bioinformatics and Biological Statistics
- **Data statement:** Anonymous review archive supplied; public versioned GitHub repository identified on title page
- **Submission declarations:** Original work; not under consideration elsewhere; all authors approved

## Abstract

Affordable longitudinal field phenotyping requires interpretable image measurements under overlap and changing camera geometry. We developed a Bayesian longitudinal method for fixed RGB cameras in which the state from earlier images guides association and candidate selection during each added image. A robust particle filter updates height, growth, and uncertainty from the available image prefix. The temporal validation was developed from 61 matched 2021 image--manual records in six camera rows and evaluated against 166 later-year manual heights from 34 new maize plants in four biological rows and six views. No 2024 manual outcome was used for fitting or tuning. Bayesian estimates reduced single-frame mean absolute error from 18.10 to 17.36 cm and root mean squared error from 23.54 to 22.41 cm; correlation increased from 0.813 to 0.847. A Gaussian filter with matched priors had mean absolute error 17.35 cm and root mean squared error 22.42 cm, effectively tying the particle estimate. The 0.74-cm gain over single frames had a biological-row cluster interval of -0.44 to 1.30 cm, indicating a modest, uncertain advantage. Transfer-aware 80%, 90%, and 95% intervals covered 78.9%, 90.4%, and 97.0% of manual heights. In controlled candidate ambiguity, placing the prior inside image analysis reduced root mean squared error from 8.61 to 6.01 cm relative to filtering preselected measurements. Released code and a browser application convert dated images into daily height trajectories with uncertainty.
