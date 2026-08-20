"""Training-only model fitting and chronological validation selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from gridsight.database.schema_contract import PROJECT_ROOT
from gridsight.forecasting.baselines import DEFAULT_BASELINE_SNAPSHOT
from gridsight.forecasting.contract import FORECAST_HORIZON_HOURS, sha256_file
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

DEFAULT_MODEL_VALIDATION_SNAPSHOT = (
    PROJECT_ROOT / "reports" / "model_validation_snapshot.json"
)
DEVELOPMENT_SPLITS = ("train", "validation")
RANDOM_STATE = 42


@dataclass(frozen=True)
class ModelCandidate:
    """One fixed estimator family and JSON-safe hyperparameter set."""

    name: str
    family: str
    parameters: dict[str, int | float]


MODEL_CANDIDATES = (
    ModelCandidate("ridge_alpha_1", "ridge", {"alpha": 1.0}),
    ModelCandidate("ridge_alpha_10", "ridge", {"alpha": 10.0}),
    ModelCandidate("ridge_alpha_100", "ridge", {"alpha": 100.0}),
    ModelCandidate(
        "hist_gradient_boosting_15_leaves",
        "hist_gradient_boosting",
        {
            "learning_rate": 0.05,
            "max_iter": 300,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 40,
            "l2_regularization": 1.0,
        },
    ),
    ModelCandidate(
        "hist_gradient_boosting_31_leaves",
        "hist_gradient_boosting",
        {
            "learning_rate": 0.05,
            "max_iter": 300,
            "max_leaf_nodes": 31,
            "min_samples_leaf": 30,
            "l2_regularization": 1.0,
        },
    ),
)


def load_frozen_feature_matrix(
    *,
    feature_path: Path = DEFAULT_FEATURE_MATRIX,
    contract_path: Path = DEFAULT_FEATURE_CONTRACT,
    project_root: Path = PROJECT_ROOT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load Step 6.3 features only when their schema and hash still match."""
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != 1:
        raise ValueError("Feature contract schema version must equal 1")
    matrix = contract.get("matrix", {})
    expected_path = feature_path.relative_to(project_root).as_posix()
    if matrix.get("path") != expected_path:
        raise ValueError("Feature-matrix path does not match its contract")
    if matrix.get("sha256") != sha256_file(feature_path):
        raise ValueError("Feature-matrix bytes do not match their contract")
    if tuple(matrix.get("model_feature_columns", ())) != MODEL_FEATURE_COLUMNS:
        raise ValueError("Model-feature columns do not match their contract")
    if matrix.get("target_column") != FEATURE_TARGET_COLUMN:
        raise ValueError("Feature target column does not match its contract")

    features = pd.read_csv(feature_path, encoding="utf-8")
    validate_forecast_features(features)
    if matrix.get("row_count") != len(features):
        raise ValueError("Feature-matrix row count does not match its contract")
    if matrix.get("origin_count") != features["forecast_origin_utc"].nunique():
        raise ValueError("Feature-matrix origin count does not match its contract")
    return features, contract


