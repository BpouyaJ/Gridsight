"""Fast tests for forecast origins, splits, leakage rules, and metrics."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gridsight.database.data_loader import (
    DatasetLoadSpec,
    ValidatedDataset,
    ValidatedInputs,
)
from gridsight.forecasting.contract import (
    FORECAST_HORIZON_HOURS,
    FORECAST_INDEX_COLUMNS,
    FORECAST_SPLITS,
    build_forecast_contract_summary,
    build_forecast_index,
    validate_forecast_index,
    write_forecast_index,
)
from gridsight.forecasting.metrics import (
    baseline_improvement_percent,
    evaluate_forecast,
)


def _source_frame() -> pd.DataFrame:
    starts = pd.date_range(
        "2021-12-31T23:00:00Z",
        periods=35_064,
        freq="h",
    )
    local = starts.tz_convert("Europe/Berlin")
    folds = [timestamp.fold for timestamp in local.to_pydatetime()]
    position = np.arange(len(starts), dtype="float64")
    load = 52_000 + 6_000 * np.sin(2 * np.pi * position / 24)
    return pd.DataFrame(
        {
            "interval_start_utc": starts,
            "local_fold": folds,
            "grid_load_mw": load,
        }
    )


@pytest.fixture(scope="module")
def forecast_index() -> pd.DataFrame:
    """Build the complete synthetic contract once for this test module."""
    return build_forecast_index(_source_frame())


def test_forecast_index_has_exact_chronological_splits_and_horizons(
    forecast_index: pd.DataFrame,
) -> None:
    """Every local-midnight origin has 24 ordered targets in one split."""
    assert tuple(forecast_index.columns) == FORECAST_INDEX_COLUMNS
    assert len(forecast_index) == 34_896
    assert forecast_index["forecast_origin_utc"].nunique() == 1_454
    assert forecast_index.iloc[0]["origin_local_date"] == "2022-01-08"
    assert forecast_index.iloc[-1]["origin_local_date"] == "2025-12-31"
    assert forecast_index.iloc[0]["horizon_step"] == 1
    assert forecast_index.iloc[23]["horizon_step"] == 24
    assert {
        split.name: forecast_index.loc[
            forecast_index["split"] == split.name,
            "forecast_origin_utc",
        ].nunique()
        for split in FORECAST_SPLITS
    } == {"train": 723, "validation": 366, "test": 365}


def test_local_midnight_origins_keep_24_real_hours_across_dst(
    forecast_index: pd.DataFrame,
) -> None:
    """Origin spacing reflects DST while each target horizon stays hourly."""
    origins = forecast_index.drop_duplicates("forecast_origin_utc").set_index(
        "origin_local_date"
    )
    spring_before = pd.Timestamp(origins.loc["2024-03-31", "forecast_origin_utc"])
    spring_after = pd.Timestamp(origins.loc["2024-04-01", "forecast_origin_utc"])
    autumn_before = pd.Timestamp(origins.loc["2024-10-27", "forecast_origin_utc"])
    autumn_after = pd.Timestamp(origins.loc["2024-10-28", "forecast_origin_utc"])

    assert spring_after - spring_before == pd.Timedelta(hours=23)
    assert autumn_after - autumn_before == pd.Timedelta(hours=25)
    spring_horizon = forecast_index.loc[
        forecast_index["origin_local_date"] == "2024-03-31"
    ]
    target_starts = pd.to_datetime(spring_horizon["target_start_utc"], utc=True)
    assert (target_starts.diff().dropna() == pd.Timedelta(hours=1)).all()
    assert spring_horizon["horizon_step"].tolist() == list(
        range(1, FORECAST_HORIZON_HOURS + 1)
    )


def test_forecast_contract_rejects_leakage_and_changed_source(
    forecast_index: pd.DataFrame,
) -> None:
    """Future baseline inputs and a duplicate source timestamp are rejected."""
    changed_index = forecast_index.copy()
    changed_index.loc[0, "daily_naive_source_utc"] = changed_index.loc[
        0, "forecast_origin_utc"
    ]
    with pytest.raises(ValueError, match="Daily-naive source timestamps"):
        validate_forecast_index(changed_index)

    changed_source = _source_frame()
    changed_source.loc[1, "interval_start_utc"] = changed_source.loc[
        0, "interval_start_utc"
    ]
    with pytest.raises(ValueError, match="must be unique"):
        build_forecast_index(changed_source)


def test_forecast_metrics_and_index_writer_are_explicit_and_deterministic(
    forecast_index: pd.DataFrame,
    tmp_path: Path,
) -> None:
    """Metric units and the ignored forecast-index bytes remain stable."""
    metrics = evaluate_forecast([100.0, 200.0], [110.0, 180.0])
    assert metrics.observations == 2
    assert metrics.mae_mw == pytest.approx(15.0)
    assert metrics.rmse_mw == pytest.approx(np.sqrt(250))
    assert metrics.mape_percent == pytest.approx(10.0)
    assert baseline_improvement_percent(12.0, 15.0) == pytest.approx(20.0)

    output_path = tmp_path / "forecast_index.csv"
    write_forecast_index(forecast_index, output_path)
    first_bytes = output_path.read_bytes()
    write_forecast_index(forecast_index, output_path)
    assert output_path.read_bytes() == first_bytes
    assert first_bytes.startswith(
        (",".join(FORECAST_INDEX_COLUMNS) + "\n").encode()
    )

    load_spec = DatasetLoadSpec(
        dataset="consumption",
        schema="staging",
        table="actual_consumption_hourly",
        relative_path="data/processed/actual_consumption_hourly.csv",
        expected_rows=len(forecast_index),
    )
    validated_inputs = ValidatedInputs(
        summary_path=tmp_path / "validation_summary.json",
        summary_sha256="b" * 64,
        datasets=(
            ValidatedDataset(
                spec=load_spec,
                path=tmp_path / "actual_consumption_hourly.csv",
                sha256="a" * 64,
                metrics={},
            ),
        ),
    )
    summary = build_forecast_contract_summary(
        forecast_index,
        validated_inputs,
        output_path,
        project_root=tmp_path,
    )
    assert summary["index"]["first_origin_utc"] == "2022-01-07T23:00:00+00:00"
    assert summary["index"]["last_origin_utc"] == "2025-12-30T23:00:00+00:00"
    assert summary["index"]["first_target_utc"] == "2022-01-07T23:00:00+00:00"
    assert summary["index"]["last_target_utc"] == "2025-12-31T22:00:00+00:00"
