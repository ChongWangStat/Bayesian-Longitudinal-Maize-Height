# Current project handoff: prior-guided Bayesian longitudinal maize phenotyping

**Handoff date:** 15 September 2026
**Workspace root:** `D:\Research\LongitudinalPlantImaging`
**Current journal target:** *Plant Phenomics*
**Article type:** Methods Article
**Special issue:** Plant Modeling, Big Data Analytics, and High-Throughput Phenotyping for Smart Agriculture
**Portal category:** `VSI: PMBDA2025`
**Special-issue deadline:** 31 October 2026
**Manuscript title:** “Prior-guided image analysis for Bayesian longitudinal maize height phenotyping with fixed cameras”

This is the current handoff authority. It supersedes the earlier Plant Phenomics
delivery note, The Plant Phenome Journal package, and handoff dated 14 September
2026. The paper has been prepared and packaged but has not been submitted through
the journal portal in this work session.

## Open these first

| Purpose | Authoritative location |
|---|---|
| Editable Git project | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\github_release\Bayesian-Longitudinal-Maize-Height` |
| Final Plant Phenomics upload ZIP | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\Plant_Phenomics_Special_Issue_Submission_v2.0.0_20260915_FINAL.zip` |
| Unpacked upload package | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\Plant_Phenomics_Special_Issue_Submission_v2.0.0_20260915` |
| Journal-specific editable source | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\github_release\Bayesian-Longitudinal-Maize-Height\journal_submissions\plant_phenomics_special_issue_2026\submission_source` |
| Audited 2024 protocol, Word | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\github_release\Bayesian-Longitudinal-Maize-Height\protocols\Manual_Height_Protocol_2024_Audited.docx` |
| Audited 2024 protocol, PDF | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\github_release\Bayesian-Longitudinal-Maize-Height\protocols\Manual_Height_Protocol_2024_Audited.pdf` |
| 2024 validation summary | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\github_release\Bayesian-Longitudinal-Maize-Height\outputs\manual_height_transfer_2024\validation_summary.json` |
| Latest standalone application | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\Bayesian_Plant_Height_App_v1.1.0.zip` |
| Unpacked application | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\Bayesian_Plant_Height_App_v1.1.0_RELEASE_FINAL` |
| Separate six-plant example | `D:\Research\LongitudinalPlantImaging\publication_review_2026-09-08\C-029_Six_Plant_Longitudinal_Example_v1.0.zip` |
| Latest journal master list | `C:\Users\chwang\Box\Research\99 99 Students\Publication_Targets_2026_FINAL_Comprehensive_v4.docx` |
| Source 2024 workbook | `D:\Research\LongitudinalPlantImaging\2024 stationary camera height ground truth.xlsx` |
| Source legacy protocol | `D:\Research\LongitudinalPlantImaging\readme_Zaki_Yawei.docx` |

For journal submission, use the v2.0.0 Plant Phenomics ZIP. For editing or new
analysis, work in the Git repository and rebuild the package. For collaborators
who only need the image-to-height tool, share the v1.1.0 application ZIP and the
six-plant example as needed.

## Integrity hashes

| Artifact | SHA-256 |
|---|---|
| Plant Phenomics final ZIP | `b003422faa5fc868b1681ef1a248a0b432885287df7d3a42d2018fd33d5d3d6d` |
| Plant-height application v1.1.0 ZIP | `44ffea29f545b69c6ea8bd228f898a8cb648c6b2c03538a4c3db00b4afef8d61` |
| Six-plant example ZIP | `82ff268efb5ad30af6c4b5c0919ce859b0456eb39a7b7851a87568127604342e` |
| Source 2024 workbook | `7e8444766cde7fa827358597105dfceacd2654b9d82d937df514aee8f7ae1369` |
| Source legacy protocol | `32670e26b875dc7454f8bfe0ac019c96f447e650bca7355f9661261a526a6c16` |

The final upload package contains 21 files. Its `MANIFEST_SHA256.txt` was checked
with zero mismatches. The nested anonymous code/data archive contains 232 files;
its own manifest also checked with zero mismatches.

## Scientific design and interpretation

The paper’s main contribution is the placement of longitudinal information inside
analysis of each new image. Earlier images form a predictive state that guides
plant association and can score competing top candidates before a height is
committed. The term “filtering” describes this sequential update: a predictive
distribution is propagated to the next image and then updated with that image.
Every output is prefix-causal. Future images are added to the pool as time moves
forward and never revise an already emitted height.

The primary validation now has a proper temporal direction:

- 2021: 61 matched image/manual development records in six camera rows fit the
  transfer equation and quantify leave-one-camera-row-out transfer error.
- 2024: all manual outcomes are held out until automated predictions are complete.
- Annual replanting means the 2024 plants are different biological subjects from
  those used in 2021.
- The 2024 image tracks had previously been used without their manual labels during
  pipeline development. The supported description is therefore **later-year,
  subject-disjoint, label-held-out temporal field validation**, not fully external-site
  validation.

The Camera layout sheet defines four biological rows, each observed by a paired
left/right camera layout:

| Biological row | Left camera, plants 7–12 | Right camera, plants 1–6 |
|---|---|---|
| M-0006 | NL5RH | NGGJK |
| M-0013 | NH888 | NGFZT |
| W-0010 | NH88X | NJQMT |
| W-0015 | NGFY5 | NH88L |

The two views are measurement views inside one biological row. They are not eight
independent rows. All bootstrap resampling uses the four biological rows and keeps
both views, every plant, and every date together. Six camera views contribute to
the matched analysis because W-0010 right has no pose output and W-0015 left has
no QC-eligible output.

## 2024 workbook and matching

- 247 nonmissing manual heights from 45 plants in four biological rows.
- 54 records belong to the two unavailable camera halves.
- 27 additional records have no same-date QC-eligible automated output.
- 166 matched plant-date records remain from 34 plants, four biological rows, six
  camera views, and seven unique dates.
- Matching is by calendar date. Absolute manual-image time lag has median 2.78 h,
  mean 2.69 h, and maximum 6.90 h.
- Plants are numbered right-to-left across the biological row. Right-camera local
  IDs 1–6 map to global IDs 1–6; left-camera local IDs map to 7–12.
- The workbook does not identify whether the pre-tasseling value used Method 1
  (topmost plant point touching the stick) or Method 2 (topmost fully visible
  collar). Manuscript and protocol therefore call the outcome “manual field height.”

## Primary results

| Estimator | Bias (cm) | MAE (cm) | RMSE (cm) | Pearson r |
|---|---:|---:|---:|---:|
| Single frame | -13.486 | 18.103 | 23.539 | 0.8129 |
| EWMA, alpha 0.5 | -16.456 | 19.698 | 24.442 | 0.8469 |
| Running median, 3 images | -16.264 | 19.937 | 24.658 | 0.8350 |
| Holt, alpha 0.5 and beta 0.2 | -13.651 | 17.603 | 22.634 | 0.8429 |
| Gaussian local-linear, matched prior | -13.224 | 17.348 | 22.423 | 0.8457 |
| Bayesian longitudinal particle method | -13.245 | 17.361 | 22.409 | 0.8467 |

The Bayesian method improves MAE over the single-frame estimate by 0.742 cm. The
95% four-row cluster interval is -0.442 to 1.302 cm. Improvements over EWMA and
the running median are 2.336 and 2.576 cm, with row-cluster intervals excluding
zero. The Holt difference is small and uncertain. The matched Gaussian model has
0.013 cm lower MAE while the particle method has 0.013 cm lower RMSE; this is a
practical tie and is stated throughout the paper.

Transfer-aware interval results:

| Nominal level | Coverage | Mean width |
|---:|---:|---:|
| 50% | 53.0% | 27.6 cm |
| 80% | 78.9% | 56.0 cm |
| 90% | 90.4% | 76.4 cm |
| 95% | 97.0% | 97.5 cm |

## Physical calibration audit

The 2024 field record documents an approximately vertical 8–10 ft pole with red
marks 1 ft apart edge-to-edge. The visible pole bottom is not assumed to be ground.
Among 237 accepted automatic calibration candidates, 89 implied more than 10 ft;
1,296 of 1,302 filtered image records used a reference span over 10 ft. The old
automatic red-component enumeration is therefore excluded from the headline
absolute 2024 comparison. The analysis uses the 2021 development calibration and
the independently recorded camera-distance ratio 8.5/10.25 = 0.829268.

## Journal-specific manuscript

The journal source uses the official Elsevier `elsarticle` class version 3.5,
released 9 January 2026. *Plant Phenomics* accepts LaTeX as editable source; the
submission system builds the PDF used for review. The main review manuscript is
19 pages, the supplement is 25 pages, the title page is two pages, and the cover
letter is one page.

Verified main-manuscript limits:

- Abstract: 225 words.
- Keywords: seven.
- Main figures: four.
- Main tables: four.
- Unique cited references: 19.
- No unresolved references, missing citations, overfull text, author identifiers,
  public repository links, or incomplete fields occur in the anonymous files.

The upload directory contains:

- `01_ANONYMIZED_MANUSCRIPT.pdf`
- `02_TITLE_PAGE.pdf`
- `03_ANONYMIZED_SUPPLEMENT.pdf`
- `04_COVER_LETTER.pdf`
- `05_HIGHLIGHTS.txt`
- `06_ANONYMIZED_LATEX_SOURCE.zip`
- `07_TITLE_AND_COVER_LATEX_SOURCE.zip`
- `08_FIGURES\` with four main and three supplementary figure files
- `09_MANUAL_HEIGHT_PROTOCOL_2024_AUDITED.pdf`
- `10_ANONYMOUS_REVIEW_CODE_DATA.zip`
- portal metadata, checklist, template provenance, upload guide, and SHA-256 manifest.

The internal acceptance estimate is in the repository source folder as
`08_editorial_fit_and_acceptance_estimate.md` and is deliberately excluded from
the upload package.

## Reproduction and validation performed

- The validation script was run from the Git working tree and from a fresh
  extraction of `10_ANONYMOUS_REVIEW_CODE_DATA.zip`; both produced the exact
  headline counts and metrics above.
- The anonymous LaTeX source ZIP was extracted and independently compiled into
  the 19-page manuscript and 25-page supplement.
- The identified title/cover source ZIP was extracted and independently compiled
  into the two-page title file and one-page cover letter.
- The protocol was rendered through Microsoft Word to a five-page letter-size PDF
  and all pages were visually inspected.
- The main manuscript and supplement were rendered as page images and visually
  inspected after the final comparator and camera-pair revisions.
- Python style checks pass for all new analysis, build, protocol, and package scripts.

## Plant-scientist application

The application accepts dated fixed-camera images and returns per-plant height as
a function of study day or calendar date, with 80% and 95% intervals, growth
estimates, quality flags, annotated images, and downloadable plots and tables.
Daily imaging at a similar time is preferred; daily, 3-day, 7-day, 30-day, and
irregular intervals were previously tested.

The v1.1.0 package includes the C-024 four-date and C-004 five-date built-in
examples. The separate C-029 ZIP demonstrates six plants in the normal upload
workflow without changing application code. The previous local address
`http://127.0.0.1:8766` is a computer-local preview, not durable public hosting.
Collaborators should currently download the application package or repository and
run it locally.

