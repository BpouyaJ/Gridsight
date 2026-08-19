"""Tests for the consolidated clean-data validation gate."""

import json
from pathlib import Path

import pandas as pd

from gridsight.transformation.consumption import (
    RAW_GRID_LOAD_COLUMN,
    RAW_GRID_LOAD_INCLUDING_PUMPED_COLUMN,
    RAW_PUMPED_STORAGE_COLUMN,
    RAW_RESIDUAL_LOAD_COLUMN,
    combine_consumption_snapshots,
    transform_consumption_snapshot,
)
from gridsight.transformation.generation import (
    GENERATION_TECHNOLOGIES,
    SOURCE_VALUE_TEXT_COLUMN,
    VALUE_STATUS_COLUMN,
    VALUE_STATUS_UNAVAILABLE,
    combine_generation_snapshots,
    transform_generation_snapshot,
)
from gridsight.transformation.lineage import SourceLineage
from gridsight.transformation.price import (
    RAW_PRICE_COLUMNS,
    RAW_PRICE_TARGET_COLUMN,
    combine_price_snapshots,
    transform_price_snapshot,
)
from gridsight.validation.clean_data import (
    ISSUE_COLUMNS,
    STATUS_FAILED,
    STATUS_PASSED,
    summarize_clean_datasets,
    validate_clean_datasets,
    write_validation_artifacts,
)

_TIME_LABELS = (
    "Jan 1, 2022 12:00 AM",
    "Jan 1, 2022 1:00 AM",
    "Jan 1, 2022 2:00 AM",
    "Jan 1, 2022 3:00 AM",
    "Jan 1, 2022 4:00 AM",
)


def _lineage(category: str, geography: str, export_id: str) -> SourceLineage:
    hash_character = {
        "actual_consumption": "a",
        "actual_generation": "b",
        "day_ahead_price": "c",
    }[category]
    return SourceLineage(
        export_id=export_id,
        source_category=category,
        source_geography=geography,
        source_resolution="hour",
        period_start="2022-01-01",
        period_end="2023-12-31",
        original_filename=f"{export_id}.csv",
        local_filename=f"smard_{export_id}.csv",
        sha256=hash_character * 64,
    )


def _consumption_source(first_hour: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Start date": _TIME_LABELS[first_hour : first_hour + 2],
            "End date": _TIME_LABELS[first_hour + 1 : first_hour + 3],
            RAW_GRID_LOAD_COLUMN: ["50,000.00", "49,000.00"],
            RAW_GRID_LOAD_INCLUDING_PUMPED_COLUMN: [
                "50,100.00",
                "49,000.00",
            ],
            RAW_PUMPED_STORAGE_COLUMN: ["100.00", "0.00"],
            RAW_RESIDUAL_LOAD_COLUMN: ["-5.00", "40,000.00"],
        }
    )


def _generation_source(first_hour: int) -> pd.DataFrame:
    data: dict[str, object] = {
        "Start date": _TIME_LABELS[first_hour : first_hour + 2],
        "End date": _TIME_LABELS[first_hour + 1 : first_hour + 3],
    }
    for order, technology in enumerate(GENERATION_TECHNOLOGIES, start=1):
        data[technology.source_column] = [f"{order},000.00", f"{order}.50"]
    nuclear_column = next(
        technology.source_column
        for technology in GENERATION_TECHNOLOGIES
        if technology.technology_id == "nuclear"
    )
    data[nuclear_column] = ["-", "0.00"]
    return pd.DataFrame(data)


def _price_source(first_hour: int) -> pd.DataFrame:
    data: dict[str, object] = {
        "Start date": _TIME_LABELS[first_hour : first_hour + 2],
        "End date": _TIME_LABELS[first_hour + 1 : first_hour + 3],
    }
    for column in RAW_PRICE_COLUMNS[2:]:
        data[column] = ["-", "-"]
    data[RAW_PRICE_TARGET_COLUMN] = ["-10.25", "50.00"]
    return pd.DataFrame(data)


