"""PostgreSQL settings and connection checks."""

import os
from dataclasses import dataclass
from typing import Self

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class DatabaseSettings:
    """Database settings loaded from environment variables."""

    database: str
    user: str
    password: str
    host: str
    port: int

    @classmethod
    def from_environment(cls) -> Self:
        """Load and validate GridSight's PostgreSQL environment variables."""
        load_dotenv()

        variable_names = (
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
        )
        values = {name: os.getenv(name) for name in variable_names}
        missing = [name for name, value in values.items() if not value]

        if missing:
            names = ", ".join(sorted(missing))
            raise RuntimeError(f"Missing database environment variables: {names}")

        try:
            port = int(values["POSTGRES_PORT"])
        except ValueError as error:
            raise RuntimeError("POSTGRES_PORT must be an integer") from error

        return cls(
            database=values["POSTGRES_DB"],
            user=values["POSTGRES_USER"],
            password=values["POSTGRES_PASSWORD"],
            host=values["POSTGRES_HOST"],
            port=port,
        )


@dataclass(frozen=True)
class DatabaseHealth:
    """Non-sensitive facts returned by the connection check."""

    database: str
    user: str
    server_version: str


def build_database_url(settings: DatabaseSettings) -> URL:
    """Build a PostgreSQL URL without manual password escaping."""
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.user,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.database,
    )


def create_database_engine(settings: DatabaseSettings | None = None) -> Engine:
    """Create a SQLAlchemy engine for GridSight's local PostgreSQL database."""
    resolved_settings = settings or DatabaseSettings.from_environment()
    return create_engine(
        build_database_url(resolved_settings),
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True,
    )


def check_database_connection() -> DatabaseHealth:
    """Connect to PostgreSQL and return safe server identity information."""
    engine = create_database_engine()

    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT current_database(), current_user, "
                    "current_setting('server_version')"
                )
            ).one()
    finally:
        engine.dispose()

    return DatabaseHealth(
        database=row[0],
        user=row[1],
        server_version=row[2],
    )