## Git and release workflow

- Public repository: `https://github.com/ChongWangStat/Bayesian-Longitudinal-Maize-Height`
- Branch: `main`
- Pre-workbook code lock: `59b42b74596c598017fdb0cd4b80af1aec7649d6`
- Plant Phenomics release tag: `v2.0.0`

To rebuild the validation:

```bash
python analysis/validate_manual_height_transfer_2024.py
```

To rebuild the journal source after numerical outputs are current:

```bash
python analysis/build_plant_phenomics_special_issue.py
```

Compile the four `.tex` files in the submission source with `latexmk -pdf`, then
build the frozen upload package:

```bash
python analysis/package_plant_phenomics_submission.py
```

The package script creates deterministic nested ZIP files, audits the anonymous
text, generates both manifests, and writes the final ZIP under
`publication_review_2026-09-08`.

## Author, funding, and declaration record

Author order: Haoming Wang; Chong Wang; Yawei Li; Cheng-Ting Yeh; Patrick S.
Schnable; Peng Liu.

- Haoming Wang performed physical-reference annotation and contributed to writing,
  code, simulation, analysis, and validation.
- Yawei Li performed the field work and contributed data curation, resources,
  validation, and revision.
- Patrick S. Schnable contributed experimental design, funding acquisition,
  resources, supervision, and revision.
- Haoming Wang, Chong Wang, and Peng Liu contributed the manuscript, coding,
  simulation, analysis, visualization, validation, and revision.
- Cheng-Ting Yeh contributed validation and manuscript revision.
- All authors approved the final manuscript.

Funding is recorded from the Plant Sciences Institute at Iowa State University and
the Laurence H. Baker Center for Bioinformatics and Biological Statistics. No
conflict of interest is declared. Code is MIT licensed. No separate reuse license
has been confirmed for data, images, annotations, model weights, figures, or
manuscript materials.

## Remaining portal-only actions

The static files are complete. During submission, select `VSI: PMBDA2025`, confirm
the final author metadata, and nominate at least two qualified reviewers after the
authors screen them for recent collaboration, institutional overlap, and other
conflicts. Reviewer identities were not invented in the package.
