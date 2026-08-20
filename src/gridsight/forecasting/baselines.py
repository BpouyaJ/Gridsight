"""Leakage-safe daily and weekly seasonal-naive load baselines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from gridsight.database.data_loader import ValidatedInputs
from gridsight.database.schema_contract import PROJECT_ROOT
from gridsight.forecasting.contract import (
    DEFAULT_FORECAST_CONTRACT,
    DEFAULT_FORECAST_INDEX,
    FORECAST_HORIZON_HOURS,
    FORECAST_SPLITS,
    _validate_source,
    sha256_file,
    validate_forecast_index,
)
from gridsight.forecasting.metrics import (
    ForecastMetrics,
    baseline_improvement_percent,
    evaluate_forecast,
)

DEFAULT_BASELINE_SNAPSHOT = PROJECT_ROOT / "reports" / "baseline_snapshot.json"
EVALUATION_SPLITS = ("train", "validation")
BASELINE_PREDICTION_COLUMNS = (
    "forecast_origin_utc",
    "origin_local_date",
    "split",
    "horizon_step",
    "information_cutoff_utc",
    "target_start_utc",
    "actual_grid_load_mw",
    "daily_naive_source_utc",
    "daily_naive_prediction_mw",
    "weekly_naive_source_utc",
    "weekly_naive_prediction_mw",
)


@dataclass(frozen=True)
class BaselineSpec:
    """One fixed lag-based baseline and its explicit source fields."""

    name: str
    lag_hours: int
    source_column: str
    prediction_column: str
    meaning: str


BASELINE_SPECS = (
    BaselineSpec(
        name="daily_seasonal_naive",
        lag_hours=24,
        source_column="daily_naive_source_utc",
        prediction_column="daily_naive_prediction_mw",
        meaning="load observed 24 real hours before the target interval",
    ),
    BaselineSpec(
        name="weekly_seasonal_naive",
        lag_hours=168,
        source_column="weekly_naive_source_utc",
        prediction_column="weekly_naive_prediction_mw",
        meaning="load observed 168 real hours before the target interval",
    ),
)


def _consumption_hash(inputs: ValidatedInputs) -> str:
    consumption = next(
        (
            dataset
            for dataset in inputs.datasets
            if dataset.spec.dataset == "consumption"
        ),
        None,
    )
    if consumption is None:
        raise ValueError("Validated inputs do not contain consumption data")
    return consumption.sha256


def load_frozen_forecast_index(
    inputs: ValidatedInputs,
    *,
    index_path: Path = DEFAULT_FORECAST_INDEX,
    contract_path: Path = DEFAULT_FORECAST_CONTRACT,
    project_root: Path = PROJECT_ROOT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load Step 6.1 artifacts only when their paths and hashes still match."""
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != 1:
        raise ValueError("Forecast contract schema version must equal 1")
    source = contract.get("source", {})
    if source.get("sha256") != _consumption_hash(inputs):
        raise ValueError("Forecast contract consumption hash is stale")
    if source.get("validation_summary_sha256") != inputs.summary_sha256:
        raise ValueError("Forecast contract validation-summary hash is stale")

    index_contract = contract.get("index", {})
    expected_path = index_path.relative_to(project_root).as_posix()
    if index_contract.get("path") != expected_path:
        raise ValueError("Forecast-index path does not match the frozen contract")
    if index_contract.get("sha256") != sha256_file(index_path):
        raise ValueError("Forecast-index bytes do not match the frozen contract")

    index = pd.read_csv(index_path, encoding="utf-8")
    validate_forecast_index(index)
    if index_contract.get("row_count") != len(index):
        raise ValueError("Forecast-index row count does not match the contract")
    if index_contract.get("origin_count") != index["forecast_origin_utc"].nunique():
        raise ValueError("Forecast-index origin count does not match the contract")
    return index, contract


def build_baseline_predictions(
    forecast_index: pd.DataFrame,
    source: pd.DataFrame,
) -> pd.DataFrame:
    """Resolve declared historical timestamps without scoring test targets."""
    validate_forecast_index(forecast_index)
    source_starts, source_actual = _validate_source(source)
    source_lookup = pd.Series(
        source_actual.to_numpy(dtype="float64"),
        index=pd.DatetimeIndex(source_starts),
    )
    columns = [
        column
        for column in BASELINE_PREDICTION_COLUMNS
        if not column.endswith("_prediction_mw")
    ]
    predictions = forecast_index.loc[
        forecast_index["split"].isin(EVALUATION_SPLITS),
        columns,
    ].copy()
    for baseline in BASELINE_SPECS:
        source_timestamps = pd.to_datetime(
            predictions[baseline.source_column],
            format="mixed",
            utc=True,
            errors="raise",
        )
        values = source_lookup.reindex(pd.DatetimeIndex(source_timestamps))
        if values.isna().any():
            raise ValueError(f"Missing source values for {baseline.name}")
        predictions[baseline.prediction_column] = values.to_numpy(
            dtype="float64"
        )
    predictions = predictions.loc[:, list(BASELINE_PREDICTION_COLUMNS)]
    validate_baseline_predictions(predictions)
    return predictions


