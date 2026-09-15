# 2024 later-year manual-height validation

The affine pose-to-height calibration is fit only on 2021 records with recovered source coordinates. Its physical scale is transferred to 2024 by the recorded 8.5/10.25 camera-distance ratio. The 2024 manual outcomes enter only after all daily image updates have been computed. Left and right camera views are paired within biological row, and bootstrap resampling uses the four biological rows.

The transfer-aware intervals retain the row-held-out 2021 calibration RMSE as a non-shrinking uncertainty component and use a Student-t multiplier with five degrees of freedom, reflecting the six 2021 development rows.

Fixed prefix-causal comparators are evaluated on the same daily image prefixes before manual outcomes are joined. The Gaussian local-linear filter receives the same initial growth prior and process scales as the particle filter.

The red-band metadata audit is diagnostic. Automated candidates can encode more one-foot intervals than the recorded 8-10-ft pole can contain; therefore that scale is not used for the manual-height transfer result.
