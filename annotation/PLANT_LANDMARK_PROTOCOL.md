# 2021 maize plant-landmark protocol

## Purpose and measurement definitions

The annotation supports a two-reader evaluation of image landmark uncertainty. The 2021 field records define two pre-tasseling manual measurements: (1) ground to the topmost plant point touching a meter stick and (2) ground to the topmost fully visible collar. After tasseling, the recorded height is ground to the flag leaves; tassel height is excluded. The primary manuscript field-height column came from the `_ft(cm)` fields and therefore corresponds to measurement 1. Because a photograph cannot reproduce physical meter-stick contact exactly, the image packet records the highest visible plant point as its closest image analogue and also records the collar and flag-leaf landmarks separately.

## Blinding and order

- Annotators work independently and do not inspect detector outputs, manual field heights, model estimates, or the other annotator's file.
- Identify plants from right to left as slots 1 through 6, matching the field convention. A row may have fewer than six living plants.
- Review images in the supplied manifest order. Do not use later images to change an earlier annotation.

## Required fields

- `plant_present`: `yes` or `no`.
- `image_usable`: `yes` or `no`. Use `no` only when the plant cannot be identified or neither top nor ground-contact landmark can be placed.
- `growth_stage`: `pre_tassel`, `post_tassel`, or `uncertain`.
- `highest_visible_*`: the highest visible pixel belonging to the focal plant. Do not include the tassel.
- `top_visible_collar_*`: the center of the topmost fully visible leaf collar, when visible.
- `flag_leaf_tip_*`: the highest point of the flag leaf after tasseling, when identifiable. Do not mark the tassel tip.
- `ground_contact_*`: the center of the stalk where it meets the soil. If hidden, place the best inferred contact and mark base occlusion.
- `top_occlusion` and `base_occlusion`: `none`, `partial`, or `severe`.
- `confidence`: `high`, `medium`, or `low`.
- `notes`: briefly record overlap, lodging, unclear identity, or another reason for low confidence.

Coordinates use the original 773-by-1030 pixel images: x increases to the right and y increases downward. Click the landmark itself rather than the edge of a marker. If `plant_present=no`, leave landmark coordinates blank. If `image_usable=no`, retain any confident coordinates but explain the failure in `notes`.

## Quality control

Before returning a sheet, confirm that every row has `plant_present` and `image_usable`, coordinate pairs are complete (both x and y or neither), coordinates lie inside the image, and the ground-contact y coordinate is below the chosen top y coordinate. Revisit all low-confidence and severely occluded annotations once without consulting the other reader.
