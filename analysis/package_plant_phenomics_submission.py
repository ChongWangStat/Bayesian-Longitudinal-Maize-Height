#!/usr/bin/env python
"""Create the final Plant Phenomics special-issue upload package."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "journal_submissions"
    / "plant_phenomics_special_issue_2026"
    / "submission_source"
)
RELEASE_ROOT = ROOT.parents[1]
PACKAGE_NAME = "Plant_Phenomics_Special_Issue_Submission_v2.0.0_20260915"
PACKAGE_DIR = RELEASE_ROOT / PACKAGE_NAME
FINAL_ZIP = RELEASE_ROOT / f"{PACKAGE_NAME}_FINAL.zip"
STAGING = RELEASE_ROOT / ".plant_phenomics_anonymous_review_staging"

FIXED_ZIP_TIME = (2026, 9, 15, 12, 0, 0)
TEXT_SUFFIXES = {
    ".cff",
    ".csv",
    ".json",
    ".md",
    ".py",
    ".tex",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
FORBIDDEN_ANONYMOUS_PATTERNS = {
    "author given name": re.compile(
        r"Haoming|Chong\s+Wang|Yawei|Cheng-Ting|Patrick\s+S\.?\s+Schnable|Peng\s+Liu",
        re.IGNORECASE,
    ),
    "institution": re.compile(r"Iowa State|iastate\.edu", re.IGNORECASE),
    "public repository": re.compile(
        r"ChongWangStat|github\.com/ChongWangStat", re.IGNORECASE
    ),
    "source filename": re.compile(r"readme_Zaki_Yawei", re.IGNORECASE),
    "workstation path": re.compile(
        r"[A-Za-z]:[\\/](?:Users|Research)[\\/]", re.IGNORECASE
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reset_directory(path: Path, expected_parent: Path) -> None:
    resolved_parent = path.resolve().parent
    if resolved_parent != expected_parent.resolve():
        raise ValueError(f"Refusing to reset unexpected path: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path, *, py_only: bool = False) -> None:
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        if py_only and path.suffix.lower() != ".py":
            continue
        copy_file(path, destination / path.relative_to(source))


def write_deterministic_zip(destination: Path, entries: list[tuple[Path, str]]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for source, arcname in sorted(entries, key=lambda item: item[1].lower()):
            if not source.is_file():
                raise FileNotFoundError(source)
            info = zipfile.ZipInfo(arcname.replace("\\", "/"), FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())


def tree_entries(directory: Path) -> list[tuple[Path, str]]:
    return [
        (path, path.relative_to(directory).as_posix())
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]


def sanitize_anonymous_text(directory: Path) -> None:
    literal_replacements = {
        "Haoming Wang's": "the study annotator's",
        "Haoming Wang": "study annotator",
        "Chong Wang": "study author",
        "Yawei Li's": "the field team's",
        "Yawei Li": "field team member",
        "Yawei": "field team",
        "Cheng-Ting Yeh": "study author",
        "Patrick S. Schnable": "study author",
        "Peng Liu": "corresponding author",
        "wang26@iastate.edu": "",
        "pliu@iastate.edu": "",
        "Iowa State University": "home institution",
        "readme_Zaki_Yawei.docx": "legacy_field_height_protocol.docx",
        "Feedback for stationary camera project questions_yawei.docx": "legacy_stationary_camera_questions.docx",
        "Yawei settings table": "field-team camera-settings table",
        "https://github.com/ChongWangStat/Bayesian-Longitudinal-Maize-Height": "repository details supplied on the separate title page",
        "github.com/ChongWangStat/Bayesian-Longitudinal-Maize-Height": "repository details supplied on the separate title page",
    }
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for old, new in literal_replacements.items():
            text = text.replace(old, new)
        if path.suffix.lower() == ".xml":
            text = re.sub(r"<url>.*?</url>", "<url></url>", text)
            text = re.sub(
                r"<owner>.*?</owner>",
                "<owner>\n        <username>study_annotator</username>\n        <email></email>\n      </owner>",
                text,
                flags=re.DOTALL,
            )
        path.write_text(text, encoding="utf-8", newline="\n")


def audit_anonymous_tree(directory: Path) -> None:
    problems: list[str] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for label, pattern in FORBIDDEN_ANONYMOUS_PATTERNS.items():
            match = pattern.search(text)
            if match:
                problems.append(
                    f"{path.relative_to(directory).as_posix()}: {label}: {match.group(0)!r}"
                )
    if problems:
        raise ValueError("Anonymous archive audit failed:\n" + "\n".join(problems))


def build_anonymous_review_archive(destination: Path) -> None:
    reset_directory(STAGING, RELEASE_ROOT)
    analysis_destination = STAGING / "analysis"
    for source in sorted((ROOT / "analysis").glob("*.py")):
        if source.name in {
            "build_plant_phenomics_special_issue.py",
            "create_manual_height_protocol_2024.py",
            "package_plant_phenomics_submission.py",
        }:
            continue
        copy_file(source, analysis_destination / source.name)

    copy_tree(ROOT / "plant_height_app", STAGING / "plant_height_app")
    for name in (
        "requirements.txt",
        "requirements-core.txt",
        "environment.yml",
    ):
        copy_file(ROOT / name, STAGING / name)

    for name in (
        "maize_pose_2021_best.pt",
        "checkpoint_metadata.json",
        "MODEL_CARD.md",
    ):
        copy_file(ROOT / "models" / name, STAGING / "models" / name)

    copy_tree(
        ROOT / "data" / "raw" / "pole_calibration_images",
        STAGING / "data" / "raw" / "pole_calibration_images",
    )
    for name in ("manual_height_2024_long.csv", "camera_layout_2024.csv"):
        copy_file(
            ROOT / "data" / "raw" / "manual_height_2024" / name,
            STAGING / "data" / "raw" / "manual_height_2024" / name,
        )
    copy_file(
        ROOT / "data" / "raw" / "heights_compare_2021.csv",
        STAGING / "data" / "raw" / "heights_compare_2021.csv",
    )
    copy_tree(
        ROOT / "data" / "manual_annotations" / "poles_2021",
        STAGING / "data" / "manual_annotations" / "poles_2021",
    )
    copy_tree(ROOT / "data" / "processed", STAGING / "data" / "processed")
    copy_tree(ROOT / "data" / "reference", STAGING / "data" / "reference")
    copy_tree(ROOT / "outputs", STAGING / "outputs")
    copy_tree(ROOT / "manuscript" / "figures", STAGING / "manuscript" / "figures")
    copy_file(
        ROOT / "protocols" / "Manual_Height_Protocol_2024_Audited.pdf",
        STAGING / "protocols" / "Manual_Height_Protocol_2024_Audited.pdf",
    )

    metadata = json.loads(
        (
            ROOT / "data" / "raw" / "manual_height_2024" / "source_metadata.json"
        ).read_text(encoding="utf-8")
    )
    anonymous_metadata = {
        "source_workbook_label": "2024 manual-height workbook",
        "source_workbook_sha256": metadata["source_workbook_sha256"],
        "source_protocol_label": "legacy field-height protocol",
        "source_protocol_sha256": metadata["source_protocol_sha256"],
        "measurements": metadata["measurements"],
        "plants": metadata["plants"],
        "biological_rows": metadata["biological_rows"],
        "camera_layout_records": metadata["camera_layout_records"],
        "camera_pairs": metadata["camera_pairs"],
        "import_note": metadata["import_note"],
    }
    metadata_path = (
        STAGING / "data" / "raw" / "manual_height_2024" / "source_metadata.json"
    )
    metadata_path.write_text(
        json.dumps(anonymous_metadata, indent=2) + "\n", encoding="utf-8"
    )

    (STAGING / "LICENSE.txt").write_text(
        """MIT License

