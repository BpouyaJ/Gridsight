"""DST-safe normalization of SMARD hourly interval timestamps."""

import re

import pandas as pd

SOURCE_START_COLUMN = "Start date"
SOURCE_END_COLUMN = "End date"
SOURCE_START_TEXT_COLUMN = "source_start_text"
SOURCE_END_TEXT_COLUMN = "source_end_text"
INTERVAL_START_UTC_COLUMN = "interval_start_utc"
INTERVAL_END_UTC_COLUMN = "interval_end_utc"
INTERVAL_START_LOCAL_COLUMN = "interval_start_local"
INTERVAL_END_LOCAL_COLUMN = "interval_end_local"
UTC_OFFSET_MINUTES_COLUMN = "utc_offset_minutes"
IS_DST_COLUMN = "is_dst"
LOCAL_FOLD_COLUMN = "local_fold"

REPORTING_TIMEZONE = "Europe/Berlin"
CANONICAL_TIME_COLUMNS = (
    SOURCE_START_TEXT_COLUMN,
    SOURCE_END_TEXT_COLUMN,
    INTERVAL_START_UTC_COLUMN,
    INTERVAL_END_UTC_COLUMN,
    INTERVAL_START_LOCAL_COLUMN,
    INTERVAL_END_LOCAL_COLUMN,
    UTC_OFFSET_MINUTES_COLUMN,
    IS_DST_COLUMN,
    LOCAL_FOLD_COLUMN,
)
_SMARD_TIMESTAMP_PATTERN = re.compile(
    r"^(?P<month>[A-Z][a-z]{2}) "
    r"(?P<day>\d{1,2}), "
    r"(?P<year>\d{4}) "
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2}) "
    r"(?P<period>AM|PM)$"
)
_ENGLISH_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
_ONE_HOUR = pd.Timedelta(hours=1)


def _parse_smard_timestamp_text(
    values: pd.Series,
    column_name: str,
) -> pd.Series:
    text = values.astype("string")
    parts = text.str.extract(_SMARD_TIMESTAMP_PATTERN)
    invalid_rows = parts.isna().any(axis=1)
    if invalid_rows.any():
        index = invalid_rows[invalid_rows].index[0]
        raise ValueError(
            f"{column_name} has invalid SMARD timestamp text at row {index}: "
            f"{text.loc[index]!r}"
        )

    months = parts["month"].map(_ENGLISH_MONTHS)
    if months.isna().any():
        index = months[months.isna()].index[0]
        raise ValueError(
            f"{column_name} has an unsupported month at row {index}: "
            f"{parts.loc[index, 'month']!r}"
        )

    hours = parts["hour"].astype("int64")
    minutes = parts["minute"].astype("int64")
    if ((hours < 1) | (hours > 12)).any() or (
        (minutes < 0) | (minutes > 59)
    ).any():
        raise ValueError(f"{column_name} contains an invalid clock value")

    hour_24 = (hours % 12) + (parts["period"] == "PM").astype("int64") * 12
    return pd.to_datetime(
        {
            "year": parts["year"].astype("int64"),
            "month": months.astype("int64"),
            "day": parts["day"].astype("int64"),
            "hour": hour_24,
            "minute": minutes,
        },
        errors="raise",
    )


def _localize_ordered_starts(parsed_starts: pd.Series) -> pd.Series:
    if not parsed_starts.is_monotonic_increasing:
        raise ValueError("SMARD start timestamps are not in source order")
    try:
        return parsed_starts.dt.tz_localize(
            REPORTING_TIMEZONE,
            ambiguous="infer",
            nonexistent="raise",
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "SMARD start timestamps cannot be localized unambiguously"
        ) from error


def normalize_hourly_timestamps(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with unique UTC intervals and preserved source text.

    Repeated autumn local starts are disambiguated from their source order.
    Canonical interval ends are derived from each UTC start plus one hour
    because SMARD end labels are not independently localizable at DST changes.
    """
    missing_columns = [
        name
        for name in (SOURCE_START_COLUMN, SOURCE_END_COLUMN)
        if name not in frame.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Missing SMARD timestamp columns: {missing}")
    if frame.empty:
        raise ValueError("Cannot normalize an empty SMARD frame")

    collisions = set(CANONICAL_TIME_COLUMNS) & set(frame.columns)
    if collisions:
        names = ", ".join(sorted(collisions))
        raise ValueError(f"Canonical timestamp columns already exist: {names}")

    parsed_starts = _parse_smard_timestamp_text(
        frame[SOURCE_START_COLUMN],
        SOURCE_START_COLUMN,
    )
    parsed_ends = _parse_smard_timestamp_text(
        frame[SOURCE_END_COLUMN],
        SOURCE_END_COLUMN,
    )
    wall_durations = parsed_ends - parsed_starts
    if not (wall_durations == _ONE_HOUR).all():
        raise ValueError("SMARD source interval labels are not one wall-clock hour")

    local_starts = _localize_ordered_starts(parsed_starts)
    utc_starts = local_starts.dt.tz_convert("UTC")
    utc_differences = utc_starts.diff().dropna()
    if not (utc_differences == _ONE_HOUR).all():
        raise ValueError("SMARD UTC start timestamps are not continuous hourly data")
    if utc_starts.duplicated().any():
        raise ValueError("SMARD UTC start timestamps are not unique")

    utc_ends = utc_starts + _ONE_HOUR
    local_ends = utc_ends.dt.tz_convert(REPORTING_TIMEZONE)

    result = frame.rename(
        columns={
            SOURCE_START_COLUMN: SOURCE_START_TEXT_COLUMN,
            SOURCE_END_COLUMN: SOURCE_END_TEXT_COLUMN,
        }
    ).copy()
    result[INTERVAL_START_UTC_COLUMN] = utc_starts
    result[INTERVAL_END_UTC_COLUMN] = utc_ends
    result[INTERVAL_START_LOCAL_COLUMN] = local_starts
    result[INTERVAL_END_LOCAL_COLUMN] = local_ends
    result[UTC_OFFSET_MINUTES_COLUMN] = local_starts.map(
        lambda value: int(value.utcoffset().total_seconds() // 60)
    )
    result[IS_DST_COLUMN] = local_starts.map(
        lambda value: value.dst().total_seconds() != 0
    )
    result[LOCAL_FOLD_COLUMN] = local_starts.map(lambda value: value.fold)

    measure_columns = [
        name for name in result.columns if name not in CANONICAL_TIME_COLUMNS
    ]
    return result[[*CANONICAL_TIME_COLUMNS, *measure_columns]]
