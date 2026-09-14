#!/usr/bin/env python3
"""Check the public release assets and the principal reported values."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
EXPECTED_MODEL_SHA256 = (
    "d813f7176890fd04f478868f8834ceae0b6f05c9c88ddfc8910c8c695745a572"
)


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
    assert not (
        ROOT / "data/raw/pole_calibration_images/C-039_2021-07-30JPG.JPG"
    ).exists()
    assert (ROOT / "data/raw/pole_calibration_images/C-039_2021-07-30.JPG").exists()
    assert (
        len(list((ROOT / "data/manual_annotations/poles_2021").glob("C-*.xml"))) == 12
    )
    pole_audit = json.loads(
        (ROOT / "data/processed/manual_poles_2021/summary.json").read_text()
    )
    assert pole_audit["retained_unique_images"] == 61
    assert pole_audit["annotations"] == 199
    assert pole_audit["usable_annotations"] == 172
    assert pole_audit["unusable_annotations"] == 27
    pole_repeatability = json.loads(
        (ROOT / "outputs/pole_repeatability_2021/summary.json").read_text()
    )
    assert pole_repeatability["design"]["usable_annotations"] == 172
    assert pole_repeatability["design"]["repeated_row_pole_series"] == 39
    assert pole_repeatability["design"]["stationary_camera_rows"] == 12
    assert pole_repeatability["series_below_5_percent_cv"] == 38
    near(pole_repeatability["median_cv_percent"], 1.236596, 1e-6)
    assert sha256(ROOT / "models/maize_pose_2021_best.pt") == EXPECTED_MODEL_SHA256
    checkpoint_metadata = json.loads(
        (ROOT / "models/checkpoint_metadata.json").read_text(encoding="utf-8")
    )
    assert checkpoint_metadata["sha256"] == EXPECTED_MODEL_SHA256
    assert checkpoint_metadata["ultralytics_version"] == "8.3.233"
    assert checkpoint_metadata["train_args"]["seed"] == 0
    assert checkpoint_metadata["train_args"]["deterministic"] is True
    assert checkpoint_metadata["train_args"]["epochs"] == 150
    assert checkpoint_metadata["train_args"]["imgsz"] == 1024

    with (ROOT / "outputs/crop_positions_2021/crop_positions.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        crop_positions = list(csv.DictReader(handle))
    assert len(crop_positions) == 87
    crop_keys = {(row["rowid"], row["date_md"], row["plant"]) for row in crop_positions}
    assert len(crop_keys) == 87
    assert len({row["rowid"] for row in crop_positions}) == 7
    assert min(float(row["match_score"]) for row in crop_positions) >= 0.98

    with (ROOT / "data/raw/heights_compare_2021.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        primary_rows = list(csv.DictReader(handle))
    recovered_primary = [
        row
        for row in primary_rows
        if (row["rowid"], row["date_md"], row["plantid"]) in crop_keys
    ]
    assert len(recovered_primary) == 63
    assert len({row["rowid"] for row in recovered_primary}) == 6

    tex = (ROOT / "manuscript/main.tex").read_text(encoding="utf-8")
    title = re.search(
        r"\\newcommand\{\\manuscripttitle\}\{(.*?)\}", tex, flags=re.DOTALL
    ).group(1)
    abstract = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, flags=re.DOTALL
    ).group(1)
    abstract_plain = re.sub(r"\\textit\{([^{}]*)\}", r"\1", abstract)
    abstract_plain = abstract_plain.replace(r"\%", "%")
    abstract_plain = re.sub(r"\s+", " ", abstract_plain).strip()
    words = abstract_plain.split()
    title_words = re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", title)
    assert len(title) <= 100, len(title)
    assert 10 <= len(title_words) <= 12, len(title_words)
    assert len(abstract_plain) <= 1500, len(abstract_plain)
    assert len(words) <= 250, len(words)
    assert "Bayesian longitudinal" in title and "longitudinal" in abstract.lower()
    assert title.startswith("Prior-guided image analysis")
    assert "94.7" in abstract and "manual heights" in abstract
    plain_summary = re.search(
        r"\\section\*\{Plain Language Summary\}\s*(.*?)\n\n\\begin\{abstract\}",
        tex,
        flags=re.DOTALL,
    ).group(1)
    plain_summary = re.sub(r"\s+", " ", plain_summary).strip()
    assert len(plain_summary) <= 1000, len(plain_summary)
    assert r"\doublespacing" in tex and r"\linenumbers" in tex
    assert "style=apa" in tex
    assert r"\documentclass[12pt,letterpaper]{article}" in tex
    assert r"\usepackage[margin=1in]{geometry}" in tex
    assert r"\usepackage{newtxtext}" in tex and r"\usepackage{newtxmath}" in tex
    assert "2438 Osborn Drive" in tex and "50011-1090" in tex
    assert "0000-0002-2093-8018" in tex
    front_order = [
        tex.index(r"\textbf{Affiliations.}"),
        tex.index(r"\textbf{Abbreviations.}"),
        tex.index(r"\section*{Plain Language Summary}"),
        tex.index(r"\begin{abstract}"),
    ]
    assert front_order == sorted(front_order)
    section_order = [
        tex.index(r"\section{Introduction}"),
        tex.index(r"\section{Materials and Methods}"),
        tex.index(r"\section{Results}"),
        tex.index(r"\section{Discussion}"),
        tex.index(r"\subsection{Conclusions}"),
    ]
    assert section_order == sorted(section_order)
    assert (ROOT / "manuscript/main.pdf").stat().st_size > 100_000
    assert (ROOT / "manuscript/supplement.pdf").stat().st_size > 100_000

    field = json.loads((ROOT / "outputs/field_baselines_2021/summary.json").read_text())
    assert field["design"]["records"] == 132
    assert field["design"]["plants"] == 33
    assert field["design"]["rows"] == 12
    assert field["design"]["dates"] == 5
    assert field["design"]["manual_height_used_for_tuning"] is False
    fm = {row["estimator"]: row for row in field["metrics"]}
    near(fm["Robust Bayesian particle filter"]["mae_cm"], 10.96718)
    near(fm["Gaussian local-linear Kalman filter"]["mae_cm"], 11.62270)
    positive_comparators = [
        "EWMA (alpha=0.5)",
        "Running median (three images)",
        "Holt level-trend (alpha=0.5, beta=0.2)",
    ]
    assert all(fm[name]["ci95_cm"][0] > 0 for name in positive_comparators)
    assert fm["Single-frame image extent"]["ci95_cm"][0] < 0
    assert fm["Gaussian local-linear Kalman filter"]["ci95_cm"][0] < 0
    distributional = field["distributional_sensitivity"]
    median_error = distributional["median_absolute_error"]
    near(median_error["single_frame_cm"], 8.735846, 1e-6)
    near(median_error["particle_filter_cm"], 7.301512, 1e-6)
    near(median_error["reduction_cm"], 1.434334, 1e-6)
    assert median_error["row_cluster_bootstrap_ci95_cm"][0] > 0
    leave_one_out = distributional["leave_one_row_out_mae"]
    assert leave_one_out["omissions"] == 12
    assert leave_one_out["all_improvements_positive"] is True
    near(leave_one_out["minimum_improvement_cm"], 0.613584, 1e-6)
    near(leave_one_out["maximum_improvement_cm"], 1.417692, 1e-6)
    error_quantiles = pd.read_csv(
        ROOT / "outputs/field_baselines_2021/absolute_error_quantiles.csv"
    ).set_index("estimator")
    proposed_quantiles = error_quantiles.loc["Robust Bayesian particle filter"]
    for column in error_quantiles.columns:
        assert proposed_quantiles[column] == error_quantiles[column].min()
    all_plants = json.loads(
        (ROOT / "outputs/filter_height_sam_2021/all_plants_primary.json").read_text()
    )
    after_first = all_plants["after_first_image_all_plants"]
    assert after_first["single_frame"]["n"] == 99
    assert after_first["single_frame"]["rows"] == 12
    near(
        after_first["paired_row_cluster_bootstrap"]["mae_improvement_cm"],
        1.437780,
    )
    assert after_first["paired_row_cluster_bootstrap"]["ci95_cm"][0] < 0

    manual_uncertainty = json.loads(
        (ROOT / "outputs/manual_height_uncertainty_2021/summary.json").read_text()
    )
    assert manual_uncertainty["design"]["records"] == 132
    assert manual_uncertainty["design"]["stationary_camera_rows"] == 12
    assert (
        manual_uncertainty["design"]["manual_height_used_for_fitting_or_tuning"]
        is False
    )
    manual_intervals = {
        row["nominal_coverage"]: row for row in manual_uncertainty["intervals"]
    }
    assert manual_intervals[0.80]["covered"] == 115
    assert manual_intervals[0.95]["covered"] == 125
    near(manual_intervals[0.80]["empirical_coverage"], 0.871212, 1e-6)
    near(manual_intervals[0.95]["empirical_coverage"], 0.946970, 1e-6)
    near(manual_intervals[0.95]["mean_width_cm"], 75.43270)

    unc = json.loads((ROOT / "outputs/uncertainty_revision/summary.json").read_text())
    test95 = next(
        row
        for row in unc["intervals"]
        if row["model"] == "unit_consistent"
        and row["split"] == "2025_locked_test"
        and row["nominal_coverage"] == 0.95
    )
    near(test95["empirical_coverage"], 0.9489247, 1e-6)
    near(test95["mean_width_cm"], 97.83876)
    development = next(
        row
        for row in unc["summary"]
        if row["model"] == "unit_consistent" and row["split"] == "2024_development"
    )
    temporal_test = next(
        row
        for row in unc["summary"]
        if row["model"] == "unit_consistent" and row["split"] == "2025_locked_test"
    )
    assert development["plants"] == 36
    assert temporal_test["plants"] == 11

    development_subjects: set[str] = set()
    test_subjects: set[str] = set()
    stream_path = (
        ROOT / "outputs/online_study/pole_camera_bayesian_daily_revised/"
        "online_bayesian_height_posteriors.csv"
    )
    with stream_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row["predictive_mean_cm"].strip():
                continue
            year = int(row["capture_datetime"][:4])
            if year == 2024:
                development_subjects.add(row["plant_uid"])
            elif year == 2025:
                test_subjects.add(row["plant_uid"])
    assert len(development_subjects) == development["plants"]
    assert len(test_subjects) == temporal_test["plants"]
    assert development_subjects.isdisjoint(test_subjects)

    real = json.loads(
        (ROOT / "outputs/real_image_candidate_ablation_2021/summary.json").read_text()
    )
    near(real["selection_agreement"], 1.0, 1e-12)

    required_app_files = [
        "START_PLANT_HEIGHT_APP.bat",
        "plant_height_app/app.py",
        "plant_height_app/engine.py",
        "plant_height_app/cli.py",
        "plant_height_app/README.md",
        "plant_height_app/requirements.txt",
        "plant_height_app/START_APP.bat",
        "plant_height_app/start_app.ps1",
        "plant_height_app/start_app.sh",
        "plant_height_app/APP_VALIDATION.json",
        "plant_height_app/COLLABORATOR_VALIDATION.json",
        "plant_height_app/examples/README.md",
        "plant_height_app/examples/image_dates_template.csv",
        "plant_height_app/examples/longitudinal_C-024/image_dates.csv",
        "plant_height_app/examples/longitudinal_C-024/example_height_estimates.csv",
        "plant_height_app/examples/longitudinal_C-024/example_height_by_day.png",
        "plant_height_app/examples/longitudinal_C-004/image_dates.csv",
        "plant_height_app/examples/longitudinal_C-004/example_height_estimates.csv",
        "plant_height_app/examples/longitudinal_C-004/example_height_by_day.png",
    ]
    assert all((ROOT / path).is_file() for path in required_app_files)
    app_validation = json.loads(
        (ROOT / "plant_height_app/APP_VALIDATION.json").read_text(encoding="utf-8")
    )
    assert app_validation["status"] == "pass"
    assert app_validation["application_version"] == "1.1.0"
    assert app_validation["source_checks"]["focused_tests"] == 12
    assert app_validation["released_filter_equivalence"]["status"] == "pass"
    assert app_validation["prefix_causality"]["status"] == "pass"
    assert app_validation["released_image_stress_test"]["images"] == 49
    assert (
        app_validation["released_image_stress_test"]["plant_image_rows_per_schedule"]
        == 248
    )
    assert app_validation["two_camera_batch_test"]["plant_image_rows"] == 46
    assert app_validation["two_camera_batch_test"]["height_versus_day_plots"] == 2
    collaborator_validation = json.loads(
        (ROOT / "plant_height_app/COLLABORATOR_VALIDATION.json").read_text(
            encoding="utf-8"
        )
    )
    assert collaborator_validation["status"] == "pass"
    assert collaborator_validation["released_field_images"] == 49
    assert set(collaborator_validation["interval_scenarios"]) == {
        "original_irregular",
        "daily",
        "every_3_days",
        "every_7_days",
        "long_gap_30_days",
    }
    assert all(
        scenario["status"] == "pass"
        and scenario["rows"] == 248
        and scenario["finite_height_rows"] == 248
        for scenario in collaborator_validation["interval_scenarios"].values()
    )
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "version: 1.4.0" in citation

    forbidden = ("C:" + "\\Users\\", "gh" + "o_", "file:" + "//")
    text_suffixes = {
        ".py",
        ".md",
        ".tex",
        ".bib",
        ".csv",
        ".json",
        ".yml",
        ".yaml",
        ".cff",
        ".txt",
        ".ps1",
        ".bat",
        ".sh",
    }
    bad: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in text_suffixes:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if any(token in content for token in forbidden):
                bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"Machine-specific paths or credential-like strings in: {bad}"

    report = {
        "status": "pass",
        "images": 61,
        "xml_files": 12,
        "model_sha256": EXPECTED_MODEL_SHA256,
        "checkpoint_training_ultralytics": checkpoint_metadata["ultralytics_version"],
        "checkpoint_training_seed": checkpoint_metadata["train_args"]["seed"],
        "checkpoint_training_epochs": checkpoint_metadata["train_args"]["epochs"],
        "recovered_crop_positions": len(crop_positions),
        "primary_records_with_recovered_source_coordinates": len(recovered_primary),
        "primary_records_without_recovered_source_coordinates": len(primary_rows)
        - len(recovered_primary),
        "title_characters": len(title),
        "title_words": len(title_words),
        "abstract_characters": len(abstract_plain),
        "abstract_words": len(words),
        "plain_language_summary_characters": len(plain_summary),
        "tppj_template_alignment": (
            "Official TPPJ Word-template order reproduced in standard LaTeX; "
            "12-point Times-family type, US letter, 1-inch margins, double spacing, "
            "continuous line numbers, full affiliations, and required declarations"
        ),
        "tppj_section_order": (
            "Introduction; Materials and Methods; Results; Discussion with Conclusions subsection"
        ),
        "field_particle_filter_mae_cm": fm["Robust Bayesian particle filter"]["mae_cm"],
        "field_comparators_with_positive_cluster_interval": positive_comparators,
        "field_median_absolute_error_reduction_cm": median_error["reduction_cm"],
        "field_leave_one_row_out_all_positive": leave_one_out[
            "all_improvements_positive"
        ],
        "field_after_first_image_mae_gain_cm": after_first[
            "paired_row_cluster_bootstrap"
        ]["mae_improvement_cm"],
        "manual_height_posterior_coverage_80": manual_intervals[0.80][
            "empirical_coverage"
        ],
        "manual_height_posterior_coverage_95": manual_intervals[0.95][
            "empirical_coverage"
        ],
        "manual_height_posterior_mean_width_95_cm": manual_intervals[0.95][
            "mean_width_cm"
        ],
        "support_pole_median_temporal_cv_percent": pole_repeatability[
            "median_cv_percent"
        ],
        "primary_validation_status": (
            "2021 independent manual-reference physical-height validation: 132 records, "
            "33 plants, 12 stationary-camera rows, five dates; labels excluded "
            "from fitting and tuning"
        ),
        "heldout_2025_coverage_95": test95["empirical_coverage"],
        "heldout_2025_mean_width_cm": test95["mean_width_cm"],
        "temporal_validation_status": (
            "2024 development and subject-disjoint 2025 test: "
            "36 versus 11 evaluated plant tracks; zero plant-subject overlap"
        ),
        "physical_annotation_status": (
            "completed human audit by Haoming Wang: 199 traces on 61 images; "
            "172 usable and 27 unusable"
        ),
        "plant_scientist_application": (
            "pass: local Streamlit image-to-height interface, one-click Windows launcher, "
            "batch CLI, two built-in longitudinal examples, per-camera plant counts, "
            "annotated QA, and downloadable height-versus-day plots with posterior intervals"
        ),
        "plant_scientist_application_version": app_validation["application_version"],
        "plant_scientist_application_tests": app_validation["source_checks"][
            "focused_tests"
        ],
        "plant_scientist_application_field_images_tested": app_validation[
            "released_image_stress_test"
        ]["images"],
        "plant_scientist_application_timing_schedules": app_validation[
            "released_image_stress_test"
        ]["timing_schedules"],
        "plant_scientist_application_rows_per_schedule": app_validation[
            "released_image_stress_test"
        ]["plant_image_rows_per_schedule"],
    }
    (ROOT / "RELEASE_VALIDATION.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