Copyright (c) 2026 The Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This license applies to code. Non-code data, images, annotations, model weights,
figures, and protocol materials are supplied for peer review; no separate reuse
license has been confirmed for those materials.
""",
        encoding="utf-8",
        newline="\n",
    )
    (STAGING / "README.md").write_text(
        """# Anonymous code, data, protocol, and application archive

This archive reproduces the reported analyses and provides a plant-scientist
application with dated longitudinal image examples. It contains no author names,
institutional identifiers, workstation paths, or public repository links.

## Reproduce the 2024 later-year validation

Use Python 3.12 or 3.13, create an isolated environment, install
`requirements-core.txt`, and run:

```bash
python analysis/validate_manual_height_transfer_2024.py --repo-root . --output-dir reproduced/manual_height_transfer_2024
```

Expected matched validation counts are 166 plant-date records, 34 plants, six
camera views, and four biological rows. Expected Bayesian longitudinal results
are 17.36 cm MAE, 22.41 cm RMSE, and Pearson correlation 0.847. The matched
Gaussian local-linear comparator is practically tied at 17.35 cm MAE and 22.42
cm RMSE. The biological row, containing its paired left/right camera views, is
the resampling unit.

The 2024 manual outcomes are joined only after predictions have been produced.
The larger 2024 raw-image archive is not included; the derived daily image
records needed for numerical reproduction are included. The 61 curated 2021
images, physical-reference annotations, pose checkpoint, and cached candidates
support the documented image-analysis and calibration checks.