def validate_baseline_predictions(predictions: pd.DataFrame) -> None:
    """Reject test scoring, incomplete grains, leakage, or invalid MW values."""
    if tuple(predictions.columns) != BASELINE_PREDICTION_COLUMNS:
        raise ValueError("Baseline-prediction columns do not match the contract")
    if set(predictions["split"].unique()) != set(EVALUATION_SPLITS):
        raise ValueError("Baselines may score only train and validation splits")
    expected_rows = sum(
        split.expected_origins * FORECAST_HORIZON_HOURS
        for split in FORECAST_SPLITS
        if split.name in EVALUATION_SPLITS
    )
    if len(predictions) != expected_rows:
        raise ValueError(f"Baseline predictions must contain {expected_rows} rows")
    if predictions.duplicated(["forecast_origin_utc", "horizon_step"]).any():
        raise ValueError("Baseline origin and horizon keys must be unique")

    origin = pd.to_datetime(
        predictions["forecast_origin_utc"], format="mixed", utc=True
    )
    target = pd.to_datetime(
        predictions["target_start_utc"], format="mixed", utc=True
    )
    horizon = pd.to_numeric(
        predictions["horizon_step"], errors="raise"
    ).astype("int64")
    if not (target == origin + pd.to_timedelta(horizon - 1, unit="h")).all():
        raise ValueError("Baseline targets do not match their horizon steps")

    for baseline in BASELINE_SPECS:
        source = pd.to_datetime(
            predictions[baseline.source_column], format="mixed", utc=True
        )
        if not (source == target - pd.Timedelta(hours=baseline.lag_hours)).all():
            raise ValueError(f"Source lag is invalid for {baseline.name}")
        if not ((source + pd.Timedelta(hours=1)) <= origin).all():
            raise ValueError(f"Source data leaks past the origin for {baseline.name}")

    value_columns = (
        "actual_grid_load_mw",
        *(baseline.prediction_column for baseline in BASELINE_SPECS),
    )
    for column in value_columns:
        values = pd.to_numeric(predictions[column], errors="raise")
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError(f"{column} must contain finite positive MW values")

    for split in FORECAST_SPLITS:
        if split.name not in EVALUATION_SPLITS:
            continue
        subset = predictions.loc[predictions["split"] == split.name]
        if subset["forecast_origin_utc"].nunique() != split.expected_origins:
            raise ValueError(f"Unexpected baseline origins for {split.name}")
        horizon_counts = subset.groupby("forecast_origin_utc")[
            "horizon_step"
        ].agg(["count", "min", "max"])
        if not (
            (horizon_counts["count"] == FORECAST_HORIZON_HOURS)
            & (horizon_counts["min"] == 1)
            & (horizon_counts["max"] == FORECAST_HORIZON_HOURS)
        ).all():
            raise ValueError(f"Incomplete baseline horizons for {split.name}")


def _metric_record(metrics: ForecastMetrics) -> dict[str, int | float]:
    return {
        "observations": metrics.observations,
        "mae_mw": round(metrics.mae_mw, 3),
        "rmse_mw": round(metrics.rmse_mw, 3),
        "mape_percent": round(metrics.mape_percent, 3),
    }


def _baseline_result(
    subset: pd.DataFrame,
    baseline: BaselineSpec,
) -> dict[str, Any]:
    overall = evaluate_forecast(
        subset["actual_grid_load_mw"],
        subset[baseline.prediction_column],
    )
    by_horizon = []
    for horizon_step in range(1, FORECAST_HORIZON_HOURS + 1):
        horizon_rows = subset.loc[subset["horizon_step"] == horizon_step]
        metrics = evaluate_forecast(
            horizon_rows["actual_grid_load_mw"],
            horizon_rows[baseline.prediction_column],
        )
        by_horizon.append(
            {"horizon_step": horizon_step, **_metric_record(metrics)}
        )
    return {
        "lag_hours": baseline.lag_hours,
        "meaning": baseline.meaning,
        "overall": _metric_record(overall),
        "by_horizon": by_horizon,
    }


def build_baseline_snapshot(
    predictions: pd.DataFrame,
    forecast_contract: dict[str, Any],
    *,
    contract_path: Path = DEFAULT_FORECAST_CONTRACT,
    index_path: Path = DEFAULT_FORECAST_INDEX,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build deterministic train/validation baseline evidence and comparison."""
    validate_baseline_predictions(predictions)
    results: dict[str, Any] = {}
    for split_name in EVALUATION_SPLITS:
        subset = predictions.loc[predictions["split"] == split_name]
        results[split_name] = {
            "origin_count": int(subset["forecast_origin_utc"].nunique()),
            "forecast_row_count": int(len(subset)),
            "baselines": {
                baseline.name: _baseline_result(subset, baseline)
                for baseline in BASELINE_SPECS
            },
        }

    validation = results["validation"]["baselines"]
    daily_mae = validation["daily_seasonal_naive"]["overall"]["mae_mw"]
    weekly_mae = validation["weekly_seasonal_naive"]["overall"]["mae_mw"]
    stronger = (
        "daily_seasonal_naive"
        if daily_mae <= weekly_mae
        else "weekly_seasonal_naive"
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
        "evaluation": {
            "included_splits": list(EVALUATION_SPLITS),
            "excluded_split": "test",
            "test_forecast_rows_scored": 0,
            "primary_metric": "MAE_MW",
            "reporting_grains": ["overall", "horizon_step"],
        },
        "results": results,
        "validation_comparison": {
            "stronger_baseline": stronger,
            "daily_mae_mw": daily_mae,
            "weekly_mae_mw": weekly_mae,
            "weekly_improvement_over_daily_percent": round(
                baseline_improvement_percent(weekly_mae, daily_mae), 3
            ),
        },
    }


def write_baseline_snapshot(snapshot: dict[str, Any], output_path: Path) -> None:
    """Write deterministic aggregate baseline results atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)
