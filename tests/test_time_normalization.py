"""Tests for DST-safe SMARD timestamp normalization."""

import pandas as pd
import pytest

from gridsight.transformation.time_normalization import (
    INTERVAL_END_LOCAL_COLUMN,
    INTERVAL_END_UTC_COLUMN,
    INTERVAL_START_UTC_COLUMN,
    IS_DST_COLUMN,
    LOCAL_FOLD_COLUMN,
    SOURCE_END_TEXT_COLUMN,
    UTC_OFFSET_MINUTES_COLUMN,
    normalize_hourly_timestamps,
)


def _frame(starts: list[str], ends: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Start date": starts,
            "End date": ends,
            "Measure": range(len(starts)),
        }
    )


def test_spring_gap_becomes_continuous_utc_hours() -> None:
    """The nonexistent local 02:00 end label does not create a UTC gap."""
    frame = _frame(
        [
            "Mar 27, 2022 12:00 AM",
            "Mar 27, 2022 1:00 AM",
            "Mar 27, 2022 3:00 AM",
            "Mar 27, 2022 4:00 AM",
        ],
        [
            "Mar 27, 2022 1:00 AM",
            "Mar 27, 2022 2:00 AM",
            "Mar 27, 2022 4:00 AM",
            "Mar 27, 2022 5:00 AM",
        ],
    )

    result = normalize_hourly_timestamps(frame)

    expected_starts = pd.to_datetime(
        [
            "2022-03-26T23:00:00Z",
            "2022-03-27T00:00:00Z",
            "2022-03-27T01:00:00Z",
            "2022-03-27T02:00:00Z",
        ],
        utc=True,
    )
    assert result[INTERVAL_START_UTC_COLUMN].tolist() == expected_starts.tolist()
    assert (
        result[INTERVAL_END_UTC_COLUMN] - result[INTERVAL_START_UTC_COLUMN]
        == pd.Timedelta(hours=1)
    ).all()
    assert result.loc[1, SOURCE_END_TEXT_COLUMN] == "Mar 27, 2022 2:00 AM"
    assert result.loc[1, INTERVAL_END_LOCAL_COLUMN].hour == 3
    assert result[UTC_OFFSET_MINUTES_COLUMN].tolist() == [60, 60, 120, 120]
    assert result[IS_DST_COLUMN].tolist() == [False, False, True, True]


def test_autumn_repeated_hour_maps_to_two_unique_utc_starts() -> None:
    """Ordered duplicate local 02:00 rows receive different UTC offsets."""
    frame = _frame(
        [
            "Oct 30, 2022 12:00 AM",
            "Oct 30, 2022 1:00 AM",
            "Oct 30, 2022 2:00 AM",
            "Oct 30, 2022 2:00 AM",
            "Oct 30, 2022 3:00 AM",
            "Oct 30, 2022 4:00 AM",
        ],
        [
            "Oct 30, 2022 1:00 AM",
            "Oct 30, 2022 2:00 AM",
            "Oct 30, 2022 3:00 AM",
            "Oct 30, 2022 3:00 AM",
            "Oct 30, 2022 4:00 AM",
            "Oct 30, 2022 5:00 AM",
        ],
    )

    result = normalize_hourly_timestamps(frame)

    assert result[INTERVAL_START_UTC_COLUMN].is_unique
    assert result[INTERVAL_START_UTC_COLUMN].is_monotonic_increasing
    assert result[UTC_OFFSET_MINUTES_COLUMN].tolist() == [120, 120, 120, 60, 60, 60]
    assert result[LOCAL_FOLD_COLUMN].tolist() == [0, 0, 0, 1, 0, 0]
    assert result[IS_DST_COLUMN].tolist() == [True, True, True, False, False, False]
    assert (
        result[INTERVAL_END_UTC_COLUMN] - result[INTERVAL_START_UTC_COLUMN]
        == pd.Timedelta(hours=1)
    ).all()


def test_normalization_rejects_a_real_hourly_gap() -> None:
    """A source gap outside DST transitions fails before clean output exists."""
    frame = _frame(
        ["Jan 1, 2022 12:00 AM", "Jan 1, 2022 2:00 AM"],
        ["Jan 1, 2022 1:00 AM", "Jan 1, 2022 3:00 AM"],
    )

    with pytest.raises(ValueError, match="not continuous hourly"):
        normalize_hourly_timestamps(frame)
