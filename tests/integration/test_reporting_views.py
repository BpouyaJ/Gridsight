"""Integration test for live PostgreSQL reporting views."""

import pytest

from gridsight.database.connection import create_database_engine
from gridsight.database.data_loader import load_database, load_validated_inputs
from gridsight.database.forecast_mart_loader import (
    load_forecast_mart,
    load_forecast_mart_artifacts,
)
from gridsight.database.reporting_contract import (
    apply_reporting_views,
    inspect_reporting_contract,
    reconcile_reporting_views,
)
from gridsight.database.schema_contract import apply_database_schema
from gridsight.reporting.sample_extracts import build_sample_frames


@pytest.mark.integration
def test_reporting_views_are_idempotent_and_reconciled() -> None:
    """Two applications retain exact contracts, grains, and KPI totals."""
    inputs = load_validated_inputs()
    forecast_artifacts = load_forecast_mart_artifacts()
    engine = create_database_engine()
    try:
        apply_database_schema(engine)
        load_report = load_database(engine, inputs)
        first_forecast_load = load_forecast_mart(engine, forecast_artifacts)
        second_forecast_load = load_forecast_mart(engine, forecast_artifacts)
        first_application = apply_reporting_views(engine)
        second_application = apply_reporting_views(engine)
        contract = inspect_reporting_contract(engine)
        first_reconciliation = reconcile_reporting_views(engine)
        second_reconciliation = reconcile_reporting_views(engine)
        with engine.connect() as connection:
            with connection.begin():
                connection.exec_driver_sql(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
                sample_frames = build_sample_frames(connection)
    finally:
        engine.dispose()

    assert load_report.ok
    assert first_forecast_load.ok
    assert second_forecast_load == first_forecast_load
    assert len(first_forecast_load.checks) == 21
    assert first_application.files_applied == 2
    assert first_application.statements_executed == 6
    assert second_application == first_application
    assert contract.ok, contract.problems
    assert contract.view_count == 6
    assert first_reconciliation.ok, first_reconciliation.problems
    assert second_reconciliation == first_reconciliation
    assert len(first_reconciliation.checks) == 28
    assert first_reconciliation.view_counts == {
        "hourly_energy": 35_064,
        "hourly_generation_by_technology": 420_768,
        "daily_energy": 1_461,
        "monthly_energy": 48,
        "forecast_performance_hourly": 8_760,
        "forecast_performance_summary": 75,
    }
    assert {product_id: len(frame) for product_id, frame in sample_frames.items()} == {
        "hourly_energy": 168,
        "hourly_generation_by_technology": 2_016,
        "daily_energy": 365,
        "monthly_energy": 48,
        "forecast_performance_hourly": 744,
        "forecast_performance_summary": 75,
        "data_quality_checks": 29,
        "source_lineage": 6,
    }
