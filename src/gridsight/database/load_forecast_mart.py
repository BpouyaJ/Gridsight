"""CLI for loading final forecast evaluation into PostgreSQL reporting."""

from sqlalchemy.exc import SQLAlchemyError

from gridsight.database.connection import create_database_engine
from gridsight.database.forecast_mart_loader import (
    load_forecast_mart,
    load_forecast_mart_artifacts,
)
from gridsight.database.reporting_contract import (
    apply_reporting_views,
    inspect_reporting_contract,
    reconcile_reporting_views,
)
from gridsight.database.schema_contract import apply_database_schema


def main() -> int:
    """Verify artifacts, load forecast facts, create views, and reconcile."""
    engine = None
    try:
        artifacts = load_forecast_mart_artifacts()
        engine = create_database_engine()
        apply_database_schema(engine)
        load_report = load_forecast_mart(engine, artifacts)
        application = apply_reporting_views(engine)
        contract = inspect_reporting_contract(engine)
        reporting = reconcile_reporting_views(engine)
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as error:
        print(f"Forecast mart load: FAILED ({error})")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    if not contract.ok:
        print("Forecast mart load: FAILED (view contract mismatch)")
        for problem in contract.problems:
            print(f"- {problem}")
        return 1
    if not reporting.ok:
        print("Forecast mart load: FAILED (reporting reconciliation mismatch)")
        for check in reporting.problems:
            print(
                f"- {check.check_id}: expected {check.expected}, "
                f"observed {check.observed}"
            )
        return 1

    load_passed = sum(check.status == "passed" for check in load_report.checks)
    reporting_passed = sum(check.status == "passed" for check in reporting.checks)
    print("Forecast mart load: OK")
    print(f"Predictions SHA-256: {artifacts.predictions_sha256}")
    print(f"Evaluation snapshot SHA-256: {artifacts.snapshot_sha256}")
    print(f"Load reconciliation checks: {load_passed} passed, 0 failed")
    for table, rows in load_report.table_counts.items():
        print(f"{table}: {rows} rows")
    print(
        f"Reporting SQL: {application.files_applied} files, "
        f"{application.statements_executed} statements"
    )
    print(f"Reporting reconciliation checks: {reporting_passed} passed, 0 failed")
    for view, rows in reporting.view_counts.items():
        print(f"reporting.{view}: {rows} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
