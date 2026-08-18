"""Command-line smoke check for GridSight's PostgreSQL connection."""

from sqlalchemy.exc import SQLAlchemyError

from gridsight.database.connection import check_database_connection


def main() -> int:
    """Print non-sensitive PostgreSQL identity information."""
    try:
        health = check_database_connection()
    except (RuntimeError, SQLAlchemyError) as error:
        print(f"Database connection: FAILED ({type(error).__name__})")
        return 1

    print("Database connection: OK")
    print(f"Database: {health.database}")
    print(f"User: {health.user}")
    print(f"PostgreSQL: {health.server_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
