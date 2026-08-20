"""Fast tests for SQL reporting-view contracts."""

from gridsight.database.reporting_contract import (
    REPORTING_SQL_FILES,
    VIEW_CONTRACTS,
)
from gridsight.database.schema_contract import split_sql_statements


def test_reporting_contract_declares_four_stable_grains() -> None:
    """Consumers receive hourly, technology, daily, and monthly grains."""
    assert set(VIEW_CONTRACTS) == {
        "hourly_energy",
        "hourly_generation_by_technology",
        "daily_energy",
        "monthly_energy",
    }
    assert VIEW_CONTRACTS["hourly_energy"].expected_rows == 35_064
    assert (
        VIEW_CONTRACTS["hourly_generation_by_technology"].expected_rows
        == 420_768
    )
    assert VIEW_CONTRACTS["daily_energy"].expected_rows == 1_461
    assert VIEW_CONTRACTS["monthly_energy"].expected_rows == 48
    assert len({contract.grain for contract in VIEW_CONTRACTS.values()}) == 4


def test_reporting_sql_is_idempotent_and_non_destructive() -> None:
    """The ordered reporting file replaces views without touching fact data."""
    assert [path.name for path in REPORTING_SQL_FILES] == [
        "001_create_reporting_views.sql"
    ]
    sql_text = REPORTING_SQL_FILES[0].read_text(encoding="utf-8")
    upper_sql = sql_text.upper()
    assert "DROP " not in upper_sql
    assert "TRUNCATE " not in upper_sql
    assert "DELETE " not in upper_sql
    statements = split_sql_statements(sql_text)
    assert len(statements) == 4
    assert all(
        "CREATE OR REPLACE VIEW" in statement.upper()
        for statement in statements
    )


def test_reporting_measure_names_keep_units_and_semantics_explicit() -> None:
    """Reporting columns distinguish MW, MWh, EUR/MWh, and percentages."""
    hourly_columns = VIEW_CONTRACTS["hourly_energy"].columns
    daily_columns = VIEW_CONTRACTS["daily_energy"].columns
    technology_columns = VIEW_CONTRACTS[
        "hourly_generation_by_technology"
    ].columns

    assert "grid_load_mwh" in hourly_columns
    assert "grid_load_mw" in hourly_columns
    assert "day_ahead_price_eur_per_mwh" in hourly_columns
    assert "renewable_generation_mwh" in hourly_columns
    assert "renewable_generation_mw" in hourly_columns
    assert "renewable_share_of_reported_generation_percent" in daily_columns
    assert "value_status" in technology_columns
    assert len(hourly_columns) == len(set(hourly_columns))
    assert len(daily_columns) == len(set(daily_columns))
