"""Stable forecast-evaluation metrics with explicit units and validation."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class ForecastMetrics:
    """Overall point-forecast errors for the grid-load target."""

    observations: int
    mae_mw: float
    rmse_mw: float
    mape_percent: float


def _validated_arrays(
    actual: ArrayLike,
    predicted: ArrayLike,
) -> tuple[np.ndarray, np.ndarray]:
    actual_array = np.asarray(actual, dtype="float64")
    predicted_array = np.asarray(predicted, dtype="float64")
    if actual_array.ndim != 1 or predicted_array.ndim != 1:
        raise ValueError("Forecast metric inputs must be one-dimensional")
    if actual_array.size == 0 or actual_array.shape != predicted_array.shape:
        raise ValueError("Forecast metric inputs must be non-empty and equal length")
    if not np.isfinite(actual_array).all() or not np.isfinite(
        predicted_array
    ).all():
        raise ValueError("Forecast metric inputs must contain only finite values")
    if (actual_array <= 0).any():
        raise ValueError("MAPE requires strictly positive actual grid load")
    return actual_array, predicted_array


def evaluate_forecast(actual: ArrayLike, predicted: ArrayLike) -> ForecastMetrics:
    """Calculate MAE/RMSE in MW and MAPE as a percentage."""
    actual_array, predicted_array = _validated_arrays(actual, predicted)
    error = predicted_array - actual_array
    return ForecastMetrics(
        observations=int(actual_array.size),
        mae_mw=float(np.mean(np.abs(error))),
        rmse_mw=float(np.sqrt(np.mean(np.square(error)))),
        mape_percent=float(np.mean(np.abs(error) / actual_array) * 100),
    )


def baseline_improvement_percent(model_mae_mw: float, baseline_mae_mw: float) -> float:
    """Return positive percentage improvement over a declared baseline MAE."""
    if not np.isfinite(model_mae_mw) or model_mae_mw < 0:
        raise ValueError("Model MAE must be finite and non-negative")
    if not np.isfinite(baseline_mae_mw) or baseline_mae_mw <= 0:
        raise ValueError("Baseline MAE must be finite and positive")
    return 100 * (baseline_mae_mw - model_mae_mw) / baseline_mae_mw
