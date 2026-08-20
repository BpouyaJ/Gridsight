"""Fast tests for training-only model fitting and validation selection."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from gridsight.forecasting.contract import sha256_file
from gridsight.forecasting.features import MODEL_FEATURE_COLUMNS
from gridsight.forecasting.model_validation import (
    MODEL_CANDIDATES,
    RANDOM_STATE,
    build_estimator,
    build_model_validation_snapshot,
    fit_candidate,
    load_frozen_feature_matrix,
    load_verified_baseline_snapshot,
    select_validation_candidate,
    write_model_validation_snapshot,
)


def _candidate_result(name: str, family: str, validation_mae: float) -> dict:
    metrics = {
        "observations": 10,
        "mae_mw": validation_mae,
        "rmse_mw": validation_mae + 100,
        "mape_percent": 5.0,
    }
    return {
        "name": name,
        "family": family,
        "parameters": {},
        "train": {"overall": metrics, "by_horizon": []},
        "validation": {"overall": metrics, "by_horizon": []},
    }


def test_candidate_contracts_use_train_fitted_deterministic_estimators() -> None:
    assert [candidate.name for candidate in MODEL_CANDIDATES] == [
        "ridge_alpha_1",
        "ridge_alpha_10",
        "ridge_alpha_100",
        "hist_gradient_boosting_15_leaves",
        "hist_gradient_boosting_31_leaves",
    ]
    ridge = build_estimator(MODEL_CANDIDATES[0])
    assert isinstance(ridge, Pipeline)
    assert isinstance(ridge.named_steps["scaler"], StandardScaler)
    assert ridge.named_steps["regressor"].solver == "lsqr"

    histogram = build_estimator(MODEL_CANDIDATES[-1])
    assert isinstance(histogram, HistGradientBoostingRegressor)
    assert histogram.early_stopping is False
    assert histogram.random_state == RANDOM_STATE


def test_ridge_and_histogram_candidates_fit_without_validation_targets() -> None:
    generator = np.random.default_rng(42)
    x_train = pd.DataFrame(
        generator.normal(size=(240, len(MODEL_FEATURE_COLUMNS))),
        columns=MODEL_FEATURE_COLUMNS,
    )
    x_validation = pd.DataFrame(
        generator.normal(size=(48, len(MODEL_FEATURE_COLUMNS))),
        columns=MODEL_FEATURE_COLUMNS,
    )
    coefficients = np.linspace(10, 100, len(MODEL_FEATURE_COLUMNS))
    y_train = pd.Series(50_000 + x_train.to_numpy() @ coefficients)

    for candidate in (MODEL_CANDIDATES[0], MODEL_CANDIDATES[3]):
        _, train_prediction, validation_prediction = fit_candidate(
            candidate,
            x_train,
            y_train,
            x_validation,
        )
        assert train_prediction.shape == (240,)
        assert validation_prediction.shape == (48,)
        assert np.isfinite(train_prediction).all()
        assert np.isfinite(validation_prediction).all()


def test_validation_selection_uses_mae_and_stable_name_tie_break() -> None:
    results = (
        _candidate_result("ridge_b", "ridge", 2_000.0),
        _candidate_result("histogram", "hist_gradient_boosting", 1_900.0),
        _candidate_result("ridge_a", "ridge", 2_000.0),
    )
    assert select_validation_candidate(results)["name"] == "histogram"
    tied = (results[0], results[2])
    assert select_validation_candidate(tied)["name"] == "ridge_a"


def test_model_snapshot_is_deterministic_and_publishes_no_test_result(
    tmp_path: Path,
) -> None:
    feature_path = tmp_path / "forecast_features.csv"
    feature_contract_path = tmp_path / "feature_contract.json"
    baseline_path = tmp_path / "baseline_snapshot.json"
    output_path = tmp_path / "model_validation_snapshot.json"
    feature_path.write_text("features\n", encoding="utf-8")
    feature_contract_path.write_text("{}\n", encoding="utf-8")
    baseline_path.write_text("{}\n", encoding="utf-8")
    results = (
        _candidate_result("ridge", "ridge", 2_400.0),
        _candidate_result("histogram", "hist_gradient_boosting", 1_800.0),
    )
    baseline = {
        "validation_comparison": {"weekly_mae_mw": 2_657.167}
    }
    snapshot = build_model_validation_snapshot(
        results,
        baseline,
        feature_path=feature_path,
        feature_contract_path=feature_contract_path,
        baseline_path=baseline_path,
        project_root=tmp_path,
    )
    write_model_validation_snapshot(snapshot, output_path)
    first_bytes = output_path.read_bytes()
    write_model_validation_snapshot(snapshot, output_path)

    assert output_path.read_bytes() == first_bytes
    parsed = json.loads(first_bytes)
    assert parsed["selection"]["selected_candidate"] == "histogram"
    assert parsed["selection"]["beats_weekly_baseline"] is True
    assert parsed["training_contract"]["test_rows_scored"] == 0
    assert parsed["test_guard"]["target_values_available"] == 0
    assert parsed["test_guard"]["test_results_published"] is False
    assert "test" not in parsed["candidates"][0]


def test_frozen_loaders_reject_changed_bytes_and_lineage(tmp_path: Path) -> None:
    feature_path = tmp_path / "forecast_features.csv"
    feature_contract_path = tmp_path / "feature_contract.json"
    feature_path.write_text("changed-features\n", encoding="utf-8")
    feature_contract = {
        "schema_version": 1,
        "matrix": {
            "path": "forecast_features.csv",
            "sha256": "0" * 64,
            "model_feature_columns": list(MODEL_FEATURE_COLUMNS),
            "target_column": "actual_grid_load_mw",
        },
    }
    feature_contract_path.write_text(
        json.dumps(feature_contract), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="bytes do not match"):
        load_frozen_feature_matrix(
            feature_path=feature_path,
            contract_path=feature_contract_path,
            project_root=tmp_path,
        )

    baseline_path = tmp_path / "baseline_snapshot.json"
    baseline = {
        "schema_version": 1,
        "evaluation": {
            "included_splits": ["train", "validation"],
            "test_forecast_rows_scored": 0,
        },
        "source": {"forecast_index": {"sha256": "a" * 64}},
        "validation_comparison": {
            "stronger_baseline": "weekly_seasonal_naive",
            "weekly_mae_mw": 2_657.167,
        },
    }
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    changed_feature_contract = {
        "source": {"forecast_index": {"sha256": "b" * 64}}
    }
    with pytest.raises(ValueError, match="hashes differ"):
        load_verified_baseline_snapshot(
            changed_feature_contract,
            baseline_path=baseline_path,
        )
    assert sha256_file(baseline_path)
