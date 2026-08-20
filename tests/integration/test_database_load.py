"""Integration test for the full validated PostgreSQL load."""

import pytest

from gridsight.database.connection import create_database_engine
from gridsight.database.data_loader import load_database, load_validated_inputs
from gridsight.database.schema_contract import apply_database_schema


@pytest.mark.integration
def test_database_load_is_idempotent_and_reconciled() -> None:
    """Two full loads produce the same complete, reconciled star model."""
    inputs = load_validated_inputs()
    engine = create_database_engine()
    try:
        apply_database_schema(engine)
        first = load_database(engine, inputs)
        second = load_database(engine, inputs)
    finally:
        engine.dispose()

    assert first.ok
    assert second.ok
    assert first.table_counts == second.table_counts
    assert first.transformation_statements == 5
    assert len(first.checks) == 19
    assert first.table_counts == {
        "staging.actual_consumption_hourly": 35_064,
        "staging.actual_generation_hourly": 420_768,
        "staging.day_ahead_price_hourly": 35_064,
        "analytics.dim_date": 1_461,
        "analytics.dim_hour": 24,
        "analytics.dim_generation_technology": 12,
        "analytics.fact_electricity_hourly": 35_064,
        "analytics.fact_generation_hourly": 420_768,
    }
