"""Fast tests for frozen-design final forecast evaluation."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import sklearn
from sklearn.pipeline import Pipeline

from gridsight.forecasting.contract import sha256_file
from gridsight.forecasting.features import (
    FEATURE_TARGET_COLUMN,
    MODEL_FEATURE_COLUMNS,
)
from gridsight.forecasting.final_evaluation import (
    FINAL_FIT_SPLITS,
    _aligned_target_values,
    _assemble_final_predictions,
    build_final_evaluation_snapshot,
    fit_final_model,
    load_frozen_model_selection,
    validate_final_predictions,
    write_final_evaluation_snapshot,
    write_final_predictions,
)
from gridsight.forecasting.model_validation import MODEL_CANDIDATES


def _candidate_result(index: int) -> dict:
    candidate = MODEL_CANDIDATES[index]
    mae = 2_500.0 - index * 250.0
    metrics = {
        "observations": 100,
        "mae_mw": mae,
        "rmse_mw": mae + 500.0,
        "mape_percent": 4.0,
    }
    return {
        "name": candidate.name,
        "family": candidate.family,
        "parameters": candidate.parameters,
        "train": {"overall": metrics, "by_horizon": []},
        "validation": {"overall": metrics, "by_horizon": []},
    }


def _model_validation_snapshot(
    root: Path,
    feature_path: Path,
    feature_contract_path: Path,
    baseline_path: Path,
) -> dict:
    results = [_candidate_result(index) for index in range(len(MODEL_CANDIDATES))]
    selected = results[-1]
    return {
        "schema_version": 1,
        "source": {
            "feature_contract": {
                "path": feature_contract_path.relative_to(root).as_posix(),
                "sha256": sha256_file(feature_contract_path),
            },
            "feature_matrix": {
                "path": feature_path.relative_to(root).as_posix(),
                "sha256": sha256_file(feature_path),
            },
            "baseline_snapshot": {
                "path": baseline_path.relative_to(root).as_posix(),
                "sha256": sha256_file(baseline_path),
            },
            "scikit_learn_version": sklearn.__version__,
        },
        "training_contract": {
            "fit_split": "train",
            "selection_split": "validation",
            "test_split": "test",
            "test_rows_scored": 0,
            "model_feature_count": len(MODEL_FEATURE_COLUMNS),
        },
        "candidates": results,
        "selection": {
            "selected_candidate": selected["name"],
            "selected_family": selected["family"],
            "selected_validation_mae_mw": selected["validation"]["overall"][
                "mae_mw"
            ],
        },
        "test_guard": {
            "target_values_available": 0,
            "forecast_rows_scored": 0,
            "test_results_published": False,
        },
    }


def _test_index(expected_origins: int) -> pd.DataFrame:
    rows = []
    first_origin = pd.Timestamp("2025-01-01T00:00:00Z")
    for origin_number in range(expected_origins):
        origin = first_origin + pd.Timedelta(days=origin_number)
        for horizon_step in range(1, 25):
            target = origin + pd.Timedelta(hours=horizon_step - 1)
            rows.append(
                {
                    "forecast_origin_utc": origin.isoformat(),
                    "origin_local_date": origin.date().isoformat(),
                    "split": "test",
                    "horizon_step": horizon_step,
                    "information_cutoff_utc": origin.isoformat(),
                    "target_start_utc": target.isoformat(),
                    "target_start_local": target.isoformat(),
                    "actual_grid_load_mw": 50_000.0 + horizon_step,
                    "daily_naive_source_utc": (
                        target - pd.Timedelta(hours=24)
                    ).isoformat(),
                    "weekly_naive_source_utc": (
                        target - pd.Timedelta(hours=168)
                    ).isoformat(),
                }
            )
    return pd.DataFrame(rows)


def _prediction_frame(expected_origins: int) -> pd.DataFrame:
    index = _test_index(expected_origins)
    rows = len(index)
    return _assemble_final_predictions(
        index,
        np.full(rows, 50_100.0),
        np.full(rows, 49_000.0),
        np.full(rows, 48_000.0),
        MODEL_CANDIDATES[-1].name,
    )


def test_frozen_selection_requires_exact_lineage_and_zero_test_evidence(
    tmp_path: Path,
) -> None:
    feature_path = tmp_path / "forecast_features.csv"
    feature_contract_path = tmp_path / "feature_contract.json"
    baseline_path = tmp_path / "baseline_snapshot.json"
    snapshot_path = tmp_path / "model_validation_snapshot.json"
    feature_path.write_text("frozen features\n", encoding="utf-8")
    feature_contract = {"matrix": {"sha256": sha256_file(feature_path)}}
    feature_contract_path.write_text("{}\n", encoding="utf-8")
    baseline_path.write_text("{}\n", encoding="utf-8")
    snapshot = _model_validation_snapshot(
        tmp_path,
        feature_path,
        feature_contract_path,
        baseline_path,
    )
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    loaded, candidate = load_frozen_model_selection(
        feature_contract,
        snapshot_path=snapshot_path,
        feature_path=feature_path,
        feature_contract_path=feature_contract_path,
        baseline_path=baseline_path,
        project_root=tmp_path,
    )
    assert loaded["test_guard"]["forecast_rows_scored"] == 0
    assert candidate == MODEL_CANDIDATES[-1]

    feature_path.write_text("changed features\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bytes do not match"):
        load_frozen_model_selection(
            feature_contract,
            snapshot_path=snapshot_path,
            feature_path=feature_path,
            feature_contract_path=feature_contract_path,
            baseline_path=baseline_path,
            project_root=tmp_path,
        )


def test_target_unlock_requires_exact_alignment_and_redacted_test() -> None:
    alignment = pd.DataFrame(
        {
            "forecast_origin_utc": ["a", "b", "c", "d"],
            "origin_local_date": ["1", "2", "3", "4"],
            "split": ["train", "validation", "test", "test"],
            "horizon_step": [1, 1, 1, 2],
            "information_cutoff_utc": ["a", "b", "c", "c"],
            "target_start_utc": ["a", "b", "c", "d"],
            "target_start_local": ["a", "b", "c", "d"],
        }
    )
    features = alignment.copy()
    features[FEATURE_TARGET_COLUMN] = [10.0, 20.0, np.nan, np.nan]
    forecast_index = alignment.copy()
    forecast_index[FEATURE_TARGET_COLUMN] = [10.0, 20.0, 30.0, 40.0]

    actual = _aligned_target_values(features, forecast_index)
    assert actual.tolist() == [10.0, 20.0, 30.0, 40.0]

    features.loc[2, FEATURE_TARGET_COLUMN] = 30.0
    with pytest.raises(ValueError, match="unlocked before final"):
        _aligned_target_values(features, forecast_index)


def test_final_refit_never_uses_test_targets() -> None:
    generator = np.random.default_rng(42)
    rows = 144
    features = pd.DataFrame(
        generator.normal(size=(rows, len(MODEL_FEATURE_COLUMNS))),
        columns=MODEL_FEATURE_COLUMNS,
    )
    features["split"] = ["train"] * 80 + ["validation"] * 40 + ["test"] * 24
    features[FEATURE_TARGET_COLUMN] = 50_000.0 + generator.normal(size=rows)
    candidate = MODEL_CANDIDATES[0]

    estimator, first_prediction = fit_final_model(candidate, features)
    changed_test = features.copy()
    changed_test.loc[
        changed_test["split"].eq("test"), FEATURE_TARGET_COLUMN
    ] *= 10
    _, second_prediction = fit_final_model(candidate, changed_test)

    assert isinstance(estimator, Pipeline)
    assert np.array_equal(first_prediction, second_prediction)
    assert set(FINAL_FIT_SPLITS) == {"train", "validation"}


def test_final_prediction_contract_rejects_incomplete_or_leaking_rows() -> None:
    predictions = _prediction_frame(2)
    validate_final_predictions(predictions, expected_origins=2)

    incomplete = predictions.iloc[:-1]
    with pytest.raises(ValueError, match="48 rows"):
        validate_final_predictions(incomplete, expected_origins=2)

    leaking = predictions.copy()
    leaking.loc[0, "daily_naive_source_utc"] = leaking.loc[
        0, "forecast_origin_utc"
    ]
    with pytest.raises(ValueError, match="source lag is invalid"):
        validate_final_predictions(leaking, expected_origins=2)


def test_final_artifacts_are_deterministic_and_forbid_more_selection(
    tmp_path: Path,
) -> None:
    candidate = MODEL_CANDIDATES[-1]
    predictions = _prediction_frame(365)
    predictions_path = tmp_path / "final_forecast_predictions.csv"
    snapshot_path = tmp_path / "final_evaluation_snapshot.json"
    source_paths = {
        "model_validation_path": tmp_path / "model_validation_snapshot.json",
        "feature_path": tmp_path / "forecast_features.csv",
        "feature_contract_path": tmp_path / "feature_contract.json",
        "baseline_path": tmp_path / "baseline_snapshot.json",
        "forecast_index_path": tmp_path / "forecast_index.csv",
        "forecast_contract_path": tmp_path / "forecast_contract.json",
    }
    for path in source_paths.values():
        path.write_text(f"{path.name}\n", encoding="utf-8")
    write_final_predictions(predictions, predictions_path)
    first_prediction_bytes = predictions_path.read_bytes()
    write_final_predictions(predictions, predictions_path)
    assert predictions_path.read_bytes() == first_prediction_bytes

    development = pd.DataFrame(
        {
            "split": ["train", "validation"],
            "forecast_origin_utc": ["train-origin", "validation-origin"],
            FEATURE_TARGET_COLUMN: [50_000.0, 51_000.0],
        }
    )
    test_features = pd.DataFrame(
        {
            "split": ["test"] * len(predictions),
            "forecast_origin_utc": predictions["forecast_origin_utc"],
            FEATURE_TARGET_COLUMN: predictions["actual_grid_load_mw"],
        }
    )
    unlocked = pd.concat([development, test_features], ignore_index=True)
    model_validation = {
        "selection": {
            "selected_candidate": candidate.name,
            "selected_validation_mae_mw": 1_462.293,
        }
    }
    forecast_contract = {
        "source": {
            "sha256": "a" * 64,
            "validation_summary_sha256": "b" * 64,
        }
    }
    snapshot = build_final_evaluation_snapshot(
        predictions,
        unlocked,
        forecast_contract,
        model_validation,
        candidate,
        predictions_path=predictions_path,
        project_root=tmp_path,
        **source_paths,
    )
    write_final_evaluation_snapshot(snapshot, snapshot_path)
    first_snapshot_bytes = snapshot_path.read_bytes()
    write_final_evaluation_snapshot(snapshot, snapshot_path)

    assert snapshot_path.read_bytes() == first_snapshot_bytes
    assert snapshot["final_fit_contract"]["test_influenced_design"] is False
    assert (
        snapshot["final_fit_contract"]["further_model_selection_allowed"]
        is False
    )
    assert snapshot["test_evaluation"]["forecast_rows"] == 8_760
    assert snapshot["prediction_artifact"]["sha256"] == sha256_file(
        predictions_path
    )
