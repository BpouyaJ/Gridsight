"""Fast tests for leakage-safe seasonal-naive forecasting baselines."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gridsight.database.data_loader import (
    DatasetLoadSpec,
    ValidatedDataset,
    ValidatedInputs,
)
from gridsight.forecasting.baselines import (
    BASELINE_PREDICTION_COLUMNS,
    build_baseline_predictions,
    build_baseline_snapshot,
    load_frozen_forecast_index,
    validate_baseline_predictions,
    write_baseline_snapshot,
)
from gridsight.forecasting.contract import (
    FORECAST_INDEX_COLUMNS,
    build_forecast_index,
    sha256_file,
    write_forecast_index,
)


@pytest.fixture(scope="module")
def source_frame() -> pd.DataFrame:
    starts = pd.date_range(
        "2021-12-31T23:00:00Z",
        periods=35_064,
        freq="h",
    )
    local = starts.tz_convert("Europe/Berlin")
    position = np.arange(len(starts), dtype="float64")
    return pd.DataFrame(
        {
            "interval_start_utc": starts,
            "local_fold": [
                timestamp.fold for timestamp in local.to_pydatetime()
            ],
            "grid_load_mw": (
                52_000
                + 6_000 * np.sin(2 * np.pi * position / 24)
                + position / 100
            ),
        }
    )


@pytest.fixture(scope="module")
def forecast_index(source_frame: pd.DataFrame) -> pd.DataFrame:
    return build_forecast_index(source_frame)


@pytest.fixture(scope="module")
def baseline_predictions(
    forecast_index: pd.DataFrame,
    source_frame: pd.DataFrame,
) -> pd.DataFrame:
    return build_baseline_predictions(forecast_index, source_frame)


def _validated_inputs(tmp_path: Path) -> ValidatedInputs:
    spec = DatasetLoadSpec(
        dataset="consumption",
        schema="staging",
        table="actual_consumption_hourly",
        relative_path="data/processed/actual_consumption_hourly.csv",
        expected_rows=35_064,
    )
    return ValidatedInputs(
        summary_path=tmp_path / "validation_summary.json",
        summary_sha256="b" * 64,
        datasets=(
            ValidatedDataset(
                spec=spec,
                path=tmp_path / "actual_consumption_hourly.csv",
                sha256="a" * 64,
                metrics={},
            ),
        ),
    )


def test_baselines_use_exact_available_lags_and_exclude_test(
    baseline_predictions: pd.DataFrame,
    source_frame: pd.DataFrame,
) -> None:
    assert tuple(baseline_predictions.columns) == BASELINE_PREDICTION_COLUMNS
    assert len(baseline_predictions) == 26_136
    assert set(baseline_predictions["split"]) == {"train", "validation"}
    assert "test" not in set(baseline_predictions["split"])

    source_lookup = source_frame.set_index("interval_start_utc")["grid_load_mw"]
    first = baseline_predictions.iloc[0]
    daily_source = pd.Timestamp(first["daily_naive_source_utc"])
    weekly_source = pd.Timestamp(first["weekly_naive_source_utc"])
    assert first["daily_naive_prediction_mw"] == pytest.approx(
        source_lookup.loc[daily_source]
    )
    assert first["weekly_naive_prediction_mw"] == pytest.approx(
        source_lookup.loc[weekly_source]
    )


def test_baseline_validation_rejects_test_scoring_and_leakage(
    baseline_predictions: pd.DataFrame,
) -> None:
    test_scored = baseline_predictions.copy()
    test_scored.loc[0, "split"] = "test"
    with pytest.raises(ValueError, match="only train and validation"):
        validate_baseline_predictions(test_scored)

    leaked = baseline_predictions.copy()
    leaked.loc[0, "daily_naive_source_utc"] = leaked.loc[
        0, "target_start_utc"
    ]
    with pytest.raises(ValueError, match="Source lag is invalid"):
        validate_baseline_predictions(leaked)


def test_baseline_snapshot_is_deterministic_and_has_all_horizons(
    baseline_predictions: pd.DataFrame,
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "forecast_contract.json"
    index_path = tmp_path / "forecast_index.csv"
    contract_path.write_text("{}\n", encoding="utf-8")
    index_path.write_text("frozen-index\n", encoding="utf-8")
    forecast_contract = {"source": {"sha256": "a" * 64}}
    snapshot = build_baseline_snapshot(
        baseline_predictions,
        forecast_contract,
        contract_path=contract_path,
        index_path=index_path,
        project_root=tmp_path,
    )
    output_path = tmp_path / "baseline_snapshot.json"
    write_baseline_snapshot(snapshot, output_path)
    first_bytes = output_path.read_bytes()
    write_baseline_snapshot(snapshot, output_path)

    assert output_path.read_bytes() == first_bytes
    parsed = json.loads(first_bytes)
    assert parsed["evaluation"]["included_splits"] == ["train", "validation"]
    assert parsed["evaluation"]["test_forecast_rows_scored"] == 0
    assert set(parsed["results"]) == {"train", "validation"}
    for split in ("train", "validation"):
        for baseline in (
            "daily_seasonal_naive",
            "weekly_seasonal_naive",
        ):
            horizons = parsed["results"][split]["baselines"][baseline][
                "by_horizon"
            ]
            assert [row["horizon_step"] for row in horizons] == list(
                range(1, 25)
            )


def test_frozen_index_loader_rejects_changed_bytes(
    forecast_index: pd.DataFrame,
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "forecast_index.csv"
    contract_path = tmp_path / "forecast_contract.json"
    write_forecast_index(forecast_index, index_path)
    contract = {
        "schema_version": 1,
        "source": {
            "sha256": "a" * 64,
            "validation_summary_sha256": "b" * 64,
        },
        "index": {
            "path": "forecast_index.csv",
            "sha256": sha256_file(index_path),
            "columns": list(FORECAST_INDEX_COLUMNS),
            "origin_count": 1_454,
            "row_count": 34_896,
        },
    }
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    inputs = _validated_inputs(tmp_path)

    loaded, loaded_contract = load_frozen_forecast_index(
        inputs,
        index_path=index_path,
        contract_path=contract_path,
        project_root=tmp_path,
    )
    assert len(loaded) == 34_896
    assert loaded_contract == contract

    index_path.write_bytes(index_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="bytes do not match"):
        load_frozen_forecast_index(
            inputs,
            index_path=index_path,
            contract_path=contract_path,
            project_root=tmp_path,
        )
