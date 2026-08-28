"""Fast tests for the Phase 7 BI/Excel data-product contract."""

import csv
import json
from pathlib import Path

import pytest

from gridsight.database.reporting_contract import VIEW_CONTRACTS
from gridsight.forecasting.contract import sha256_file
from gridsight.forecasting.final_evaluation import FINAL_PREDICTION_COLUMNS
from gridsight.reporting.mart_contract import (
    ALLOWED_UNITS,
    MART_CONTRACTS,
    SOURCE_LINEAGE_COLUMNS,
    build_reporting_mart_contract,
    validate_mart_contracts,
    write_reporting_mart_contract,
)


def _contract(product_id: str):
    return next(
        contract
        for contract in MART_CONTRACTS
        if contract.product_id == product_id
    )


def test_contract_has_eight_unique_products_and_fixed_samples() -> None:
    validate_mart_contracts()
    assert len(MART_CONTRACTS) == 8
    assert len({contract.product_id for contract in MART_CONTRACTS}) == 8
    assert len({contract.sample.path for contract in MART_CONTRACTS}) == 8
    assert all(
        contract.sample.path.startswith("data/samples/")
        for contract in MART_CONTRACTS
    )
    assert sum(
        contract.source_kind == "postgresql_view"
        for contract in MART_CONTRACTS
    ) == 6


def test_existing_sql_products_match_verified_view_contracts() -> None:
    existing = [
        contract
        for contract in MART_CONTRACTS
        if contract.source_kind == "postgresql_view"
        and contract.implementation_status == "verified_existing"
    ]
    assert len(existing) == 6
    for contract in existing:
        view_name = contract.source_name.removeprefix("reporting.")
        view = VIEW_CONTRACTS[view_name]
        assert contract.grain == view.grain
        assert contract.columns == view.columns
        assert contract.expected_full_rows == view.expected_rows
        assert set(contract.key_columns).issubset(contract.columns)


def test_measure_units_and_forecast_grains_are_explicit() -> None:
    measures = {
        column: unit
        for contract in MART_CONTRACTS
        for column, unit in contract.measures
    }
    assert set(measures.values()).issubset(ALLOWED_UNITS)
    assert measures["grid_load_mwh"] == "MWh"
    assert measures["average_grid_load_mw"] == "MW"
    assert measures["day_ahead_price_eur_per_mwh"] == "EUR/MWh"
    assert measures["renewable_share_of_reported_generation_percent"] == (
        "percent"
    )

    hourly = _contract("forecast_performance_hourly")
    summary = _contract("forecast_performance_summary")
    assert hourly.expected_full_rows == 8_760
    assert hourly.sample.expected_rows == 744
    assert hourly.key_columns == ("forecast_origin_utc", "horizon_step")
    assert summary.expected_full_rows == 75
    assert summary.sample.expected_rows == 75
    assert {"mae_mw", "rmse_mw", "mape_percent"}.issubset(summary.columns)


def _write_manifest(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SOURCE_LINEAGE_COLUMNS)
        writer.writeheader()
        for index in range(6):
            writer.writerow(
                {
                    column: f"value-{index}-{column}"
                    for column in SOURCE_LINEAGE_COLUMNS
                }
            )


def _source_artifacts(tmp_path: Path) -> dict[str, Path]:
    reporting_sql_path = tmp_path / "001_create_reporting_views.sql"
    final_snapshot_path = tmp_path / "final_evaluation_snapshot.json"
    predictions_path = tmp_path / "final_forecast_predictions.csv"
    validation_summary_path = tmp_path / "validation_summary.json"
    source_manifest_path = tmp_path / "smard_source_manifest.csv"
    reporting_sql_path.write_text("SELECT 1;\n", encoding="utf-8")
    predictions_path.write_text("frozen predictions\n", encoding="utf-8")
    final_snapshot = {
        "schema_version": 1,
        "prediction_artifact": {
            "path": predictions_path.relative_to(tmp_path).as_posix(),
            "sha256": sha256_file(predictions_path),
            "row_count": 8_760,
            "columns": list(FINAL_PREDICTION_COLUMNS),
        },
        "final_fit_contract": {"further_model_selection_allowed": False},
    }
    final_snapshot_path.write_text(
        json.dumps(final_snapshot), encoding="utf-8"
    )
    validation_summary = {
        "schema_version": 1,
        "status": "passed",
        "check_counts": {"failed": 0, "passed": 29},
        "checks": [
            {"check_id": f"check-{index}", "status": "passed"}
            for index in range(29)
        ],
    }
    validation_summary_path.write_text(
        json.dumps(validation_summary), encoding="utf-8"
    )
    _write_manifest(source_manifest_path)
    return {
        "reporting_sql_path": reporting_sql_path,
        "final_snapshot_path": final_snapshot_path,
        "predictions_path": predictions_path,
        "validation_summary_path": validation_summary_path,
        "source_manifest_path": source_manifest_path,
    }


def test_snapshot_is_hash_gated_and_deterministic(tmp_path: Path) -> None:
    paths = _source_artifacts(tmp_path)
    output_path = tmp_path / "reporting_mart_contract.json"
    snapshot = build_reporting_mart_contract(
        project_root=tmp_path,
        **paths,
    )
    write_reporting_mart_contract(snapshot, output_path)
    first_bytes = output_path.read_bytes()
    write_reporting_mart_contract(snapshot, output_path)

    assert output_path.read_bytes() == first_bytes
    assert snapshot["status"] == "reporting_marts_and_samples_implemented"
    assert len(snapshot["products"]) == 8
    assert snapshot["source"]["validation_summary"]["checks"] == 29
    assert snapshot["source"]["source_manifest"]["exports"] == 6

    paths["predictions_path"].write_text(
        "changed predictions\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="bytes do not match"):
        build_reporting_mart_contract(project_root=tmp_path, **paths)


def test_sample_policy_is_small_fixed_and_portfolio_safe() -> None:
    sample_rows = {
        contract.product_id: contract.sample.expected_rows
        for contract in MART_CONTRACTS
    }
    assert sample_rows == {
        "hourly_energy": 168,
        "hourly_generation_by_technology": 2_016,
        "daily_energy": 365,
        "monthly_energy": 48,
        "forecast_performance_hourly": 744,
        "forecast_performance_summary": 75,
        "data_quality_checks": 29,
        "source_lineage": 6,
    }
    assert all(
        contract.sample.expected_rows <= contract.expected_full_rows
        for contract in MART_CONTRACTS
    )
