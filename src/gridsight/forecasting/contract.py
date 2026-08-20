"""Forecast-origin, horizon, chronological split, and index contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from gridsight.database.data_loader import ValidatedInputs
from gridsight.database.schema_contract import PROJECT_ROOT
from gridsight.transformation.time_normalization import REPORTING_TIMEZONE

FORECAST_HORIZON_HOURS = 24
MINIMUM_HISTORY_HOURS = 168
FORECAST_ORIGIN_LOCAL_HOUR = 0
TARGET_COLUMN = "grid_load_mw"
DEFAULT_FORECAST_INDEX = (
    PROJECT_ROOT / "data" / "processed" / "forecast_index.csv"
)
DEFAULT_FORECAST_CONTRACT = PROJECT_ROOT / "reports" / "forecast_contract.json"
FORECAST_SOURCE_COLUMNS = (
    "interval_start_utc",
    "local_fold",
    TARGET_COLUMN,
)
FORECAST_INDEX_COLUMNS = (
    "forecast_origin_utc",
    "forecast_origin_local",
    "origin_local_date",
    "split",
    "horizon_step",
    "information_cutoff_utc",
    "target_start_utc",
    "target_start_local",
    "target_local_fold",
    "actual_grid_load_mw",
    "daily_naive_source_utc",
    "weekly_naive_source_utc",
)


@dataclass(frozen=True)
class ForecastSplit:
    """Inclusive local-date boundaries for one chronological role."""

    name: str
    start_local_date: date
    end_local_date: date
    expected_origins: int


FORECAST_SPLITS = (
    ForecastSplit("train", date(2022, 1, 8), date(2023, 12, 31), 723),
    ForecastSplit("validation", date(2024, 1, 1), date(2024, 12, 31), 366),
    ForecastSplit("test", date(2025, 1, 1), date(2025, 12, 31), 365),
)


def _split_for_date(local_date: date) -> str | None:
    for split in FORECAST_SPLITS:
        if split.start_local_date <= local_date <= split.end_local_date:
            return split.name
    return None


def load_forecast_source(inputs: ValidatedInputs) -> pd.DataFrame:
    """Read only the validated canonical columns needed by forecasting."""
    consumption = next(
        dataset
        for dataset in inputs.datasets
        if dataset.spec.dataset == "consumption"
    )
    frame = pd.read_csv(
        consumption.path,
        usecols=list(FORECAST_SOURCE_COLUMNS),
        dtype={"local_fold": "int64", TARGET_COLUMN: "float64"},
    )
    return frame.loc[:, list(FORECAST_SOURCE_COLUMNS)]


def _validate_source(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    if tuple(frame.columns) != FORECAST_SOURCE_COLUMNS:
        raise ValueError("Forecast source columns do not match the contract")
    if len(frame) != 35_064:
        raise ValueError("Forecast source must contain 35,064 hourly rows")
    starts = pd.to_datetime(
        frame["interval_start_utc"],
        format="mixed",
        utc=True,
        errors="raise",
    )
    if starts.duplicated().any():
        raise ValueError("Forecast source UTC starts must be unique")
    if not (starts.diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("Forecast source UTC starts must be continuous hourly")
    actual = pd.to_numeric(frame[TARGET_COLUMN], errors="raise").astype("float64")
    if not np.isfinite(actual).all() or (actual <= 0).any():
        raise ValueError("Forecast target must contain finite positive MW values")
    folds = pd.to_numeric(frame["local_fold"], errors="raise").astype("int64")
    if not folds.isin((0, 1)).all():
        raise ValueError("Forecast source local_fold must contain only 0 or 1")
    return starts, actual


def build_forecast_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Build one row per daily origin and forecast horizon without leakage."""
    starts, actual = _validate_source(frame)
    local_starts = starts.dt.tz_convert(REPORTING_TIMEZONE)
    local_folds = frame["local_fold"].astype("int64")
    origin_positions = np.flatnonzero(
        local_starts.dt.hour.to_numpy() == FORECAST_ORIGIN_LOCAL_HOUR
    )
    rows: list[dict[str, Any]] = []
    for origin_position in origin_positions:
        origin_local = local_starts.iloc[origin_position]
        origin_date = origin_local.date()
        split = _split_for_date(origin_date)
        if split is None:
            continue
        if origin_position < MINIMUM_HISTORY_HOURS:
            raise ValueError("Forecast origin does not have 168 hours of history")
        if origin_position + FORECAST_HORIZON_HOURS > len(frame):
            raise ValueError("Forecast origin does not have 24 target hours")

        origin_utc = starts.iloc[origin_position]
        origin_utc_text = origin_utc.isoformat()
        for horizon_step in range(1, FORECAST_HORIZON_HOURS + 1):
            target_position = origin_position + horizon_step - 1
            daily_position = target_position - 24
            weekly_position = target_position - 168
            rows.append(
                {
                    "forecast_origin_utc": origin_utc_text,
                    "forecast_origin_local": origin_local.isoformat(),
                    "origin_local_date": origin_date.isoformat(),
                    "split": split,
                    "horizon_step": horizon_step,
                    "information_cutoff_utc": origin_utc_text,
                    "target_start_utc": starts.iloc[target_position].isoformat(),
                    "target_start_local": (
                        local_starts.iloc[target_position].isoformat()
                    ),
                    "target_local_fold": int(local_folds.iloc[target_position]),
                    "actual_grid_load_mw": float(actual.iloc[target_position]),
                    "daily_naive_source_utc": (
                        starts.iloc[daily_position].isoformat()
                    ),
                    "weekly_naive_source_utc": (
                        starts.iloc[weekly_position].isoformat()
                    ),
                }
            )
    index = pd.DataFrame(rows, columns=FORECAST_INDEX_COLUMNS)
    validate_forecast_index(index)
    return index