def load_verified_baseline_snapshot(
    feature_contract: dict[str, Any],
    *,
    baseline_path: Path = DEFAULT_BASELINE_SNAPSHOT,
) -> dict[str, Any]:
    """Load the Step 6.2 comparison only when its test guard and source match."""
    snapshot = json.loads(baseline_path.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != 1:
        raise ValueError("Baseline snapshot schema version must equal 1")
    evaluation = snapshot.get("evaluation", {})
    if evaluation.get("test_forecast_rows_scored") != 0:
        raise ValueError("Baseline snapshot must not contain scored test rows")
    if evaluation.get("included_splits") != ["train", "validation"]:
        raise ValueError("Baseline snapshot splits do not match the contract")
    baseline_index_hash = snapshot.get("source", {}).get("forecast_index", {}).get(
        "sha256"
    )
    feature_index_hash = feature_contract.get("source", {}).get(
        "forecast_index", {}
    ).get("sha256")
    if baseline_index_hash != feature_index_hash:
        raise ValueError("Baseline and feature forecast-index hashes differ")
    comparison = snapshot.get("validation_comparison", {})
    if comparison.get("stronger_baseline") != "weekly_seasonal_naive":
        raise ValueError("Weekly seasonal naive must be the frozen benchmark")
    weekly_mae = comparison.get("weekly_mae_mw")
    if not isinstance(weekly_mae, (int, float)) or weekly_mae <= 0:
        raise ValueError("Weekly baseline validation MAE must be positive")
    return snapshot


def build_estimator(candidate: ModelCandidate) -> Any:
    """Create one deterministic estimator without touching any data."""
    if candidate.family == "ridge":
        return Pipeline(
            steps=(
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    Ridge(
                        alpha=float(candidate.parameters["alpha"]),
                        solver="lsqr",
                        tol=1e-8,
                        max_iter=10_000,
                    ),
                ),
            )
        )
    if candidate.family == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=float(candidate.parameters["learning_rate"]),
            max_iter=int(candidate.parameters["max_iter"]),
            max_leaf_nodes=int(candidate.parameters["max_leaf_nodes"]),
            min_samples_leaf=int(candidate.parameters["min_samples_leaf"]),
            l2_regularization=float(
                candidate.parameters["l2_regularization"]
            ),
            early_stopping=False,
            random_state=RANDOM_STATE,
        )
    raise ValueError(f"Unsupported model family: {candidate.family}")


def fit_candidate(
    candidate: ModelCandidate,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_validation: pd.DataFrame,
) -> tuple[Any, np.ndarray, np.ndarray]:
    """Fit on training only and predict training plus chronological validation."""
    if tuple(x_train.columns) != MODEL_FEATURE_COLUMNS:
        raise ValueError("Training columns do not match the model-feature contract")
    if tuple(x_validation.columns) != MODEL_FEATURE_COLUMNS:
        raise ValueError("Validation columns do not match the model-feature contract")
    if len(x_train) == 0 or len(x_validation) == 0 or len(y_train) != len(x_train):
        raise ValueError("Model fitting requires non-empty aligned development data")
    if y_train.isna().any():
        raise ValueError("Training targets must not contain missing values")
    estimator = build_estimator(candidate)
    estimator.fit(x_train, y_train)
    train_prediction = np.asarray(estimator.predict(x_train), dtype="float64")
    validation_prediction = np.asarray(
        estimator.predict(x_validation), dtype="float64"
    )
    if not np.isfinite(train_prediction).all() or not np.isfinite(
        validation_prediction
    ).all():
        raise ValueError(f"Non-finite predictions from {candidate.name}")
    return estimator, train_prediction, validation_prediction


def _metric_record(metrics: ForecastMetrics) -> dict[str, int | float]:
    return {
        "observations": metrics.observations,
        "mae_mw": round(metrics.mae_mw, 3),
        "rmse_mw": round(metrics.rmse_mw, 3),
        "mape_percent": round(metrics.mape_percent, 3),
    }


def _evaluate_split(
    frame: pd.DataFrame,
    prediction: np.ndarray,
) -> dict[str, Any]:
    if len(frame) != len(prediction):
        raise ValueError("Prediction count does not match its evaluation frame")
    overall = evaluate_forecast(frame[FEATURE_TARGET_COLUMN], prediction)
    by_horizon = []
    horizon_values = frame["horizon_step"].to_numpy(dtype="int64")
    actual = frame[FEATURE_TARGET_COLUMN].to_numpy(dtype="float64")
    for horizon_step in range(1, FORECAST_HORIZON_HOURS + 1):
        mask = horizon_values == horizon_step
        metrics = evaluate_forecast(actual[mask], prediction[mask])
        by_horizon.append(
            {"horizon_step": horizon_step, **_metric_record(metrics)}
        )
    return {"overall": _metric_record(overall), "by_horizon": by_horizon}


