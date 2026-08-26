"""CLI for the frozen final refit and one-time 2025 test evaluation."""

from gridsight.database.data_loader import load_validated_inputs
from gridsight.forecasting.baselines import load_frozen_forecast_index
from gridsight.forecasting.contract import load_forecast_source, sha256_file
from gridsight.forecasting.final_evaluation import (
    DEFAULT_FINAL_EVALUATION_SNAPSHOT,
    DEFAULT_FINAL_PREDICTIONS,
    build_final_evaluation_snapshot,
    build_final_predictions,
    fit_final_model,
    load_frozen_model_selection,
    unlock_final_test_targets,
    write_final_evaluation_snapshot,
    write_final_predictions,
)
from gridsight.forecasting.model_validation import load_frozen_feature_matrix


def main() -> int:
    """Refit the frozen model and publish its final test evidence."""
    try:
        inputs = load_validated_inputs()
        forecast_index, forecast_contract = load_frozen_forecast_index(inputs)
        source = load_forecast_source(inputs)
        features, feature_contract = load_frozen_feature_matrix()
        model_validation, candidate = load_frozen_model_selection(
            feature_contract
        )
        unlocked = unlock_final_test_targets(features, forecast_index)
        _, model_prediction = fit_final_model(candidate, unlocked)
        predictions = build_final_predictions(
            forecast_index,
            source,
            model_prediction,
            candidate,
        )
        write_final_predictions(predictions, DEFAULT_FINAL_PREDICTIONS)
        snapshot = build_final_evaluation_snapshot(
            predictions,
            unlocked,
            forecast_contract,
            model_validation,
            candidate,
        )
        write_final_evaluation_snapshot(
            snapshot,
            DEFAULT_FINAL_EVALUATION_SNAPSHOT,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"Final forecast evaluation: FAILED ({error})")
        return 1

    evaluation = snapshot["test_evaluation"]
    model = evaluation["model"]["overall"]
    daily = evaluation["baselines"]["daily_seasonal_naive"]["overall"]
    weekly = evaluation["baselines"]["weekly_seasonal_naive"]["overall"]
    comparison = evaluation["comparison"]
    print("Final forecast evaluation: OK")
    print(f"Selected model: {evaluation['model']['name']}")
    print(
        f"Final fit: {snapshot['final_fit_contract']['fit_rows']} rows "
        "(train + validation)"
    )
    print(
        f"Test: origins={evaluation['origins']}, "
        f"rows={evaluation['forecast_rows']}"
    )
    print(
        f"Model: MAE={model['mae_mw']:.3f} MW, "
        f"RMSE={model['rmse_mw']:.3f} MW, "
        f"MAPE={model['mape_percent']:.3f}%"
    )
    print(
        f"Daily baseline: MAE={daily['mae_mw']:.3f} MW, "
        f"RMSE={daily['rmse_mw']:.3f} MW, "
        f"MAPE={daily['mape_percent']:.3f}%"
    )
    print(
        f"Weekly baseline: MAE={weekly['mae_mw']:.3f} MW, "
        f"RMSE={weekly['rmse_mw']:.3f} MW, "
        f"MAPE={weekly['mape_percent']:.3f}%"
    )
    print(
        "Improvement over weekly baseline: "
        f"{comparison['model_improvement_over_weekly_percent']:.3f}%"
    )
    print(f"Beats weekly baseline: {comparison['beats_weekly_baseline']}")
    print("Further model selection allowed: False")
    relative_predictions = DEFAULT_FINAL_PREDICTIONS.relative_to(
        DEFAULT_FINAL_PREDICTIONS.parents[2]
    )
    relative_snapshot = DEFAULT_FINAL_EVALUATION_SNAPSHOT.relative_to(
        DEFAULT_FINAL_EVALUATION_SNAPSHOT.parents[1]
    )
    print(f"Predictions: {relative_predictions}")
    print(f"Predictions SHA-256: {sha256_file(DEFAULT_FINAL_PREDICTIONS)}")
    print(f"Output: {relative_snapshot}")
    print(f"SHA-256: {sha256_file(DEFAULT_FINAL_EVALUATION_SNAPSHOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