def _valid_datasets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    consumption = combine_consumption_snapshots(
        [
            transform_consumption_snapshot(
                _consumption_source(0),
                _lineage("actual_consumption", "DE", "consumption_first"),
            ),
            transform_consumption_snapshot(
                _consumption_source(2),
                _lineage("actual_consumption", "DE", "consumption_second"),
            ),
        ]
    )
    generation = combine_generation_snapshots(
        [
            transform_generation_snapshot(
                _generation_source(0),
                _lineage("actual_generation", "DE", "generation_first"),
            ),
            transform_generation_snapshot(
                _generation_source(2),
                _lineage("actual_generation", "DE", "generation_second"),
            ),
        ]
    )
    price = combine_price_snapshots(
        [
            transform_price_snapshot(
                _price_source(0),
                _lineage("day_ahead_price", "DE-LU", "price_first"),
            ),
            transform_price_snapshot(
                _price_source(2),
                _lineage("day_ahead_price", "DE-LU", "price_second"),
            ),
        ]
    )
    return consumption, generation, price


def test_valid_clean_datasets_pass_every_check() -> None:
    """A complete aligned clean layer produces no structured issues."""
    consumption, generation, price = _valid_datasets()

    report = validate_clean_datasets(
        consumption,
        generation,
        price,
        expected_intervals=4,
    )

    assert report.status == STATUS_PASSED
    assert len(report.checks) == 29
    assert not report.issues
    assert all(check.status == STATUS_PASSED for check in report.checks)


def test_missing_price_hour_reports_row_count_and_spine_failures() -> None:
    """A missing market hour is identified by stable check IDs."""
    consumption, generation, price = _valid_datasets()
    price = price.iloc[:-1].copy()

    report = validate_clean_datasets(
        consumption,
        generation,
        price,
        expected_intervals=4,
    )

    assert report.status == STATUS_FAILED
    issue_ids = {issue.check_id for issue in report.issues}
    assert "price.row_count" in issue_ids
    assert "cross_dataset.utc_spine" in issue_ids


def test_invalid_unavailable_generation_row_is_actionable() -> None:
    """Broken marker semantics produce a row-counted generation issue."""
    consumption, generation, price = _valid_datasets()
    generation = generation.copy()
    marker_row = generation[VALUE_STATUS_COLUMN] == VALUE_STATUS_UNAVAILABLE
    generation.loc[marker_row, SOURCE_VALUE_TEXT_COLUMN] = "missing"

    report = validate_clean_datasets(
        consumption,
        generation,
        price,
        expected_intervals=4,
    )

    issue = next(
        issue
        for issue in report.issues
        if issue.check_id == "generation.unavailable_semantics"
    )
    assert issue.dataset == "generation"
    assert issue.affected_rows == 2


def test_validation_artifacts_are_deterministic_and_machine_readable(
    tmp_path: Path,
) -> None:
    """Header-only issues and JSON summary reproduce byte for byte."""
    consumption, generation, price = _valid_datasets()
    report = validate_clean_datasets(
        consumption,
        generation,
        price,
        expected_intervals=4,
    )
    outputs = {
        name: {
            "output": f"data/processed/{name}.csv",
            "sha256": character * 64,
        }
        for name, character in zip(
            ("consumption", "generation", "price"),
            "def",
            strict=True,
        )
    }
    datasets = summarize_clean_datasets(
        consumption,
        generation,
        price,
        outputs,
    )
    issues_path = tmp_path / "validation_issues.csv"
    summary_path = tmp_path / "validation_summary.json"

    write_validation_artifacts(
        report,
        datasets,
        issues_path,
        summary_path,
    )
    first_issues = issues_path.read_bytes()
    first_summary = summary_path.read_bytes()
    write_validation_artifacts(
        report,
        datasets,
        issues_path,
        summary_path,
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert issues_path.read_text(encoding="utf-8").strip() == ",".join(
        ISSUE_COLUMNS
    )
    assert summary["status"] == STATUS_PASSED
    assert summary["check_counts"] == {"failed": 0, "passed": 29}
    assert summary["datasets"]["generation"]["rows"] == 48
    assert issues_path.read_bytes() == first_issues
    assert summary_path.read_bytes() == first_summary
    assert not (tmp_path / ".validation_issues.csv.tmp").exists()
    assert not (tmp_path / ".validation_summary.json.tmp").exists()
