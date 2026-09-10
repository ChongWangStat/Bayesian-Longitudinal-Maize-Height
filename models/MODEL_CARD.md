# Maize pose checkpoint

## File and integrity

- File: `maize_pose_2021_best.pt`
- Format: Ultralytics PyTorch checkpoint
- Task recorded by the project: maize top/root pose estimation
- SHA-256: `d813f7176890fd04f478868f8834ceae0b6f05c9c88ddfc8910c8c695745a572`
- Release inference environment: Ultralytics 8.4.145, PyTorch 2.9.1, CPU

## Recovered embedded training record

The checkpoint itself records training on 1 December 2025 with Ultralytics 8.3.233, starting from `yolov8n-pose.pt`. It records 150 epochs, image size 1024, batch size 8, Apple MPS execution, random seed 0, deterministic mode enabled, validation enabled, and the complete saved optimizer and augmentation arguments. The recorded dataset reference is the relative path `yolo_dataset/dataset.yaml`. Summary validation metrics and a machine-readable copy of the embedded training arguments are preserved in `checkpoint_metadata.json`.

The released 61-image candidate cache was generated with image size 640, confidence threshold 0.05, intersection-over-union threshold 0.5, and at most 50 detections per image. It contains 320 candidates and at least one candidate for every image.

## Intended use

The checkpoint supports reproducible inference and candidate auditing on field maize images similar to the released 2021 set. It outputs plant instances with top and root keypoints. Physical height still requires a valid landmark definition, scale calibration, and camera geometry.

## Provenance limits

The archive identifies the model as a YOLOv8 pose checkpoint and preserves the final weights and embedded training configuration. It does not contain the referenced `dataset.yaml`, a complete immutable list of training and validation images, the original training masks, or a software source commit; the checkpoint's embedded Git fields are empty. It therefore supports exact inference with the released weights but does not by itself reproduce construction of the original training split. Reported out-of-fold detector metrics come from the separately documented five-fold evaluation and are released as derived per-instance outputs; they are described as agreement with human mask extent rather than independent agronomic landmark validation.

## Known limitations

Performance can change with lighting, canopy overlap, occlusion, growth stage, camera geometry, and the definition of the plant top. The matched natural-image audit found no candidate-choice conflict under the prespecified gates, so the simulation benefit from height-prior candidate scoring should not be assumed for every field set.
