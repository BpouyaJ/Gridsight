"""Frozen-model refit and one-time chronological test evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn

from gridsight.database.schema_contract import PROJECT_ROOT
from gridsight.forecasting.baselines import (
    BASELINE_SPECS,
    DEFAULT_BASELINE_SNAPSHOT,
)
from gridsight.forecasting.contract import (
    DEFAULT_FORECAST_CONTRACT,
    DEFAULT_FORECAST_INDEX,
    FORECAST_HORIZON_HOURS,
    _validate_source,
    sha256_file,
    validate_forecast_index,
)
from gridsight.forecasting.features import (
    DEFAULT_FEATURE_CONTRACT,
    DEFAULT_FEATURE_MATRIX,
    FEATURE_TARGET_COLUMN,
    MODEL_FEATURE_COLUMNS,
    validate_forecast_features,
)
from gridsight.forecasting.metrics import (
    ForecastMetrics,
    baseline_improvement_percent,
    evaluate_forecast,
)
from gridsight.forecasting.model_validation import (
    DEFAULT_MODEL_VALIDATION_SNAPSHOT,
    MODEL_CANDIDATES,
    RANDOM_STATE,
    ModelCandidate,
    build_estimator,
    select_validation_candidate,
)

DEFAULT_FINAL_PREDICTIONS = (
    PROJECT_ROOT / "data" / "processed" / "final_forecast_predictions.csv"
)
DEFAULT_FINAL_EVALUATION_SNAPSHOT = (
    PROJECT_ROOT / "reports" / "final_evaluation_snapshot.json"
)
FINAL_PREDICTION_COLUMNS = (
    "forecast_origin_utc",
    "origin_local_date",
    "split",
    "horizon_step",
    "information_cutoff_utc",
    "target_start_utc",
    "target_start_local",
    "actual_grid_load_mw",
    "daily_naive_source_utc",
    "daily_naive_prediction_mw",
    "weekly_naive_source_utc",
    "weekly_naive_prediction_mw",
    "model_name",
    "model_prediction_mw",
    "model_error_mw",
    "model_absolute_error_mw",
)
ALIGNMENT_COLUMNS = (
    "forecast_origin_utc",
    "origin_local_date",
    "split",
    "horizon_step",
    "information_cutoff_utc",
    "target_start_utc",
    "target_start_local",
)
FINAL_FIT_SPLITS = ("train", "validation")
FINAL_TEST_SPLIT = "test"


def _artifact_record(
    snapshot: dict[str, Any],
    key: str,
    path: Path,
    project_root: Path,
) -> dict[str, Any]:
    source = snapshot.get("source", {})
    record = source.get(key, {})
    expected_path = path.relative_to(project_root).as_posix()
    if record.get("path") != expected_path:
        raise ValueError(f"{key} path does not match the frozen model report")
    if record.get("sha256") != sha256_file(path):
        raise ValueError(f"{key} bytes do not match the frozen model report")
    return record


def load_frozen_model_selection(
    feature_contract: dict[str, Any],
    *,
    snapshot_path: Path = DEFAULT_MODEL_VALIDATION_SNAPSHOT,
    feature_path: Path = DEFAULT_FEATURE_MATRIX,
    feature_contract_path: Path = DEFAULT_FEATURE_CONTRACT,
    baseline_path: Path = DEFAULT_BASELINE_SNAPSHOT,
    project_root: Path = PROJECT_ROOT,
) -> tuple[dict[str, Any], ModelCandidate]:
    """Verify Step 6.4 lineage and return its pre-test selected design."""
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != 1:
        raise ValueError("Model-validation schema version must equal 1")

    _artifact_record(
        snapshot,
        "feature_contract",
        feature_contract_path,
        project_root,
    )
    matrix_record = _artifact_record(
        snapshot,
        "feature_matrix",
        feature_path,
        project_root,
    )
    _artifact_record(snapshot, "baseline_snapshot", baseline_path, project_root)
    if matrix_record.get("sha256") != feature_contract.get("matrix", {}).get(
        "sha256"
    ):
        raise ValueError("Feature matrix and contract lineage do not match")
    if snapshot.get("source", {}).get("scikit_learn_version") != sklearn.__version__:
        raise ValueError("scikit-learn version differs from model validation")

    training = snapshot.get("training_contract", {})
    if (
        training.get("fit_split") != "train"
        or training.get("selection_split") != "validation"
        or training.get("test_split") != FINAL_TEST_SPLIT
        or training.get("test_rows_scored") != 0
        or training.get("model_feature_count") != len(MODEL_FEATURE_COLUMNS)
    ):
        raise ValueError("Model-validation training contract is not frozen")
    guard = snapshot.get("test_guard", {})
    if (
        guard.get("target_values_available") != 0
        or guard.get("forecast_rows_scored") != 0
        or guard.get("test_results_published") is not False
    ):
        raise ValueError("Model-validation report already contains test evidence")

    results = snapshot.get("candidates")
    if not isinstance(results, list) or [result.get("name") for result in results] != [
        candidate.name for candidate in MODEL_CANDIDATES
    ]:
        raise ValueError("Model-validation candidates do not match the frozen list")
    selected_result = select_validation_candidate(tuple(results))
    selection = snapshot.get("selection", {})
    if selection.get("selected_candidate") != selected_result.get("name"):
        raise ValueError("Frozen model selection does not match validation MAE")
    if selection.get("selected_family") != selected_result.get("family"):
        raise ValueError("Frozen selected model family is inconsistent")
    selected_mae = selected_result.get("validation", {}).get("overall", {}).get(
        "mae_mw"
    )
    if selection.get("selected_validation_mae_mw") != selected_mae:
        raise ValueError("Frozen selected validation MAE is inconsistent")

    candidate = next(
        (
            item
            for item in MODEL_CANDIDATES
            if item.name == selection["selected_candidate"]
        ),
        None,
    )
    if candidate is None:
        raise ValueError("Frozen selected candidate is not declared")
    if (
        selected_result.get("family") != candidate.family
        or selected_result.get("parameters") != candidate.parameters
    ):
        raise ValueError("Frozen selected parameters are not predeclared")
    return snapshot, candidate


def _aligned_target_values(
    features: pd.DataFrame,
    forecast_index: pd.DataFrame,
) -> pd.Series:
    """Align hidden index targets to features without changing row order."""
    if len(features) != len(forecast_index):
        raise ValueError("Feature and forecast-index row counts differ")
    for column in ALIGNMENT_COLUMNS:
        if column not in features or column not in forecast_index:
            raise ValueError(f"Missing target-alignment column: {column}")
        if not np.array_equal(
            features[column].astype(str).to_numpy(),
            forecast_index[column].astype(str).to_numpy(),
        ):
            raise ValueError(f"Feature and forecast-index {column} values differ")

    actual = pd.to_numeric(
        forecast_index[FEATURE_TARGET_COLUMN], errors="raise"
    ).astype("float64")
    if not np.isfinite(actual).all() or (actual <= 0).any():
        raise ValueError("Final target values must be finite positive MW")
    existing = pd.to_numeric(features[FEATURE_TARGET_COLUMN], errors="coerce")
    development = features["split"].isin(FINAL_FIT_SPLITS)
    test = features["split"].eq(FINAL_TEST_SPLIT)
    if existing.loc[development].isna().any():
        raise ValueError("Development targets must already be materialized")
    if not np.allclose(
        existing.loc[development],
        actual.loc[development],
        rtol=0.0,
        atol=1e-9,
    ):
        raise ValueError("Development targets differ from the frozen index")
    if existing.loc[test].notna().any():
        raise ValueError("Test targets were unlocked before final evaluation")
    return actual


def unlock_final_test_targets(
    features: pd.DataFrame,
    forecast_index: pd.DataFrame,
) -> pd.DataFrame:
    """Materialize test labels only after all design choices are frozen."""
    validate_forecast_features(features)
    validate_forecast_index(forecast_index)
    actual = _aligned_target_values(features, forecast_index)
    unlocked = features.copy()
    test = unlocked["split"].eq(FINAL_TEST_SPLIT)
    unlocked.loc[test, FEATURE_TARGET_COLUMN] = actual.to_numpy()[
        test.to_numpy()
    ]
    if int(test.sum()) != 8_760:
        raise ValueError("Final evaluation must unlock exactly 8,760 test targets")
    if unlocked[FEATURE_TARGET_COLUMN].isna().any():
        raise ValueError("Final evaluation requires complete target labels")
    return unlocked


def fit_final_model(
    candidate: ModelCandidate,
    unlocked_features: pd.DataFrame,
) -> tuple[Any, np.ndarray]:
    """Refit the frozen design on train plus validation and predict test."""
    if tuple(
        unlocked_features.loc[:, list(MODEL_FEATURE_COLUMNS)].columns
    ) != MODEL_FEATURE_COLUMNS:
        raise ValueError("Final model features do not match the frozen contract")
    development = unlocked_features.loc[
        unlocked_features["split"].isin(FINAL_FIT_SPLITS)
    ]
    test = unlocked_features.loc[
        unlocked_features["split"].eq(FINAL_TEST_SPLIT)
    ]
    if development.empty or test.empty:
        raise ValueError("Final fitting requires development and test rows")
    y_development = pd.to_numeric(
        development[FEATURE_TARGET_COLUMN], errors="raise"
    )
    if y_development.isna().any():
        raise ValueError("Final fitting requires complete development targets")

    estimator = build_estimator(candidate)
    estimator.fit(
        development.loc[:, list(MODEL_FEATURE_COLUMNS)],
        y_development,
    )
    prediction = np.asarray(
        estimator.predict(test.loc[:, list(MODEL_FEATURE_COLUMNS)]),
        dtype="float64",
    )
    if not np.isfinite(prediction).all() or (prediction <= 0).any():
        raise ValueError("Final model predictions must be finite positive MW")
    return estimator, prediction


def _assemble_final_predictions(
    test_index: pd.DataFrame,
    model_prediction: np.ndarray,
    daily_prediction: np.ndarray,
    weekly_prediction: np.ndarray,
    model_name: str,
) -> pd.DataFrame:
    if not (
        len(test_index)
        == len(model_prediction)
        == len(daily_prediction)
        == len(weekly_prediction)
    ):
        raise ValueError("Final prediction arrays must have equal row counts")
    actual = pd.to_numeric(
        test_index[FEATURE_TARGET_COLUMN], errors="raise"
    ).to_numpy(dtype="float64")
    model_values = np.round(np.asarray(model_prediction, dtype="float64"), 6)
    daily_values = np.round(np.asarray(daily_prediction, dtype="float64"), 6)
    weekly_values = np.round(np.asarray(weekly_prediction, dtype="float64"), 6)
    error = np.round(model_values - actual, 6)
    return pd.DataFrame(
        {
            "forecast_origin_utc": test_index["forecast_origin_utc"].to_numpy(),
            "origin_local_date": test_index["origin_local_date"].to_numpy(),
            "split": test_index["split"].to_numpy(),
            "horizon_step": test_index["horizon_step"].to_numpy(),
            "information_cutoff_utc": test_index[
                "information_cutoff_utc"
            ].to_numpy(),
            "target_start_utc": test_index["target_start_utc"].to_numpy(),
            "target_start_local": test_index["target_start_local"].to_numpy(),
            "actual_grid_load_mw": actual,
            "daily_naive_source_utc": test_index[
                "daily_naive_source_utc"
            ].to_numpy(),
            "daily_naive_prediction_mw": daily_values,
            "weekly_naive_source_utc": test_index[
                "weekly_naive_source_utc"
            ].to_numpy(),
            "weekly_naive_prediction_mw": weekly_values,
            "model_name": model_name,
            "model_prediction_mw": model_values,
            "model_error_mw": error,
            "model_absolute_error_mw": np.round(np.abs(error), 6),
        },
        columns=FINAL_PREDICTION_COLUMNS,
    )


def build_final_predictions(
    forecast_index: pd.DataFrame,
    source: pd.DataFrame,
    model_prediction: np.ndarray,
    candidate: ModelCandidate,
) -> pd.DataFrame:
    """Build model and baseline predictions for the frozen test split."""
    validate_forecast_index(forecast_index)
    source_starts, source_actual = _validate_source(source)
    source_lookup = pd.Series(
        source_actual.to_numpy(dtype="float64"),
        index=pd.DatetimeIndex(source_starts),
    )
    test_index = forecast_index.loc[
        forecast_index["split"].eq(FINAL_TEST_SPLIT)
    ].copy()
    baseline_values: dict[str, np.ndarray] = {}
    for baseline in BASELINE_SPECS:
        timestamps = pd.to_datetime(
            test_index[baseline.source_column],
            format="mixed",
            utc=True,
            errors="raise",
        )
        values = source_lookup.reindex(pd.DatetimeIndex(timestamps))
        if values.isna().any():
            raise ValueError(f"Missing final sources for {baseline.name}")
        baseline_values[baseline.name] = values.to_numpy(dtype="float64")

    predictions = _assemble_final_predictions(
        test_index,
        model_prediction,
        baseline_values["daily_seasonal_naive"],
        baseline_values["weekly_seasonal_naive"],
        candidate.name,
    )
    validate_final_predictions(predictions)
    return predictions


def validate_final_predictions(
    predictions: pd.DataFrame,
    *,
    expected_origins: int = 365,
) -> None:
    """Validate final test grain, availability, values, and error columns."""
    if tuple(predictions.columns) != FINAL_PREDICTION_COLUMNS:
        raise ValueError("Final-prediction columns do not match the contract")
    expected_rows = expected_origins * FORECAST_HORIZON_HOURS
    if len(predictions) != expected_rows:
        raise ValueError(f"Final predictions must contain {expected_rows} rows")
    if set(predictions["split"].unique()) != {FINAL_TEST_SPLIT}:
        raise ValueError("Final predictions may contain only test rows")
    if predictions["forecast_origin_utc"].nunique() != expected_origins:
        raise ValueError("Final prediction origin count is invalid")
    if predictions.duplicated(["forecast_origin_utc", "horizon_step"]).any():
        raise ValueError("Final origin and horizon keys must be unique")
    horizon_counts = predictions.groupby("forecast_origin_utc")[
        "horizon_step"
    ].agg(["count", "min", "max"])
    if not (
        (horizon_counts["count"] == FORECAST_HORIZON_HOURS)
        & (horizon_counts["min"] == 1)
        & (horizon_counts["max"] == FORECAST_HORIZON_HOURS)
    ).all():
        raise ValueError("Final predictions require complete 24-step horizons")

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
        raise ValueError("Final targets do not match their horizon steps")
    if not (predictions["information_cutoff_utc"] == predictions[
        "forecast_origin_utc"
    ]).all():
        raise ValueError("Final information cutoff must equal the origin")

    for baseline in BASELINE_SPECS:
        source = pd.to_datetime(
            predictions[baseline.source_column], format="mixed", utc=True
        )
        if not (source == target - pd.Timedelta(hours=baseline.lag_hours)).all():
            raise ValueError(f"Final source lag is invalid for {baseline.name}")
        if not ((source + pd.Timedelta(hours=1)) <= origin).all():
            raise ValueError(f"Final source leaks for {baseline.name}")

    positive_columns = (
        "actual_grid_load_mw",
        "daily_naive_prediction_mw",
        "weekly_naive_prediction_mw",
        "model_prediction_mw",
    )
    numeric = predictions.loc[:, list(positive_columns)].apply(
        pd.to_numeric, errors="raise"
    )
    if not np.isfinite(numeric.to_numpy(dtype="float64")).all():
        raise ValueError("Final load values must be finite")
    if (numeric <= 0).any().any():
        raise ValueError("Final load values must be positive MW")
    if predictions["model_name"].nunique() != 1:
        raise ValueError("Final predictions must use one frozen model")
    expected_error = (
        numeric["model_prediction_mw"] - numeric["actual_grid_load_mw"]
    )
    error = pd.to_numeric(predictions["model_error_mw"], errors="raise")
    absolute = pd.to_numeric(
        predictions["model_absolute_error_mw"], errors="raise"
    )
    if not np.allclose(error, expected_error, rtol=0.0, atol=1e-6):
        raise ValueError("Final model error does not reconcile")
    if not np.allclose(absolute, np.abs(error), rtol=0.0, atol=1e-6):
        raise ValueError("Final absolute error does not reconcile")


def _metric_record(metrics: ForecastMetrics) -> dict[str, int | float]:
    return {
        "observations": metrics.observations,
        "mae_mw": round(metrics.mae_mw, 3),
        "rmse_mw": round(metrics.rmse_mw, 3),
        "mape_percent": round(metrics.mape_percent, 3),
    }


def _evaluate_prediction_column(
    predictions: pd.DataFrame,
    column: str,
) -> dict[str, Any]:
    actual = predictions["actual_grid_load_mw"].to_numpy(dtype="float64")
    predicted = predictions[column].to_numpy(dtype="float64")
    horizon = predictions["horizon_step"].to_numpy(dtype="int64")
    by_horizon = []
    for horizon_step in range(1, FORECAST_HORIZON_HOURS + 1):
        mask = horizon == horizon_step
        by_horizon.append(
            {
                "horizon_step": horizon_step,
                **_metric_record(evaluate_forecast(actual[mask], predicted[mask])),
            }
        )
    return {
        "overall": _metric_record(evaluate_forecast(actual, predicted)),
        "by_horizon": by_horizon,
    }


def build_final_evaluation_snapshot(
    predictions: pd.DataFrame,
    unlocked_features: pd.DataFrame,
    forecast_contract: dict[str, Any],
    model_validation: dict[str, Any],
    candidate: ModelCandidate,
    *,
    predictions_path: Path = DEFAULT_FINAL_PREDICTIONS,
    model_validation_path: Path = DEFAULT_MODEL_VALIDATION_SNAPSHOT,
    feature_path: Path = DEFAULT_FEATURE_MATRIX,
    feature_contract_path: Path = DEFAULT_FEATURE_CONTRACT,
    baseline_path: Path = DEFAULT_BASELINE_SNAPSHOT,
    forecast_index_path: Path = DEFAULT_FORECAST_INDEX,
    forecast_contract_path: Path = DEFAULT_FORECAST_CONTRACT,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build aggregate final evidence without committing target-level rows."""
    validate_final_predictions(predictions)
    development = unlocked_features["split"].isin(FINAL_FIT_SPLITS)
    test = unlocked_features["split"].eq(FINAL_TEST_SPLIT)
    if unlocked_features.loc[test, FEATURE_TARGET_COLUMN].isna().any():
        raise ValueError("Final snapshot requires unlocked test labels")
    if predictions["model_name"].iloc[0] != candidate.name:
        raise ValueError("Prediction model differs from the frozen candidate")
    if model_validation.get("selection", {}).get(
        "selected_candidate"
    ) != candidate.name:
        raise ValueError("Final candidate differs from frozen model selection")

    model = _evaluate_prediction_column(predictions, "model_prediction_mw")
    daily = _evaluate_prediction_column(
        predictions, "daily_naive_prediction_mw"
    )
    weekly = _evaluate_prediction_column(
        predictions, "weekly_naive_prediction_mw"
    )
    model_mae = float(model["overall"]["mae_mw"])
    daily_mae = float(daily["overall"]["mae_mw"])
    weekly_mae = float(weekly["overall"]["mae_mw"])
    validation_mae = float(
        model_validation["selection"]["selected_validation_mae_mw"]
    )
    return {
        "schema_version": 1,
        "source": {
            "model_validation_snapshot": {
                "path": model_validation_path.relative_to(
                    project_root
                ).as_posix(),
                "sha256": sha256_file(model_validation_path),
            },
            "feature_contract": {
                "path": feature_contract_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(feature_contract_path),
            },
            "feature_matrix": {
                "path": feature_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(feature_path),
            },
            "baseline_snapshot": {
                "path": baseline_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(baseline_path),
            },
            "forecast_contract": {
                "path": forecast_contract_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(forecast_contract_path),
            },
            "forecast_index": {
                "path": forecast_index_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(forecast_index_path),
            },
            "consumption_sha256": forecast_contract["source"]["sha256"],
            "validation_summary_sha256": forecast_contract["source"][
                "validation_summary_sha256"
            ],
            "scikit_learn_version": sklearn.__version__,
        },
        "final_fit_contract": {
            "selected_candidate": candidate.name,
            "selected_family": candidate.family,
            "selected_parameters": candidate.parameters,
            "selection_source": "2024 validation MAE frozen in Step 6.4",
            "fit_splits": list(FINAL_FIT_SPLITS),
            "fit_rows": int(development.sum()),
            "fit_origins": int(
                unlocked_features.loc[development, "forecast_origin_utc"].nunique()
            ),
            "preprocessing_fit_on": "train and validation only",
            "model_feature_count": len(MODEL_FEATURE_COLUMNS),
            "histogram_early_stopping": False,
            "random_state": RANDOM_STATE,
            "test_split": FINAL_TEST_SPLIT,
            "test_rows": int(test.sum()),
            "test_origins": int(
                unlocked_features.loc[test, "forecast_origin_utc"].nunique()
            ),
            "test_influenced_design": False,
            "further_model_selection_allowed": False,
            "model_binary_published": False,
        },
        "test_evaluation": {
            "target": FEATURE_TARGET_COLUMN,
            "unit": "MW",
            "forecast_rows": int(len(predictions)),
            "origins": int(predictions["forecast_origin_utc"].nunique()),
            "model": {
                "name": candidate.name,
                "family": candidate.family,
                **model,
            },
            "baselines": {
                "daily_seasonal_naive": daily,
                "weekly_seasonal_naive": weekly,
            },
            "comparison": {
                "model_improvement_over_daily_percent": round(
                    baseline_improvement_percent(model_mae, daily_mae), 3
                ),
                "model_improvement_over_weekly_percent": round(
                    baseline_improvement_percent(model_mae, weekly_mae), 3
                ),
                "beats_daily_baseline": bool(model_mae < daily_mae),
                "beats_weekly_baseline": bool(model_mae < weekly_mae),
                "selected_validation_mae_mw": validation_mae,
                "test_mae_change_from_validation_percent": round(
                    100 * (model_mae - validation_mae) / validation_mae,
                    3,
                ),
            },
        },
        "prediction_artifact": {
            "path": predictions_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(predictions_path),
            "row_count": int(len(predictions)),
            "columns": list(FINAL_PREDICTION_COLUMNS),
            "git_policy": "ignored row-level evaluation artifact",
        },
    }


def write_final_predictions(
    predictions: pd.DataFrame,
    output_path: Path,
) -> None:
    """Write ignored row-level final predictions atomically."""
    validate_final_predictions(predictions)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        predictions.to_csv(
            temporary_path,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
            float_format="%.6f",
        )
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_final_evaluation_snapshot(
    snapshot: dict[str, Any],
    output_path: Path,
) -> None:
    """Write deterministic aggregate final-evaluation JSON atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)