## Run the plant-height application

Install `plant_height_app/requirements.txt`, then run:

```bash
streamlit run plant_height_app/app.py
```

The application accepts fixed-camera images and dates and returns each plant's
height as a function of study day, uncertainty intervals, quality flags, and
annotated images. Built-in multi-date examples are in
`plant_height_app/examples/`.

## Protocol and rights

The audited manual-height and camera-pair protocol is
`protocols/Manual_Height_Protocol_2024_Audited.pdf`. Code is provided under the
MIT License. Non-code materials are supplied for peer review; no separate reuse
license has been confirmed.
""",
        encoding="utf-8",
        newline="\n",
    )

    sanitize_anonymous_text(STAGING)
    audit_anonymous_tree(STAGING)
    manifest_lines = [
        f"{sha256(path)}  {path.relative_to(STAGING).as_posix()}"
        for path in sorted(STAGING.rglob("*"))
        if path.is_file() and path.name != "MANIFEST_SHA256.txt"
    ]
    (STAGING / "MANIFEST_SHA256.txt").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8", newline="\n"
    )
    write_deterministic_zip(destination, tree_entries(STAGING))


def build_source_archives() -> None:
    source_names = [
        "01_anonymized_manuscript.tex",
        "03_anonymized_supplement.tex",
        "references.bib",
        "numbers.tex",
        "numbers_2024.tex",
        "per_plant_table.tex",
        "elsarticle.cls",
        "elsarticle-harv.bst",
    ]
    entries = [(SOURCE / name, name) for name in source_names]
    entries.extend(
        (path, f"figures/{path.name}")
        for path in sorted((SOURCE / "figures").iterdir())
        if path.is_file()
    )
    readme = PACKAGE_DIR / ".anonymous_source_readme.txt"
    readme.write_text(
        "Compile 01_anonymized_manuscript.tex and 03_anonymized_supplement.tex with pdflatex/bibtex. The package uses the official Elsevier elsarticle class v3.5 dated 9 January 2026.\n",
        encoding="utf-8",
        newline="\n",
    )
    entries.append((readme, "README.txt"))
    write_deterministic_zip(PACKAGE_DIR / "06_ANONYMIZED_LATEX_SOURCE.zip", entries)
    readme.unlink()

    identified_entries = [
        (SOURCE / "02_title_page.tex", "02_title_page.tex"),
        (SOURCE / "04_cover_letter.tex", "04_cover_letter.tex"),
        (SOURCE / "elsarticle.cls", "elsarticle.cls"),
        (SOURCE / "numbers.tex", "numbers.tex"),
        (SOURCE / "numbers_2024.tex", "numbers_2024.tex"),
    ]
    write_deterministic_zip(
        PACKAGE_DIR / "07_TITLE_AND_COVER_LATEX_SOURCE.zip", identified_entries
    )


def build_package() -> dict[str, object]:
    reset_directory(PACKAGE_DIR, RELEASE_ROOT)
    copy_map = {
        "01_anonymized_manuscript.pdf": "01_ANONYMIZED_MANUSCRIPT.pdf",
        "02_title_page.pdf": "02_TITLE_PAGE.pdf",
        "03_anonymized_supplement.pdf": "03_ANONYMIZED_SUPPLEMENT.pdf",
        "04_cover_letter.pdf": "04_COVER_LETTER.pdf",
        "05_highlights.txt": "05_HIGHLIGHTS.txt",
        "06_portal_metadata.md": "PORTAL_METADATA.md",
        "07_submission_checklist.md": "SUBMISSION_CHECKLIST.md",
    }
    for source_name, destination_name in copy_map.items():
        copy_file(SOURCE / source_name, PACKAGE_DIR / destination_name)

    build_source_archives()
    figures = {
        "online_bayesian_workflow.pdf": "Figure_1_Workflow.pdf",
        "pole_annotation_2021.pdf": "Figure_2_Physical_References.pdf",
        "manual_height_transfer_2024.pdf": "Figure_3_Temporal_Validation.pdf",
        "prior_in_detection_sim.pdf": "Figure_4_Prior_Guided_Ambiguity.pdf",
        "geometry_diagram.png": "Supplementary_Figure_S1_Geometry.png",
        "bayesian_trajectories.png": "Supplementary_Figure_S2_Trajectories.png",
        "uncertainty_calibration.pdf": "Supplementary_Figure_S3_Uncertainty.pdf",
    }
    for source_name, destination_name in figures.items():
        copy_file(
            SOURCE / "figures" / source_name,
            PACKAGE_DIR / "08_FIGURES" / destination_name,
        )

    copy_file(
        ROOT / "protocols" / "Manual_Height_Protocol_2024_Audited.pdf",
        PACKAGE_DIR / "09_MANUAL_HEIGHT_PROTOCOL_2024_AUDITED.pdf",
    )
    build_anonymous_review_archive(PACKAGE_DIR / "10_ANONYMOUS_REVIEW_CODE_DATA.zip")

    (PACKAGE_DIR / "SUBMISSION_FILE_GUIDE.md").write_text(
        """# Plant Phenomics submission file guide

