"""Deterministic leakage-safe features for 24-hour grid-load forecasts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from gridsight.database.schema_contract import PROJECT_ROOT
from gridsight.forecasting.contract import (
    DEFAULT_FORECAST_CONTRACT,
    DEFAULT_FORECAST_INDEX,
    FORECAST_HORIZON_HOURS,
    FORECAST_SPLITS,
    MINIMUM_HISTORY_HOURS,
    _validate_source,
    sha256_file,
    validate_forecast_index,
)
from gridsight.transformation.time_normalization import REPORTING_TIMEZONE

DEFAULT_FEATURE_MATRIX = PROJECT_ROOT / "data" / "processed" / "forecast_features.csv"
DEFAULT_FEATURE_CONTRACT = PROJECT_ROOT / "reports" / "feature_contract.json"
FEATURE_TARGET_COLUMN = "actual_grid_load_mw"
FEATURE_AUDIT_COLUMNS = (
    "forecast_origin_utc",
    "origin_local_date",
    "split",
    "information_cutoff_utc",
    "latest_observed_start_utc",
    "target_start_utc",
    "target_start_local",
)
MODEL_FEATURE_COLUMNS = (
    "horizon_step",
    "target_hour_local",
    "target_day_of_week",
    "target_is_weekend",
    "target_month",
    "target_day_of_year",
    "target_local_fold",
    "target_utc_offset_hours",
    "target_hour_sin",
    "target_hour_cos",
    "target_weekday_sin",
    "target_weekday_cos",
    "target_year_sin",
    "target_year_cos",
    "latest_load_mw",
    "load_lag_24h_mw",
    "load_lag_168h_mw",
    "load_rolling_mean_24h_mw",
    "load_rolling_std_24h_mw",
    "load_rolling_min_24h_mw",
    "load_rolling_max_24h_mw",
    "load_rolling_mean_168h_mw",
    "load_rolling_std_168h_mw",
    "load_rolling_min_168h_mw",
    "load_rolling_max_168h_mw",
    "load_change_1h_mw",
    "load_change_24h_mw",
)
FORECAST_FEATURE_COLUMNS = (
    *FEATURE_AUDIT_COLUMNS,
    FEATURE_TARGET_COLUMN,
    *MODEL_FEATURE_COLUMNS,
)


def _rolling_values(
    actual: np.ndarray,
    latest_positions: np.ndarray,
    window: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    series = pd.Series(actual)
    rolling = series.rolling(window=window, min_periods=window)
    return tuple(
        values.to_numpy(dtype="float64")[latest_positions]
        for values in (
            rolling.mean(),
            rolling.std(ddof=0),
            rolling.min(),
            rolling.max(),
        )
    )


def build_forecast_features(
    forecast_index: pd.DataFrame,
    source: pd.DataFrame,
) -> pd.DataFrame:
    """Build calendar and historical-load features available at each origin."""
    validate_forecast_index(forecast_index)
    source_starts, source_actual = _validate_source(source)
    source_time_index = pd.DatetimeIndex(source_starts)
    actual = source_actual.to_numpy(dtype="float64")
    origins = pd.to_datetime(
        forecast_index["forecast_origin_utc"], format="mixed", utc=True
    )
    targets = pd.to_datetime(
        forecast_index["target_start_utc"], format="mixed", utc=True
    )
    origin_positions = source_time_index.get_indexer(pd.DatetimeIndex(origins))
    target_positions = source_time_index.get_indexer(pd.DatetimeIndex(targets))
    if (origin_positions < MINIMUM_HISTORY_HOURS).any():
        raise ValueError("Feature origins require at least 168 history hours")
    if (target_positions < 0).any():
        raise ValueError("Feature targets must exist in the canonical load spine")

    latest_positions = origin_positions - 1
    mean_24, std_24, min_24, max_24 = _rolling_values(
        actual, latest_positions, 24
    )
    mean_168, std_168, min_168, max_168 = _rolling_values(
        actual, latest_positions, 168
    )
    target_local = targets.dt.tz_convert(REPORTING_TIMEZONE)
    hour = target_local.dt.hour.to_numpy(dtype="int64")
    weekday = target_local.dt.dayofweek.to_numpy(dtype="int64")
    month = target_local.dt.month.to_numpy(dtype="int64")
    day_of_year = target_local.dt.dayofyear.to_numpy(dtype="int64")
    days_in_year = np.where(target_local.dt.is_leap_year, 366.0, 365.0)
    hour_angle = 2 * np.pi * hour / 24
    weekday_angle = 2 * np.pi * weekday / 7
    year_angle = 2 * np.pi * (day_of_year - 1) / days_in_year
    utc_offset_hours = np.array(
        [
            timestamp.utcoffset().total_seconds() / 3_600
            for timestamp in target_local.to_list()
        ],
        dtype="float64",
    )
    latest_observed = source_time_index[latest_positions]
    test_mask = forecast_index["split"].eq("test").to_numpy()
    target_values = pd.to_numeric(
        forecast_index[FEATURE_TARGET_COLUMN], errors="raise"
    ).to_numpy(dtype="float64", copy=True)
    target_values[test_mask] = np.nan

    features = pd.DataFrame(
        {
            "forecast_origin_utc": forecast_index[
                "forecast_origin_utc"
            ].to_numpy(),
            "origin_local_date": forecast_index["origin_local_date"].to_numpy(),
            "split": forecast_index["split"].to_numpy(),
            "information_cutoff_utc": forecast_index[
                "information_cutoff_utc"
            ].to_numpy(),
            "latest_observed_start_utc": [
                timestamp.isoformat() for timestamp in latest_observed
            ],
            "target_start_utc": forecast_index["target_start_utc"].to_numpy(),
            "target_start_local": forecast_index[
                "target_start_local"
            ].to_numpy(),
            FEATURE_TARGET_COLUMN: target_values,
            "horizon_step": pd.to_numeric(
                forecast_index["horizon_step"], errors="raise"
            ).to_numpy(dtype="int64"),
            "target_hour_local": hour,
            "target_day_of_week": weekday,
            "target_is_weekend": (weekday >= 5).astype("int64"),
            "target_month": month,
            "target_day_of_year": day_of_year,
            "target_local_fold": pd.to_numeric(
                forecast_index["target_local_fold"], errors="raise"
            ).to_numpy(dtype="int64"),
            "target_utc_offset_hours": utc_offset_hours,
            "target_hour_sin": np.sin(hour_angle),
            "target_hour_cos": np.cos(hour_angle),
            "target_weekday_sin": np.sin(weekday_angle),
            "target_weekday_cos": np.cos(weekday_angle),
            "target_year_sin": np.sin(year_angle),
            "target_year_cos": np.cos(year_angle),
            "latest_load_mw": actual[latest_positions],
            "load_lag_24h_mw": actual[target_positions - 24],
            "load_lag_168h_mw": actual[target_positions - 168],
            "load_rolling_mean_24h_mw": mean_24,
            "load_rolling_std_24h_mw": std_24,
            "load_rolling_min_24h_mw": min_24,
            "load_rolling_max_24h_mw": max_24,
            "load_rolling_mean_168h_mw": mean_168,
            "load_rolling_std_168h_mw": std_168,
            "load_rolling_min_168h_mw": min_168,
            "load_rolling_max_168h_mw": max_168,
            "load_change_1h_mw": (
                actual[latest_positions] - actual[latest_positions - 1]
            ),
            "load_change_24h_mw": (
                actual[latest_positions] - actual[latest_positions - 24]
            ),
        },
        columns=FORECAST_FEATURE_COLUMNS,
    )
    validate_forecast_features(features)
    return features


def validate_forecast_features(features: pd.DataFrame) -> None:
    """Enforce feature grain, availability, domains, and redacted test labels."""
    if tuple(features.columns) != FORECAST_FEATURE_COLUMNS:
        raise ValueError("Forecast-feature columns do not match the contract")
    expected_rows = sum(
        split.expected_origins * FORECAST_HORIZON_HOURS
        for split in FORECAST_SPLITS
    )
    if len(features) != expected_rows:
        raise ValueError(f"Forecast features must contain {expected_rows} rows")
    if features.duplicated(["forecast_origin_utc", "horizon_step"]).any():
        raise ValueError("Feature origin and horizon keys must be unique")
    if FEATURE_TARGET_COLUMN in MODEL_FEATURE_COLUMNS:
        raise ValueError("Target column must not be declared as a model feature")

    origins = pd.to_datetime(
        features["forecast_origin_utc"], format="mixed", utc=True
    )
    cutoff = pd.to_datetime(
        features["information_cutoff_utc"], format="mixed", utc=True
    )
    latest = pd.to_datetime(
        features["latest_observed_start_utc"], format="mixed", utc=True
    )
    targets = pd.to_datetime(
        features["target_start_utc"], format="mixed", utc=True
    )
    horizon = pd.to_numeric(features["horizon_step"], errors="raise").astype(
        "int64"
    )
    if not (cutoff == origins).all():
        raise ValueError("Feature information cutoff must equal the origin")
    if not (latest + pd.Timedelta(hours=1) == origins).all():
        raise ValueError("Latest observed load must end exactly at the origin")
    if not (targets == origins + pd.to_timedelta(horizon - 1, unit="h")).all():
        raise ValueError("Feature targets do not match horizon steps")

    train_validation = features["split"].isin(("train", "validation"))
    test = features["split"].eq("test")
    target = pd.to_numeric(features[FEATURE_TARGET_COLUMN], errors="coerce")
    if target.loc[train_validation].isna().any() or (
        target.loc[train_validation] <= 0
    ).any():
        raise ValueError("Train and validation target labels must be positive")
    if target.loc[test].notna().any():
        raise ValueError("Test target labels must remain redacted")

    numeric = features.loc[:, list(MODEL_FEATURE_COLUMNS)].apply(
        pd.to_numeric, errors="raise"
    )
    if not np.isfinite(numeric.to_numpy(dtype="float64")).all():
        raise ValueError("Model features must contain only finite values")
    domains = {
        "horizon_step": range(1, 25),
        "target_hour_local": range(24),
        "target_day_of_week": range(7),
        "target_is_weekend": (0, 1),
        "target_month": range(1, 13),
        "target_local_fold": (0, 1),
        "target_utc_offset_hours": (1.0, 2.0),
    }
    for column, allowed in domains.items():
        if not numeric[column].isin(allowed).all():
            raise ValueError(f"Invalid feature domain for {column}")
    if not numeric["target_day_of_year"].between(1, 366).all():
        raise ValueError("Invalid feature domain for target_day_of_year")

    target_local = targets.dt.tz_convert(REPORTING_TIMEZONE)
    expected_calendar = {
        "target_hour_local": target_local.dt.hour.to_numpy(dtype="int64"),
        "target_day_of_week": target_local.dt.dayofweek.to_numpy(dtype="int64"),
        "target_is_weekend": (
            target_local.dt.dayofweek.to_numpy(dtype="int64") >= 5
        ).astype("int64"),
        "target_month": target_local.dt.month.to_numpy(dtype="int64"),
        "target_day_of_year": target_local.dt.dayofyear.to_numpy(dtype="int64"),
        "target_local_fold": np.array(
            [timestamp.fold for timestamp in target_local.to_list()],
            dtype="int64",
        ),
        "target_utc_offset_hours": np.array(
            [
                timestamp.utcoffset().total_seconds() / 3_600
                for timestamp in target_local.to_list()
            ],
            dtype="float64",
        ),
    }
    for column, expected in expected_calendar.items():
        if not np.array_equal(numeric[column].to_numpy(), expected):
            raise ValueError(f"{column} does not match the UTC target timestamp")
    cyclical = [
        column
        for column in MODEL_FEATURE_COLUMNS
        if column.endswith(("_sin", "_cos"))
    ]
    if not numeric[cyclical].stack().between(-1.0, 1.0).all():
        raise ValueError("Cyclical features must remain between -1 and 1")
    positive_loads = (
        "latest_load_mw",
        "load_lag_24h_mw",
        "load_lag_168h_mw",
        "load_rolling_mean_24h_mw",
        "load_rolling_min_24h_mw",
        "load_rolling_max_24h_mw",
        "load_rolling_mean_168h_mw",
        "load_rolling_min_168h_mw",
        "load_rolling_max_168h_mw",
    )
    if (numeric[list(positive_loads)] <= 0).any().any():
        raise ValueError("Load-level features must remain positive")
    standard_deviations = numeric[
        ["load_rolling_std_24h_mw", "load_rolling_std_168h_mw"]
    ]
    if (standard_deviations < 0).any().any():
        raise ValueError("Rolling standard deviations must be non-negative")
    for window in (24, 168):
        minimum = numeric[f"load_rolling_min_{window}h_mw"]
        mean = numeric[f"load_rolling_mean_{window}h_mw"]
        maximum = numeric[f"load_rolling_max_{window}h_mw"]
        if not ((minimum <= mean) & (mean <= maximum)).all():
            raise ValueError(f"Rolling {window}-hour statistics are inconsistent")

    for split in FORECAST_SPLITS:
        subset = features.loc[features["split"] == split.name]
        if len(subset) != split.expected_origins * FORECAST_HORIZON_HOURS:
            raise ValueError(f"Unexpected feature-row count for {split.name}")
        if subset["forecast_origin_utc"].nunique() != split.expected_origins:
            raise ValueError(f"Unexpected feature-origin count for {split.name}")


def write_feature_matrix(features: pd.DataFrame, output_path: Path) -> None:
    """Write the ignored feature matrix atomically with stable float bytes."""
    validate_forecast_features(features)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        features.to_csv(
            temporary_path,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
            float_format="%.10f",
            na_rep="",
        )
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def build_feature_contract(
    features: pd.DataFrame,
    forecast_contract: dict[str, Any],
    *,
    feature_path: Path = DEFAULT_FEATURE_MATRIX,
    index_path: Path = DEFAULT_FORECAST_INDEX,
    contract_path: Path = DEFAULT_FORECAST_CONTRACT,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build a small deterministic contract for the ignored feature matrix."""
    validate_forecast_features(features)
    split_rows = []
    for split in FORECAST_SPLITS:
        subset = features.loc[features["split"] == split.name]
        split_rows.append(
            {
                "name": split.name,
                "origin_count": int(subset["forecast_origin_utc"].nunique()),
                "forecast_row_count": int(len(subset)),
                "materialized_target_count": int(
                    subset[FEATURE_TARGET_COLUMN].notna().sum()
                ),
            }
        )
    return {
        "schema_version": 1,
        "source": {
            "forecast_contract": {
                "path": contract_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(contract_path),
            },
            "forecast_index": {
                "path": index_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(index_path),
            },
            "consumption_sha256": forecast_contract["source"]["sha256"],
        },
        "matrix": {
            "path": feature_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(feature_path),
            "row_count": int(len(features)),
            "origin_count": int(features["forecast_origin_utc"].nunique()),
            "columns": list(FORECAST_FEATURE_COLUMNS),
            "model_feature_count": len(MODEL_FEATURE_COLUMNS),
            "model_feature_columns": list(MODEL_FEATURE_COLUMNS),
            "target_column": FEATURE_TARGET_COLUMN,
        },
        "splits": split_rows,
        "feature_families": {
            "known_target_calendar": [
                column
                for column in MODEL_FEATURE_COLUMNS
                if column.startswith("target_") or column == "horizon_step"
            ],
            "historical_load": [
                column
                for column in MODEL_FEATURE_COLUMNS
                if column.startswith(("latest_", "load_"))
            ],
        },
        "availability": {
            "minimum_history_hours": MINIMUM_HISTORY_HOURS,
            "latest_observation": "interval ending at the forecast origin",
            "rolling_windows_hours": [24, 168],
            "test_target_values_materialized": 0,
            "test_evaluation_performed": False,
        },
    }


def write_feature_contract(contract: dict[str, Any], output_path: Path) -> None:
    """Write deterministic feature-contract JSON atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    payload = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)
