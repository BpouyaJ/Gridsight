"""Integration tests for GridSight's live PostgreSQL table contracts."""

import pytest

from gridsight.database.connection import create_database_engine
from gridsight.database.schema_contract import (
    apply_database_schema,
    inspect_database_contract,
)


@pytest.mark.integration
def test_database_schema_is_idempotent_and_matches_contract() -> None:
    """Applying DDL twice leaves every live table contract valid."""
    engine = create_database_engine()
    try:
        first = apply_database_schema(engine)
        second = apply_database_schema(engine)
        report = inspect_database_contract(engine)
    finally:
        engine.dispose()

    assert first.files_applied == 3
    assert first.statements_executed == 14
    assert second == first
    assert report.ok, report.problems
    assert report.schema_table_counts == {
        "staging": 3,
        "analytics": 5,
        "reporting": 0,
    }