def validate_forecast_index(index: pd.DataFrame) -> None:
    """Enforce split counts, 24-step horizons, UTC math, and information cutoff."""
    if tuple(index.columns) != FORECAST_INDEX_COLUMNS:
        raise ValueError("Forecast-index columns do not match the contract")
    expected_origins = sum(split.expected_origins for split in FORECAST_SPLITS)
    expected_rows = expected_origins * FORECAST_HORIZON_HOURS
    if len(index) != expected_rows:
        raise ValueError(f"Forecast index must contain {expected_rows} rows")
    if index.duplicated(["forecast_origin_utc", "horizon_step"]).any():
        raise ValueError("Forecast origin and horizon keys must be unique")

    origin = pd.to_datetime(index["forecast_origin_utc"], utc=True)
    target = pd.to_datetime(index["target_start_utc"], utc=True)
    daily_source = pd.to_datetime(index["daily_naive_source_utc"], utc=True)
    weekly_source = pd.to_datetime(index["weekly_naive_source_utc"], utc=True)
    horizon = pd.to_numeric(index["horizon_step"], errors="raise").astype("int64")
    expected_target = origin + pd.to_timedelta(horizon - 1, unit="h")
    if not (target == expected_target).all():
        raise ValueError("Forecast target timestamps do not match horizon steps")
    if not (daily_source == target - pd.Timedelta(hours=24)).all():
        raise ValueError("Daily-naive source timestamps must lag targets by 24 hours")
    if not (weekly_source == target - pd.Timedelta(hours=168)).all():
        raise ValueError("Weekly-naive source timestamps must lag targets by 168 hours")
    if not ((daily_source + pd.Timedelta(hours=1)) <= origin).all():
        raise ValueError("Daily-naive source is not complete at the forecast origin")
    if not ((weekly_source + pd.Timedelta(hours=1)) <= origin).all():
        raise ValueError("Weekly-naive source is not complete at the forecast origin")
    if not (index["information_cutoff_utc"] == index["forecast_origin_utc"]).all():
        raise ValueError("Information cutoff must equal the forecast origin")
    if not index["target_local_fold"].isin((0, 1)).all():
        raise ValueError("Forecast target folds must contain only 0 or 1")
    actual = pd.to_numeric(index["actual_grid_load_mw"], errors="raise")
    if not np.isfinite(actual).all() or (actual <= 0).any():
        raise ValueError("Forecast-index actual values must be finite and positive")

    for split in FORECAST_SPLITS:
        subset = index.loc[index["split"] == split.name]
        observed_origins = subset["forecast_origin_utc"].nunique()
        if observed_origins != split.expected_origins:
            raise ValueError(f"Unexpected origin count for {split.name}")
        if len(subset) != split.expected_origins * FORECAST_HORIZON_HOURS:
            raise ValueError(f"Unexpected forecast-row count for {split.name}")
        horizon_counts = subset.groupby("forecast_origin_utc")[
            "horizon_step"
        ].agg(["count", "min", "max"])
        if not (
            (horizon_counts["count"] == 24)
            & (horizon_counts["min"] == 1)
            & (horizon_counts["max"] == 24)
        ).all():
            raise ValueError(f"Incomplete 24-step horizon for {split.name}")


