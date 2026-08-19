"""Tests for canonical SMARD DE/LU day-ahead-price transformation."""

from pathlib import Path

import pandas as pd
import pytest

from gridsight.transformation.lineage import SOURCE_EXPORT_ID_COLUMN, SourceLineage
from gridsight.transformation.price import (
    CANONICAL_PRICE_COLUMNS,
    CURRENCY_COLUMN,
    DAY_AHEAD_PRICE_COLUMN,
    MARKET_AREA_COLUMN,
    RAW_PRICE_COLUMNS,
    RAW_PRICE_TARGET_COLUMN,
    SOURCE_VALUE_TEXT_COLUMN,
    combine_price_snapshots,
    transform_price_snapshot,
    write_price_csv,
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
        source_category="day_ahead_price",
        source_geography="DE-LU",
        source_resolution="hour",
        period_start="2022-01-01",
        period_end="2023-12-31",
        original_filename=f"{export_id}.csv",
        local_filename=f"smard_{export_id}.csv",
        sha256="c" * 64,
    )


def _source_frame(first_hour: int = 0) -> pd.DataFrame:
    data: dict[str, object] = {
        "Start date": _TIME_LABELS[first_hour : first_hour + 2],
        "End date": _TIME_LABELS[first_hour + 1 : first_hour + 3],
    }
    for column in RAW_PRICE_COLUMNS[2:]:
        data[column] = ["-", "-"]
    data[RAW_PRICE_TARGET_COLUMN] = ["-10.25", "50.00"]
    return pd.DataFrame(data)


def test_transform_price_snapshot_selects_target_and_keeps_negative() -> None:
    """Other market columns are excluded while valid DE/LU negatives remain."""
    result = transform_price_snapshot(
        _source_frame(),
        _lineage("price_first"),
    )

    assert tuple(result.columns) == CANONICAL_PRICE_COLUMNS
    assert len(result) == 2
    assert result[DAY_AHEAD_PRICE_COLUMN].tolist() == [-10.25, 50.0]
    assert result[SOURCE_VALUE_TEXT_COLUMN].tolist() == ["-10.25", "50.00"]
    assert result[MARKET_AREA_COLUMN].unique().tolist() == ["DE-LU"]
    assert result[CURRENCY_COLUMN].unique().tolist() == ["EUR"]
    assert result[SOURCE_EXPORT_ID_COLUMN].unique().tolist() == ["price_first"]
    assert not any("Belgium" in column for column in result.columns)


def test_transform_price_snapshot_rejects_target_marker() -> None:
    """A marker in the selected DE/LU target is never silently imputed."""
    frame = _source_frame()
    frame.loc[0, RAW_PRICE_TARGET_COLUMN] = "-"

    with pytest.raises(ValueError, match="non-numeric value at row 0"):
        transform_price_snapshot(frame, _lineage("bad_marker"))


def test_transform_price_snapshot_rejects_changed_source_schema() -> None:
    """Unexpected market-export columns require an explicit contract update."""
    frame = _source_frame().drop(columns=[RAW_PRICE_COLUMNS[-1]])

    with pytest.raises(ValueError, match="source columns changed"):
        transform_price_snapshot(frame, _lineage("bad_schema"))


def test_combine_price_snapshots_is_continuous_and_unique() -> None:
    """Adjacent DE/LU periods form one ordered UTC price series."""
    first = transform_price_snapshot(
        _source_frame(0),
        _lineage("first_period"),
    )
    second = transform_price_snapshot(
        _source_frame(2),
        _lineage("second_period"),
    )

    combined = combine_price_snapshots([second, first])

    assert len(combined) == 4
    assert combined["interval_start_utc"].is_unique
    assert combined["interval_start_utc"].is_monotonic_increasing
    assert combined[SOURCE_EXPORT_ID_COLUMN].tolist() == [
        "first_period",
        "first_period",
        "second_period",
        "second_period",
    ]


def test_write_price_csv_is_reproducible_and_atomic(tmp_path: Path) -> None:
    """The generated price CSV is deterministic and leaves no temp file."""
    transformed = transform_price_snapshot(
        _source_frame(),
        _lineage("write_test"),
    )
    output_path = tmp_path / "processed" / "price.csv"

    write_price_csv(transformed, output_path)
    first_bytes = output_path.read_bytes()
    write_price_csv(transformed, output_path)

    written = pd.read_csv(output_path)
    assert tuple(written.columns) == CANONICAL_PRICE_COLUMNS
    assert len(written) == 2
    assert output_path.read_bytes() == first_bytes
    assert not (output_path.parent / ".price.csv.tmp").exists()
