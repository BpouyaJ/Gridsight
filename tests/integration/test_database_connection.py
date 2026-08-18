"""Integration tests for the local PostgreSQL service."""

import pytest

from gridsight.database.connection import check_database_connection


@pytest.mark.integration
def test_database_connection_returns_expected_identity() -> None:
    """GridSight connects to its expected database, user, and server line."""
    health = check_database_connection()

    assert health.database == "gridsight"
    assert health.user == "gridsight"
    assert health.server_version.startswith("17.")
