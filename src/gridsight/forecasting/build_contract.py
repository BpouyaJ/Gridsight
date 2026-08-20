"""CLI for building and verifying the GridSight forecast protocol."""

from gridsight.database.data_loader import load_validated_inputs
from gridsight.forecasting.contract import (
    DEFAULT_FORECAST_CONTRACT,
    DEFAULT_FORECAST_INDEX,
    FORECAST_HORIZON_HOURS,
    FORECAST_SPLITS,
    TARGET_COLUMN,
    build_forecast_contract_summary,
    build_forecast_index,
    load_forecast_source,
    sha256_file,
    write_forecast_contract,
    write_forecast_index,
)


def main() -> int:
    """Validate clean load data and publish the deterministic forecast index."""
    try:
        inputs = load_validated_inputs()
        source = load_forecast_source(inputs)
        index = build_forecast_index(source)
        write_forecast_index(index, DEFAULT_FORECAST_INDEX)
        summary = build_forecast_contract_summary(
            index,
            inputs,
            DEFAULT_FORECAST_INDEX,
        )
        write_forecast_contract(summary, DEFAULT_FORECAST_CONTRACT)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"Forecast contract: FAILED ({error})")
        return 1

    print("Forecast contract: OK")
    print(f"Target: {TARGET_COLUMN} [MW]")
    print(f"Horizon: {FORECAST_HORIZON_HOURS} real hourly steps")
    print(f"Origins: {summary['index']['origin_count']}")
    print(f"Forecast rows: {summary['index']['row_count']}")
    for split in FORECAST_SPLITS:
        rows = split.expected_origins * FORECAST_HORIZON_HOURS
        print(f"{split.name}: origins={split.expected_origins}, rows={rows}")
    relative_index = DEFAULT_FORECAST_INDEX.relative_to(
        DEFAULT_FORECAST_INDEX.parents[2]
    )
    relative_contract = DEFAULT_FORECAST_CONTRACT.relative_to(
        DEFAULT_FORECAST_CONTRACT.parents[1]
    )
    print(f"Index: {relative_index}")
    print(f"Index SHA-256: {sha256_file(DEFAULT_FORECAST_INDEX)}")
    print(f"Contract: {relative_contract}")
    print(f"Contract SHA-256: {sha256_file(DEFAULT_FORECAST_CONTRACT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
