# Data dictionary and analysis roles

| Path | Unit | Role |
|---|---:|---|
| `data/raw/heights_compare_2021.csv` | 132 plant-dates | Archived 2021 image extents and manual field heights used for scoring. |
| `data/raw/pole_calibration_images/` | 61 images | Curated images with support-pole annotations and prospective plant annotation. |
| `data/manual_annotations/poles_2021/` | 12 XML files, 199 traces | Camera-support-pole polylines; 172 usable and 27 unusable. |
| `data/processed/manual_poles_2021/` | trace and definition tables | Imported pole endpoints, status, lengths, and physical definitions. |
| `data/processed/yolo_candidates_2021.csv` | cached candidates | Candidate table used by the matched 2021 real-image audit. |
| `outputs/filter_height_sam_2021/filtered_height_sam__phi1.0_plus_pole_growth_field.csv` | 132 plant-dates | Canonical leakage-free 2021 particle-filter output. |
| `outputs/online_study/depth_corrected_heights_daily.csv` | measurement stream | Public 2024–2025 measurement-level input after 0.85 depth conversion. |
| `outputs/online_study/pole_camera_bayesian_daily*_revised/` | 1,638 forecasts | Guessed and 2024-estimated predictive/posterior outputs. |
| `outputs/uncertainty_revision/` | summaries | Coverage, width, log score, weighted interval score, and 2025 held-out results. |
| `outputs/field_baselines_2021/` | summaries and 132 records | Fixed causal smoother comparisons and row-cluster bootstrap intervals. |
| `outputs/real_image_candidate_ablation_2021/` | 63 matched plant-dates | Same-candidate audit of post-detection and prior-guided scoring. |
| `annotation/annotator_A.csv`, `annotator_B.csv` | 366 rows each | Blank, blinded human-annotation forms; these are prospective, not completed data. |

Pixel coordinates use the original image origin at the upper-left: x increases rightward and y increases downward. `plant_id_rtl` and `plant_slot_right_to_left` number plants from right to left, matching the field convention.
