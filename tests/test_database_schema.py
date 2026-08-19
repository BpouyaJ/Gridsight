"""Fast tests for the declared PostgreSQL schema contract."""

import pytest

from gridsight.database.schema_contract import (
    EXPECTED_SCHEMAS,
    SCHEMA_SQL_FILES,
    TABLE_CONTRACTS,
    split_sql_statements,
)


def test_schema_contract_has_expected_star_model_boundaries() -> None:
    """The declared model contains three staging and five analytics tables."""
    assert EXPECTED_SCHEMAS == ("staging", "analytics", "reporting")
    tables_by_schema = {
        schema: {
            table
            for contract_schema, table in TABLE_CONTRACTS
            if contract_schema == schema
        }
        for schema in EXPECTED_SCHEMAS
    }

    assert tables_by_schema["staging"] == {
        "actual_consumption_hourly",
        "actual_generation_hourly",
        "day_ahead_price_hourly",
    }
    assert tables_by_schema["analytics"] == {
        "dim_date",
        "dim_generation_technology",
        "dim_hour",
        "fact_electricity_hourly",
        "fact_generation_hourly",
    }
    assert tables_by_schema["reporting"] == set()


def test_sql_files_are_ordered_idempotent_and_non_destructive() -> None:
    """Step 4.1 DDL can be repeated and never drops or truncates data."""
    assert [path.name for path in SCHEMA_SQL_FILES] == [
        "001_create_schemas.sql",
        "001_create_staging_tables.sql",
        "002_create_analytics_tables.sql",
    ]
    statements = []
    for path in SCHEMA_SQL_FILES:
        sql_text = path.read_text(encoding="utf-8")
        upper_sql = sql_text.upper()
        assert "DROP " not in upper_sql
        assert "TRUNCATE " not in upper_sql
        statements.extend(split_sql_statements(sql_text))

    assert len(statements) == 14
    assert all("IF NOT EXISTS" in statement.upper() for statement in statements)


def test_staging_contracts_match_canonical_column_counts() -> None:
    """Staging tables retain every clean column in its canonical order."""
    expected_counts = {
        "actual_consumption_hourly": 24,
        "actual_generation_hourly": 29,
        "day_ahead_price_hourly": 25,
    }
    for table, expected_count in expected_counts.items():
        contract = TABLE_CONTRACTS[("staging", table)]
        assert len(contract.columns) == expected_count


def test_sql_splitter_rejects_psql_meta_commands() -> None:
    """DDL execution accepts SQL only, not client-specific commands."""
    with pytest.raises(ValueError, match="meta-commands"):
        split_sql_statements("CREATE SCHEMA example; \\i another.sql;")