Use the journal's Methods Article route and choose special-issue category
`VSI: PMBDA2025`.

1. Upload `01_ANONYMIZED_MANUSCRIPT.pdf` as the anonymous manuscript review copy.
2. Upload `06_ANONYMIZED_LATEX_SOURCE.zip` as editable manuscript source. The
   journal system uses the `.tex`, `.bib`, `.bst`, `.cls`, and figure files to
   generate the review PDF.
3. Upload `02_TITLE_PAGE.pdf` separately as the title page. Its editable source
   is in `07_TITLE_AND_COVER_LATEX_SOURCE.zip`.
4. Upload `03_ANONYMIZED_SUPPLEMENT.pdf`,
   `09_MANUAL_HEIGHT_PROTOCOL_2024_AUDITED.pdf`, and
   `10_ANONYMOUS_REVIEW_CODE_DATA.zip` as supplementary files for review.
5. Upload the four main files in `08_FIGURES/` separately if the portal requests
   individual figures. All seven main and supplementary figure sources are also
   present in the anonymous LaTeX source archive.
6. Paste `05_HIGHLIGHTS.txt` into the Highlights field and use
   `PORTAL_METADATA.md` for title, abstract, keywords, author order, funding, and
   declarations.
7. Upload `04_COVER_LETTER.pdf` as the cover letter.

The internal acceptance estimate is intentionally excluded from this upload
package. Reviewer nominations must be selected in the portal after the authors
screen candidates for conflicts; none are invented in these files.
""",
        encoding="utf-8",
        newline="\n",
    )

    provenance = (
        ROOT
        / "journal_submissions"
        / "plant_phenomics_special_issue_2026"
        / "TEMPLATE_PROVENANCE.md"
    )
    provenance.write_text(
        f"""# Elsevier LaTeX template provenance

- Class: `elsarticle`
- Version: 3.5
- Release date embedded in class: 9 January 2026
- Distribution source: https://ctan.org/pkg/elsarticle
- Bundled class SHA-256: `{sha256(SOURCE / "elsarticle.cls")}`
- Bundled author-year style SHA-256: `{sha256(SOURCE / "elsarticle-harv.bst")}`

Plant Phenomics accepts LaTeX as editable source. The submission portal compiles
that source into the PDF used for review; PDF alone is not the editable source.
""",
        encoding="utf-8",
        newline="\n",
    )
    copy_file(provenance, PACKAGE_DIR / "TEMPLATE_PROVENANCE.md")

    package_manifest = [
        f"{sha256(path)}  {path.relative_to(PACKAGE_DIR).as_posix()}"
        for path in sorted(PACKAGE_DIR.rglob("*"))
        if path.is_file() and path.name != "MANIFEST_SHA256.txt"
    ]
    (PACKAGE_DIR / "MANIFEST_SHA256.txt").write_text(
        "\n".join(package_manifest) + "\n", encoding="utf-8", newline="\n"
    )
    write_deterministic_zip(FINAL_ZIP, tree_entries(PACKAGE_DIR))

    if STAGING.exists():
        shutil.rmtree(STAGING)
    return {
        "package_directory": str(PACKAGE_DIR),
        "final_zip": str(FINAL_ZIP),
        "final_zip_sha256": sha256(FINAL_ZIP),
        "package_files": len([p for p in PACKAGE_DIR.rglob("*") if p.is_file()]),
        "anonymous_review_zip_bytes": (
            PACKAGE_DIR / "10_ANONYMOUS_REVIEW_CODE_DATA.zip"
        )
        .stat()
        .st_size,
    }


if __name__ == "__main__":
    print(json.dumps(build_package(), indent=2))
