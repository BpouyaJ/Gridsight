"""CLI for applying and verifying GridSight's PostgreSQL table contracts."""

from sqlalchemy.exc import SQLAlchemyError

from gridsight.database.connection import create_database_engine
from gridsight.database.schema_contract import (
    EXPECTED_SCHEMAS,
    apply_database_schema,
    inspect_database_contract,
)


def main() -> int:
    """Apply idempotent DDL and inspect the resulting live contract."""
    engine = None
    try:
        engine = create_database_engine()
        application = apply_database_schema(engine)
        report = inspect_database_contract(engine)
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as error:
        print(f"Database schema application: FAILED ({type(error).__name__})")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    if not report.ok:
        print("Database schema application: FAILED (contract mismatch)")
        for problem in report.problems:
            print(f"- {problem}")
        return 1

    print("Database schema application: OK")
    print(f"SQL files: {application.files_applied}")
    print(f"Statements: {application.statements_executed}")
    print(f"Schemas: {', '.join(EXPECTED_SCHEMAS)}")
    for schema in EXPECTED_SCHEMAS:
        print(f"Tables [{schema}]: {report.schema_table_counts[schema]}")
    print("Database contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
