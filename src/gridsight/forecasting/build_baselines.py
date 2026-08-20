"""CLI for evaluating frozen seasonal-naive load baselines."""

from gridsight.database.data_loader import load_validated_inputs
from gridsight.forecasting.baselines import (
    BASELINE_SPECS,
    DEFAULT_BASELINE_SNAPSHOT,
    EVALUATION_SPLITS,
    build_baseline_predictions,
    build_baseline_snapshot,
    load_frozen_forecast_index,
    write_baseline_snapshot,
)
from gridsight.forecasting.contract import (
    DEFAULT_FORECAST_INDEX,
    load_forecast_source,
    sha256_file,
)


def main() -> int:
    """Hash-gate Step 6.1 and publish train/validation baseline metrics."""
    try:
        inputs = load_validated_inputs()
        forecast_index, forecast_contract = load_frozen_forecast_index(inputs)
        source = load_forecast_source(inputs)
        predictions = build_baseline_predictions(forecast_index, source)
        snapshot = build_baseline_snapshot(predictions, forecast_contract)
        write_baseline_snapshot(snapshot, DEFAULT_BASELINE_SNAPSHOT)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"Seasonal-naive baselines: FAILED ({error})")
        return 1

    print("Seasonal-naive baselines: OK")
    for split_name in EVALUATION_SPLITS:
        split = snapshot["results"][split_name]
        print(
            f"{split_name}: origins={split['origin_count']}, "
            f"rows={split['forecast_row_count']}"
        )
        for baseline in BASELINE_SPECS:
            metrics = split["baselines"][baseline.name]["overall"]
            print(
                f"  {baseline.name}: MAE={metrics['mae_mw']:.3f} MW, "
                f"RMSE={metrics['rmse_mw']:.3f} MW, "
                f"MAPE={metrics['mape_percent']:.3f}%"
            )
    comparison = snapshot["validation_comparison"]
    print(f"Stronger validation baseline: {comparison['stronger_baseline']}")
    print("Test forecast rows scored: 0")
    relative_index = DEFAULT_FORECAST_INDEX.relative_to(
        DEFAULT_FORECAST_INDEX.parents[2]
    )
    relative_output = DEFAULT_BASELINE_SNAPSHOT.relative_to(
        DEFAULT_BASELINE_SNAPSHOT.parents[1]
    )
    print(f"Frozen index: {relative_index}")
    print(f"Output: {relative_output}")
    print(f"SHA-256: {sha256_file(DEFAULT_BASELINE_SNAPSHOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
