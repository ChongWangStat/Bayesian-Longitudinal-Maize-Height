# Maize pose checkpoint

## File and integrity

- File: `maize_pose_2021_best.pt`
- Format: Ultralytics PyTorch checkpoint
- Task recorded by the project: maize top/root pose estimation
- SHA-256: `d813f7176890fd04f478868f8834ceae0b6f05c9c88ddfc8910c8c695745a572`
- Release inference environment: Ultralytics 8.4.145, PyTorch 2.9.1, CPU

The released 61-image candidate cache was generated with image size 640, confidence threshold 0.05, intersection-over-union threshold 0.5, and at most 50 detections per image. It contains 320 candidates and at least one candidate for every image.

## Intended use

The checkpoint supports reproducible inference and candidate auditing on field maize images similar to the released 2021 set. It outputs plant instances with top and root keypoints. Physical height still requires a valid landmark definition, scale calibration, and camera geometry.

## Provenance limits

The archive identifies the model as a YOLOv8 pose checkpoint and preserves the final weights. It does not contain a complete immutable training manifest with the exact image list, software commit, augmentation configuration, training random seed, and original cross-validation masks. The checkpoint therefore enables inference but does not by itself reproduce original training. Reported out-of-fold detector metrics are released as derived per-instance outputs and are described as agreement with human mask extent rather than independent agronomic landmark validation.

## Known limitations

Performance can change with lighting, canopy overlap, occlusion, growth stage, camera geometry, and the definition of the plant top. The matched natural-image audit found no candidate-choice conflict under the prespecified gates, so the simulation benefit from height-prior candidate scoring should not be assumed for every field set. Two independent human annotations using the released protocol remain pending.
