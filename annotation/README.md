# Independent plant-landmark annotation packet

This packet is prepared for two independent human passes over the same 61 images that contain the completed support-pole annotations. Annotators A and B should work separately and should not view model predictions or each other's sheets. Plant IDs run from right to left, matching the 2021 field convention. Each image has six preallocated slots; mark absent slots explicitly.

1. Read `PLANT_LANDMARK_PROTOCOL.md` before starting.
2. Work only in the assigned `annotator_A.csv` or `annotator_B.csv` file.
3. Enter `yes` or `no` for `plant_present` and `image_usable` on every row.
4. Enter pixel coordinates with the image origin at the upper-left corner. Record all visible landmarks allowed by the growth stage; leave a coordinate pair blank only when the landmark is not visible or does not apply.
5. Use the controlled values specified in the protocol for stage, occlusion, and confidence.
6. After both sheets are complete, run `python analysis/score_dual_annotations.py` from the repository root.

The sheets are intentionally blank. Their current presence documents a prospective annotation protocol and cannot be cited as completed inter-annotator validation until two people finish them.
