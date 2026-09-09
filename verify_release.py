#!/usr/bin/env python3
"""Check the public release assets and the principal reported values."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
EXPECTED_MODEL_SHA256 = "d813f7176890fd04f478868f8834ceae0b6f05c9c88ddfc8910c8c695745a572"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def near(value: float, expected: float, tolerance: float = 0.015) -> None:
    if abs(value - expected) > tolerance:
        raise AssertionError(f"Expected {expected}, found {value}")


def main() -> None:
    images = sorted((ROOT / "data/raw/pole_calibration_images").glob("*.JPG"))
    assert len(images) == 61, len(images)
    assert not (ROOT / "data/raw/pole_calibration_images/C-039_2021-07-30JPG.JPG").exists()
    assert (ROOT / "data/raw/pole_calibration_images/C-039_2021-07-30.JPG").exists()
    assert len(list((ROOT / "data/manual_annotations/poles_2021").glob("C-*.xml"))) == 12
    assert sha256(ROOT / "models/maize_pose_2021_best.pt") == EXPECTED_MODEL_SHA256

    tex = (ROOT / "manuscript/main.tex").read_text(encoding="utf-8")
    title = re.search(r"\\title\{(.*?)\}", tex, flags=re.S).group(1)
    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, flags=re.S).group(1)
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", abstract)
    assert len(title) <= 100, len(title)
    assert len(words) <= 250, len(words)
    assert "Longitudinal" in title and "longitudinal" in abstract.lower()
    assert (ROOT / "manuscript/main.pdf").stat().st_size > 100_000
    assert (ROOT / "manuscript/supplement.pdf").stat().st_size > 100_000

    field = json.loads((ROOT / "outputs/field_baselines_2021/summary.json").read_text())
    fm = {row["estimator"]: row for row in field["metrics"]}
    near(fm["Robust Bayesian particle filter"]["mae_cm"], 10.96718)
    near(fm["Gaussian local-linear Kalman filter"]["mae_cm"], 11.62270)

    unc = json.loads((ROOT / "outputs/uncertainty_revision/summary.json").read_text())
    test95 = next(
        row for row in unc["intervals"]
        if row["model"] == "unit_consistent"
        and row["split"] == "2025_locked_test"
        and row["nominal_coverage"] == 0.95
    )
    near(test95["empirical_coverage"], 0.9489247, 1e-6)
    near(test95["mean_width_cm"], 97.83876)

    real = json.loads((ROOT / "outputs/real_image_candidate_ablation_2021/summary.json").read_text())
    near(real["selection_agreement"], 1.0, 1e-12)

    for name in ("annotator_A.csv", "annotator_B.csv"):
        sheet = pd.read_csv(ROOT / "annotation" / name, keep_default_na=False)
        assert len(sheet) == 366
        assert (sheet["plant_present"].astype(str).str.strip() == "").all()

    forbidden = ("C:" + "\\Users\\", "gh" + "o_", "file:" + "//")
    text_suffixes = {".py", ".md", ".tex", ".bib", ".csv", ".json", ".yml", ".yaml", ".cff", ".txt"}
    bad: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in text_suffixes:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if any(token in content for token in forbidden):
                bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"Machine-specific paths or credential-like strings in: {bad}"

    report = {
        "status": "pass", "images": 61, "xml_files": 12,
        "model_sha256": EXPECTED_MODEL_SHA256,
        "title_characters": len(title), "abstract_words": len(words),
        "field_particle_filter_mae_cm": fm["Robust Bayesian particle filter"]["mae_cm"],
        "heldout_2025_coverage_95": test95["empirical_coverage"],
        "heldout_2025_mean_width_cm": test95["mean_width_cm"],
        "annotation_status": "two blank independent sheets prepared; human passes pending",
    }
    (ROOT / "RELEASE_VALIDATION.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
