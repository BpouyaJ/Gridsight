"""Fast tests for deterministic leakage-safe forecast feature engineering."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gridsight.forecasting.contract import build_forecast_index
from gridsight.forecasting.features import (
    FEATURE_TARGET_COLUMN,
    FORECAST_FEATURE_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    build_feature_contract,
    build_forecast_features,
    validate_forecast_features,
    write_feature_contract,
    write_feature_matrix,
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
def forecast_features(
    forecast_index: pd.DataFrame,
    source_frame: pd.DataFrame,
) -> pd.DataFrame:
    return build_forecast_features(forecast_index, source_frame)


def test_features_have_exact_history_values_and_redacted_test_targets(
    forecast_features: pd.DataFrame,
    source_frame: pd.DataFrame,
) -> None:
    assert tuple(forecast_features.columns) == FORECAST_FEATURE_COLUMNS
    assert len(forecast_features) == 34_896
    assert len(MODEL_FEATURE_COLUMNS) == 27
    assert FEATURE_TARGET_COLUMN not in MODEL_FEATURE_COLUMNS
    test_rows = forecast_features.loc[forecast_features["split"] == "test"]
    development_rows = forecast_features.loc[
        forecast_features["split"].isin(("train", "validation"))
    ]
    assert test_rows[FEATURE_TARGET_COLUMN].isna().all()
    assert development_rows[FEATURE_TARGET_COLUMN].notna().all()

    actual = source_frame["grid_load_mw"].to_numpy()
    first = forecast_features.iloc[0]
    last_first_origin = forecast_features.iloc[23]
    assert first["latest_load_mw"] == pytest.approx(actual[167])
    assert first["load_lag_24h_mw"] == pytest.approx(actual[144])
    assert first["load_lag_168h_mw"] == pytest.approx(actual[0])
    assert last_first_origin["load_lag_24h_mw"] == pytest.approx(actual[167])
    assert first["load_rolling_mean_24h_mw"] == pytest.approx(
        actual[144:168].mean()
    )
    assert first["load_rolling_mean_168h_mw"] == pytest.approx(
        actual[:168].mean()
    )

    folded = forecast_features.loc[forecast_features["target_local_fold"] == 1]
    assert not folded.empty
    assert set(folded["target_hour_local"]) == {2}
    assert set(folded["target_utc_offset_hours"]) == {1.0}


def test_future_target_changes_do_not_change_same_origin_features(
    forecast_features: pd.DataFrame,
    forecast_index: pd.DataFrame,
    source_frame: pd.DataFrame,
) -> None:
    first_origin = forecast_index["forecast_origin_utc"].iloc[0]
    first_origin_rows = forecast_index["forecast_origin_utc"].eq(first_origin)
    target_times = pd.to_datetime(
        forecast_index.loc[first_origin_rows, "target_start_utc"],
        utc=True,
    )
    changed_source = source_frame.copy()
    source_times = pd.to_datetime(changed_source["interval_start_utc"], utc=True)
    changed_source.loc[
        source_times.isin(target_times), "grid_load_mw"
    ] += 1_000
    changed_index = forecast_index.copy()
    changed_index.loc[first_origin_rows, "actual_grid_load_mw"] += 1_000

    changed_features = build_forecast_features(changed_index, changed_source)
    original = forecast_features.loc[first_origin_rows]
    changed = changed_features.loc[first_origin_rows]
    pd.testing.assert_frame_equal(
        original.loc[:, list(MODEL_FEATURE_COLUMNS)].reset_index(drop=True),
        changed.loc[:, list(MODEL_FEATURE_COLUMNS)].reset_index(drop=True),
    )
    assert (
        changed[FEATURE_TARGET_COLUMN].to_numpy()
        == original[FEATURE_TARGET_COLUMN].to_numpy() + 1_000
    ).all()


def test_feature_validation_rejects_test_labels_and_latest_load_leakage(
    forecast_features: pd.DataFrame,
) -> None:
    materialized_test = forecast_features.copy()
    test_index = materialized_test.index[materialized_test["split"] == "test"][0]
    materialized_test.loc[test_index, FEATURE_TARGET_COLUMN] = 50_000
    with pytest.raises(ValueError, match="Test target labels must remain redacted"):
        validate_forecast_features(materialized_test)

    leaked = forecast_features.copy()
    leaked.loc[0, "latest_observed_start_utc"] = leaked.loc[
        0, "forecast_origin_utc"
    ]
    with pytest.raises(ValueError, match="end exactly at the origin"):
        validate_forecast_features(leaked)


def test_feature_artifacts_are_deterministic_and_machine_readable(
    forecast_features: pd.DataFrame,
    tmp_path: Path,
) -> None:
    feature_path = tmp_path / "forecast_features.csv"
    index_path = tmp_path / "forecast_index.csv"
    source_contract_path = tmp_path / "forecast_contract.json"
    output_path = tmp_path / "feature_contract.json"
    index_path.write_text("frozen-index\n", encoding="utf-8")
    source_contract_path.write_text("{}\n", encoding="utf-8")
    write_feature_matrix(forecast_features, feature_path)
    first_feature_bytes = feature_path.read_bytes()
    write_feature_matrix(forecast_features, feature_path)
    assert feature_path.read_bytes() == first_feature_bytes

    source_contract = {"source": {"sha256": "a" * 64}}
    contract = build_feature_contract(
        forecast_features,
        source_contract,
        feature_path=feature_path,
        index_path=index_path,
        contract_path=source_contract_path,
        project_root=tmp_path,
    )
    write_feature_contract(contract, output_path)
    first_contract_bytes = output_path.read_bytes()
    write_feature_contract(contract, output_path)
    assert output_path.read_bytes() == first_contract_bytes

    parsed = json.loads(first_contract_bytes)
    assert parsed["matrix"]["model_feature_count"] == 27
    assert parsed["availability"]["test_target_values_materialized"] == 0
    assert parsed["availability"]["test_evaluation_performed"] is False
    test_split = next(row for row in parsed["splits"] if row["name"] == "test")
    assert test_split["materialized_target_count"] == 0

    reloaded = pd.read_csv(feature_path)
    assert reloaded.loc[reloaded["split"] == "test", FEATURE_TARGET_COLUMN].isna().all()
