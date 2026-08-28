"""CLI for publishing GridSight's checked BI and portfolio sample bundle."""

from sqlalchemy.exc import SQLAlchemyError

from gridsight.database.connection import create_database_engine
from gridsight.database.reporting_contract import (
    inspect_reporting_contract,
    reconcile_reporting_views,
)
from gridsight.forecasting.contract import sha256_file
from gridsight.reporting.sample_extracts import (
    DEFAULT_SAMPLE_MANIFEST,
    build_sample_frames,
    current_mart_contract,
    publish_sample_bundle,
)


def main() -> int:
    """Verify live marts and publish all eight checked extracts."""
    engine = None
    try:
        mart_contract = current_mart_contract()
        engine = create_database_engine()
        contract = inspect_reporting_contract(engine)
        if not contract.ok:
            raise ValueError("Live reporting view contract does not match code")
        reconciliation = reconcile_reporting_views(engine)
        if not reconciliation.ok:
            failed = ", ".join(
                check.check_id for check in reconciliation.problems
            )
            raise ValueError(f"Live reporting reconciliation failed: {failed}")
        with engine.connect() as connection:
            with connection.begin():
                connection.exec_driver_sql(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
                frames = build_sample_frames(connection)
        manifest = publish_sample_bundle(
            frames,
            mart_contract,
            reporting_checks=len(reconciliation.checks),
        )
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as error:
        print(f"Checked sample extracts: FAILED ({error})")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    print("Checked sample extracts: OK")
    print(f"Reporting reconciliation checks: {len(reconciliation.checks)}")
    print(f"Samples: {manifest['sample_count']}")
    print(f"Rows: {manifest['sample_rows']}")
    for record in manifest["samples"]:
        print(
            f"{record['product_id']}: rows={record['rows']}, "
            f"sha256={record['sha256']}"
        )
    relative_manifest = DEFAULT_SAMPLE_MANIFEST.relative_to(
        DEFAULT_SAMPLE_MANIFEST.parents[1]
    )
    print(f"Manifest: {relative_manifest}")
    print(f"Manifest SHA-256: {sha256_file(DEFAULT_SAMPLE_MANIFEST)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
