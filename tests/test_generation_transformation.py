"""Tests for canonical long-form SMARD generation transformation."""

from pathlib import Path

import pandas as pd
import pytest

from gridsight.transformation.generation import (
    CANONICAL_GENERATION_COLUMNS,
    GENERATION_MWH_COLUMN,
    GENERATION_TECHNOLOGIES,
    IS_RENEWABLE_COLUMN,
    SOURCE_VALUE_TEXT_COLUMN,
    TECHNOLOGY_GROUP_COLUMN,
    TECHNOLOGY_ID_COLUMN,
    VALUE_STATUS_COLUMN,
    VALUE_STATUS_REPORTED,
    VALUE_STATUS_UNAVAILABLE,
    combine_generation_snapshots,
    transform_generation_snapshot,
    write_generation_csv,
)
from gridsight.transformation.lineage import SOURCE_EXPORT_ID_COLUMN, SourceLineage

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
        source_category="actual_generation",
        source_geography="DE",
        source_resolution="hour",
        period_start="2022-01-01",
        period_end="2023-12-31",
        original_filename=f"{export_id}.csv",
        local_filename=f"smard_{export_id}.csv",
        sha256="b" * 64,
    )


def _source_frame(first_hour: int = 0) -> pd.DataFrame:
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


def test_transform_generation_snapshot_is_long_and_preserves_marker() -> None:
    """Each interval has 12 classified rows and an explicit Nuclear status."""
    result = transform_generation_snapshot(
        _source_frame(),
        _lineage("generation_first"),
    )

    assert tuple(result.columns) == CANONICAL_GENERATION_COLUMNS
    assert len(result) == 24
    assert result[["interval_start_utc", TECHNOLOGY_ID_COLUMN]].duplicated().sum() == 0
    assert result[TECHNOLOGY_ID_COLUMN].nunique() == 12
    assert result.groupby("interval_start_utc").size().eq(12).all()
    assert result.loc[result[IS_RENEWABLE_COLUMN]].groupby(
        "interval_start_utc"
    ).size().eq(6).all()
    assert (result[TECHNOLOGY_GROUP_COLUMN] == "storage").sum() == 2

    nuclear = result.loc[result[TECHNOLOGY_ID_COLUMN] == "nuclear"]
    assert nuclear[SOURCE_VALUE_TEXT_COLUMN].tolist() == ["-", "0.00"]
    assert nuclear[VALUE_STATUS_COLUMN].tolist() == [
        VALUE_STATUS_UNAVAILABLE,
        VALUE_STATUS_REPORTED,
    ]
    assert pd.isna(nuclear.iloc[0][GENERATION_MWH_COLUMN])
    assert nuclear.iloc[1][GENERATION_MWH_COLUMN] == 0.0
    assert result[SOURCE_EXPORT_ID_COLUMN].unique().tolist() == [
        "generation_first"
    ]


@pytest.mark.parametrize(
    ("technology_id", "value", "message"),
    [
        ("biomass", "-", "contains an unavailable marker"),
        ("wind_onshore", "-1.00", "contains negative generation"),
    ],
)
def test_transform_generation_snapshot_rejects_invalid_values(
    technology_id: str,
    value: str,
    message: str,
) -> None:
    """Only Nuclear may use the marker and no reported value may be negative."""
    frame = _source_frame()
    source_column = next(
        technology.source_column
        for technology in GENERATION_TECHNOLOGIES
        if technology.technology_id == technology_id
    )
    frame.loc[0, source_column] = value

    with pytest.raises(ValueError, match=message):
        transform_generation_snapshot(frame, _lineage("bad_generation"))


def test_combine_generation_snapshots_is_complete_and_continuous() -> None:
    """Adjacent periods retain every interval/technology key exactly once."""
    first = transform_generation_snapshot(
        _source_frame(0),
        _lineage("first_period"),
    )
    second = transform_generation_snapshot(
        _source_frame(2),
        _lineage("second_period"),
    )

    combined = combine_generation_snapshots([second, first])

    assert len(combined) == 48
    assert combined["interval_start_utc"].nunique() == 4
    assert combined.groupby("interval_start_utc").size().eq(12).all()
    combined_keys = combined[["interval_start_utc", TECHNOLOGY_ID_COLUMN]]
    assert combined_keys.duplicated().sum() == 0


def test_write_generation_csv_is_reproducible_and_atomic(
    tmp_path: Path,
) -> None:
    """The generated long CSV is deterministic and leaves no temp file."""
    transformed = transform_generation_snapshot(
        _source_frame(),
        _lineage("write_test"),
    )
    output_path = tmp_path / "processed" / "generation.csv"

    write_generation_csv(transformed, output_path)
    first_bytes = output_path.read_bytes()
    write_generation_csv(transformed, output_path)

    written = pd.read_csv(output_path)
    assert tuple(written.columns) == CANONICAL_GENERATION_COLUMNS
    assert len(written) == 24
    assert output_path.read_bytes() == first_bytes
    assert not (output_path.parent / ".generation.csv.tmp").exists()
