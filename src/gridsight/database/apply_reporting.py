"""CLI for applying and reconciling GridSight's PostgreSQL reporting views."""

from sqlalchemy.exc import SQLAlchemyError

from gridsight.database.connection import create_database_engine
from gridsight.database.reporting_contract import (
    apply_reporting_views,
    inspect_reporting_contract,
    reconcile_reporting_views,
)
from gridsight.database.schema_contract import apply_database_schema


def main() -> int:
    """Create views and verify their metadata, grains, and measures."""
    engine = None
    try:
        engine = create_database_engine()
        apply_database_schema(engine)
        application = apply_reporting_views(engine)
        contract = inspect_reporting_contract(engine)
        reconciliation = reconcile_reporting_views(engine)
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as error:
        print(f"Reporting views: FAILED ({error})")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    if not contract.ok:
        print("Reporting views: FAILED (contract mismatch)")
        for problem in contract.problems:
            print(f"- {problem}")
        return 1
    if not reconciliation.ok:
        print("Reporting views: FAILED (reconciliation mismatch)")
        for check in reconciliation.problems:
            print(
                f"- {check.check_id}: expected {check.expected}, "
                f"observed {check.observed}"
            )
        return 1

    passed = sum(check.status == "passed" for check in reconciliation.checks)
    print("Reporting views: OK")
    print(f"SQL files: {application.files_applied}")
    print(f"Statements: {application.statements_executed}")
    print(f"View contract: OK ({contract.view_count} views)")
    print(f"Reconciliation checks: {passed} passed, 0 failed")
    for view, rows in reconciliation.view_counts.items():
        print(f"reporting.{view}: {rows} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
