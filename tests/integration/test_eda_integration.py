"""Integration test for focused EDA queries against live PostgreSQL."""

import pytest

from gridsight.database.connection import create_database_engine
from gridsight.database.data_loader import load_database, load_validated_inputs
from gridsight.database.reporting_contract import apply_reporting_views
from gridsight.database.schema_contract import apply_database_schema
from gridsight.reporting.eda import build_eda_snapshot, run_eda_queries


@pytest.mark.integration
def test_eda_queries_match_live_reporting_data() -> None:
    """The EDA grains reconcile after a complete repeatable database load."""
    inputs = load_validated_inputs()
    engine = create_database_engine()
    try:
        apply_database_schema(engine)
        load_report = load_database(engine, inputs)
        apply_reporting_views(engine)
        results = run_eda_queries(engine)
        snapshot = build_eda_snapshot(results)
    finally:
        engine.dispose()

    assert load_report.ok
    assert [len(result.rows) for result in results] == [48, 48, 1_461]
    assert len(snapshot["daily_correlations"]) == 5
    assert all(
        -1 <= row["renewable_share_vs_average_price_pearson"] <= 1
        for row in snapshot["daily_correlations"]
    )
    assert len(snapshot["load_shape_extremes"]) == 4
    assert len(snapshot["unusual_days"]) == 6
    assert sum(
        row["observed_hour_count"] for row in snapshot["monthly_series"]
    ) == 35_064
