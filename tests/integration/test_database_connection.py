"""Integration tests for the local PostgreSQL service."""

import pytest

from gridsight.database.connection import (
    DatabaseSettings,
    check_database_connection,
)


@pytest.mark.integration
def test_database_connection_returns_expected_identity() -> None:
    """GridSight connects to its expected database, user, and server line."""
    settings = DatabaseSettings.from_environment()
    health = check_database_connection()

    assert health.database == settings.database
    assert health.user == settings.user
    assert health.server_version.startswith("17.")
