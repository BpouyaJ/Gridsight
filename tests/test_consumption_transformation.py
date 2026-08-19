"""Tests for canonical SMARD actual-consumption transformation."""

from pathlib import Path

import pandas as pd
import pytest

from gridsight.transformation.consumption import (
    CANONICAL_CONSUMPTION_COLUMNS,
    GRID_LOAD_MW_COLUMN,
    RAW_GRID_LOAD_COLUMN,
    RAW_GRID_LOAD_INCLUDING_PUMPED_COLUMN,
    RAW_PUMPED_STORAGE_COLUMN,
    RAW_RESIDUAL_LOAD_COLUMN,
    combine_consumption_snapshots,
    transform_consumption_snapshot,
    write_consumption_csv,
)
from gridsight.transformation.lineage import (
    SOURCE_EXPORT_ID_COLUMN,
    SOURCE_ORIGINAL_FILENAME_COLUMN,
    SourceLineage,
)

_TIME_LABELS = (
    "Jan 1, 2022 12:00 AM",
    "Jan 1, 2022 1:00 AM",
    "Jan 1, 2022 2:00 AM",
    "Jan 1, 2022 3:00 AM",
    "Jan 1, 2022 4:00 AM",
)


def _lineage(export_id: str) -> SourceLineage:
    return SourceLineage(
        export_id=export_id,
        source_category="actual_consumption",
        source_geography="DE",
        source_resolution="hour",
        period_start="2022-01-01",
        period_end="2023-12-31",
        original_filename=f"{export_id}.csv",
        local_filename=f"smard_{export_id}.csv",
        sha256="a" * 64,
    )


def _source_frame(first_hour: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Start date": _TIME_LABELS[first_hour : first_hour + 2],
            "End date": _TIME_LABELS[first_hour + 1 : first_hour + 3],
            RAW_GRID_LOAD_COLUMN: ["50,000.25", "49,000.00"],
            RAW_GRID_LOAD_INCLUDING_PUMPED_COLUMN: [
                "50,100.25",
                "49,000.00",
            ],
            RAW_PUMPED_STORAGE_COLUMN: ["100.00", "0.00"],
            RAW_RESIDUAL_LOAD_COLUMN: ["-5.00", "40,000.00"],
        }
    )


def test_transform_consumption_snapshot_parses_measures_and_lineage() -> None:
    """Canonical output preserves lineage and valid negative residual load."""
    result = transform_consumption_snapshot(
        _source_frame(),
        _lineage("consumption_first"),
    )

    assert tuple(result.columns) == CANONICAL_CONSUMPTION_COLUMNS
    assert result["grid_load_mwh"].tolist() == [50_000.25, 49_000.0]
    assert result[GRID_LOAD_MW_COLUMN].tolist() == result["grid_load_mwh"].tolist()
    assert result["residual_load_mwh"].tolist() == [-5.0, 40_000.0]
    assert result[SOURCE_EXPORT_ID_COLUMN].unique().tolist() == [
        "consumption_first"
    ]
    assert result[SOURCE_ORIGINAL_FILENAME_COLUMN].unique().tolist() == [
        "consumption_first.csv"
    ]
    assert result.iloc[0]["interval_start_utc"] == pd.Timestamp(
        "2021-12-31T23:00:00Z"
    )


def test_transform_consumption_snapshot_rejects_source_marker() -> None:
    """Consumption measures must be numeric rather than silently imputed."""
    frame = _source_frame()
    frame.loc[1, RAW_GRID_LOAD_COLUMN] = "-"

    with pytest.raises(ValueError, match="non-numeric value at row 1"):
        transform_consumption_snapshot(frame, _lineage("bad_marker"))


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        (RAW_PUMPED_STORAGE_COLUMN, "-1.00", "negative energy"),
        (
            RAW_GRID_LOAD_INCLUDING_PUMPED_COLUMN,
            "50,200.25",
            "violates its source identity",
        ),
    ],
)
def test_transform_consumption_snapshot_enforces_measure_rules(
    column: str,
    value: str,
    message: str,
) -> None:
    """Impossible signs and material arithmetic mismatches fail explicitly."""
    frame = _source_frame()
    frame.loc[0, column] = value

    with pytest.raises(ValueError, match=message):
        transform_consumption_snapshot(frame, _lineage("bad_measure"))


def test_combine_consumption_snapshots_is_continuous_and_unique() -> None:
    """Adjacent clean periods form one ordered UTC series with lineage."""
    first = transform_consumption_snapshot(
        _source_frame(0),
        _lineage("first_period"),
    )
    second = transform_consumption_snapshot(
        _source_frame(2),
        _lineage("second_period"),
    )

    combined = combine_consumption_snapshots([second, first])

    assert len(combined) == 4
    assert combined["interval_start_utc"].is_unique
    assert combined["interval_start_utc"].is_monotonic_increasing
    assert combined[SOURCE_EXPORT_ID_COLUMN].tolist() == [
        "first_period",
        "first_period",
        "second_period",
        "second_period",
    ]


def test_write_consumption_csv_is_reproducible_and_atomic(
    tmp_path: Path,
) -> None:
    """The generated CSV uses its canonical order and leaves no temp file."""
    transformed = transform_consumption_snapshot(
        _source_frame(),
        _lineage("write_test"),
    )
    output_path = tmp_path / "processed" / "consumption.csv"

    write_consumption_csv(transformed, output_path)
    first_bytes = output_path.read_bytes()
    write_consumption_csv(transformed, output_path)

    written = pd.read_csv(output_path)
    assert tuple(written.columns) == CANONICAL_CONSUMPTION_COLUMNS
    assert len(written) == 2
    assert output_path.read_bytes() == first_bytes
    assert not (output_path.parent / ".consumption.csv.tmp").exists()
