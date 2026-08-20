"""CLI for building the leakage-safe GridSight forecast feature matrix."""

from gridsight.database.data_loader import load_validated_inputs
from gridsight.forecasting.baselines import load_frozen_forecast_index
from gridsight.forecasting.contract import load_forecast_source, sha256_file
from gridsight.forecasting.features import (
    DEFAULT_FEATURE_CONTRACT,
    DEFAULT_FEATURE_MATRIX,
    FEATURE_TARGET_COLUMN,
    MODEL_FEATURE_COLUMNS,
    build_feature_contract,
    build_forecast_features,
    write_feature_contract,
    write_feature_matrix,
)


def main() -> int:
    """Hash-gate source artifacts and publish features plus their contract."""
    try:
        inputs = load_validated_inputs()
        forecast_index, forecast_contract = load_frozen_forecast_index(inputs)
        source = load_forecast_source(inputs)
        features = build_forecast_features(forecast_index, source)
        write_feature_matrix(features, DEFAULT_FEATURE_MATRIX)
        contract = build_feature_contract(features, forecast_contract)
        write_feature_contract(contract, DEFAULT_FEATURE_CONTRACT)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"Forecast features: FAILED ({error})")
        return 1

    print("Forecast features: OK")
    print(f"Rows: {len(features)}")
    print(f"Model features: {len(MODEL_FEATURE_COLUMNS)}")
    for split in contract["splits"]:
        print(
            f"{split['name']}: origins={split['origin_count']}, "
            f"rows={split['forecast_row_count']}, "
            f"targets={split['materialized_target_count']}"
        )
    print(
        "Test target values materialized: "
        f"{contract['availability']['test_target_values_materialized']}"
    )
    print(f"Target column: {FEATURE_TARGET_COLUMN} [MW]")
    relative_matrix = DEFAULT_FEATURE_MATRIX.relative_to(
        DEFAULT_FEATURE_MATRIX.parents[2]
    )
    print(f"Matrix: {relative_matrix}")
    print(f"Matrix SHA-256: {sha256_file(DEFAULT_FEATURE_MATRIX)}")
    print(
        "Contract: "
        f"{DEFAULT_FEATURE_CONTRACT.relative_to(DEFAULT_FEATURE_CONTRACT.parents[1])}"
    )
    print(f"Contract SHA-256: {sha256_file(DEFAULT_FEATURE_CONTRACT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