def write_forecast_index(index: pd.DataFrame, output_path: Path) -> None:
    """Write the generated forecast index atomically with stable formatting."""
    validate_forecast_index(index)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        index.to_csv(
            temporary_path,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
            float_format="%.2f",
        )
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest for one forecast artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_forecast_contract_summary(
    index: pd.DataFrame,
    inputs: ValidatedInputs,
    index_path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build a deterministic machine-readable forecast protocol summary."""
    validate_forecast_index(index)
    consumption = next(
        dataset
        for dataset in inputs.datasets
        if dataset.spec.dataset == "consumption"
    )
    split_rows = []
    for split in FORECAST_SPLITS:
        subset = index.loc[index["split"] == split.name]
        split_rows.append(
            {
                "name": split.name,
                "start_origin_local_date": split.start_local_date.isoformat(),
                "end_origin_local_date": split.end_local_date.isoformat(),
                "origin_count": split.expected_origins,
                "forecast_row_count": int(len(subset)),
            }
        )
    return {
        "schema_version": 1,
        "source": {
            "dataset": "data/processed/actual_consumption_hourly.csv",
            "sha256": consumption.sha256,
            "validation_summary_sha256": inputs.summary_sha256,
        },
        "target": {
            "column": TARGET_COLUMN,
            "unit": "MW",
            "meaning": "Germany-wide average grid load during one real hour",
        },
        "schedule": {
            "forecast_origin": "Europe/Berlin local midnight",
            "frequency": "one forecast per local calendar date",
            "horizon_steps": FORECAST_HORIZON_HOURS,
            "step_duration": "one real hour",
            "first_target_step": "interval beginning at the forecast origin",
            "information_cutoff": (
                "only observations with interval_end_utc <= forecast_origin_utc"
            ),
        },
        "history": {
            "minimum_hours": MINIMUM_HISTORY_HOURS,
            "daily_naive_lag_hours": 24,
            "weekly_naive_lag_hours": 168,
        },
        "splits": split_rows,
        "index": {
            "path": index_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(index_path),
            "columns": list(FORECAST_INDEX_COLUMNS),
            "origin_count": int(index["forecast_origin_utc"].nunique()),
            "row_count": int(len(index)),
            "first_origin_utc": str(index["forecast_origin_utc"].iloc[0]),
            "last_origin_utc": str(index["forecast_origin_utc"].iloc[-1]),
            "first_target_utc": str(index["target_start_utc"].iloc[0]),
            "last_target_utc": str(index["target_start_utc"].iloc[-1]),
        },
        "evaluation": {
            "selection_split": "validation",
            "final_test_split": "test",
            "primary_metric": "MAE_MW",
            "secondary_metrics": ["RMSE_MW", "MAPE_percent"],
            "reporting_grains": ["overall", "horizon_step"],
            "baseline_improvement": (
                "100 * (baseline_MAE - model_MAE) / baseline_MAE"
            ),
        },
        "leakage_rules": [
            "fit preprocessing and models on training rows only",
            "select features and hyperparameters using validation rows only",
            "open the 2025 test split once after the design is frozen",
            "use only data complete at each forecast origin",
            "never use random train/test splits",
        ],
    }


def write_forecast_contract(summary: dict[str, Any], output_path: Path) -> None:
    """Write deterministic forecast-contract JSON atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)