def evaluate_model_candidates(
    features: pd.DataFrame,
    candidates: tuple[ModelCandidate, ...] = MODEL_CANDIDATES,
) -> tuple[dict[str, Any], ...]:
    """Fit fixed candidates on train and evaluate train/validation only."""
    validate_forecast_features(features)
    if not candidates or len({candidate.name for candidate in candidates}) != len(
        candidates
    ):
        raise ValueError("Model candidate names must be non-empty and unique")
    train = features.loc[features["split"] == "train"]
    validation = features.loc[features["split"] == "validation"]
    test = features.loc[features["split"] == "test"]
    if test[FEATURE_TARGET_COLUMN].notna().any():
        raise ValueError("Model selection cannot access test target labels")
    x_train = train.loc[:, list(MODEL_FEATURE_COLUMNS)]
    y_train = train[FEATURE_TARGET_COLUMN]
    x_validation = validation.loc[:, list(MODEL_FEATURE_COLUMNS)]

    results = []
    for candidate in candidates:
        _, train_prediction, validation_prediction = fit_candidate(
            candidate,
            x_train,
            y_train,
            x_validation,
        )
        results.append(
            {
                "name": candidate.name,
                "family": candidate.family,
                "parameters": candidate.parameters,
                "train": _evaluate_split(train, train_prediction),
                "validation": _evaluate_split(
                    validation, validation_prediction
                ),
            }
        )
    return tuple(results)


def select_validation_candidate(
    results: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Select the lowest validation MAE with model name as a stable tie-break."""
    if not results:
        raise ValueError("At least one candidate result is required")
    names = [str(result.get("name")) for result in results]
    if len(set(names)) != len(names):
        raise ValueError("Candidate result names must be unique")
    for result in results:
        validation = result.get("validation", {}).get("overall", {})
        mae = validation.get("mae_mw")
        if not isinstance(mae, (int, float)) or not np.isfinite(mae) or mae < 0:
            raise ValueError("Every candidate requires a finite validation MAE")
    return min(
        results,
        key=lambda result: (
            result["validation"]["overall"]["mae_mw"],
            result["name"],
        ),
    )


def build_model_validation_snapshot(
    results: tuple[dict[str, Any], ...],
    baseline_snapshot: dict[str, Any],
    *,
    feature_path: Path = DEFAULT_FEATURE_MATRIX,
    feature_contract_path: Path = DEFAULT_FEATURE_CONTRACT,
    baseline_path: Path = DEFAULT_BASELINE_SNAPSHOT,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build deterministic validation evidence without test outcomes."""
    selected = select_validation_candidate(results)
    selected_mae = float(selected["validation"]["overall"]["mae_mw"])
    weekly_mae = float(
        baseline_snapshot["validation_comparison"]["weekly_mae_mw"]
    )
    improvement = baseline_improvement_percent(selected_mae, weekly_mae)
    return {
        "schema_version": 1,
        "source": {
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
                "weekly_validation_mae_mw": weekly_mae,
            },
            "scikit_learn_version": sklearn.__version__,
        },
        "training_contract": {
            "fit_split": "train",
            "selection_split": "validation",
            "test_split": "test",
            "train_rows": 17_352,
            "validation_rows": 8_784,
            "test_rows_scored": 0,
            "model_feature_count": len(MODEL_FEATURE_COLUMNS),
            "preprocessing_fit_on": "train only",
            "histogram_early_stopping": False,
            "random_state": RANDOM_STATE,
            "selection_metric": "validation MAE_MW",
        },
        "candidates": list(results),
        "selection": {
            "selected_candidate": selected["name"],
            "selected_family": selected["family"],
            "selected_validation_mae_mw": selected_mae,
            "weekly_baseline_validation_mae_mw": weekly_mae,
            "improvement_over_weekly_baseline_percent": round(improvement, 3),
            "beats_weekly_baseline": bool(selected_mae < weekly_mae),
        },
        "test_guard": {
            "feature_rows_available": 8_760,
            "target_values_available": 0,
            "forecast_rows_scored": 0,
            "test_results_published": False,
        },
    }


def write_model_validation_snapshot(
    snapshot: dict[str, Any],
    output_path: Path,
) -> None:
    """Write deterministic aggregate model-validation JSON atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)
