"""Integration test for KPI queries against live PostgreSQL reporting views."""

import pytest

from gridsight.database.connection import create_database_engine
from gridsight.database.data_loader import load_database, load_validated_inputs
from gridsight.database.reporting_contract import apply_reporting_views
from gridsight.database.schema_contract import apply_database_schema
from gridsight.reporting.kpi_contract import build_kpi_snapshot, run_kpi_queries


@pytest.mark.integration
def test_kpi_queries_match_live_reporting_data() -> None:
    """The three KPI grains reconcile after a complete repeatable database load."""
    inputs = load_validated_inputs()
    engine = create_database_engine()
    try:
        apply_database_schema(engine)
        load_report = load_database(engine, inputs)
        apply_reporting_views(engine)
        results = run_kpi_queries(engine)
        snapshot = build_kpi_snapshot(results)
    finally:
        engine.dispose()

    assert load_report.ok
    assert [result.name for result in results] == [
        "headline_kpis",
        "annual_kpis",
        "generation_mix",
    ]
    assert snapshot["headline_kpis"]["observed_hour_count"] == 35_064
    assert sum(row["observed_hour_count"] for row in snapshot["annual_kpis"]) == 35_064
    assert [row["calendar_year"] for row in snapshot["annual_kpis"]] == [
        2022,
        2023,
        2024,
        2025,
    ]
    assert len(snapshot["generation_mix"]) == 12
    assert sum(
        row["unavailable_hour_count"] for row in snapshot["generation_mix"]
    ) == snapshot["headline_kpis"]["unavailable_generation_value_count"]
