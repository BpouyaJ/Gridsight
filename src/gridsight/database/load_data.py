"""CLI for loading validated clean data into PostgreSQL analytics tables."""

from sqlalchemy.exc import SQLAlchemyError

from gridsight.database.connection import create_database_engine
from gridsight.database.data_loader import (
    load_database,
    load_validated_inputs,
)
from gridsight.database.schema_contract import apply_database_schema


def main() -> int:
    """Verify artifacts, apply schema, load atomically, and reconcile."""
    engine = None
    try:
        inputs = load_validated_inputs()
        engine = create_database_engine()
        apply_database_schema(engine)
        report = load_database(engine, inputs)
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as error:
        print(f"Database load: FAILED ({error})")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    passed = sum(check.status == "passed" for check in report.checks)
    print("Database load: OK")
    print(f"Validation summary SHA-256: {inputs.summary_sha256}")
    print(f"Transformation statements: {report.transformation_statements}")
    print(f"Reconciliation checks: {passed} passed, 0 failed")
    for table, rows in report.table_counts.items():
        print(f"{table}: {rows} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
